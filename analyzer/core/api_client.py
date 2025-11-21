"""
Hyperliquid API client for fetching trader history.

This module provides an async interface to fetch user fills (trade history)
from the Hyperliquid API with rate limiting and error handling.
"""

import aiohttp
import asyncio
import logging
from typing import List, Dict, Optional
from aiolimiter import AsyncLimiter
from datetime import datetime


logger = logging.getLogger(__name__)


class HyperliquidAPIError(Exception):
    """Raised when Hyperliquid API returns an error."""
    pass


class HyperliquidAPIClient:
    """
    Async client for Hyperliquid Info API.

    Handles rate limiting, retries, and error handling for fetching
    user trade history.
    """

    def __init__(
        self,
        base_url: str = "https://api.hyperliquid.xyz",
        rate_limit_calls: int = 20,
        rate_limit_period: float = 1.0,
        timeout: int = 10,
        max_retries: int = 3
    ):
        """
        Initialize the Hyperliquid API client.

        Args:
            base_url: Base URL for Hyperliquid API
            rate_limit_calls: Maximum API calls per period
            rate_limit_period: Rate limit period in seconds
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries

        # Rate limiter: max_rate calls per time_period seconds
        self.rate_limiter = AsyncLimiter(rate_limit_calls, rate_limit_period)

        # Circuit breaker for rate limits
        self._rate_limit_cooldown_until = 0  # Timestamp when cooldown ends

        # Session will be created when needed
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch_user_fills(
        self,
        address: str,
        aggregate_by_time: bool = False
    ) -> List[Dict]:
        """
        Fetch trade fills for a specific user address.

        Args:
            address: User's Ethereum address (0x...)
            aggregate_by_time: Combine partial fills when a crossing order
                             gets filled by multiple resting orders

        Returns:
            List of fill dictionaries with structure:
            {
                'coin': str,           # Asset identifier
                'px': str,             # Fill price
                'sz': str,             # Fill size
                'side': str,           # 'B' or 'A' (Buy/Sell)
                'time': int,           # Timestamp in milliseconds
                'startPosition': str,  # Position before fill
                'dir': str,            # Direction (e.g., "Open Long")
                'closedPnl': str,      # Realized PnL
                'hash': str,           # Transaction hash
                'oid': int,            # Order ID
                'crossed': bool,       # Whether order crossed the book
                'fee': str,            # Total fee
                'feeToken': str,       # Fee token (usually USDC)
                'tid': int             # Trade ID
            }

        Raises:
            HyperliquidAPIError: If API request fails after retries
        """
        if not self._is_valid_address(address):
            raise ValueError(f"Invalid Ethereum address: {address}")

        payload = {
            "type": "userFills",
            "user": address
        }

        if aggregate_by_time:
            payload["aggregateByTime"] = True

        for attempt in range(self.max_retries):
            try:
                # Check circuit breaker before making request
                now = asyncio.get_event_loop().time()
                if now < self._rate_limit_cooldown_until:
                    wait_time = int(self._rate_limit_cooldown_until - now)
                    logger.warning(
                        f"Circuit breaker active, waiting {wait_time}s before retrying..."
                    )
                    await asyncio.sleep(wait_time)

                async with self.rate_limiter:
                    data = await self._make_request(payload)

                    # userFills returns a list
                    if not isinstance(data, list):
                        logger.warning(f"Expected list for userFills, got {type(data)}")
                        return []

                    logger.info(
                        f"Fetched {len(data)} fills for address {self._shorten_address(address)}"
                    )

                    return data

            except aiohttp.ClientError as e:
                # Check if it's a 429 (rate limit) error
                is_rate_limit = '429' in str(e) or 'Too Many Requests' in str(e)

                if attempt == self.max_retries - 1:
                    logger.error(
                        f"Failed to fetch fills for {self._shorten_address(address)} "
                        f"after {self.max_retries} attempts: {e}"
                    )
                    raise HyperliquidAPIError(f"API request failed: {e}")

                # Longer backoff for rate limit errors
                if is_rate_limit:
                    wait_time = 30  # Wait 30 seconds for rate limit
                    # Activate circuit breaker for ALL requests
                    loop = asyncio.get_event_loop()
                    self._rate_limit_cooldown_until = loop.time() + wait_time
                    logger.warning(
                        f"Rate limit hit (429), activating circuit breaker for {wait_time}s"
                    )
                else:
                    # Normal exponential backoff for other errors
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}"
                    )

                await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"Unexpected error fetching fills: {e}")
                raise HyperliquidAPIError(f"Unexpected error: {e}")

        raise HyperliquidAPIError("Max retries exceeded")

    async def _make_request(self, payload: Dict):
        """
        Make POST request to Hyperliquid Info API.

        Args:
            payload: Request payload

        Returns:
            API response data (list or dict depending on endpoint)

        Raises:
            aiohttp.ClientError: If request fails
        """
        session = await self._get_session()

        async with session.post(
            f"{self.base_url}/info",
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            response.raise_for_status()

            data = await response.json()

            # Check for error response
            if isinstance(data, dict) and 'error' in data:
                raise HyperliquidAPIError(f"API error: {data['error']}")

            # Return data as-is (can be list or dict)
            return data

    def _is_valid_address(self, address: str) -> bool:
        """
        Validate Ethereum address format.

        Args:
            address: Address to validate

        Returns:
            True if valid, False otherwise
        """
        if not isinstance(address, str):
            return False

        # Ethereum addresses are 42 characters (0x + 40 hex characters)
        if len(address) != 42:
            return False

        if not address.startswith('0x'):
            return False

        # Check if remaining characters are hexadecimal
        try:
            int(address[2:], 16)
            return True
        except ValueError:
            return False

    def _shorten_address(self, address: str) -> str:
        """Shorten address for logging (0x1234...5678)."""
        if len(address) > 10:
            return f"{address[:6]}...{address[-4:]}"
        return address

    async def fetch_user_state(self, address: str) -> Dict:
        """
        Fetch current user state (positions, balances, etc.).

        This is useful for getting current position information,
        though not needed for historical analysis.

        Args:
            address: User's Ethereum address

        Returns:
            User state dictionary

        Raises:
            HyperliquidAPIError: If API request fails
        """
        if not self._is_valid_address(address):
            raise ValueError(f"Invalid Ethereum address: {address}")

        payload = {
            "type": "clearinghouseState",
            "user": address
        }

        async with self.rate_limiter:
            try:
                data = await self._make_request(payload)
                logger.info(f"Fetched user state for {self._shorten_address(address)}")
                return data
            except Exception as e:
                logger.error(f"Failed to fetch user state: {e}")
                raise HyperliquidAPIError(f"Failed to fetch user state: {e}")

    async def batch_fetch_fills(
        self,
        addresses: List[str],
        concurrency: int = 10
    ) -> Dict[str, List[Dict]]:
        """
        Fetch fills for multiple addresses concurrently.

        Args:
            addresses: List of Ethereum addresses
            concurrency: Maximum concurrent requests

        Returns:
            Dictionary mapping address -> fills list
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_semaphore(addr: str) -> tuple:
            async with semaphore:
                try:
                    fills = await self.fetch_user_fills(addr)
                    return addr, fills
                except Exception as e:
                    logger.error(f"Error fetching fills for {addr}: {e}")
                    return addr, []

        tasks = [fetch_with_semaphore(addr) for addr in addresses]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        return dict(results)


class FillsCache:
    """
    Simple in-memory cache for fills to avoid redundant API calls.

    Cache entries expire after a configurable TTL.
    """

    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize cache.

        Args:
            ttl_seconds: Time-to-live for cache entries (default: 5 minutes)
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, tuple[List[Dict], float]] = {}

    def get(self, address: str) -> Optional[List[Dict]]:
        """
        Get cached fills for address if not expired.

        Args:
            address: Ethereum address

        Returns:
            Cached fills or None if not in cache or expired
        """
        if address not in self._cache:
            return None

        fills, timestamp = self._cache[address]
        age = datetime.now().timestamp() - timestamp

        if age > self.ttl_seconds:
            # Expired, remove from cache
            del self._cache[address]
            return None

        return fills

    def set(self, address: str, fills: List[Dict]):
        """
        Cache fills for address.

        Args:
            address: Ethereum address
            fills: List of fills to cache
        """
        self._cache[address] = (fills, datetime.now().timestamp())

    def clear(self):
        """Clear all cached entries."""
        self._cache.clear()

    def size(self) -> int:
        """Get number of cached addresses."""
        return len(self._cache)


# Example usage
async def main():
    """Example usage of the API client."""
    client = HyperliquidAPIClient()

    try:
        # Example address (replace with real address)
        address = "0x0000000000000000000000000000000000000000"

        # Fetch fills
        fills = await client.fetch_user_fills(address)

        print(f"Fetched {len(fills)} fills")

        if fills:
            print(f"Latest fill: {fills[0]}")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
