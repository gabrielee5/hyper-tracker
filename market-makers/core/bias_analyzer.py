"""Analyze market maker positions to calculate directional bias."""

import logging
from typing import List, Dict, Optional
from collections import defaultdict


logger = logging.getLogger(__name__)


class BiasAnalyzer:
    """
    Analyzes market maker positions to calculate directional bias.

    Bias calculation:
    - Net Bias (USD) = Long Value - Short Value
    - Bias Percentage = (Net Bias / Total Value) × 100
    - Direction: BULLISH (>10%), BEARISH (<-10%), NEUTRAL (-10% to +10%)
    - Strength: STRONG (|bias| > 30%), MODERATE (10-30%), WEAK (<10%)
    """

    def __init__(
        self,
        neutral_threshold: float = 10.0,
        strong_threshold: float = 30.0
    ):
        """
        Initialize bias analyzer.

        Args:
            neutral_threshold: Percentage threshold for neutral bias (default: 10%)
            strong_threshold: Percentage threshold for strong bias (default: 30%)
        """
        self.neutral_threshold = neutral_threshold
        self.strong_threshold = strong_threshold

    def analyze_positions(self, positions: List[Dict]) -> List[Dict]:
        """
        Analyze positions and calculate bias for each coin.

        Args:
            positions: List of position dictionaries with keys:
                - address: MM address
                - coin: Asset symbol
                - side: 'LONG' or 'SHORT'
                - position_value_usd: Position value in USD
                - size: Position size
                - entry_price: Entry price
                - leverage_value: Leverage
                - unrealized_pnl: Unrealized PnL

        Returns:
            List of bias dictionaries, one per coin, sorted by total value
        """
        if not positions:
            logger.warning("No positions to analyze")
            return []

        # Group positions by coin
        positions_by_coin = defaultdict(list)
        for pos in positions:
            positions_by_coin[pos['coin']].append(pos)

        bias_results = []

        for coin, coin_positions in positions_by_coin.items():
            bias = self._calculate_coin_bias(coin, coin_positions)
            if bias:
                bias_results.append(bias)

        # Sort by total value descending
        bias_results.sort(key=lambda x: x['total_value_usd'], reverse=True)

        logger.info(f"Calculated bias for {len(bias_results)} coins")

        return bias_results

    def _calculate_coin_bias(self, coin: str, positions: List[Dict]) -> Optional[Dict]:
        """
        Calculate bias for a single coin.

        Args:
            coin: Coin symbol
            positions: List of positions for this coin

        Returns:
            Bias dictionary or None if invalid
        """
        if not positions:
            return None

        # Count unique market makers
        unique_mms = set(p['address'] for p in positions)
        mm_count = len(unique_mms)

        # Aggregate positions by side
        long_positions = [p for p in positions if p['side'] == 'LONG']
        short_positions = [p for p in positions if p['side'] == 'SHORT']

        long_count = len(long_positions)
        short_count = len(short_positions)

        # Calculate total values
        long_value = sum(p['position_value_usd'] for p in long_positions)
        short_value = sum(p['position_value_usd'] for p in short_positions)
        total_value = long_value + short_value

        if total_value == 0:
            logger.warning(f"Zero total value for {coin}, skipping")
            return None

        # Calculate bias
        net_bias = long_value - short_value
        bias_percentage = (net_bias / total_value) * 100

        # Determine direction
        if bias_percentage > self.neutral_threshold:
            direction = 'BULLISH'
        elif bias_percentage < -self.neutral_threshold:
            direction = 'BEARISH'
        else:
            direction = 'NEUTRAL'

        # Determine strength
        abs_bias = abs(bias_percentage)
        if abs_bias > self.strong_threshold:
            strength = 'STRONG'
        elif abs_bias > self.neutral_threshold:
            strength = 'MODERATE'
        else:
            strength = 'WEAK'

        return {
            'coin': coin,
            'mm_count': mm_count,
            'long_count': long_count,
            'short_count': short_count,
            'long_value_usd': long_value,
            'short_value_usd': short_value,
            'total_value_usd': total_value,
            'net_bias_usd': net_bias,
            'bias_percentage': bias_percentage,
            'direction': direction,
            'strength': strength
        }

    def get_extreme_consensus(
        self,
        bias_results: List[Dict],
        threshold: float = 90.0
    ) -> List[Dict]:
        """
        Identify coins with extreme consensus (>90% on one side).

        This can be a contrarian indicator for potential reversals.

        Args:
            bias_results: List of bias dictionaries
            threshold: Percentage threshold for extreme consensus (default: 90%)

        Returns:
            List of extreme consensus coins
        """
        extreme = []

        for bias in bias_results:
            abs_percentage = abs(bias['bias_percentage'])

            # Calculate percentage of MMs on dominant side
            total_positions = bias['long_count'] + bias['short_count']
            if total_positions == 0:
                continue

            dominant_count = max(bias['long_count'], bias['short_count'])
            mm_consensus_pct = (dominant_count / total_positions) * 100

            if mm_consensus_pct >= threshold:
                extreme.append({
                    'coin': bias['coin'],
                    'direction': bias['direction'],
                    'mm_consensus_pct': mm_consensus_pct,
                    'bias_percentage': bias['bias_percentage'],
                    'mm_count': bias['mm_count']
                })

        return extreme

    def calculate_aggregate_sentiment(self, bias_results: List[Dict]) -> Dict:
        """
        Calculate aggregate market maker sentiment across all coins.

        Args:
            bias_results: List of bias dictionaries

        Returns:
            Dictionary with aggregate metrics
        """
        if not bias_results:
            return {
                'total_coins': 0,
                'bullish_count': 0,
                'bearish_count': 0,
                'neutral_count': 0,
                'avg_bias_percentage': 0,
                'total_position_value': 0,
                'net_aggregate_bias': 0
            }

        bullish_count = sum(1 for b in bias_results if b['direction'] == 'BULLISH')
        bearish_count = sum(1 for b in bias_results if b['direction'] == 'BEARISH')
        neutral_count = sum(1 for b in bias_results if b['direction'] == 'NEUTRAL')

        total_value = sum(b['total_value_usd'] for b in bias_results)
        net_aggregate = sum(b['net_bias_usd'] for b in bias_results)
        avg_bias = sum(b['bias_percentage'] for b in bias_results) / len(bias_results)

        return {
            'total_coins': len(bias_results),
            'bullish_count': bullish_count,
            'bearish_count': bearish_count,
            'neutral_count': neutral_count,
            'avg_bias_percentage': avg_bias,
            'total_position_value': total_value,
            'net_aggregate_bias': net_aggregate
        }
