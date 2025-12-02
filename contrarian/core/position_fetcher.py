"""
Position fetcher for Hyperliquid API.

Fetches current open positions for bad traders using the clearinghouseState endpoint.
"""

import aiohttp
import asyncio
import logging
from typing import List, Dict, Optional
from aiolimiter import AsyncLimiter
from datetime import datetime


logger = logging.getLogger(__name__)


class HyperliquidPositionFetcher:
    """
    Fetches open positions from Hyperliquid for specified addresses.

    Uses the clearinghouseState endpoint to get current position data.
    """

    def __init__(
        self,
        base_url: str = "https://api.hyperliquid.xyz",
        rate_limit_calls: int = 15,
        rate_limit_period: float = 1.0,
        timeout: int = 10,
        max_retries: int = 3
    ):
        """
        Initialize position fetcher.

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

        # Rate limiter
        self.rate_limiter = AsyncLimiter(rate_limit_calls, rate_limit_period)

        # Circuit breaker for rate limits
        self._rate_limit_cooldown_until = 0

        # Session
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

    async def fetch_positions(self, address: str) -> Optional[Dict]:
        """
        Fetch current positions for a user address.

        Args:
            address: User's Ethereum address (0x...)

        Returns:
            Dictionary with positions and account state, or None if error
            Structure:
            {
                'address': str,
                'assetPositions': [
                    {
                        'coin': str,
                        'szi': str,  # Size (negative = short, positive = long)
                        'entryPx': str,
                        'positionValue': str,
                        'unrealizedPnl': str,
                        'leverage': {'type': str, 'value': int},
                        ...
                    }
                ],
                'marginSummary': {...},
                'withdrawable': str,
                'time': int
            }
        """
        if not self._is_valid_address(address):
            logger.warning(f"Invalid address format: {address}")
            return None

        payload = {
            "type": "clearinghouseState",
            "user": address
        }

        for attempt in range(self.max_retries):
            try:
                # Check circuit breaker
                now = asyncio.get_event_loop().time()
                if now < self._rate_limit_cooldown_until:
                    wait_time = int(self._rate_limit_cooldown_until - now)
                    await asyncio.sleep(wait_time)

                async with self.rate_limiter:
                    data = await self._make_request(payload)

                    # Add address to response for tracking
                    if data:
                        data['address'] = address

                    return data

            except aiohttp.ClientError as e:
                is_rate_limit = '429' in str(e) or 'Too Many Requests' in str(e)

                if attempt == self.max_retries - 1:
                    logger.error(
                        f"Failed to fetch positions for {self._shorten_address(address)} "
                        f"after {self.max_retries} attempts: {e}"
                    )
                    return None

                if is_rate_limit:
                    wait_time = 30
                    loop = asyncio.get_event_loop()
                    self._rate_limit_cooldown_until = loop.time() + wait_time
                    logger.warning(f"Rate limit hit, waiting {wait_time}s")
                else:
                    wait_time = 2 ** attempt
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")

                await asyncio.sleep(wait_time)

            except Exception as e:
                logger.error(f"Unexpected error fetching positions for {address}: {e}")
                return None

        return None

    async def batch_fetch_positions(
        self,
        addresses: List[str],
        concurrency: int = 10
    ) -> Dict[str, Optional[Dict]]:
        """
        Fetch positions for multiple addresses concurrently.

        Args:
            addresses: List of Ethereum addresses
            concurrency: Maximum concurrent requests

        Returns:
            Dictionary mapping address -> position data (or None if error)
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_semaphore(addr: str) -> tuple:
            async with semaphore:
                try:
                    positions = await self.fetch_positions(addr)
                    return addr, positions
                except Exception as e:
                    logger.error(f"Error fetching positions for {addr}: {e}")
                    return addr, None

        logger.info(f"Fetching positions for {len(addresses)} addresses...")

        tasks = [fetch_with_semaphore(addr) for addr in addresses]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        result_dict = dict(results)

        # Log summary
        successful = sum(1 for v in result_dict.values() if v is not None)
        logger.info(f"Successfully fetched {successful}/{len(addresses)} positions")

        return result_dict

    async def _make_request(self, payload: Dict):
        """
        Make POST request to Hyperliquid Info API.

        Args:
            payload: Request payload

        Returns:
            API response data

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
                raise aiohttp.ClientError(f"API error: {data['error']}")

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

        if len(address) != 42:
            return False

        if not address.startswith('0x'):
            return False

        try:
            int(address[2:], 16)
            return True
        except ValueError:
            return False

    def _shorten_address(self, address: str) -> str:
        """Shorten address for logging."""
        if len(address) > 10:
            return f"{address[:6]}...{address[-4:]}"
        return address


def parse_positions(user_state: Dict) -> List[Dict]:
    """
    Parse position data from clearinghouseState response.

    Converts raw API response into normalized position dictionaries.

    Args:
        user_state: Response from clearinghouseState API

    Returns:
        List of normalized position dictionaries with structure:
        {
            'address': str,
            'coin': str,
            'side': 'LONG' or 'SHORT',
            'size': float (absolute value),
            'position_value_usd': float,
            'entry_price': float,
            'leverage_value': float,
            'unrealized_pnl': float
        }
    """
    if not user_state:
        return []

    address = user_state.get('address')
    asset_positions = user_state.get('assetPositions', [])

    if not asset_positions:
        return []

    positions = []

    for asset_pos in asset_positions:
        try:
            # Parse size (szi) - negative = short, positive = long
            szi = float(asset_pos.get('szi', 0))

            # Skip if no position
            if szi == 0:
                continue

            side = 'SHORT' if szi < 0 else 'LONG'
            size = abs(szi)

            # Parse other fields
            coin = asset_pos.get('coin', 'UNKNOWN')
            position_value = abs(float(asset_pos.get('positionValue', 0)))
            entry_px = float(asset_pos.get('entryPx', 0))
            unrealized_pnl = float(asset_pos.get('unrealizedPnl', 0))

            # Parse leverage
            leverage_obj = asset_pos.get('leverage', {})
            if isinstance(leverage_obj, dict):
                leverage_value = float(leverage_obj.get('value', 1))
            else:
                leverage_value = 1.0

            position = {
                'address': address,
                'coin': coin,
                'side': side,
                'size': size,
                'position_value_usd': position_value,
                'entry_price': entry_px,
                'leverage_value': leverage_value,
                'unrealized_pnl': unrealized_pnl
            }

            positions.append(position)

        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Failed to parse position for {coin}: {e}")
            continue

    return positions


# Example usage
async def main():
    """Example usage of the position fetcher."""
    fetcher = HyperliquidPositionFetcher()

    try:
        # Example address (replace with real)
        address = "0x0000000000000000000000000000000000000000"

        # Fetch positions
        user_state = await fetcher.fetch_positions(address)

        if user_state:
            positions = parse_positions(user_state)
            print(f"Found {len(positions)} open positions")

            for pos in positions:
                print(f"  {pos['coin']}: {pos['side']} {pos['size']} "
                      f"@ ${pos['position_value_usd']:.2f}")
        else:
            print("No positions or error fetching")

    finally:
        await fetcher.close()


if __name__ == "__main__":
    asyncio.run(main())
