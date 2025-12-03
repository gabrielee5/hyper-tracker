"""
Position sizing logic with confidence-weighted allocation.
"""

from typing import Dict, List
from signal_reader import ContrarianSignal
import logging

logger = logging.getLogger(__name__)


class PositionSizer:
    """Calculates position sizes based on confidence-weighted allocation."""

    def __init__(self, max_position_pct: float = 0.40):
        """
        Initialize position sizer.

        Args:
            max_position_pct: Maximum allocation for a single position (default 0.40 = 40%)
        """
        self.max_position_pct = max_position_pct

    def calculate_allocations(self, signals: List[ContrarianSignal],
                             total_capital: float) -> Dict[str, Dict]:
        """
        Calculate target allocations for all signals using confidence weighting.

        Args:
            signals: List of contrarian signals (already filtered and sorted)
            total_capital: Total portfolio value to allocate

        Returns:
            Dict mapping pair -> {'usd_value': float, 'direction': str, 'confidence': float}

        Example:
            signals = [
                Signal(pair='BTC', confidence=0.85, direction='SHORT'),
                Signal(pair='ETH', confidence=0.78, direction='SHORT'),
                Signal(pair='SOL', confidence=0.72, direction='LONG'),
            ]
            total_capital = 100000

            Result:
            {
                'BTC': {'usd_value': 36170, 'direction': 'SHORT', 'confidence': 0.85},
                'ETH': {'usd_value': 33191, 'direction': 'SHORT', 'confidence': 0.78},
                'SOL': {'usd_value': 30638, 'direction': 'LONG', 'confidence': 0.72}
            }
        """
        if not signals:
            logger.warning("No signals provided for allocation")
            return {}

        if total_capital <= 0:
            logger.error(f"Invalid total capital: {total_capital}")
            return {}

        # Step 1: Sum all confidences
        total_confidence = sum(signal.confidence for signal in signals)

        if total_confidence == 0:
            logger.error("Total confidence is zero, cannot allocate")
            return {}

        # Step 2: Calculate raw weights (normalized by confidence)
        raw_allocations = {}
        for signal in signals:
            weight = signal.confidence / total_confidence
            raw_allocations[signal.pair] = {
                'weight': weight,
                'direction': signal.signal,
                'confidence': signal.confidence
            }

        # Step 3: Apply position cap (40% max per position)
        capped_allocations = {}
        total_capped_weight = 0
        uncapped_pairs = []

        for pair, data in raw_allocations.items():
            if data['weight'] > self.max_position_pct:
                # Cap this position at max %
                capped_allocations[pair] = {
                    'weight': self.max_position_pct,
                    'direction': data['direction'],
                    'confidence': data['confidence'],
                    'capped': True
                }
                total_capped_weight += self.max_position_pct
                logger.info(f"{pair} capped at {self.max_position_pct*100:.1f}% "
                          f"(was {data['weight']*100:.1f}%)")
            else:
                uncapped_pairs.append(pair)

        # Step 4: Redistribute excess weight to uncapped positions
        if uncapped_pairs and total_capped_weight < 1.0:
            remaining_weight = 1.0 - total_capped_weight
            uncapped_total_weight = sum(raw_allocations[p]['weight'] for p in uncapped_pairs)

            if uncapped_total_weight > 0:
                for pair in uncapped_pairs:
                    # Proportionally scale uncapped positions to use remaining weight
                    original_weight = raw_allocations[pair]['weight']
                    scaled_weight = (original_weight / uncapped_total_weight) * remaining_weight

                    capped_allocations[pair] = {
                        'weight': scaled_weight,
                        'direction': raw_allocations[pair]['direction'],
                        'confidence': raw_allocations[pair]['confidence'],
                        'capped': False
                    }

        # Step 5: Convert weights to USD values
        final_allocations = {}
        total_allocated = 0

        for pair, data in capped_allocations.items():
            usd_value = data['weight'] * total_capital
            final_allocations[pair] = {
                'usd_value': round(usd_value, 2),
                'weight': data['weight'],
                'direction': data['direction'],
                'confidence': data['confidence']
            }
            total_allocated += usd_value

        # Log summary
        logger.info(f"Calculated allocations for {len(final_allocations)} positions")
        logger.info(f"Total capital: ${total_capital:,.2f}")
        logger.info(f"Total allocated: ${total_allocated:,.2f} ({total_allocated/total_capital*100:.1f}%)")

        for pair, data in sorted(final_allocations.items(),
                                key=lambda x: x[1]['usd_value'],
                                reverse=True):
            logger.debug(f"  {pair}: ${data['usd_value']:,.2f} ({data['weight']*100:.1f}%) "
                        f"{data['direction']} conf={data['confidence']:.2f}")

        return final_allocations

    def calculate_position_delta(self, current_positions: Dict[str, float],
                                 target_allocations: Dict[str, Dict],
                                 min_trade_size: float = 1000) -> Dict[str, Dict]:
        """
        Calculate the changes needed to rebalance from current to target.

        Args:
            current_positions: Dict mapping pair -> current USD value
            target_allocations: Dict from calculate_allocations()
            min_trade_size: Minimum trade size to execute (default $1000)

        Returns:
            Dict mapping pair -> {'action': str, 'delta_usd': float, 'direction': str}
            where action is: 'OPEN', 'CLOSE', 'INCREASE', 'DECREASE', 'FLIP', 'HOLD'
        """
        adjustments = {}

        # Check positions to close (no longer in targets)
        for pair, current_value in current_positions.items():
            if pair not in target_allocations:
                adjustments[pair] = {
                    'action': 'CLOSE',
                    'delta_usd': current_value,
                    'current_usd': current_value,
                    'target_usd': 0,
                    'direction': None  # Will be filled by caller
                }

        # Check positions to open or adjust
        for pair, target_data in target_allocations.items():
            target_usd = target_data['usd_value']
            target_direction = target_data['direction']
            current_usd = current_positions.get(pair, 0)

            if current_usd == 0:
                # New position
                adjustments[pair] = {
                    'action': 'OPEN',
                    'delta_usd': target_usd,
                    'current_usd': 0,
                    'target_usd': target_usd,
                    'direction': target_direction,
                    'confidence': target_data['confidence']
                }

            else:
                # Existing position - check if adjustment needed
                delta = target_usd - current_usd

                if abs(delta) >= min_trade_size:
                    if delta > 0:
                        action = 'INCREASE'
                    else:
                        action = 'DECREASE'

                    adjustments[pair] = {
                        'action': action,
                        'delta_usd': abs(delta),
                        'current_usd': current_usd,
                        'target_usd': target_usd,
                        'direction': target_direction,
                        'confidence': target_data['confidence']
                    }
                else:
                    # No adjustment needed (within tolerance)
                    logger.debug(f"{pair}: delta ${abs(delta):.2f} < min ${min_trade_size}, "
                               f"no adjustment")

        logger.info(f"Calculated {len(adjustments)} position adjustments")
        return adjustments
