"""
Contrarian signal generator.

Generates inverse trading signals based on bad traders' positioning.
Supports both count-based and size-weighted signal generation.
"""

import logging
from typing import Dict, List, Literal
from dataclasses import dataclass


logger = logging.getLogger(__name__)


SignalDirection = Literal['LONG', 'SHORT', 'NEUTRAL']
SignalStrength = Literal['STRONG', 'MODERATE', 'WEAK', 'NONE']


@dataclass
class SignalThresholds:
    """Thresholds for signal generation."""
    strong: float = 0.70  # 70%+
    moderate: float = 0.60  # 60%+


class ContrarianSignalGenerator:
    """
    Generates contrarian trading signals from aggregated position data.

    Logic: If bad traders are heavily positioned one way, signal the opposite.
    """

    def __init__(
        self,
        thresholds: SignalThresholds,
        min_traders_for_signal: int = 10
    ):
        """
        Initialize signal generator.

        Args:
            thresholds: Signal strength thresholds
            min_traders_for_signal: Minimum traders required for signal
        """
        self.thresholds = thresholds
        self.min_traders_for_signal = min_traders_for_signal

    def generate_signals(
        self,
        aggregated: Dict[str, Dict],
        use_size_weighted: bool = False
    ) -> List[Dict]:
        """
        Generate contrarian signals for all coins.

        Args:
            aggregated: Aggregated position data by coin
            use_size_weighted: Use size-weighted percentages instead of count-based

        Returns:
            List of signal dictionaries sorted by confidence (highest first)
        """
        signals = []

        for coin, agg_data in aggregated.items():
            # Skip if insufficient sample size
            if not agg_data['has_min_sample_size']:
                continue

            signal = self.generate_signal_for_coin(agg_data, use_size_weighted)
            signals.append(signal)

        # Sort by confidence (descending)
        signals.sort(key=lambda s: s['confidence_score'], reverse=True)

        logger.info(f"Generated {len(signals)} signals")

        return signals

    def generate_signal_for_coin(
        self,
        aggregated_coin: Dict,
        use_size_weighted: bool = False
    ) -> Dict:
        """
        Generate contrarian signal for a single coin.

        Args:
            aggregated_coin: Aggregated data for one coin
            use_size_weighted: Use size-weighted percentages

        Returns:
            Signal dictionary with all metrics and signal direction/strength
        """
        coin = aggregated_coin['coin']
        total_traders = aggregated_coin['total_traders']

        # Choose which metric to use for signal generation
        if use_size_weighted:
            long_pct = aggregated_coin['long_usd_percentage']
            short_pct = aggregated_coin['short_usd_percentage']
            primary_metric = 'size'
        else:
            long_pct = aggregated_coin['long_percentage']
            short_pct = aggregated_coin['short_percentage']
            primary_metric = 'count'

        # Generate contrarian signal based on bad traders' positioning
        signal_direction, signal_strength = self._calculate_signal(
            long_pct,
            short_pct
        )

        # Calculate confidence score
        confidence = self._calculate_confidence(
            long_pct,
            short_pct,
            total_traders
        )

        # Build complete signal dictionary
        signal = {
            'coin': coin,
            'signal_direction': signal_direction,
            'signal_strength': signal_strength,
            'confidence_score': confidence,
            'primary_metric': primary_metric,

            # Count-based metrics (always included)
            'bad_traders_total': total_traders,
            'long_count': aggregated_coin['long_count'],
            'short_count': aggregated_coin['short_count'],
            'long_percentage': aggregated_coin['long_percentage'],
            'short_percentage': aggregated_coin['short_percentage'],

            # Size-weighted metrics (always included)
            'long_usd_value': aggregated_coin['long_usd_value'],
            'short_usd_value': aggregated_coin['short_usd_value'],
            'long_usd_percentage': aggregated_coin['long_usd_percentage'],
            'short_usd_percentage': aggregated_coin['short_usd_percentage']
        }

        return signal

    def _calculate_signal(
        self,
        long_pct: float,
        short_pct: float
    ) -> tuple[SignalDirection, SignalStrength]:
        """
        Calculate signal direction and strength.

        Contrarian logic:
        - If bad traders are mostly LONG → Signal SHORT
        - If bad traders are mostly SHORT → Signal LONG

        Args:
            long_pct: Percentage of bad traders long (0-100)
            short_pct: Percentage of bad traders short (0-100)

        Returns:
            Tuple of (direction, strength)
        """
        # Convert thresholds to percentages (0-100 scale)
        strong_threshold = self.thresholds.strong * 100  # 70%
        moderate_threshold = self.thresholds.moderate * 100  # 60%

        # Check LONG positioning (generate SHORT signal)
        if long_pct >= strong_threshold:
            return 'SHORT', 'STRONG'
        elif long_pct >= moderate_threshold:
            return 'SHORT', 'MODERATE'

        # Check SHORT positioning (generate LONG signal)
        elif short_pct >= strong_threshold:
            return 'LONG', 'STRONG'
        elif short_pct >= moderate_threshold:
            return 'LONG', 'MODERATE'

        # Balanced positioning - no clear signal
        else:
            return 'NEUTRAL', 'NONE'

    def _calculate_confidence(
        self,
        long_pct: float,
        short_pct: float,
        total_traders: int
    ) -> float:
        """
        Calculate confidence score for the signal (0.0 to 1.0).

        Higher confidence when:
        1. More extreme positioning (far from 50/50)
        2. Sufficient sample size (scales down if too small)

        Args:
            long_pct: Percentage long (0-100)
            short_pct: Percentage short (0-100)
            total_traders: Number of traders in sample

        Returns:
            Confidence score (0.0 to 1.0)
        """
        # 1. Positioning extremity (0.0 to 1.0)
        # How far from neutral (50/50)?
        imbalance = abs(long_pct - 50.0) / 50.0  # 0.0 at 50%, 1.0 at 0% or 100%

        # 2. Sample size multiplier (0.0 to 1.0)
        # Penalize small samples, full confidence at 30+ traders
        sample_multiplier = min(1.0, total_traders / (self.min_traders_for_signal * 3))

        # Multiply factors: confidence scales with both imbalance AND sample size
        confidence = imbalance * sample_multiplier

        return round(confidence, 3)

    def get_actionable_signals(
        self,
        signals: List[Dict],
        min_strength: SignalStrength = 'MODERATE',
        min_confidence: float = 0.5
    ) -> List[Dict]:
        """
        Filter signals to only actionable ones.

        Args:
            signals: List of all signals
            min_strength: Minimum signal strength ('MODERATE' or 'STRONG')
            min_confidence: Minimum confidence score (0.0 to 1.0)

        Returns:
            Filtered list of actionable signals
        """
        strength_order = {'NONE': 0, 'WEAK': 1, 'MODERATE': 2, 'STRONG': 3}
        min_strength_value = strength_order.get(min_strength, 2)

        actionable = [
            signal for signal in signals
            if (
                strength_order.get(signal['signal_strength'], 0) >= min_strength_value
                and signal['confidence_score'] >= min_confidence
                and signal['signal_direction'] != 'NEUTRAL'
            )
        ]

        return actionable

    def get_signal_summary(self, signals: List[Dict]) -> Dict:
        """
        Get summary statistics about generated signals.

        Args:
            signals: List of signals

        Returns:
            Summary dictionary
        """
        if not signals:
            return {
                'total_signals': 0,
                'actionable_signals': 0,
                'long_signals': 0,
                'short_signals': 0,
                'strong_signals': 0,
                'moderate_signals': 0,
                'avg_confidence': 0.0
            }

        actionable = self.get_actionable_signals(signals)

        long_signals = sum(1 for s in signals if s['signal_direction'] == 'LONG')
        short_signals = sum(1 for s in signals if s['signal_direction'] == 'SHORT')
        strong_signals = sum(1 for s in signals if s['signal_strength'] == 'STRONG')
        moderate_signals = sum(1 for s in signals if s['signal_strength'] == 'MODERATE')

        avg_confidence = sum(s['confidence_score'] for s in signals) / len(signals)

        return {
            'total_signals': len(signals),
            'actionable_signals': len(actionable),
            'long_signals': long_signals,
            'short_signals': short_signals,
            'strong_signals': strong_signals,
            'moderate_signals': moderate_signals,
            'avg_confidence': round(avg_confidence, 3)
        }

    def explain_signal(self, signal: Dict) -> str:
        """
        Generate human-readable explanation of a signal.

        Args:
            signal: Signal dictionary

        Returns:
            Explanation string
        """
        coin = signal['coin']
        direction = signal['signal_direction']
        strength = signal['signal_strength']
        confidence = signal['confidence_score']

        # Get the metric that drove the signal
        if signal['primary_metric'] == 'size':
            long_pct = signal['long_usd_percentage']
            short_pct = signal['short_usd_percentage']
            metric_name = "by USD value"
        else:
            long_pct = signal['long_percentage']
            short_pct = signal['short_percentage']
            metric_name = "by trader count"

        if direction == 'NEUTRAL':
            return (f"{coin}: No clear signal - positioning is balanced "
                   f"({long_pct:.1f}% long, {short_pct:.1f}% short)")

        # Determine what bad traders are doing
        if direction == 'SHORT':
            bad_trader_bias = f"{long_pct:.1f}% of bad traders are LONG"
        else:
            bad_trader_bias = f"{short_pct:.1f}% of bad traders are SHORT"

        explanation = (
            f"{coin}: {strength} {direction} signal "
            f"(confidence: {confidence:.2f})\n"
            f"  → {bad_trader_bias} {metric_name}\n"
            f"  → Contrarian strategy suggests: {direction} {coin}"
        )

        return explanation
