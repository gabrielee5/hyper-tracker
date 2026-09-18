"""
Main orchestrator for Phase 3 follower signal system.

Coordinates all components:
1. Fetch good traders from Phase 2
2. Fetch their current positions from Hyperliquid
3. Aggregate positions by coin
4. Generate follower signals
5. Display in dashboard and store in database
"""

import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Ensure we're running from the follower directory
script_dir = Path(__file__).parent
os.chdir(script_dir)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from follower.core.config import FollowerConfig
from follower.core.database import Phase2Reader, FollowerDatabase
from follower.core.position_fetcher import HyperliquidPositionFetcher, parse_positions
from follower.core.aggregator import PositionAggregator
from follower.core.signal_generator import (
    FollowerSignalGenerator,
    SignalThresholds
)
from follower.core.dashboard import FollowerDashboard
from follower.core.web_dashboard import WebDashboard


# Setup logging
# Ensure logs directory exists
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'follower.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class FollowerEngine:
    """
    Main follower signal engine.

    Orchestrates the complete pipeline from fetching good traders
    to generating and displaying signals.
    """

    def __init__(self, config: Optional[FollowerConfig] = None, enable_web: bool = True):
        """
        Initialize follower engine.

        Args:
            config: Configuration object (uses default if None)
            enable_web: Whether to enable web dashboard
        """
        self.config = config or FollowerConfig()
        self.enable_web = enable_web

        # Initialize components
        self.phase2_reader = Phase2Reader(self.config.database.phase2_path)
        self.follower_db = FollowerDatabase(self.config.database.follower_path)
        self.position_fetcher = HyperliquidPositionFetcher(
            base_url=self.config.api.base_url,
            rate_limit_calls=self.config.api.rate_limit_calls,
            rate_limit_period=self.config.api.rate_limit_period,
            timeout=self.config.api.timeout,
            max_retries=self.config.api.max_retries
        )
        self.aggregator = PositionAggregator(
            min_traders_for_signal=self.config.min_traders_for_signal
        )
        self.signal_generator = FollowerSignalGenerator(
            thresholds=self.config.signal_thresholds,
            min_traders_for_signal=self.config.min_traders_for_signal
        )
        self.dashboard = FollowerDashboard(
            show_size_weighted=self.config.dashboard.show_size_weighted,
            top_signals_limit=self.config.dashboard.top_signals_limit,
            enable_colors=self.config.dashboard.enable_colors,
            priority_coins=self.config.dashboard.priority_coins
        )

        # Web dashboard
        self.web_dashboard = None
        if self.enable_web:
            self.web_dashboard = WebDashboard(
                priority_coins=self.config.dashboard.priority_coins,
                timezone=self.config.dashboard.timezone
            )

        # State
        self.running = False
        self.stop_event = asyncio.Event()
        self.last_signals = []
        self.good_traders_count = 0
        self.traders_with_positions = 0

    async def initialize(self):
        """Initialize database and components."""
        logger.info("Initializing follower engine...")

        # Initialize follower database
        await self.follower_db.initialize()

        # Count good traders
        self.good_traders_count = await self.phase2_reader.get_trader_count(
            self.config.good_trader_score_threshold
        )

        logger.info(f"Found {self.good_traders_count} good traders in Phase 2 database")

        if self.good_traders_count < self.config.min_traders_for_signal:
            logger.warning(
                f"Only {self.good_traders_count} good traders found. "
                f"Minimum {self.config.min_traders_for_signal} required for signals."
            )

    async def run_once(self) -> bool:
        """
        Run one complete cycle of the pipeline.

        Returns:
            True if successful, False if error
        """
        try:
            logger.info("Starting signal generation cycle...")

            # 1. Fetch good traders from Phase 2
            logger.info(f"Fetching good traders (score >= {self.config.good_trader_score_threshold})...")
            good_traders = await self.phase2_reader.get_good_traders(
                score_threshold=self.config.good_trader_score_threshold
            )

            if not good_traders:
                logger.warning("No good traders found")
                return False

            self.good_traders_count = len(good_traders)
            addresses = [trader['address'] for trader in good_traders]

            logger.info(f"Found {len(addresses)} good traders")

            # 2. Fetch current positions for all good traders
            logger.info("Fetching positions from Hyperliquid...")
            positions_by_address = await self.position_fetcher.batch_fetch_positions(
                addresses,
                concurrency=self.config.api.concurrency_limit
            )

            # 3. Parse and flatten positions
            all_positions = []
            for address, user_state in positions_by_address.items():
                if user_state:
                    positions = parse_positions(user_state)
                    all_positions.extend(positions)

            self.traders_with_positions = sum(
                1 for user_state in positions_by_address.values()
                if user_state and user_state.get('assetPositions')
            )

            logger.info(
                f"Found {len(all_positions)} positions from "
                f"{self.traders_with_positions} traders"
            )

            if not all_positions:
                logger.warning("No open positions found")
                self.last_signals = []
                return False

            # 4. Aggregate positions by coin
            logger.info("Aggregating positions by coin...")
            aggregated = self.aggregator.aggregate_positions(all_positions)

            # 5. Generate signals
            logger.info("Generating follower signals...")
            signals = self.signal_generator.generate_signals(
                aggregated,
                use_size_weighted=False  # Use count-based as primary
            )

            self.last_signals = signals

            logger.info(f"Generated {len(signals)} signals")

            # 6. Enrich signals with change data (before saving)
            if signals:
                for signal in signals:
                    # Get previous signal for this coin to calculate changes
                    prev_signal = await self.follower_db.get_previous_signal(signal['coin'])

                    if prev_signal:
                        # Calculate changes in trader counts
                        signal['total_traders_change'] = signal['good_traders_total'] - prev_signal['good_traders_total']
                        signal['long_count_change'] = signal['long_count'] - prev_signal['long_count']
                        signal['short_count_change'] = signal['short_count'] - prev_signal['short_count']

                        # Calculate change in confidence score
                        signal['confidence_score_change'] = signal['confidence_score'] - prev_signal['confidence_score']
                    else:
                        # No previous data, set changes to 0
                        signal['total_traders_change'] = 0
                        signal['long_count_change'] = 0
                        signal['short_count_change'] = 0
                        signal['confidence_score_change'] = 0

            # 7. Save signals to database
            if signals:
                for signal in signals:
                    await self.follower_db.save_signal(signal)

                # Save position snapshots
                await self.follower_db.save_position_snapshot(all_positions)

                logger.info("Saved signals to database")

            return True

        except Exception as e:
            logger.error(f"Error in run_once: {e}", exc_info=True)
            return False

    async def run_continuous(self):
        """
        Run continuous monitoring with periodic updates.

        Updates every N seconds as configured.
        """
        self.running = True

        logger.info(
            f"Starting continuous monitoring "
            f"(update interval: {self.config.update_interval_seconds}s)"
        )

        try:
            while self.running:
                # Run one cycle
                success = await self.run_once()

                # Display dashboard
                if success and self.last_signals:
                    self.dashboard.print_static(
                        self.last_signals,
                        self.good_traders_count,
                        self.traders_with_positions,
                        self.config.get_now()
                    )

                    # Also print concise summary
                    self.dashboard.print_summary(self.last_signals)

                    # Update web dashboard
                    if self.web_dashboard:
                        self.web_dashboard.update_data(
                            self.last_signals,
                            self.good_traders_count,
                            self.traders_with_positions
                        )
                else:
                    self.dashboard.print_status(
                        "No signals generated. Waiting for next cycle..."
                    )

                    # Update web dashboard with empty signals
                    if self.web_dashboard:
                        self.web_dashboard.update_data(
                            [],
                            self.good_traders_count,
                            self.traders_with_positions
                        )

                # Wait for next cycle (can be interrupted by stop_event)
                logger.info(f"Waiting {self.config.update_interval_seconds}s for next update...")
                try:
                    await asyncio.wait_for(
                        self.stop_event.wait(),
                        timeout=self.config.update_interval_seconds
                    )
                    # If we get here, stop_event was set, so break the loop
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
        await self.position_fetcher.close()
        self.running = False


async def main():
    """Main entry point."""
    # Load configuration
    config = FollowerConfig()

    logger.info("=" * 80)
    logger.info("Phase 3: Follower Signal System")
    logger.info("=" * 80)
    logger.info(f"Good trader threshold: score >= {config.good_trader_score_threshold}")
    logger.info(f"Min traders for signal: {config.min_traders_for_signal}")
    logger.info(f"Update interval: {config.update_interval_seconds}s")
    logger.info("=" * 80)

    # Create engine with web dashboard enabled
    engine = FollowerEngine(config, enable_web=True)

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
            logger.info(f"Web Dashboard: http://127.0.0.1:{engine.web_dashboard.port}")
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
