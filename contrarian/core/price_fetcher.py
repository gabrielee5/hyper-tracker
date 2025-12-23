"""
Async price fetcher for Hyperliquid API.
Retrieves real-time market prices for trading pairs.
"""

import aiohttp
import logging
from typing import Dict, Optional
import time

logger = logging.getLogger(__name__)


class AsyncPriceFetcher:
    """Fetches real-time prices from Hyperliquid API using async/await."""

    def __init__(self, api_url: str = "https://api.hyperliquid.xyz", timeout: int = 10):
        self.api_url = api_url
        self.info_endpoint = f"{api_url}/info"
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.last_prices: Dict[str, float] = {}
        self.last_fetch_time: float = 0
        self._session: Optional[aiohttp.ClientSession] = None
        logger.info(f"Async price fetcher initialized for {api_url}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch_all_prices(self) -> Dict[str, float]:
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

            session = await self._get_session()
            async with session.post(
                self.info_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                response.raise_for_status()
                prices = await response.json()

            self.last_prices = {k: float(v) for k, v in prices.items()}
            self.last_fetch_time = time.time()

            logger.debug(f"Fetched {len(self.last_prices)} prices from Hyperliquid")
            return self.last_prices

        except aiohttp.ClientError as e:
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

    async def get_price(self, pair: str) -> Optional[float]:
        """
        Get current price for a specific pair.

        Args:
            pair: Trading pair (e.g., 'BTC', 'ETH')

        Returns:
            Current price or None if not available
        """
        # Try from cached prices first
        if pair in self.last_prices:
            # Check if cache is still fresh (within 1 minute)
            if time.time() - self.last_fetch_time < 60:
                return self.last_prices[pair]

        # If cache is stale or doesn't have the pair, fetch fresh prices
        logger.debug(f"Fetching fresh prices for {pair}")
        prices = await self.fetch_all_prices()
        return prices.get(pair)

    async def get_prices_for_pairs(self, pairs: list) -> Dict[str, float]:
        """
        Get prices for multiple specific pairs.

        Args:
            pairs: List of pair names

        Returns:
            Dict mapping pair -> price
        """
        # Fetch all prices if cache is stale
        if time.time() - self.last_fetch_time > 60:
            await self.fetch_all_prices()

        result = {}
        for pair in pairs:
            if pair in self.last_prices:
                result[pair] = self.last_prices[pair]
            else:
                logger.warning(f"Price not available for {pair}")

        return result

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
