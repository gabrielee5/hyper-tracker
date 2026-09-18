"""
Main orchestrator for Phase 3 contrarian signal system.

Coordinates all components:
1. Fetch bad traders from Phase 2
2. Fetch their current positions from Hyperliquid
3. Aggregate positions by coin
4. Generate contrarian signals
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

# Ensure we're running from the contrarian directory
script_dir = Path(__file__).parent
os.chdir(script_dir)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from contrarian.core.config import ConrarianConfig
from contrarian.core.database import Phase2Reader, ContrarianDatabase
from contrarian.core.position_fetcher import HyperliquidPositionFetcher, parse_positions
from contrarian.core.aggregator import PositionAggregator
from contrarian.core.signal_generator import (
    ContrarianSignalGenerator,
    SignalThresholds
)
from contrarian.core.dashboard import ContrarianDashboard


# Setup logging
# Ensure logs directory exists
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'contrarian.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class ContrarianEngine:
    """
    Main contrarian signal engine.

    Orchestrates the complete pipeline from fetching bad traders
    to generating and displaying signals.
    """

    def __init__(self, config: Optional[ConrarianConfig] = None):
        """
        Initialize contrarian engine.

        Args:
            config: Configuration object (uses default if None)
        """
        self.config = config or ConrarianConfig()

        # Initialize components
        self.phase2_reader = Phase2Reader(self.config.database.phase2_path)
        self.contrarian_db = ContrarianDatabase(self.config.database.contrarian_path)
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
        self.signal_generator = ContrarianSignalGenerator(
            thresholds=self.config.signal_thresholds,
            min_traders_for_signal=self.config.min_traders_for_signal
        )
        self.dashboard = ContrarianDashboard(
            show_size_weighted=self.config.dashboard.show_size_weighted,
            top_signals_limit=self.config.dashboard.top_signals_limit,
            enable_colors=self.config.dashboard.enable_colors,
            priority_coins=self.config.dashboard.priority_coins
        )

        # State
        self.running = False
        self.last_signals = []
        self.bad_traders_count = 0
        self.traders_with_positions = 0

    async def initialize(self):
        """Initialize database and components."""
        logger.info("Initializing contrarian engine...")

        # Initialize contrarian database
        await self.contrarian_db.initialize()

        # Count bad traders
        self.bad_traders_count = await self.phase2_reader.get_trader_count(
            self.config.bad_trader_score_threshold
        )

        logger.info(f"Found {self.bad_traders_count} bad traders in Phase 2 database")

        if self.bad_traders_count < self.config.min_traders_for_signal:
            logger.warning(
                f"Only {self.bad_traders_count} bad traders found. "
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

            # 1. Fetch bad traders from Phase 2
            logger.info(f"Fetching bad traders (score <= {self.config.bad_trader_score_threshold})...")
            bad_traders = await self.phase2_reader.get_bad_traders(
                score_threshold=self.config.bad_trader_score_threshold
            )

            if not bad_traders:
                logger.warning("No bad traders found")
                return False

            self.bad_traders_count = len(bad_traders)
            addresses = [trader['address'] for trader in bad_traders]

            logger.info(f"Found {len(addresses)} bad traders")

            # 2. Fetch current positions for all bad traders
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
            logger.info("Generating contrarian signals...")
            signals = self.signal_generator.generate_signals(
                aggregated,
                use_size_weighted=False  # Use count-based as primary
            )

            self.last_signals = signals

            logger.info(f"Generated {len(signals)} signals")

            # 6. Save signals to database
            if signals:
                for signal in signals:
                    await self.contrarian_db.save_signal(signal)

                # Save position snapshots
                await self.contrarian_db.save_position_snapshot(all_positions)

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
                        self.bad_traders_count,
                        self.traders_with_positions,
                        datetime.now()
                    )

                    # Also print concise summary
                    self.dashboard.print_summary(self.last_signals)
                else:
                    self.dashboard.print_status(
                        "No signals generated. Waiting for next cycle..."
                    )

                # Wait for next cycle
                logger.info(f"Waiting {self.config.update_interval_seconds}s for next update...")
                await asyncio.sleep(self.config.update_interval_seconds)

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
    config = ConrarianConfig()

    logger.info("=" * 80)
    logger.info("Phase 3: Contrarian Signal System")
    logger.info("=" * 80)
    logger.info(f"Bad trader threshold: score <= {config.bad_trader_score_threshold}")
    logger.info(f"Min traders for signal: {config.min_traders_for_signal}")
    logger.info(f"Update interval: {config.update_interval_seconds}s")
    logger.info("=" * 80)

    # Create engine
    engine = ContrarianEngine(config)

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        engine.running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Initialize
        await engine.initialize()

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
