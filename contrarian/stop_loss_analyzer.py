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
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime
from zoneinfo import ZoneInfo

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
        rate_limit_period: float = 1.0,
        circuit_breaker_wait: int = 30
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.rate_limiter = AsyncLimiter(rate_limit_calls, rate_limit_period)
        self._session: Optional[aiohttp.ClientSession] = None
        self.circuit_breaker_wait = circuit_breaker_wait
        self._circuit_breaker_active = False
        self._rate_limit_count = 0

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch_current_price(self, coin: str) -> Optional[float]:
        """
        Fetch current mid price for a coin.

        Args:
            coin: Coin symbol (e.g., "BTC", "ETH")

        Returns:
            Current mid price or None if error
        """
        payload = {
            "type": "allMids"
        }

        try:
            async with self.rate_limiter:
                session = await self._get_session()
                async with session.post(
                    f"{self.base_url}/info",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    if response.status == 429:
                        await self._activate_circuit_breaker()
                        return await self.fetch_current_price(coin)

                    response.raise_for_status()
                    data = await response.json()

                    if isinstance(data, dict) and coin in data:
                        return float(data[coin])

                    logger.warning(f"Price not found for {coin}")
                    return None

        except Exception as e:
            logger.warning(f"Failed to fetch current price for {coin}: {e}")
            return None

    async def _activate_circuit_breaker(self):
        """Activate circuit breaker to pause requests."""
        if not self._circuit_breaker_active:
            self._circuit_breaker_active = True
            logger.warning(
                f"⚠️  CIRCUIT BREAKER ACTIVATED - Rate limit detected. "
                f"Pausing for {self.circuit_breaker_wait}s..."
            )
            await asyncio.sleep(self.circuit_breaker_wait)
            self._circuit_breaker_active = False
            self._rate_limit_count = 0
            logger.info("✓ Circuit breaker reset. Resuming requests...")

    async def fetch_user_positions(self, address: str) -> List[Dict]:
        """
        Fetch open positions for a trader using clearinghouseState endpoint.

        Args:
            address: Trader's Ethereum address

        Returns:
            List of position dictionaries from assetPositions
        """
        # Wait if circuit breaker is active
        while self._circuit_breaker_active:
            await asyncio.sleep(1)

        payload = {
            "type": "clearinghouseState",
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
                    if response.status == 429:
                        self._rate_limit_count += 1
                        logger.debug(f"Rate limit hit for {address[:10]}")
                        await self._activate_circuit_breaker()
                        return await self.fetch_user_positions(address)

                    response.raise_for_status()
                    data = await response.json()

                    if isinstance(data, dict):
                        if 'error' in data:
                            logger.warning(f"API error for {address[:10]}: {data['error']}")
                            return []
                        # Extract assetPositions from response
                        return data.get('assetPositions', [])

                    self._rate_limit_count = 0
                    return []

        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                await self._activate_circuit_breaker()
                return await self.fetch_user_positions(address)
            logger.warning(f"Failed to fetch positions for {address[:10]}: {e}")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch positions for {address[:10]}: {e}")
            return []

    async def fetch_open_orders(self, address: str) -> List[Dict]:
        """
        Fetch open orders for a trader using frontendOpenOrders endpoint.

        Args:
            address: Trader's Ethereum address

        Returns:
            List of open order dictionaries
        """
        # Wait if circuit breaker is active
        while self._circuit_breaker_active:
            await asyncio.sleep(1)

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
                    # Check for rate limit before raising
                    if response.status == 429:
                        self._rate_limit_count += 1
                        logger.debug(f"Rate limit hit for {address[:10]}")
                        # Trigger circuit breaker
                        await self._activate_circuit_breaker()
                        # Retry after circuit breaker reset
                        return await self.fetch_open_orders(address)

                    response.raise_for_status()
                    data = await response.json()

                    if isinstance(data, dict) and 'error' in data:
                        logger.warning(f"API error for {address[:10]}: {data['error']}")
                        return []

                    # Reset rate limit counter on success
                    self._rate_limit_count = 0
                    return data if isinstance(data, list) else []

        except aiohttp.ClientResponseError as e:
            if e.status == 429:
                # Handle 429 that wasn't caught above
                await self._activate_circuit_breaker()
                return await self.fetch_open_orders(address)
            logger.warning(f"Failed to fetch orders for {address[:10]}: {e}")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch orders for {address[:10]}: {e}")
            return []

    async def batch_fetch_orders_and_positions(
        self,
        addresses: List[str],
        concurrency: int = 5
    ) -> Dict[str, Dict]:
        """
        Fetch orders and positions for multiple addresses concurrently.

        Args:
            addresses: List of trader addresses
            concurrency: Max concurrent requests

        Returns:
            Dict mapping address -> {"orders": [...], "positions": [...]}
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_semaphore(addr: str):
            async with semaphore:
                # Fetch both orders and positions
                orders = await self.fetch_open_orders(addr)
                positions = await self.fetch_user_positions(addr)
                return addr, {"orders": orders, "positions": positions}

        logger.info(f"Fetching orders and positions for {len(addresses)} traders...")

        tasks = [fetch_with_semaphore(addr) for addr in addresses]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        return dict(results)

    def filter_stop_losses(
        self,
        orders: List[Dict],
        positions: List[Dict],
        target_coin: str,
        current_price: float
    ) -> List[Dict]:
        """
        Filter orders for stop losses on the target coin.

        Distinguishes stop losses from take profits by analyzing position direction
        and trigger price relative to current market price.

        Logic:
        - Long position + trigger below current price = stop loss
        - Short position + trigger above current price = stop loss
        - Long position + trigger above current price = take profit (excluded)
        - Short position + trigger below current price = take profit (excluded)

        Args:
            orders: List of order dictionaries
            positions: List of position dictionaries from clearinghouseState
            target_coin: Coin symbol to filter (e.g., "BTC", "ETH")
            current_price: Current market price of the coin

        Returns:
            List of stop loss orders for the target coin
        """
        # Find the position for this coin
        position = None
        for pos in positions:
            if pos.get('position', {}).get('coin') == target_coin:
                position = pos.get('position', {})
                break

        # If no position, we can't determine stop loss vs take profit
        if not position:
            return []

        # Get position size (positive = long, negative = short)
        try:
            position_size = float(position.get('szi', 0))
        except (ValueError, TypeError):
            return []

        # No position means no stop losses
        if position_size == 0:
            return []

        is_long = position_size > 0
        stop_losses = []

        for order in orders:
            # Check if it's the target coin
            if order.get('coin') != target_coin:
                continue

            # Check if it's a trigger order (stop loss/take profit)
            if not order.get('isTrigger', False):
                continue

            # Must be reduce-only
            if not order.get('reduceOnly', False):
                continue

            # Get trigger price
            try:
                trigger_price = float(order.get('triggerPx', 0))
            except (ValueError, TypeError):
                continue

            # Apply logic to distinguish stop loss from take profit
            if is_long:
                # Long position: stop loss is below current price
                if trigger_price < current_price:
                    stop_losses.append(order)
            else:
                # Short position: stop loss is above current price
                if trigger_price > current_price:
                    stop_losses.append(order)

        return stop_losses

    def visualize_distribution(
        self,
        stop_losses: List[Dict],
        coin: str,
        current_price: Optional[float] = None,
        num_bins: int = 15
    ):
        """
        Visualize stop loss price distribution using matplotlib.

        Args:
            stop_losses: List of stop loss orders
            coin: Coin symbol
            current_price: Current market price (optional)
            num_bins: Number of bins for histogram
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
        if current_price:
            print(f"Current price: ${current_price:,.2f}")
        print(f"{'='*60}\n")

        # Create matplotlib figure
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        fig.suptitle(f'Stop Loss Distribution Analysis - {coin}',
                     fontsize=16, fontweight='bold')

        # Top plot: Histogram
        counts, bins, patches = ax1.hist(prices, bins=num_bins,
                                         color='#ff6b6b', alpha=0.7,
                                         edgecolor='black', linewidth=1.2)

        ax1.set_xlabel('Stop Loss Price (USD)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Number of Orders', fontsize=12, fontweight='bold')
        ax1.set_title('Stop Loss Order Distribution', fontsize=13, fontweight='bold')
        ax1.grid(True, alpha=0.3, linestyle='--')

        # Add current price line to histogram
        if current_price:
            ax1.axvline(current_price, color='green', linestyle='--',
                       linewidth=2.5, label=f'Current Price: ${current_price:,.2f}')
            ax1.legend(loc='upper right', fontsize=10)

        # Add value labels on bars
        for i, (count, patch) in enumerate(zip(counts, patches)):
            if count > 0:
                height = patch.get_height()
                ax1.text(patch.get_x() + patch.get_width()/2., height,
                        f'{int(count)}',
                        ha='center', va='bottom', fontsize=9, fontweight='bold')

        # Bottom plot: Individual stop loss lines
        ax2.set_title('Individual Stop Loss Levels', fontsize=13, fontweight='bold')
        ax2.set_ylabel('Stop Loss Price (USD)', fontsize=12, fontweight='bold')
        ax2.set_xlabel('Order Count', fontsize=12, fontweight='bold')

        # Count occurrences of each price
        from collections import Counter
        price_counts = Counter(prices)
        unique_prices = sorted(price_counts.keys())

        # Plot horizontal lines for each unique stop loss price
        for price in unique_prices:
            count = price_counts[price]
            # Line length proportional to count
            ax2.hlines(price, 0, count, colors='#ff6b6b', linewidth=3, alpha=0.7)
            # Add a marker at the end
            ax2.plot(count, price, 'o', color='#ff6b6b', markersize=8, alpha=0.9)
            # Add count label
            ax2.text(count + 0.1, price, f'{count}',
                    va='center', fontsize=9, fontweight='bold')

        # Add current price line
        if current_price:
            ax2.axhline(current_price, color='green', linestyle='--',
                       linewidth=2.5, label=f'Current Price: ${current_price:,.2f}',
                       zorder=10)
            ax2.legend(loc='upper right', fontsize=10)

        ax2.grid(True, alpha=0.3, linestyle='--', axis='both')
        ax2.set_xlim(0, max(price_counts.values()) * 1.15)

        # Add statistics text box
        stats_text = (
            f"Total Orders: {len(prices)}\n"
            f"Unique Levels: {len(unique_prices)}\n"
            f"Min Price: ${min(prices):,.2f}\n"
            f"Max Price: ${max(prices):,.2f}\n"
            f"Median: ${sorted(prices)[len(prices)//2]:,.2f}\n"
            f"Mean: ${sum(prices)/len(prices):,.2f}"
        )

        if current_price:
            stats_text += f"\nCurrent: ${current_price:,.2f}"

        props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
        fig.text(0.02, 0.98, stats_text, transform=fig.transFigure,
                fontsize=10, verticalalignment='top', bbox=props,
                family='monospace')

        # Add timestamp
        timestamp = datetime.now(ZoneInfo("Europe/Rome")).strftime('%Y-%m-%d %H:%M:%S')
        fig.text(0.98, 0.02, f'Generated: {timestamp}',
                transform=fig.transFigure, fontsize=8,
                verticalalignment='bottom', horizontalalignment='right',
                style='italic', alpha=0.7)

        plt.tight_layout()
        plt.subplots_adjust(top=0.93, bottom=0.07)

        # Show the plot
        plt.show()

        print("📊 Graph displayed. Close the window to continue...")


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

        # Fetch current price first (needed for stop loss filtering)
        logger.info(f"Fetching current price for {target_coin}...")
        current_price = await analyzer.fetch_current_price(target_coin)

        if not current_price:
            logger.error("Could not fetch current price - required for stop loss detection")
            return

        logger.info(f"Current {target_coin} price: ${current_price:,.2f}")

        # Fetch open orders and positions
        data_by_address = await analyzer.batch_fetch_orders_and_positions(
            addresses,
            concurrency=5
        )

        # Collect all stop losses for the target coin
        all_stop_losses = []
        traders_with_sl = 0
        traders_with_positions = 0

        for address, data in data_by_address.items():
            orders = data.get('orders', [])
            positions = data.get('positions', [])

            if positions:
                traders_with_positions += 1

            if orders and positions:
                stop_losses = analyzer.filter_stop_losses(
                    orders,
                    positions,
                    target_coin,
                    current_price
                )
                if stop_losses:
                    all_stop_losses.extend(stop_losses)
                    traders_with_sl += 1

        logger.info(f"Found {traders_with_positions} traders with open positions")
        logger.info(
            f"Found {len(all_stop_losses)} stop loss orders from "
            f"{traders_with_sl} traders"
        )

        # Visualize distribution
        analyzer.visualize_distribution(all_stop_losses, target_coin, current_price)

    finally:
        await analyzer.close()


if __name__ == "__main__":
    asyncio.run(main())
