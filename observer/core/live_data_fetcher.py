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

            # Calculate trading statistics from fills
            trading_stats = self.calculate_trading_statistics(fills)

            return {
                'fills': fills,
                'state': state,
                'pnl_timeline': pnl_timeline,
                'current_positions': current_positions,
                'trading_stats': trading_stats
            }

        except Exception as e:
            logger.error(f"Error fetching trader data for {address}: {e}")
            return {
                'fills': [],
                'state': {},
                'pnl_timeline': [],
                'current_positions': [],
                'trading_stats': {},
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

    def calculate_trading_statistics(self, fills: List[Dict]) -> Dict:
        """
        Calculate comprehensive trading statistics from fills.

        Args:
            fills: List of fill dictionaries from API

        Returns:
            Dictionary with statistics:
            {
                'first_trade_time': int (timestamp ms),
                'last_trade_time': int (timestamp ms),
                'first_trade_date': str,
                'last_trade_date': str,
                'total_volume_usd': float,
                'avg_volume_per_trade_usd': float,
                'avg_time_in_trade_hours': float or None,
                'num_position_cycles': int
            }
        """
        if not fills:
            return {
                'first_trade_time': None,
                'last_trade_time': None,
                'first_trade_date': 'N/A',
                'last_trade_date': 'N/A',
                'total_volume_usd': 0,
                'avg_volume_per_trade_usd': 0,
                'avg_time_in_trade_hours': None,
                'num_position_cycles': 0
            }

        # Sort fills by time
        sorted_fills = sorted(fills, key=lambda x: x.get('time', 0))

        # Calculate time-based metrics
        first_trade_time = sorted_fills[0].get('time', 0)
        last_trade_time = sorted_fills[-1].get('time', 0)

        first_trade_date = self._format_timestamp(first_trade_time)
        last_trade_date = self._format_timestamp(last_trade_time)

        # Calculate volume metrics
        total_volume = 0
        for fill in fills:
            try:
                size = abs(float(fill.get('sz', 0)))
                price = float(fill.get('px', 0))
                total_volume += size * price
            except (ValueError, TypeError):
                continue

        avg_volume_per_trade = total_volume / len(fills) if fills else 0

        # Calculate average time in trade (position lifecycle tracking)
        avg_time_in_trade, num_cycles = self._calculate_avg_time_in_trade(sorted_fills)

        return {
            'first_trade_time': first_trade_time,
            'last_trade_time': last_trade_time,
            'first_trade_date': first_trade_date,
            'last_trade_date': last_trade_date,
            'total_volume_usd': round(total_volume, 2),
            'avg_volume_per_trade_usd': round(avg_volume_per_trade, 2),
            'avg_time_in_trade_hours': round(avg_time_in_trade, 2) if avg_time_in_trade else None,
            'num_position_cycles': num_cycles
        }

    def _calculate_avg_time_in_trade(self, sorted_fills: List[Dict]) -> tuple[Optional[float], int]:
        """
        Calculate average time in trade by tracking position lifecycles.

        A position cycle is from opening (position goes from 0 to non-zero)
        to closing (position returns to 0).

        Args:
            sorted_fills: List of fills sorted by time

        Returns:
            Tuple of (avg_time_hours, num_complete_cycles)
        """
        if not sorted_fills:
            return None, 0

        # Track positions per coin
        positions_by_coin = {}
        position_durations = []

        for fill in sorted_fills:
            try:
                coin = fill.get('coin', 'UNKNOWN')
                timestamp = fill.get('time', 0)
                start_pos = float(fill.get('startPosition', 0))
                size = float(fill.get('sz', 0))
                side = fill.get('side', '')

                # Calculate position after this fill
                if side == 'B':  # Buy
                    end_pos = start_pos + size
                elif side == 'A':  # Ask/Sell
                    end_pos = start_pos - size
                else:
                    end_pos = start_pos

                # Initialize coin tracking
                if coin not in positions_by_coin:
                    positions_by_coin[coin] = {'open_time': None, 'position': 0}

                coin_data = positions_by_coin[coin]

                # Check if we're opening a position (going from 0 to non-zero)
                if abs(coin_data['position']) < 0.0001 and abs(end_pos) >= 0.0001:
                    coin_data['open_time'] = timestamp

                # Check if we're closing a position (going from non-zero to 0)
                elif abs(coin_data['position']) >= 0.0001 and abs(end_pos) < 0.0001:
                    if coin_data['open_time'] is not None:
                        duration_ms = timestamp - coin_data['open_time']
                        duration_hours = duration_ms / (1000 * 60 * 60)
                        position_durations.append(duration_hours)
                        coin_data['open_time'] = None

                # Update position
                coin_data['position'] = end_pos

            except (ValueError, TypeError, KeyError) as e:
                logger.warning(f"Error processing fill for avg time calculation: {e}")
                continue

        # Calculate average
        if position_durations:
            avg_time = sum(position_durations) / len(position_durations)
            return avg_time, len(position_durations)
        else:
            return None, 0

    def _format_timestamp(self, timestamp_ms: int) -> str:
        """Format timestamp to human-readable date."""
        if not timestamp_ms:
            return 'N/A'
        try:
            dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=ZoneInfo(self.timezone))
            return dt.strftime('%Y-%m-%d %H:%M')
        except Exception:
            return 'N/A'

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
