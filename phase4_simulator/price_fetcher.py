"""
Price fetcher for Hyperliquid API.
Retrieves real-time market prices for trading pairs.
"""

import requests
import logging
from typing import Dict, Optional
import time

logger = logging.getLogger(__name__)


class PriceFetcher:
    """Fetches real-time prices from Hyperliquid API."""

    def __init__(self, api_url: str = "https://api.hyperliquid.xyz"):
        self.api_url = api_url
        self.info_endpoint = f"{api_url}/info"
        self.last_prices: Dict[str, float] = {}
        self.last_fetch_time: float = 0
        logger.info(f"Price fetcher initialized for {api_url}")

    def fetch_all_prices(self) -> Dict[str, float]:
        """
        Fetch current mid prices for all trading pairs.

        Returns:
            Dict mapping pair name -> mid price
            Example: {'BTC': 95234.5, 'ETH': 3456.78, 'SOL': 142.34}
        """
        try:
            payload = {
                "type": "allMids"
            }

            response = requests.post(
                self.info_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()

            prices = response.json()
            self.last_prices = {k: float(v) for k, v in prices.items()}
            self.last_fetch_time = time.time()

            logger.debug(f"Fetched {len(self.last_prices)} prices from Hyperliquid")
            return self.last_prices

        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error fetching prices: {e}")
            # Return last known prices if available
            if self.last_prices:
                logger.warning("Using last known prices due to fetch error")
                return self.last_prices
            return {}

        except Exception as e:
            logger.error(f"Error fetching prices: {e}")
            if self.last_prices:
                return self.last_prices
            return {}

    def get_price(self, pair: str) -> Optional[float]:
        """
        Get current price for a specific pair.

        Args:
            pair: Trading pair (e.g., 'BTC', 'ETH')

        Returns:
            Current price or None if not available
        """
        # Try from cached prices first
        if pair in self.last_prices:
            return self.last_prices[pair]

        # If cache is stale, fetch fresh prices
        if time.time() - self.last_fetch_time > 60:  # 1 minute stale threshold
            logger.debug(f"Price cache stale, fetching fresh prices for {pair}")
            prices = self.fetch_all_prices()
            return prices.get(pair)

        logger.warning(f"Price not available for {pair}")
        return None

    def get_prices_for_pairs(self, pairs: list) -> Dict[str, float]:
        """
        Get prices for multiple specific pairs.

        Args:
            pairs: List of pair names

        Returns:
            Dict mapping pair -> price
        """
        # Fetch all prices if cache is stale
        if time.time() - self.last_fetch_time > 60:
            self.fetch_all_prices()

        result = {}
        for pair in pairs:
            if pair in self.last_prices:
                result[pair] = self.last_prices[pair]
            else:
                logger.warning(f"Price not available for {pair}")

        return result

    def fetch_asset_contexts(self) -> Dict:
        """
        Fetch detailed asset contexts including mark price, funding, open interest.

        Returns:
            Dict with asset context data
        """
        try:
            payload = {
                "type": "metaAndAssetCtxs"
            }

            response = requests.post(
                self.info_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            logger.debug("Fetched asset contexts from Hyperliquid")
            return data

        except Exception as e:
            logger.error(f"Error fetching asset contexts: {e}")
            return {}

    def get_available_pairs(self) -> list:
        """
        Get list of all available trading pairs.

        Returns:
            List of pair names
        """
        try:
            payload = {
                "type": "meta"
            }

            response = requests.post(
                self.info_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()

            data = response.json()
            if 'universe' in data:
                pairs = [asset['name'] for asset in data['universe']]
                logger.info(f"Retrieved {len(pairs)} available pairs")
                return pairs

            return []

        except Exception as e:
            logger.error(f"Error fetching available pairs: {e}")
            return []

    def normalize_pair_name(self, pair: str) -> str:
        """
        Normalize pair name to match Hyperliquid format.

        Examples:
            'BTC-USD' -> 'BTC'
            'ETH-USDT' -> 'ETH'
            'SOL' -> 'SOL'
        """
        # Remove common suffixes
        for suffix in ['-USD', '-USDT', '-PERP', 'USD', 'USDT']:
            if pair.endswith(suffix):
                return pair[:-len(suffix)]

        return pair

    def get_last_fetch_age(self) -> float:
        """Get age of last price fetch in seconds."""
        if self.last_fetch_time == 0:
            return float('inf')
        return time.time() - self.last_fetch_time
