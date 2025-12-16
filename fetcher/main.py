"""Main application entry point."""

import logging
import signal
import sys
import time
from datetime import datetime
from threading import Thread, Event
from typing import List

from config import Config
from connection import HyperliquidConnection
from address_tracker import AddressTracker
from storage import AddressStorage
from utils import setup_logging

logger = logging.getLogger(__name__)


class HyperliquidTracker:
    """Main tracker application."""

    def __init__(self, config: Config):
        """
        Initialize the tracker.

        Args:
            config: Application configuration
        """
        self.config = config
        self.storage = AddressStorage(config.database_path)
        self.tracker = AddressTracker(batch_size=config.batch_size, track_role=config.track_role)
        self.connection = HyperliquidConnection(config.api_url)

        self.coins_tracked: List[str] = []
        self.is_running = False
        self.stop_event = Event()
        self.start_time = datetime.now()
        self._dashboard_server = None

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.stop()

    def _trade_callback(self, ws_msg):
        """
        Callback for trade events.

        Args:
            ws_msg: WebSocket message dict with 'channel' and 'data' keys
        """
        try:
            # Extract the trades data from the WebSocket message
            # Expected format: {"channel": "trades", "data": [{trade1}, {trade2}, ...]}
            trades = ws_msg.get("data", [])

            # Process each trade in the data array
            for trade in trades:
                self.tracker.process_trade_event(trade)

            # Check if we should flush the batch
            if self.tracker.should_flush():
                self._flush_batch()

        except Exception as e:
            logger.error(f"Error in trade callback: {e}", exc_info=True)

    def _flush_batch(self):
        """Flush pending addresses to database."""
        try:
            batch = self.tracker.flush_batch()
            if batch:
                new_count = self.storage.batch_insert_addresses(batch)
                logger.info(f"Flushed batch: {new_count} new addresses added")
        except Exception as e:
            logger.error(f"Error flushing batch: {e}", exc_info=True)

    def _periodic_flush_worker(self):
        """Worker thread that flushes batches periodically."""
        logger.info(f"Starting periodic flush worker (interval: {self.config.dedup_interval}s)")

        while not self.stop_event.is_set():
            # Wait for interval or stop event
            if self.stop_event.wait(timeout=self.config.dedup_interval):
                break

            try:
                # Flush any pending addresses
                self._flush_batch()

                # Log statistics
                tracker_stats = self.tracker.get_statistics()
                db_stats = self.storage.get_statistics()

                logger.info(
                    f"Statistics - "
                    f"Trades: {tracker_stats['total_trades_processed']}, "
                    f"Total Addresses: {db_stats['total_addresses']}, "
                    f"Active (1h): {db_stats['active_last_1h']}, "
                    f"Active (24h): {db_stats['active_last_24h']}, "
                    f"Total Volume: ${db_stats['total_volume_usd']:,.2f}"
                )

            except Exception as e:
                logger.error(f"Error in periodic flush worker: {e}", exc_info=True)

        logger.info("Periodic flush worker stopped")

    def start(self):
        """Start the tracker."""
        try:
            logger.info("Starting Hyperliquid Tracker")
            logger.info(f"Network: {self.config.network}")
            logger.info(f"Database: {self.config.database_path}")
            logger.info("Tracking: All addresses (both buyers and sellers)")

            # Connect to Hyperliquid
            self.connection.connect()

            # Get available coins
            all_coins = self.connection.get_all_coins()
            self.coins_tracked = self.config.get_coins_to_track(all_coins)

            if not self.coins_tracked:
                logger.error("No coins to track! Check your configuration.")
                return

            logger.info(f"Tracking {len(self.coins_tracked)} coins: {', '.join(self.coins_tracked)}")

            # Subscribe to trades for each coin
            for coin in self.coins_tracked:
                try:
                    self.connection.subscribe_to_trades(coin, self._trade_callback)
                    logger.info(f"Subscribed to {coin}")
                except Exception as e:
                    logger.error(f"Failed to subscribe to {coin}: {e}")

            # Start periodic flush worker
            self.is_running = True
            flush_thread = Thread(target=self._periodic_flush_worker, daemon=True)
            flush_thread.start()

            logger.info("Tracker started successfully - press Ctrl+C to stop")

            # Keep main thread alive
            while self.is_running:
                time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            self.stop()
        except Exception as e:
            logger.error(f"Fatal error in tracker: {e}", exc_info=True)
            self.stop()

    def stop(self):
        """Stop the tracker gracefully."""
        if not self.is_running:
            return

        logger.info("Stopping tracker...")
        self.is_running = False
        self.stop_event.set()

        # Stop dashboard server first to prevent new requests
        if self._dashboard_server:
            logger.info("Shutting down dashboard server...")
            try:
                self._dashboard_server.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down dashboard: {e}")

        # Disconnect from Hyperliquid first to stop receiving messages
        logger.info("Disconnecting from Hyperliquid...")
        self.connection.disconnect()

        # Flush any remaining addresses after disconnect
        logger.info("Flushing remaining addresses...")
        self._flush_batch()

        # Final statistics
        tracker_stats = self.tracker.get_statistics()
        db_stats = self.storage.get_statistics()

        logger.info("=" * 80)
        logger.info("FINAL STATISTICS")
        logger.info("=" * 80)
        logger.info(f"Total Trades Processed: {tracker_stats['total_trades_processed']}")
        logger.info(f"Total Unique Addresses: {db_stats['total_addresses']}")
        logger.info(f"Total Volume: ${db_stats['total_volume_usd']:,.2f}")
        logger.info(f"Trades by Coin: {tracker_stats['trades_by_coin']}")
        logger.info("=" * 80)

        logger.info("Tracker stopped")


def main():
    """Main entry point."""
    # Load configuration
    config = Config.from_env()

    # Setup logging
    setup_logging(config.log_level, config.log_file)

    logger.info("=" * 80)
    logger.info("HYPERLIQUID TRADER ADDRESS TRACKER")
    logger.info("=" * 80)

    # Create and start tracker
    tracker = HyperliquidTracker(config)

    # Start dashboard if enabled
    if config.dashboard_enabled:
        from dashboard import start_dashboard
        dashboard_thread = Thread(
            target=start_dashboard,
            args=(tracker, config, tracker.stop_event),
            daemon=True
        )
        dashboard_thread.start()
        logger.info(f"Dashboard started at http://{config.dashboard_host}:{config.dashboard_port}")

    # Start tracker (blocking)
    tracker.start()


if __name__ == "__main__":
    main()
