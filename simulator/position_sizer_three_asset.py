"""
Position sizing logic for Three-Asset Strategy (BTC, SOL, ETH only).

Strategy:
- Only allocates to BTC, SOL, and ETH
- Each asset has max allocation of 1/3 of total capital
- Actual allocation = confidence × (total_capital / 3)
- No confidence threshold - any confidence level is accepted
"""

from typing import Dict, List
from signal_reader import ContrarianSignal
import logging

logger = logging.getLogger(__name__)


class PositionSizerThreeAsset:
    """
    Position sizer for three-asset strategy.

    Allocates capital only to BTC, SOL, and ETH based on confidence scores.
    """

    # Whitelist of allowed assets
    ALLOWED_ASSETS = ['BTC', 'SOL', 'ETH']

    def __init__(self):
        """Initialize three-asset position sizer."""
        self.num_assets = len(self.ALLOWED_ASSETS)
        logger.info(f"Three-Asset Position Sizer initialized")
        logger.info(f"Allowed assets: {', '.join(self.ALLOWED_ASSETS)}")
        logger.info(f"Max allocation per asset: {1/self.num_assets:.1%}")

    def calculate_allocations(self, signals: List[ContrarianSignal],
                             total_capital: float) -> Dict[str, Dict]:
        """
        Calculate target allocations for three-asset strategy.

        Args:
            signals: List of contrarian signals
            total_capital: Total portfolio value to allocate

        Returns:
            Dict mapping pair -> {'usd_value': float, 'direction': str, 'confidence': float}

        Strategy Logic:
            - Per-asset max allocation = total_capital / 3
            - Actual allocation = confidence × per_asset_max
            - Only BTC, SOL, ETH are considered

        Example:
            total_capital = $100,000
            per_asset_max = $33,333.33

            BTC: 70% confidence → $23,333.33 (0.70 × $33,333.33)
            SOL: 40% confidence → $13,333.33 (0.40 × $33,333.33)
            ETH: 85% confidence → $28,333.33 (0.85 × $33,333.33)

            Total allocated: $65,000
            Cash reserve: $35,000
        """
        if total_capital <= 0:
            logger.error(f"Invalid total capital: {total_capital}")
            return {}

        # Calculate max allocation per asset
        per_asset_max = total_capital / self.num_assets

        logger.info("=" * 80)
        logger.info("THREE-ASSET STRATEGY ALLOCATION")
        logger.info("=" * 80)
        logger.info(f"Total capital: ${total_capital:,.2f}")
        logger.info(f"Per-asset max: ${per_asset_max:,.2f} ({1/self.num_assets:.1%})")
        logger.info("")

        # Filter signals for allowed assets only
        allowed_signals = {
            signal.pair: signal
            for signal in signals
            if signal.pair in self.ALLOWED_ASSETS
        }

        logger.info(f"Signals received: {len(signals)} total")
        logger.info(f"Signals for allowed assets: {len(allowed_signals)}")

        # Calculate allocations
        allocations = {}
        total_allocated = 0

        for asset in self.ALLOWED_ASSETS:
            if asset in allowed_signals:
                signal = allowed_signals[asset]

                # Allocation = confidence × per-asset max
                allocation_usd = signal.confidence * per_asset_max

                allocations[asset] = {
                    'usd_value': round(allocation_usd, 2),
                    'weight': signal.confidence / self.num_assets,
                    'direction': signal.signal,
                    'confidence': signal.confidence
                }

                total_allocated += allocation_usd

                logger.info(f"  {asset}: ${allocation_usd:,.2f} "
                          f"({signal.confidence:.1%} conf × ${per_asset_max:,.2f}) "
                          f"{signal.signal}")
            else:
                logger.info(f"  {asset}: No signal - $0 allocated")

        # Calculate cash reserve
        cash_reserve = total_capital - total_allocated
        cash_reserve_pct = (cash_reserve / total_capital) * 100 if total_capital > 0 else 0

        logger.info("")
        logger.info(f"Total allocated: ${total_allocated:,.2f} ({total_allocated/total_capital*100:.1f}%)")
        logger.info(f"Cash reserve: ${cash_reserve:,.2f} ({cash_reserve_pct:.1f}%)")
        logger.info("=" * 80)

        return allocations

    def calculate_position_delta(self, current_positions: Dict[str, float],
                                 target_allocations: Dict[str, Dict],
                                 min_trade_size: float = 100) -> Dict[str, Dict]:
        """
        Calculate the changes needed to rebalance from current to target.

        Args:
            current_positions: Dict mapping pair -> current USD value
            target_allocations: Dict from calculate_allocations()
            min_trade_size: Minimum trade size to execute (default $100)

        Returns:
            Dict mapping pair -> {'action': str, 'delta_usd': float, 'direction': str}
            where action is: 'OPEN', 'CLOSE', 'INCREASE', 'DECREASE'
        """
        adjustments = {}

        # Check positions to close (not in allowed assets or no longer in targets)
        for pair, current_value in current_positions.items():
            if pair not in self.ALLOWED_ASSETS or pair not in target_allocations:
                adjustments[pair] = {
                    'action': 'CLOSE',
                    'delta_usd': current_value,
                    'current_usd': current_value,
                    'target_usd': 0,
                    'direction': None  # Will be filled by caller
                }
                logger.info(f"  {pair}: CLOSE position (${current_value:,.2f})")

        # Check positions to open or adjust (only for allowed assets)
        for pair in self.ALLOWED_ASSETS:
            if pair in target_allocations:
                target_data = target_allocations[pair]
                target_usd = target_data['usd_value']
                target_direction = target_data['direction']
                current_usd = current_positions.get(pair, 0)

                if current_usd == 0 and target_usd > 0:
                    # New position
                    adjustments[pair] = {
                        'action': 'OPEN',
                        'delta_usd': target_usd,
                        'current_usd': 0,
                        'target_usd': target_usd,
                        'direction': target_direction,
                        'confidence': target_data['confidence']
                    }
                    logger.info(f"  {pair}: OPEN {target_direction} (${target_usd:,.2f})")

                elif current_usd > 0:
                    # Existing position - check if adjustment needed
                    delta = target_usd - current_usd

                    if abs(delta) >= min_trade_size:
                        action = 'INCREASE' if delta > 0 else 'DECREASE'

                        adjustments[pair] = {
                            'action': action,
                            'delta_usd': abs(delta),
                            'current_usd': current_usd,
                            'target_usd': target_usd,
                            'direction': target_direction,
                            'confidence': target_data['confidence']
                        }
                        logger.info(f"  {pair}: {action} by ${abs(delta):,.2f} "
                                  f"(${current_usd:,.2f} → ${target_usd:,.2f})")
                    else:
                        logger.debug(f"  {pair}: No adjustment needed "
                                   f"(delta ${abs(delta):.2f} < min ${min_trade_size})")

        logger.info(f"Calculated {len(adjustments)} position adjustments")
        return adjustments
