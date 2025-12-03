"""
Main simulator entry point.
Manages rebalancing schedule and coordinates all components.
"""

import time
import threading
import logging
from datetime import datetime
from typing import Dict

from config import Config
from database import SimulatorDatabase
from signal_reader import SignalReader
from position_sizer import PositionSizer
from price_fetcher import PriceFetcher
from order_executor import OrderExecutor
from portfolio_manager import PortfolioManager
from performance_tracker import PerformanceTracker

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('simulator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TradingSimulator:
    """Main trading simulator orchestrating all components."""

    def __init__(self, config_path: str = "config.json"):
        """Initialize simulator with configuration."""
        logger.info("=" * 80)
        logger.info("PAPER TRADING SIMULATOR STARTING")
        logger.info("=" * 80)

        # Load configuration
        self.config = Config(config_path)
        logger.info(f"Configuration loaded from {config_path}")

        # Initialize components
        self.db = SimulatorDatabase(self.config.simulator_db_path)
        self.signal_reader = SignalReader(self.config.signals_db_path)
        self.position_sizer = PositionSizer(self.config.max_position_pct)
        self.price_fetcher = PriceFetcher(self.config.hyperliquid_rest)
        self.executor = OrderExecutor(
            maker_fee=self.config.maker_fee,
            taker_fee=self.config.taker_fee,
            slippage_config=self.config.slippage_model
        )
        self.portfolio = PortfolioManager(
            db=self.db,
            executor=self.executor,
            price_fetcher=self.price_fetcher,
            starting_capital=self.config.starting_capital
        )
        self.performance = PerformanceTracker(
            db=self.db,
            starting_capital=self.config.starting_capital
        )

        # Threading control
        self.running = False
        self.price_update_thread = None
        self.rebalance_thread = None

        logger.info("All components initialized successfully")

    def start(self):
        """Start the simulator."""
        if self.running:
            logger.warning("Simulator already running")
            return

        self.running = True

        # Validate connectivity
        logger.info("Validating connectivity...")
        if not self._validate_connectivity():
            logger.error("Connectivity validation failed, cannot start")
            self.running = False
            return

        # Start background threads
        self.price_update_thread = threading.Thread(target=self._price_update_loop, daemon=True)
        self.price_update_thread.start()
        logger.info("Price update thread started")

        self.rebalance_thread = threading.Thread(target=self._rebalance_loop, daemon=True)
        self.rebalance_thread.start()
        logger.info("Rebalancing thread started")

        logger.info("=" * 80)
        logger.info("SIMULATOR RUNNING")
        logger.info(f"Dashboard: http://localhost:{self.config.dashboard_port}")
        logger.info(f"Starting capital: ${self.config.starting_capital:,.2f}")
        logger.info(f"Rebalance interval: {self.config.rebalance_interval_seconds}s")
        logger.info(f"Min confidence: {self.config.min_confidence_threshold*100:.0f}%")
        logger.info("=" * 80)

    def stop(self):
        """Stop the simulator gracefully."""
        logger.info("Stopping simulator...")
        self.running = False

        # Wait for threads to finish
        if self.price_update_thread:
            self.price_update_thread.join(timeout=5)
        if self.rebalance_thread:
            self.rebalance_thread.join(timeout=5)

        # Save final state
        self.portfolio.save_state()
        self.db.close()

        logger.info("Simulator stopped")

    def _validate_connectivity(self) -> bool:
        """Validate API and database connectivity."""
        try:
            # Test Hyperliquid API
            prices = self.price_fetcher.fetch_all_prices()
            if not prices:
                logger.error("Failed to fetch prices from Hyperliquid API")
                return False
            logger.info(f"✓ Hyperliquid API connected ({len(prices)} pairs available)")

            # Test Phase 3 signals database
            signal_count = self.signal_reader.get_signal_count()
            logger.info(f"✓ Phase 3 signals database connected ({signal_count} signals)")

            # Test simulator database
            self.portfolio.save_state()
            logger.info("✓ Simulator database connected")

            return True

        except Exception as e:
            logger.error(f"Connectivity validation error: {e}")
            return False

    def _price_update_loop(self):
        """Background thread to update prices continuously."""
        logger.info("Price update loop started")

        while self.running:
            try:
                # Fetch all prices
                self.price_fetcher.fetch_all_prices()

                # Update portfolio positions with new prices
                self.portfolio.update_prices()

                # Calculate and save portfolio value
                self.portfolio.calculate_portfolio_value()

                # Sleep for configured interval
                time.sleep(self.config.price_update_interval_seconds)

            except Exception as e:
                logger.error(f"Error in price update loop: {e}")
                time.sleep(5)  # Wait before retrying

        logger.info("Price update loop stopped")

    def _rebalance_loop(self):
        """Background thread to rebalance portfolio periodically."""
        logger.info("Rebalancing loop started")

        # Initial rebalance
        time.sleep(5)  # Give price updater time to fetch initial prices
        self.rebalance_portfolio()

        last_rebalance = time.time()

        while self.running:
            try:
                # Check if it's time to rebalance
                elapsed = time.time() - last_rebalance
                if elapsed >= self.config.rebalance_interval_seconds:
                    self.rebalance_portfolio()
                    last_rebalance = time.time()

                # Sleep for 1 second and check again
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error in rebalance loop: {e}")
                time.sleep(5)

        logger.info("Rebalancing loop stopped")

    def rebalance_portfolio(self):
        """Execute portfolio rebalancing logic."""
        logger.info("=" * 80)
        logger.info(f"REBALANCING PORTFOLIO - {datetime.utcnow().isoformat()}")
        logger.info("=" * 80)

        try:
            portfolio_value_before = self.portfolio.calculate_portfolio_value()

            # Step 1: Fetch latest signals from Phase 3
            signals = self.signal_reader.get_top_signals(
                min_confidence=self.config.min_confidence_threshold,
                max_signals=self.config.max_positions,
                exclude_neutral=True
            )

            logger.info(f"Retrieved {len(signals)} qualifying signals")

            if not signals:
                logger.warning("No signals available - closing all positions")
                # Close all positions
                for pair in list(self.portfolio.positions.keys()):
                    self.portfolio.close_position(pair, reason="no_signals_available")

                portfolio_value_after = self.portfolio.calculate_portfolio_value()
                self.db.log_rebalance(
                    num_adjustments=len(self.portfolio.positions),
                    total_fees=0,
                    value_before=portfolio_value_before,
                    value_after=portfolio_value_after,
                    signals_used=0
                )
                return

            # Step 2: Calculate target allocations
            target_allocations = self.position_sizer.calculate_allocations(
                signals=signals,
                total_capital=portfolio_value_before
            )

            # Step 3: Get current positions
            current_allocations = self.portfolio.get_current_allocations()

            # Step 4: Calculate required adjustments
            adjustments = self.position_sizer.calculate_position_delta(
                current_positions=current_allocations,
                target_allocations=target_allocations,
                min_trade_size=self.config.min_trade_size_usd
            )

            logger.info(f"Calculated {len(adjustments)} position adjustments")

            # Step 5: Execute adjustments
            num_adjustments = 0
            total_fees = 0

            for pair, adjustment in adjustments.items():
                action = adjustment['action']
                direction = adjustment['direction']
                delta_usd = adjustment['delta_usd']
                confidence = adjustment.get('confidence', 0)

                if action == 'CLOSE':
                    # Get direction from current position
                    if pair in self.portfolio.positions:
                        result = self.portfolio.close_position(pair, reason="signal_removed")
                        if result is not None:
                            num_adjustments += 1

                elif action == 'OPEN':
                    result = self.portfolio.open_position(
                        pair=pair,
                        direction=direction,
                        usd_value=delta_usd,
                        signal_confidence=confidence,
                        reason="new_signal"
                    )
                    if result:
                        num_adjustments += 1

                elif action in ['INCREASE', 'DECREASE']:
                    target_usd = adjustment['target_usd']
                    result = self.portfolio.adjust_position(
                        pair=pair,
                        target_usd=target_usd,
                        signal_confidence=confidence,
                        reason=f"rebalance_{action.lower()}"
                    )
                    if result:
                        num_adjustments += 1

            # Step 6: Save portfolio state
            self.portfolio.save_state()
            portfolio_value_after = self.portfolio.calculate_portfolio_value()

            # Step 7: Log rebalancing event
            self.db.log_rebalance(
                num_adjustments=num_adjustments,
                total_fees=total_fees,
                value_before=portfolio_value_before,
                value_after=portfolio_value_after,
                signals_used=len(signals)
            )

            # Step 8: Save performance snapshot
            self.performance.save_performance_snapshot(
                current_equity=portfolio_value_after,
                total_pnl=self.portfolio.total_pnl
            )

            logger.info(f"Rebalancing complete: {num_adjustments} adjustments, "
                       f"portfolio value ${portfolio_value_after:,.2f}")
            logger.info("=" * 80)

        except Exception as e:
            logger.error(f"Error during rebalancing: {e}", exc_info=True)

    def get_status(self) -> Dict:
        """Get current simulator status."""
        return {
            'running': self.running,
            'portfolio_value': self.portfolio.total_equity,
            'num_positions': len(self.portfolio.positions),
            'total_pnl': self.portfolio.total_pnl,
            'total_fees_paid': self.portfolio.total_fees_paid,
            'starting_capital': self.config.starting_capital,
            'return_pct': ((self.portfolio.total_equity - self.config.starting_capital) /
                          self.config.starting_capital * 100)
        }


def main():
    """Main entry point."""
    import sys

    simulator = TradingSimulator()

    try:
        simulator.start()

        # Keep main thread alive
        while simulator.running:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        simulator.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
