"""Core address tracking logic with batch processing."""

import logging
from typing import List, Dict, Any, Set
from datetime import datetime
from threading import Lock
from collections import deque

logger = logging.getLogger(__name__)


class AddressTracker:
    """Tracks trader addresses from trade events with batch processing."""

    def __init__(self, batch_size: int = 1000, track_role: str = "both"):
        """
        Initialize the tracker.

        Args:
            batch_size: Number of addresses to accumulate before flushing
            track_role: DEPRECATED - kept for compatibility, always tracks both addresses
                       (taker/maker cannot be reliably determined from public trade data)
        """
        self.batch_size = batch_size
        # Note: track_role parameter is ignored - we always track both addresses
        # because the WebSocket 'trades' subscription doesn't include the 'crossed'
        # field needed to distinguish taker from maker
        self.pending_addresses: deque = deque()
        self.seen_in_batch: Set[str] = set()
        self.lock = Lock()

        # Statistics
        self.total_trades_processed = 0
        self.total_addresses_found = 0
        self.trades_by_coin: Dict[str, int] = {}

    def process_trade_event(self, trade_data: Dict[str, Any]):
        """
        Process a trade event and extract addresses.

        Expected trade_data format:
        {
            "coin": "BTC",
            "side": "A",  # "A" = ask/sell, "B" = bid/buy
            "px": "42000.50",
            "sz": "1.5",
            "hash": "0x...",
            "time": 1234567890,
            "tid": 12345,
            "users": ["0xbuyer...", "0xseller..."]  # [buyer, seller]
        }

        Note: The 'side' field only indicates trade direction (buy/sell), not taker/maker.
        The WebSocket 'trades' subscription does not include the 'crossed' field needed
        to distinguish taker from maker. Therefore, we track both buyer and seller addresses.

        Args:
            trade_data: Trade data from WebSocket
        """
        with self.lock:
            try:
                # Extract data
                coin = trade_data.get("coin")
                users = trade_data.get("users", [])
                price = float(trade_data.get("px", 0))
                size = float(trade_data.get("sz", 0))
                timestamp = datetime.fromtimestamp(trade_data.get("time", 0) / 1000)

                # Calculate trade value (approximate, may need coin-specific conversion)
                trade_value_usd = price * size

                # Update statistics
                self.total_trades_processed += 1
                self.trades_by_coin[coin] = self.trades_by_coin.get(coin, 0) + 1

                # Track both buyer and seller addresses
                # users = [buyer, seller]
                if len(users) >= 2:
                    buyer = users[0]
                    seller = users[1]
                    addresses_to_track = [buyer, seller]

                    # Process both addresses
                    for address in addresses_to_track:
                        if address and address not in self.seen_in_batch:
                            self.pending_addresses.append({
                                "address": address,
                                "timestamp": timestamp,
                                "volume": trade_value_usd / len(addresses_to_track),
                            })
                            self.seen_in_batch.add(address)
                            self.total_addresses_found += 1

                # Log periodically
                if self.total_trades_processed % 100 == 0:
                    logger.debug(
                        f"Processed {self.total_trades_processed} trades, "
                        f"found {self.total_addresses_found} unique addresses, "
                        f"pending batch: {len(self.pending_addresses)}"
                    )

            except Exception as e:
                logger.error(f"Error processing trade event: {e}", exc_info=True)

    def should_flush(self) -> bool:
        """
        Check if batch should be flushed.

        Returns:
            True if batch size threshold is reached
        """
        with self.lock:
            return len(self.pending_addresses) >= self.batch_size

    def flush_batch(self) -> List[Dict[str, Any]]:
        """
        Flush pending addresses and return them.

        Returns:
            List of address data dictionaries
        """
        with self.lock:
            if not self.pending_addresses:
                return []

            # Extract all pending addresses
            batch = list(self.pending_addresses)
            self.pending_addresses.clear()
            self.seen_in_batch.clear()

            logger.info(f"Flushing batch of {len(batch)} addresses")
            return batch

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get current tracking statistics.

        Returns:
            Dictionary with statistics
        """
        with self.lock:
            return {
                "total_trades_processed": self.total_trades_processed,
                "total_addresses_found": self.total_addresses_found,
                "pending_batch_size": len(self.pending_addresses),
                "trades_by_coin": dict(self.trades_by_coin),
            }

    def reset_statistics(self):
        """Reset statistics counters (useful for periodic reporting)."""
        with self.lock:
            self.total_trades_processed = 0
            self.total_addresses_found = 0
            self.trades_by_coin.clear()
