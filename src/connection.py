"""WebSocket connection manager for Hyperliquid."""

import logging
from typing import Callable, List, Any, Dict, Optional
from hyperliquid.info import Info
from hyperliquid.utils import constants

logger = logging.getLogger(__name__)


class HyperliquidConnection:
    """Manages WebSocket connections to Hyperliquid."""

    def __init__(self, api_url: str):
        """
        Initialize the connection.

        Args:
            api_url: The Hyperliquid API URL
        """
        self.api_url = api_url
        self.info: Optional[Info] = None
        self.subscription_ids: Dict[str, int] = {}
        self.is_connected = False

    def connect(self):
        """Establish connection to Hyperliquid."""
        try:
            logger.info(f"Connecting to Hyperliquid at {self.api_url}")
            self.info = Info(self.api_url, skip_ws=False)
            self.is_connected = True
            logger.info("Successfully connected to Hyperliquid")
        except Exception as e:
            logger.error(f"Failed to connect to Hyperliquid: {e}")
            raise

    def get_all_coins(self) -> List[str]:
        """
        Fetch all available trading pairs from Hyperliquid.

        Returns:
            List of coin symbols
        """
        if not self.info:
            raise RuntimeError("Not connected to Hyperliquid")

        try:
            # Fetch all mid prices (this gives us all available coins)
            meta = self.info.meta()
            universe = meta.get("universe", [])

            coins = [asset["name"] for asset in universe]
            logger.info(f"Found {len(coins)} available coins: {coins}")
            return coins
        except Exception as e:
            logger.error(f"Failed to fetch available coins: {e}")
            raise

    def subscribe_to_trades(self, coin: str, callback: Callable[[Any], None]) -> int:
        """
        Subscribe to trade events for a specific coin.

        Args:
            coin: The coin symbol to subscribe to
            callback: Function to call when trade data is received

        Returns:
            Subscription ID
        """
        if not self.info:
            raise RuntimeError("Not connected to Hyperliquid")

        try:
            subscription = {"type": "trades", "coin": coin}
            subscription_id = self.info.subscribe(subscription, callback)
            self.subscription_ids[coin] = subscription_id
            logger.info(f"Subscribed to trades for {coin} (ID: {subscription_id})")
            return subscription_id
        except Exception as e:
            logger.error(f"Failed to subscribe to {coin}: {e}")
            raise

    def unsubscribe_from_trades(self, coin: str) -> bool:
        """
        Unsubscribe from trade events for a specific coin.

        Args:
            coin: The coin symbol to unsubscribe from

        Returns:
            True if successful
        """
        if not self.info or coin not in self.subscription_ids:
            return False

        try:
            subscription = {"type": "trades", "coin": coin}
            subscription_id = self.subscription_ids[coin]
            result = self.info.unsubscribe(subscription, subscription_id)
            del self.subscription_ids[coin]
            logger.info(f"Unsubscribed from trades for {coin}")
            return result
        except Exception as e:
            logger.error(f"Failed to unsubscribe from {coin}: {e}")
            return False

    def disconnect(self):
        """Close all connections."""
        if self.info:
            # Unsubscribe from all active subscriptions
            for coin in list(self.subscription_ids.keys()):
                self.unsubscribe_from_trades(coin)

            # Properly close the WebSocket connection
            try:
                self.info.disconnect_websocket()
                logger.info("WebSocket disconnected")
            except Exception as e:
                logger.warning(f"Error disconnecting WebSocket: {e}")

            self.info = None
            self.is_connected = False
            logger.info("Disconnected from Hyperliquid")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
