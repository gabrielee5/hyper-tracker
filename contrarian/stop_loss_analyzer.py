"""
Stop Loss Distribution Analyzer for Bad Traders

A simple contrarian tool that:
1. Fetches open orders for bad traders
2. Filters for stop loss orders
3. Visualizes the distribution of stop loss prices for a specific asset

USAGE:
    python3 contrarian/stop_loss_analyzer.py [COIN]

EXAMPLES:
    python3 contrarian/stop_loss_analyzer.py BTC
    python3 contrarian/stop_loss_analyzer.py ETH
    python3 contrarian/stop_loss_analyzer.py SOL

The tool will:
- Load bad traders from the Phase 2 database
- Fetch their open orders from Hyperliquid
- Filter for stop loss orders on the specified coin
- Display a histogram showing the distribution of stop loss prices

This helps identify price levels where many bad traders have placed stop losses,
which could indicate potential areas of liquidity for contrarian trades.

NOTE: The script respects API rate limits (10 calls/second by default).
With 400+ traders, expect the script to take 40-80 seconds to complete.
"""

import asyncio
import aiohttp
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional
from collections import Counter
from aiolimiter import AsyncLimiter

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from contrarian.core.database import Phase2Reader
from contrarian.core.config import ConrarianConfig


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class StopLossAnalyzer:
    """Analyzes stop loss orders from bad traders."""

    def __init__(
        self,
        base_url: str = "https://api.hyperliquid.xyz",
        rate_limit_calls: int = 10,
        rate_limit_period: float = 1.0
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.rate_limiter = AsyncLimiter(rate_limit_calls, rate_limit_period)
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

    async def fetch_open_orders(self, address: str) -> List[Dict]:
        """
        Fetch open orders for a trader using frontendOpenOrders endpoint.

        Args:
            address: Trader's Ethereum address

        Returns:
            List of open order dictionaries
        """
        payload = {
            "type": "frontendOpenOrders",
            "user": address
        }

        try:
            async with self.rate_limiter:
                session = await self._get_session()
                async with session.post(
                    f"{self.base_url}/info",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    response.raise_for_status()
                    data = await response.json()

                    if isinstance(data, dict) and 'error' in data:
                        logger.warning(f"API error for {address[:10]}: {data['error']}")
                        return []

                    return data if isinstance(data, list) else []

        except Exception as e:
            logger.warning(f"Failed to fetch orders for {address[:10]}: {e}")
            return []

    async def batch_fetch_orders(
        self,
        addresses: List[str],
        concurrency: int = 5
    ) -> Dict[str, List[Dict]]:
        """
        Fetch orders for multiple addresses concurrently.

        Args:
            addresses: List of trader addresses
            concurrency: Max concurrent requests

        Returns:
            Dict mapping address -> list of orders
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_semaphore(addr: str):
            async with semaphore:
                orders = await self.fetch_open_orders(addr)
                return addr, orders

        logger.info(f"Fetching orders for {len(addresses)} traders...")

        tasks = [fetch_with_semaphore(addr) for addr in addresses]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        return dict(results)

    def filter_stop_losses(
        self,
        orders: List[Dict],
        target_coin: str
    ) -> List[Dict]:
        """
        Filter orders for stop losses on the target coin.

        Args:
            orders: List of order dictionaries
            target_coin: Coin symbol to filter (e.g., "BTC", "ETH")

        Returns:
            List of stop loss orders for the target coin
        """
        stop_losses = []

        for order in orders:
            # Check if it's the target coin
            if order.get('coin') != target_coin:
                continue

            # Check if it's a trigger order (stop loss/take profit)
            if not order.get('isTrigger', False):
                continue

            # We could further filter by checking if it's reduce-only
            # Stop losses typically have reduceOnly = True
            if order.get('reduceOnly', False):
                stop_losses.append(order)

        return stop_losses

    def print_distribution(
        self,
        stop_losses: List[Dict],
        coin: str,
        bin_size: float = None
    ):
        """
        Print a visual distribution of stop loss prices.

        Args:
            stop_losses: List of stop loss orders
            coin: Coin symbol
            bin_size: Optional bin size for grouping prices
        """
        if not stop_losses:
            print(f"\nNo stop loss orders found for {coin}")
            return

        # Extract trigger prices
        prices = []
        for order in stop_losses:
            trigger_px = order.get('triggerPx')
            if trigger_px:
                try:
                    prices.append(float(trigger_px))
                except (ValueError, TypeError):
                    continue

        if not prices:
            print(f"\nNo valid stop loss prices found for {coin}")
            return

        prices.sort()

        # Print summary statistics
        print(f"\n{'='*60}")
        print(f"STOP LOSS DISTRIBUTION - {coin}")
        print(f"{'='*60}")
        print(f"Total stop loss orders: {len(prices)}")
        print(f"Price range: ${min(prices):,.2f} - ${max(prices):,.2f}")
        print(f"Median price: ${sorted(prices)[len(prices)//2]:,.2f}")
        print(f"\n{'='*60}")

        # Create histogram
        if bin_size is None:
            # Auto-calculate bin size (10 bins)
            price_range = max(prices) - min(prices)
            bin_size = price_range / 10 if price_range > 0 else 1

        # Group prices into bins
        bins = {}
        for price in prices:
            bin_key = int(price / bin_size) * bin_size
            bins[bin_key] = bins.get(bin_key, 0) + 1

        # Find max count for scaling
        max_count = max(bins.values()) if bins else 1
        bar_width = 50

        # Print histogram
        print("\nPrice Distribution:")
        print(f"{'Price Range':<20} {'Count':<8} {'Bar'}")
        print(f"{'-'*60}")

        for bin_start in sorted(bins.keys()):
            count = bins[bin_start]
            bin_end = bin_start + bin_size
            bar_length = int((count / max_count) * bar_width)
            bar = '█' * bar_length

            print(f"${bin_start:>8,.2f}-{bin_end:<8,.2f} {count:<8} {bar}")

        print(f"{'='*60}\n")

        # Print individual orders for reference
        if len(stop_losses) <= 20:
            print("\nIndividual Stop Loss Orders:")
            print(f"{'Price':<15} {'Size':<15} {'Side':<8} {'Type'}")
            print(f"{'-'*60}")
            for order in stop_losses:
                price = order.get('triggerPx', 'N/A')
                size = order.get('sz', 'N/A')
                side = order.get('side', 'N/A')
                order_type = order.get('orderType', 'N/A')
                print(f"${float(price):>13,.2f} {size:<15} {side:<8} {order_type}")
            print()


async def main():
    """Main entry point."""

    # Configuration
    config = ConrarianConfig()

    # Get target coin from command line or use default
    target_coin = sys.argv[1] if len(sys.argv) > 1 else "BTC"

    print(f"\n{'='*60}")
    print(f"Stop Loss Analyzer - {target_coin}")
    print(f"{'='*60}\n")

    # Resolve database path relative to project root
    project_root = Path(__file__).parent.parent
    db_path = project_root / "data" / "analyzed_traders.db"

    # Initialize components
    phase2_reader = Phase2Reader(str(db_path))
    analyzer = StopLossAnalyzer()

    try:
        # Get bad traders
        logger.info(f"Loading bad traders (score <= {config.bad_trader_score_threshold})...")
        bad_traders = await phase2_reader.get_bad_traders(
            score_threshold=config.bad_trader_score_threshold
        )

        if not bad_traders:
            print("No bad traders found in database")
            return

        addresses = [trader['address'] for trader in bad_traders]
        logger.info(f"Found {len(addresses)} bad traders")

        # Fetch open orders
        orders_by_address = await analyzer.batch_fetch_orders(
            addresses,
            concurrency=5
        )

        # Collect all stop losses for the target coin
        all_stop_losses = []
        traders_with_sl = 0

        for address, orders in orders_by_address.items():
            if orders:
                stop_losses = analyzer.filter_stop_losses(orders, target_coin)
                if stop_losses:
                    all_stop_losses.extend(stop_losses)
                    traders_with_sl += 1

        logger.info(
            f"Found {len(all_stop_losses)} stop loss orders from "
            f"{traders_with_sl} traders"
        )

        # Print distribution
        analyzer.print_distribution(all_stop_losses, target_coin)

    finally:
        await analyzer.close()


if __name__ == "__main__":
    asyncio.run(main())
