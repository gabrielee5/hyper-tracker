"""
Live data fetcher for Observer dashboard.

Integrates with Hyperliquid API to fetch real-time trader data.
"""

import logging
import sys
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

# Add analyzer to path to import API client
analyzer_path = Path(__file__).parent.parent.parent / "analyzer"
if str(analyzer_path) not in sys.path:
    sys.path.insert(0, str(analyzer_path))

try:
    from core.api_client import HyperliquidAPIClient, FillsCache
except ImportError:
    # Fallback to absolute import
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from analyzer.core.api_client import HyperliquidAPIClient, FillsCache


logger = logging.getLogger(__name__)


class LiveTraderDataFetcher:
    """
    Fetches live trader data from Hyperliquid API.

    Reuses the HyperliquidAPIClient from analyzer module.
    """

    def __init__(
        self,
        base_url: str = "https://api.hyperliquid.xyz",
        rate_limit_calls: int = 20,
        rate_limit_period: float = 1.0,
        timeout: int = 10,
        cache_ttl_seconds: int = 300,
        timezone: str = "Europe/Rome"
    ):
        """
        Initialize live data fetcher.

        Args:
            base_url: Hyperliquid API base URL
            rate_limit_calls: API rate limit
            rate_limit_period: Rate limit period in seconds
            timeout: Request timeout
            cache_ttl_seconds: Cache TTL (default 5 minutes)
            timezone: Timezone for datetime operations
        """
        self.api_client = HyperliquidAPIClient(
            base_url=base_url,
            rate_limit_calls=rate_limit_calls,
            rate_limit_period=rate_limit_period,
            timeout=timeout
        )

        self.fills_cache = FillsCache(ttl_seconds=cache_ttl_seconds, timezone=timezone)
        self.timezone = timezone

    async def close(self):
        """Close API client session."""
        await self.api_client.close()

    async def fetch_trader_complete_data(self, address: str) -> Dict:
        """
        Fetch complete data for a trader (fills + current state).

        Args:
            address: Trader's Ethereum address

        Returns:
            Dictionary with:
            {
                'fills': List[Dict],           # Historical trades
                'state': Dict,                 # Current positions/balance
                'pnl_timeline': List[Dict],    # [{timestamp, cumulative_pnl}]
                'current_positions': List[Dict] # Open positions
            }
        """
        try:
            # Try to get fills from cache first
            fills = self.fills_cache.get(address)

            if fills is None:
                logger.info(f"Fetching fills for {self._shorten_address(address)} from API")
                fills = await self.api_client.fetch_user_fills(address, aggregate_by_time=True)
                self.fills_cache.set(address, fills)
            else:
                logger.info(f"Using cached fills for {self._shorten_address(address)}")

            # Fetch current state (always fresh, not cached)
            try:
                state = await self.api_client.fetch_user_state(address)
            except Exception as e:
                logger.warning(f"Failed to fetch state for {address}: {e}")
                state = {}

            # Calculate PnL timeline from fills
            pnl_timeline = self.calculate_pnl_timeline(fills)

            # Extract current positions from state
            current_positions = self._extract_positions(state)

            return {
                'fills': fills,
                'state': state,
                'pnl_timeline': pnl_timeline,
                'current_positions': current_positions
            }

        except Exception as e:
            logger.error(f"Error fetching trader data for {address}: {e}")
            return {
                'fills': [],
                'state': {},
                'pnl_timeline': [],
                'current_positions': [],
                'error': str(e)
            }

    def calculate_pnl_timeline(self, fills: List[Dict]) -> List[Dict]:
        """
        Calculate cumulative PnL over time from fills.

        Args:
            fills: List of fill dictionaries from API

        Returns:
            List of {timestamp, cumulative_pnl, date_str} sorted by time
        """
        if not fills:
            return []

        # Sort fills by time (oldest first)
        sorted_fills = sorted(fills, key=lambda x: x.get('time', 0))

        timeline = []
        cumulative_pnl = 0.0

        for fill in sorted_fills:
            # Extract closedPnl from fill
            closed_pnl = fill.get('closedPnl', '0')

            try:
                # Convert closedPnl string to float
                pnl_delta = float(closed_pnl)
                cumulative_pnl += pnl_delta

                # Get timestamp
                timestamp_ms = fill.get('time', 0)

                # Convert timestamp to human-readable date
                dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=ZoneInfo(self.timezone))
                date_str = dt.strftime('%Y-%m-%d %H:%M:%S')

                timeline.append({
                    'timestamp': timestamp_ms,
                    'cumulative_pnl': round(cumulative_pnl, 2),
                    'date_str': date_str
                })

            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing PnL from fill: {e}")
                continue

        return timeline

    def _extract_positions(self, state: Dict) -> List[Dict]:
        """
        Extract current open positions from user state.

        Args:
            state: User state dictionary from API

        Returns:
            List of position dictionaries with formatted data
        """
        positions = []

        if not state or 'assetPositions' not in state:
            return positions

        for asset_pos in state.get('assetPositions', []):
            try:
                coin = asset_pos.get('position', {}).get('coin', 'UNKNOWN')
                szi = asset_pos.get('position', {}).get('szi', '0')
                entry_px = asset_pos.get('position', {}).get('entryPx', '0')
                position_value = asset_pos.get('position', {}).get('positionValue', '0')
                unrealized_pnl = asset_pos.get('position', {}).get('unrealizedPnl', '0')
                leverage = asset_pos.get('position', {}).get('leverage', {})

                # Convert size to float
                size = float(szi)

                # Skip if position is closed (size = 0)
                if abs(size) < 0.0001:
                    continue

                # Determine side
                side = 'LONG' if size > 0 else 'SHORT'

                positions.append({
                    'coin': coin,
                    'side': side,
                    'size': abs(size),
                    'entry_price': float(entry_px) if entry_px else 0,
                    'position_value_usd': float(position_value) if position_value else 0,
                    'unrealized_pnl': float(unrealized_pnl) if unrealized_pnl else 0,
                    'leverage': leverage.get('value', 1) if isinstance(leverage, dict) else 1
                })

            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Error parsing position: {e}")
                continue

        return positions

    def _shorten_address(self, address: str) -> str:
        """Shorten address for logging."""
        if len(address) > 10:
            return f"{address[:6]}...{address[-4:]}"
        return address
