"""
Portfolio manager for tracking positions and calculating mark-to-market values.
"""

from typing import Dict, List, Optional
from datetime import datetime
from database import SimulatorDatabase
from order_executor import OrderExecutor, ExecutionResult
from price_fetcher import PriceFetcher
from signal_reader import ContrarianSignal
import logging

logger = logging.getLogger(__name__)


class Position:
    """Represents an open trading position."""

    def __init__(self, pair: str, direction: str, entry_price: float,
                 quantity: float, entry_size_usd: float, entry_timestamp: datetime,
                 signal_confidence: float, total_fees_paid: float = 0):
        self.pair = pair
        self.direction = direction
        self.entry_price = entry_price
        self.quantity = quantity
        self.entry_size_usd = entry_size_usd
        self.entry_timestamp = entry_timestamp
        self.signal_confidence = signal_confidence
        self.total_fees_paid = total_fees_paid

        self.current_price = entry_price
        self.unrealized_pnl = 0.0
        self.unrealized_pnl_pct = 0.0
        self.current_size_usd = entry_size_usd

    def update_price(self, new_price: float):
        """Update position with new market price."""
        self.current_price = new_price

        # Calculate unrealized P&L
        if self.direction == 'LONG':
            self.unrealized_pnl = (self.current_price - self.entry_price) * self.quantity
        else:  # SHORT
            self.unrealized_pnl = (self.entry_price - self.current_price) * self.quantity

        # Calculate P&L percentage
        if self.entry_size_usd > 0:
            self.unrealized_pnl_pct = (self.unrealized_pnl / self.entry_size_usd) * 100

        # Update current position value
        self.current_size_usd = self.entry_size_usd + self.unrealized_pnl

    def to_dict(self) -> Dict:
        """Convert position to dictionary."""
        return {
            'pair': self.pair,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'current_price': self.current_price,
            'quantity': self.quantity,
            'entry_size_usd': self.entry_size_usd,
            'current_size_usd': self.current_size_usd,
            'unrealized_pnl': self.unrealized_pnl,
            'unrealized_pnl_pct': self.unrealized_pnl_pct,
            'entry_timestamp': self.entry_timestamp,
            'signal_confidence': self.signal_confidence,
            'total_fees_paid': self.total_fees_paid
        }


class PortfolioManager:
    """Manages portfolio state, positions, and mark-to-market calculations."""

    def __init__(self, db: SimulatorDatabase, executor: OrderExecutor,
                 price_fetcher: PriceFetcher, starting_capital: float = 100000):
        self.db = db
        self.executor = executor
        self.price_fetcher = price_fetcher
        self.starting_capital = starting_capital

        self.positions: Dict[str, Position] = {}
        self.total_equity = starting_capital
        self.total_pnl = 0.0
        self.total_fees_paid = 0.0

        # Try to restore state from database
        self._restore_state()

        logger.info(f"Portfolio manager initialized with ${starting_capital:,.2f}")

    def _restore_state(self):
        """Restore portfolio state from database."""
        try:
            # Restore positions
            db_positions = self.db.get_all_positions()
            for pos_data in db_positions:
                position = Position(
                    pair=pos_data['pair'],
                    direction=pos_data['direction'],
                    entry_price=pos_data['entry_price'],
                    quantity=pos_data['quantity'],
                    entry_size_usd=pos_data['entry_size_usd'],
                    entry_timestamp=datetime.fromisoformat(pos_data['entry_timestamp']),
                    signal_confidence=pos_data['signal_confidence'],
                    total_fees_paid=pos_data['total_fees_paid']
                )
                position.update_price(pos_data['current_price'])
                self.positions[pos_data['pair']] = position

            # Restore portfolio state
            latest_state = self.db.get_latest_portfolio_state()
            if latest_state and latest_state['total_equity'] > 0:
                self.total_equity = latest_state['total_equity']
                self.total_pnl = latest_state['total_pnl']
                self.total_fees_paid = latest_state['total_fees_paid']
            else:
                # First run or invalid state - use starting capital
                self.total_equity = self.starting_capital

            logger.info(f"Restored {len(self.positions)} positions from database")

        except Exception as e:
            logger.warning(f"Could not restore state: {e}")

    def open_position(self, pair: str, direction: str, usd_value: float,
                     signal_confidence: float, reason: str = "new_signal") -> bool:
        """
        Open a new position.

        Args:
            pair: Trading pair
            direction: 'LONG' or 'SHORT'
            usd_value: USD value to invest
            signal_confidence: Confidence score from signal
            reason: Reason for opening

        Returns:
            True if successful
        """
        # Get current market price
        market_price = self.price_fetcher.get_price(pair)
        if market_price is None:
            logger.error(f"Cannot open position for {pair}: price not available")
            return False

        # Execute order
        result = self.executor.execute_order(
            pair=pair,
            direction=direction,
            action='OPEN',
            market_price=market_price,
            usd_value=usd_value
        )

        if not result.success:
            logger.error(f"Failed to open {pair}: {result.error_message}")
            return False

        # Create position
        position = Position(
            pair=pair,
            direction=direction,
            entry_price=result.execution_price,
            quantity=result.quantity,
            entry_size_usd=usd_value,
            entry_timestamp=datetime.utcnow(),
            signal_confidence=signal_confidence,
            total_fees_paid=result.fees
        )
        position.update_price(market_price)
        self.positions[pair] = position

        # Update totals
        self.total_fees_paid += result.fees

        # Log to database
        self.db.log_trade(
            pair=pair,
            direction=direction,
            action='OPEN',
            price=result.execution_price,
            quantity=result.quantity,
            usd_value=usd_value,
            fees=result.fees,
            slippage=result.slippage,
            signal_confidence=signal_confidence,
            reason=reason
        )

        self.db.upsert_position(
            pair=pair,
            direction=direction,
            entry_price=result.execution_price,
            current_price=market_price,
            entry_size_usd=usd_value,
            current_size_usd=position.current_size_usd,
            quantity=result.quantity,
            entry_timestamp=position.entry_timestamp,
            unrealized_pnl=position.unrealized_pnl,
            unrealized_pnl_pct=position.unrealized_pnl_pct,
            signal_confidence=signal_confidence,
            total_fees_paid=result.fees
        )

        logger.info(f"Opened {direction} position in {pair}: ${usd_value:,.2f} "
                   f"@ ${result.execution_price:.2f}")
        return True

    def close_position(self, pair: str, reason: str = "signal_removed") -> Optional[float]:
        """
        Close an existing position.

        Returns:
            Realized P&L or None if failed
        """
        if pair not in self.positions:
            logger.warning(f"Cannot close {pair}: position not found")
            return None

        position = self.positions[pair]

        # Get current market price
        market_price = self.price_fetcher.get_price(pair)
        if market_price is None:
            logger.error(f"Cannot close {pair}: price not available")
            return None

        # Execute closing order
        result = self.executor.execute_order(
            pair=pair,
            direction=position.direction,
            action='CLOSE',
            market_price=market_price,
            usd_value=position.current_size_usd
        )

        if not result.success:
            logger.error(f"Failed to close {pair}: {result.error_message}")
            return None

        # Calculate realized P&L
        realized_pnl = self.executor.calculate_pnl(
            direction=position.direction,
            entry_price=position.entry_price,
            exit_price=result.execution_price,
            quantity=position.quantity
        )

        # Update totals
        self.total_pnl += realized_pnl
        self.total_fees_paid += result.fees

        # Log to database
        self.db.log_trade(
            pair=pair,
            direction=position.direction,
            action='CLOSE',
            price=result.execution_price,
            quantity=result.quantity,
            usd_value=position.current_size_usd,
            fees=result.fees,
            slippage=result.slippage,
            reason=reason,
            pnl=realized_pnl
        )

        # Remove position
        self.db.delete_position(pair)
        del self.positions[pair]

        logger.info(f"Closed {position.direction} position in {pair}: "
                   f"P&L=${realized_pnl:,.2f} ({realized_pnl/position.entry_size_usd*100:.2f}%)")

        return realized_pnl

    def adjust_position(self, pair: str, target_usd: float, signal_confidence: float,
                       reason: str = "rebalance") -> bool:
        """
        Adjust an existing position to a target size.

        Returns:
            True if successful
        """
        if pair not in self.positions:
            logger.error(f"Cannot adjust {pair}: position not found")
            return False

        position = self.positions[pair]
        current_usd = position.current_size_usd
        delta = target_usd - current_usd

        if abs(delta) < 100:  # Ignore tiny adjustments
            return True

        # Get current market price
        market_price = self.price_fetcher.get_price(pair)
        if market_price is None:
            logger.error(f"Cannot adjust {pair}: price not available")
            return False

        # Determine action
        action = 'INCREASE' if delta > 0 else 'DECREASE'

        # Execute adjustment order
        result = self.executor.execute_order(
            pair=pair,
            direction=position.direction,
            action=action,
            market_price=market_price,
            usd_value=abs(delta)
        )

        if not result.success:
            logger.error(f"Failed to adjust {pair}: {result.error_message}")
            return False

        # Update position
        if action == 'INCREASE':
            # Recalculate average entry price
            total_cost = (position.entry_price * position.quantity +
                         result.execution_price * result.quantity)
            position.quantity += result.quantity
            position.entry_price = total_cost / position.quantity
            position.entry_size_usd += abs(delta)
        else:  # DECREASE
            position.quantity -= result.quantity
            position.entry_size_usd -= abs(delta)

        position.total_fees_paid += result.fees
        position.update_price(market_price)

        # Update totals
        self.total_fees_paid += result.fees

        # Log to database
        self.db.log_trade(
            pair=pair,
            direction=position.direction,
            action=action,
            price=result.execution_price,
            quantity=result.quantity,
            usd_value=abs(delta),
            fees=result.fees,
            slippage=result.slippage,
            signal_confidence=signal_confidence,
            reason=reason
        )

        self.db.upsert_position(
            pair=pair,
            direction=position.direction,
            entry_price=position.entry_price,
            current_price=market_price,
            entry_size_usd=position.entry_size_usd,
            current_size_usd=position.current_size_usd,
            quantity=position.quantity,
            entry_timestamp=position.entry_timestamp,
            unrealized_pnl=position.unrealized_pnl,
            unrealized_pnl_pct=position.unrealized_pnl_pct,
            signal_confidence=signal_confidence,
            total_fees_paid=position.total_fees_paid
        )

        logger.info(f"Adjusted {pair} position: {action} ${abs(delta):,.2f}")
        return True

    def update_prices(self):
        """Update all positions with current market prices."""
        pairs = list(self.positions.keys())
        if not pairs:
            return

        prices = self.price_fetcher.get_prices_for_pairs(pairs)

        for pair, position in self.positions.items():
            if pair in prices:
                position.update_price(prices[pair])

                # Update database
                self.db.update_position_price(
                    pair=pair,
                    current_price=prices[pair],
                    current_size_usd=position.current_size_usd,
                    unrealized_pnl=position.unrealized_pnl,
                    unrealized_pnl_pct=position.unrealized_pnl_pct
                )

    def calculate_portfolio_value(self) -> float:
        """Calculate total portfolio value (mark-to-market)."""
        if self.positions:
            # Sum all position values
            total = sum(pos.current_size_usd for pos in self.positions.values())
        else:
            # No positions - maintain starting capital minus fees
            total = self.starting_capital + self.total_pnl - self.total_fees_paid

        self.total_equity = total
        return total

    def get_positions_summary(self) -> Dict:
        """Get summary of all positions."""
        return {
            pair: position.to_dict()
            for pair, position in self.positions.items()
        }

    def get_current_allocations(self) -> Dict[str, float]:
        """Get current USD value of each position."""
        return {
            pair: position.current_size_usd
            for pair, position in self.positions.items()
        }

    def save_state(self):
        """Save current portfolio state to database."""
        self.calculate_portfolio_value()

        return_pct = ((self.total_equity - self.starting_capital) /
                     self.starting_capital * 100)

        self.db.save_portfolio_state(
            equity=self.total_equity,
            cash=0.0,  # Always fully invested
            pnl=self.total_pnl,
            return_pct=return_pct,
            num_positions=len(self.positions),
            total_fees=self.total_fees_paid
        )
