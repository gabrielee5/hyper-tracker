"""
Main orchestrator for market maker position monitor.

Coordinates:
1. Fetch market makers from analyzer database
2. Fetch their current positions from Hyperliquid
3. Calculate bias metrics
4. Store in local database
5. Display in dashboard
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from datetime import datetime

# Setup path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir.parent))

from core.config import MMMonitorConfig
from core.database import AnalyzerDatabaseReader, MMPositionDatabase
from core.position_fetcher import HyperliquidPositionFetcher, parse_positions
from core.bias_analyzer import BiasAnalyzer
from core.price_fetcher import AsyncPriceFetcher
from core.web_dashboard import MMWebDashboard

# Logging
log_dir = script_dir.parent / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'mm_monitor.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class MMMonitorEngine:
    """Main market maker monitoring engine."""

    def __init__(self, config: MMMonitorConfig = None):
        """
        Initialize monitoring engine.

        Args:
            config: Configuration object (uses default if None)
        """
        self.config = config or MMMonitorConfig()

        # Initialize components
        self.analyzer_reader = AnalyzerDatabaseReader(
            self.config.database.analyzer_db_path
        )
        self.mm_db = MMPositionDatabase(
            self.config.database.local_db_path
        )
        self.position_fetcher = HyperliquidPositionFetcher(
            base_url=self.config.api.base_url,
            rate_limit_calls=self.config.api.rate_limit_calls,
            rate_limit_period=self.config.api.rate_limit_period,
            timeout=self.config.api.timeout,
            max_retries=self.config.api.max_retries
        )
        self.price_fetcher = AsyncPriceFetcher(
            api_url=self.config.api.base_url,
            timeout=self.config.api.timeout
        )
        self.bias_analyzer = BiasAnalyzer(
            neutral_threshold=self.config.bias_analysis.neutral_threshold_percent,
            strong_threshold=self.config.bias_analysis.strong_bias_threshold_percent
        )

        # Web dashboard
        self.web_dashboard = None
        if self.config.dashboard.enabled:
            self.web_dashboard = MMWebDashboard(
                port=self.config.dashboard.port,
                host=self.config.dashboard.host,
                timezone=self.config.dashboard.timezone
            )

        # State
        self.running = False
        self.stop_event = asyncio.Event()
        self.last_bias_results = []
        self.total_mm_count = 0
        self.active_mm_count = 0

    async def initialize(self):
        """Initialize databases and components."""
        logger.info("Initializing MM monitor engine...")

        # Initialize local database
        await self.mm_db.initialize()

        # Count market makers
        self.total_mm_count = await self.analyzer_reader.get_market_maker_count(
            min_balance=self.config.monitoring.min_mm_balance
        )

        logger.info(f"Found {self.total_mm_count} market makers in analyzer database")

        if self.total_mm_count == 0:
            logger.warning(
                "No market makers found in analyzer database. "
                "Make sure the analyzer module is running and detecting market makers."
            )

    async def run_once(self) -> bool:
        """
        Run one monitoring cycle.

        Returns:
            True if successful, False if error
        """
        try:
            logger.info("Starting monitoring cycle...")

            # 1. Fetch market makers from analyzer database
            logger.info(
                f"Fetching market makers (balance >= ${self.config.monitoring.min_mm_balance:,.0f}, "
                f"active within {self.config.monitoring.max_mm_age_hours}h)..."
            )

            market_makers = await self.analyzer_reader.get_market_makers(
                min_balance=self.config.monitoring.min_mm_balance,
                max_age_hours=self.config.monitoring.max_mm_age_hours
            )

            if not market_makers:
                logger.warning("No active market makers found")
                self.last_bias_results = []
                if self.web_dashboard:
                    self.web_dashboard.update_data([], 0, 0)
                return False

            self.total_mm_count = len(market_makers)
            logger.info(f"Found {self.total_mm_count} active market makers")

            addresses = [mm['address'] for mm in market_makers]

            # 2. Fetch positions from Hyperliquid
            logger.info("Fetching positions from Hyperliquid...")
            positions_by_address = await self.position_fetcher.batch_fetch_positions(
                addresses,
                concurrency=self.config.monitoring.concurrency_limit
            )

            # 3. Parse and flatten positions
            all_positions = []
            active_mm_count = 0

            for address, user_state in positions_by_address.items():
                has_positions = False
                position_count = 0

                if user_state:
                    positions = parse_positions(user_state)

                    # Filter by minimum value
                    positions = [
                        p for p in positions
                        if p['position_value_usd'] >= self.config.monitoring.min_position_value_usd
                    ]

                    if positions:
                        all_positions.extend(positions)
                        has_positions = True
                        position_count = len(positions)
                        active_mm_count += 1

                # Update activity tracking
                await self.mm_db.update_mm_activity(
                    address,
                    has_positions,
                    position_count
                )

            self.active_mm_count = active_mm_count

            logger.info(
                f"Found {len(all_positions)} positions from "
                f"{active_mm_count} active market makers"
            )

            if not all_positions:
                logger.warning("No positions found")
                self.last_bias_results = []
                if self.web_dashboard:
                    self.web_dashboard.update_data([], self.total_mm_count, 0)
                return False

            # 4. Save position snapshots
            if self.config.monitoring.position_snapshot_enabled:
                await self.mm_db.save_position_snapshots(all_positions)
                logger.debug(f"Saved {len(all_positions)} position snapshots")

            # 5. Calculate bias
            logger.info("Calculating bias...")
            bias_results = self.bias_analyzer.analyze_positions(all_positions)

            if not bias_results:
                logger.warning("No bias results generated")
                self.last_bias_results = []
                if self.web_dashboard:
                    self.web_dashboard.update_data([], self.total_mm_count, active_mm_count)
                return False

            logger.info(f"Calculated bias for {len(bias_results)} coins")

            # 6. Fetch current prices
            logger.info("Fetching current prices...")
            try:
                coins = [b['coin'] for b in bias_results]
                prices = await self.price_fetcher.get_prices_for_pairs(coins)

                for bias in bias_results:
                    bias['current_price'] = prices.get(bias['coin'])
                    if bias['current_price']:
                        logger.debug(f"{bias['coin']}: ${bias['current_price']:.2f}")
            except Exception as e:
                logger.error(f"Error fetching prices: {e}")

            # 7. Save bias history
            for bias in bias_results:
                await self.mm_db.save_bias(bias)

            logger.info(f"Saved bias for {len(bias_results)} coins")

            # 8. Update web dashboard
            self.last_bias_results = bias_results
            if self.web_dashboard:
                self.web_dashboard.update_data(
                    bias_results,
                    self.total_mm_count,
                    active_mm_count
                )

            # 9. Log summary
            self._log_summary(bias_results)

            return True

        except Exception as e:
            logger.error(f"Error in run_once: {e}", exc_info=True)
            return False

    def _log_summary(self, bias_results: list):
        """Log a summary of bias results."""
        if not bias_results:
            return

        aggregate = self.bias_analyzer.calculate_aggregate_sentiment(bias_results)

        logger.info("=" * 60)
        logger.info("MARKET MAKER BIAS SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Coins: {aggregate['total_coins']}")
        logger.info(
            f"Direction Breakdown: "
            f"{aggregate['bullish_count']} BULLISH, "
            f"{aggregate['bearish_count']} BEARISH, "
            f"{aggregate['neutral_count']} NEUTRAL"
        )
        logger.info(f"Average Bias: {aggregate['avg_bias_percentage']:.1f}%")
        logger.info(f"Total Position Value: ${aggregate['total_position_value']:,.0f}")

        # Show top 5 coins by position value
        logger.info("\nTop 5 Coins by Position Value:")
        for i, bias in enumerate(bias_results[:5], 1):
            logger.info(
                f"  {i}. {bias['coin']}: {bias['direction']} {bias['strength']} "
                f"({bias['bias_percentage']:+.1f}%) - "
                f"${bias['total_value_usd']:,.0f} "
                f"({bias['mm_count']} MMs)"
            )
        logger.info("=" * 60)

    async def run_continuous(self):
        """Run continuous monitoring."""
        self.running = True

        logger.info(
            f"Starting continuous monitoring "
            f"(interval: {self.config.monitoring.fetch_interval_seconds}s)"
        )

        try:
            while self.running:
                success = await self.run_once()

                if success:
                    logger.info("✓ Cycle completed successfully")
                else:
                    logger.warning("⚠ Cycle completed with warnings")

                # Wait for next cycle
                logger.info(
                    f"Waiting {self.config.monitoring.fetch_interval_seconds}s "
                    f"for next update..."
                )

                try:
                    await asyncio.wait_for(
                        self.stop_event.wait(),
                        timeout=self.config.monitoring.fetch_interval_seconds
                    )
                    # If we get here, stop_event was set
                    break
                except asyncio.TimeoutError:
                    # Timeout is normal - just means it's time for next cycle
                    pass

        except asyncio.CancelledError:
            logger.info("Monitoring cancelled")
        except Exception as e:
            logger.error(f"Error in continuous monitoring: {e}", exc_info=True)
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up...")

        # Close API connections
        await self.position_fetcher.close()
        await self.price_fetcher.close()

        # Run cleanup on database
        try:
            await self.mm_db.cleanup_old_data(
                snapshots_days=self.config.retention.position_snapshots_days,
                bias_days=self.config.retention.bias_history_days
            )
        except Exception as e:
            logger.error(f"Error during database cleanup: {e}")

        self.running = False


async def main():
    """Main entry point."""
    # Load configuration
    config = MMMonitorConfig()

    logger.info("=" * 80)
    logger.info("Market Maker Position Monitor")
    logger.info("=" * 80)
    logger.info(f"Min MM balance: ${config.monitoring.min_mm_balance:,.0f}")
    logger.info(f"Max MM age: {config.monitoring.max_mm_age_hours}h")
    logger.info(f"Fetch interval: {config.monitoring.fetch_interval_seconds}s")
    logger.info(f"Neutral threshold: ±{config.bias_analysis.neutral_threshold_percent}%")
    logger.info(f"Strong threshold: ±{config.bias_analysis.strong_bias_threshold_percent}%")
    logger.info("=" * 80)

    # Create engine
    engine = MMMonitorEngine(config)

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        engine.running = False
        engine.stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize
        await engine.initialize()

        # Start web dashboard in background thread
        if engine.web_dashboard:
            engine.web_dashboard.run_in_thread()
            logger.info("")
            logger.info("=" * 80)
            logger.info(f"📊 Web Dashboard: http://{config.dashboard.host}:{config.dashboard.port}")
            logger.info("=" * 80)
            logger.info("")

        # Run continuous monitoring
        await engine.run_continuous()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await engine.cleanup()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
