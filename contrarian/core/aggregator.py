"""
Position aggregator for contrarian signal system.

Aggregates positions by coin and calculates both count-based and size-weighted metrics.
"""

import logging
from typing import List, Dict
from collections import defaultdict


logger = logging.getLogger(__name__)


class PositionAggregator:
    """
    Aggregates trader positions by coin/pair.

    Calculates both count-based and size-weighted metrics for signal generation.
    """

    def __init__(self, min_traders_for_signal: int = 10):
        """
        Initialize aggregator.

        Args:
            min_traders_for_signal: Minimum number of traders required to generate a signal
        """
        self.min_traders_for_signal = min_traders_for_signal

    def aggregate_positions(self, positions: List[Dict]) -> Dict[str, Dict]:
        """
        Aggregate positions by coin.

        Args:
            positions: List of normalized position dictionaries from parse_positions()

        Returns:
            Dictionary mapping coin -> aggregated metrics:
            {
                'BTC': {
                    'coin': 'BTC',
                    'total_traders': int,
                    'long_count': int,
                    'short_count': int,
                    'long_percentage': float (0-100),
                    'short_percentage': float (0-100),
                    'long_usd_value': float,
                    'short_usd_value': float,
                    'long_usd_percentage': float (0-100),
                    'short_usd_percentage': float (0-100),
                    'has_min_sample_size': bool,
                    'positions': List[Dict]  # Raw positions for this coin
                }
            }
        """
        if not positions:
            return {}

        # Group by coin
        by_coin = defaultdict(list)
        for pos in positions:
            coin = pos['coin']
            by_coin[coin].append(pos)

        # Aggregate each coin
        aggregated = {}

        for coin, coin_positions in by_coin.items():
            agg = self._aggregate_coin(coin, coin_positions)
            aggregated[coin] = agg

        logger.info(f"Aggregated positions for {len(aggregated)} coins")

        return aggregated

    def _aggregate_coin(self, coin: str, positions: List[Dict]) -> Dict:
        """
        Aggregate positions for a single coin.

        Args:
            coin: Coin identifier (e.g., 'BTC')
            positions: List of positions for this coin

        Returns:
            Aggregated metrics dictionary
        """
        # Count-based metrics
        long_count = sum(1 for p in positions if p['side'] == 'LONG')
        short_count = sum(1 for p in positions if p['side'] == 'SHORT')
        total_traders = long_count + short_count

        # Calculate percentages (avoid division by zero)
        if total_traders > 0:
            long_percentage = (long_count / total_traders) * 100
            short_percentage = (short_count / total_traders) * 100
        else:
            long_percentage = 0.0
            short_percentage = 0.0

        # Size-weighted metrics (USD value)
        long_usd_value = sum(
            p['position_value_usd']
            for p in positions
            if p['side'] == 'LONG' and p['position_value_usd']
        )

        short_usd_value = sum(
            p['position_value_usd']
            for p in positions
            if p['side'] == 'SHORT' and p['position_value_usd']
        )

        total_usd_value = long_usd_value + short_usd_value

        # Calculate USD percentages
        if total_usd_value > 0:
            long_usd_percentage = (long_usd_value / total_usd_value) * 100
            short_usd_percentage = (short_usd_value / total_usd_value) * 100
        else:
            long_usd_percentage = 0.0
            short_usd_percentage = 0.0

        # Check if we have enough sample size
        has_min_sample_size = total_traders >= self.min_traders_for_signal

        return {
            'coin': coin,
            'total_traders': total_traders,
            'long_count': long_count,
            'short_count': short_count,
            'long_percentage': long_percentage,
            'short_percentage': short_percentage,
            'long_usd_value': long_usd_value,
            'short_usd_value': short_usd_value,
            'long_usd_percentage': long_usd_percentage,
            'short_usd_percentage': short_usd_percentage,
            'has_min_sample_size': has_min_sample_size,
            'positions': positions  # Keep raw positions for reference
        }

    def get_top_coins_by_activity(
        self,
        aggregated: Dict[str, Dict],
        limit: int = 10
    ) -> List[Dict]:
        """
        Get top coins by number of active traders.

        Args:
            aggregated: Aggregated positions dictionary
            limit: Maximum number of coins to return

        Returns:
            List of aggregated coin dictionaries, sorted by trader count
        """
        coins = list(aggregated.values())

        # Sort by total traders (descending)
        coins.sort(key=lambda x: x['total_traders'], reverse=True)

        return coins[:limit]

    def get_coins_with_min_sample(
        self,
        aggregated: Dict[str, Dict]
    ) -> List[Dict]:
        """
        Get coins that meet minimum sample size requirement.

        Args:
            aggregated: Aggregated positions dictionary

        Returns:
            List of coin dictionaries with sufficient sample size
        """
        return [
            coin_data
            for coin_data in aggregated.values()
            if coin_data['has_min_sample_size']
        ]

    def calculate_imbalance_score(self, aggregated_coin: Dict) -> float:
        """
        Calculate position imbalance score (0-1).

        Higher score = more imbalanced positioning = stronger signal potential.

        Args:
            aggregated_coin: Aggregated data for a single coin

        Returns:
            Imbalance score (0.0 to 1.0)
        """
        # Use count-based percentage by default
        long_pct = aggregated_coin['long_percentage']

        # Calculate how far from 50/50 (neutral)
        imbalance = abs(long_pct - 50.0) / 50.0  # 0.0 to 1.0

        return imbalance

    def get_statistics(self, aggregated: Dict[str, Dict]) -> Dict:
        """
        Get overall statistics about aggregated positions.

        Args:
            aggregated: Aggregated positions dictionary

        Returns:
            Statistics dictionary
        """
        if not aggregated:
            return {
                'total_coins': 0,
                'total_positions': 0,
                'coins_with_signals': 0,
                'avg_traders_per_coin': 0.0
            }

        total_coins = len(aggregated)
        total_positions = sum(c['total_traders'] for c in aggregated.values())
        coins_with_signals = sum(1 for c in aggregated.values() if c['has_min_sample_size'])
        avg_traders = total_positions / total_coins if total_coins > 0 else 0.0

        return {
            'total_coins': total_coins,
            'total_positions': total_positions,
            'coins_with_signals': coins_with_signals,
            'avg_traders_per_coin': avg_traders
        }
