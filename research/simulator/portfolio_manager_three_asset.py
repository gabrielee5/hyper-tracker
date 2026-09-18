"""
Portfolio manager for Three-Asset Strategy with explicit cash tracking.

This extends the base PortfolioManager to properly track uninvested cash,
which is important for the three-asset strategy where cash reserves are expected.
"""

from typing import Dict, Optional
from datetime import datetime
from database import SimulatorDatabase
from order_executor import OrderExecutor
from price_fetcher import PriceFetcher
from portfolio_manager import PortfolioManager, Position
import logging

logger = logging.getLogger(__name__)


class PortfolioManagerThreeAsset(PortfolioManager):
    """
    Portfolio manager with explicit cash tracking.

    Maintains:
    - Cash balance (money not invested in positions)
    - Positions (money currently in trades)
    - Total equity = cash + positions value
    """

    def __init__(self, db: SimulatorDatabase, executor: OrderExecutor,
                 price_fetcher: PriceFetcher, starting_capital: float = 100000):
        """Initialize portfolio manager with cash tracking."""
        # Initialize base class
        super().__init__(db, executor, price_fetcher, starting_capital)

        # Track cash explicitly
        self.cash = starting_capital

        # Restore cash from database if available
        self._restore_cash()

        logger.info(f"Three-Asset Portfolio Manager initialized")
        logger.info(f"Starting capital: ${starting_capital:,.2f}")
        logger.info(f"Initial cash: ${self.cash:,.2f}")

    def _restore_cash(self):
        """Restore cash balance from database."""
        try:
            # Calculate cash based on starting capital minus what's been deployed
            deployed_capital = sum(pos.entry_size_usd for pos in self.positions.values())

            # Cash = starting capital - deployed capital + realized PnL - fees
            self.cash = self.starting_capital - deployed_capital + self.total_pnl - self.total_fees_paid

            logger.info(f"Restored cash balance: ${self.cash:,.2f}")
            logger.info(f"  Starting capital: ${self.starting_capital:,.2f}")
            logger.info(f"  Deployed in positions: ${deployed_capital:,.2f}")
            logger.info(f"  Realized PnL: ${self.total_pnl:,.2f}")
            logger.info(f"  Total fees: ${self.total_fees_paid:,.2f}")

        except Exception as e:
            logger.warning(f"Could not restore cash balance: {e}")
            self.cash = self.starting_capital

    def open_position(self, pair: str, direction: str, usd_value: float,
                     signal_confidence: float, reason: str = "new_signal") -> bool:
        """
        Open a new position and deduct from cash.

        Returns:
            True if successful
        """
        # Check if we have enough cash
        if usd_value > self.cash:
            logger.warning(f"Insufficient cash for {pair}: need ${usd_value:,.2f}, have ${self.cash:,.2f}")
            # Allow small rounding differences
            if usd_value - self.cash > 10:
                return False
            # Adjust to available cash
            usd_value = self.cash

        # Call parent's open_position
        success = super().open_position(pair, direction, usd_value, signal_confidence, reason)

        if success:
            # Deduct from cash (including fees)
            position = self.positions[pair]
            self.cash -= (usd_value + position.total_fees_paid)
            logger.info(f"Cash after opening {pair}: ${self.cash:,.2f}")

        return success

    def close_position(self, pair: str, reason: str = "signal_removed") -> Optional[float]:
        """
        Close an existing position and add proceeds to cash.

        Returns:
            Realized P&L or None if failed
        """
        if pair not in self.positions:
            return None

        position = self.positions[pair]
        entry_size = position.entry_size_usd

        # Call parent's close_position
        realized_pnl = super().close_position(pair, reason)

        if realized_pnl is not None:
            # Add proceeds back to cash
            # Proceeds = entry size + realized PnL - fees paid on close
            # (fees on close are already included in total_fees_paid)
            proceeds = entry_size + realized_pnl
            self.cash += proceeds
            logger.info(f"Cash after closing {pair}: ${self.cash:,.2f} (proceeds: ${proceeds:,.2f})")

        return realized_pnl

    def adjust_position(self, pair: str, target_usd: float, signal_confidence: float,
                       reason: str = "rebalance") -> bool:
        """
        Adjust an existing position and update cash accordingly.

        Returns:
            True if successful
        """
        if pair not in self.positions:
            return False

        position = self.positions[pair]
        current_usd = position.current_size_usd
        delta = target_usd - current_usd

        # For INCREASE, check if we have enough cash
        if delta > 0 and abs(delta) > self.cash:
            logger.warning(f"Insufficient cash to increase {pair}: need ${abs(delta):,.2f}, have ${self.cash:,.2f}")
            if abs(delta) - self.cash > 10:
                return False

        # Track fees before adjustment
        fees_before = position.total_fees_paid

        # Call parent's adjust_position
        success = super().adjust_position(pair, target_usd, signal_confidence, reason)

        if success:
            # Update cash based on adjustment
            fees_incurred = position.total_fees_paid - fees_before

            if delta > 0:
                # INCREASE - deduct from cash
                self.cash -= (abs(delta) + fees_incurred)
            else:
                # DECREASE - add to cash
                self.cash += (abs(delta) - fees_incurred)

            logger.info(f"Cash after adjusting {pair}: ${self.cash:,.2f}")

        return success

    def calculate_portfolio_value(self) -> float:
        """
        Calculate total portfolio value including cash.

        Total Equity = Cash + Sum of all position values (mark-to-market)
        """
        # Sum all position values (mark-to-market)
        positions_value = sum(pos.current_size_usd for pos in self.positions.values())

        # Total equity = cash + positions
        self.total_equity = self.cash + positions_value

        return self.total_equity

    def get_cash_balance(self) -> float:
        """Get current cash balance."""
        return self.cash

    def get_positions_value(self) -> float:
        """Get total value of all positions."""
        return sum(pos.current_size_usd for pos in self.positions.values())

    def save_state(self):
        """Save current portfolio state to database."""
        self.calculate_portfolio_value()

        positions_value = self.get_positions_value()

        return_pct = ((self.total_equity - self.starting_capital) /
                     self.starting_capital * 100)

        self.db.save_portfolio_state(
            equity=self.total_equity,
            cash=self.cash,  # Now we track real cash
            pnl=self.total_pnl,
            return_pct=return_pct,
            num_positions=len(self.positions),
            total_fees=self.total_fees_paid
        )

        logger.debug(f"Portfolio state saved: equity=${self.total_equity:,.2f}, "
                    f"cash=${self.cash:,.2f}, positions=${positions_value:,.2f}")

    def get_portfolio_summary(self) -> Dict:
        """Get detailed portfolio summary including cash breakdown."""
        positions_value = self.get_positions_value()

        return {
            'total_equity': self.total_equity,
            'cash': self.cash,
            'cash_pct': (self.cash / self.total_equity * 100) if self.total_equity > 0 else 0,
            'positions_value': positions_value,
            'positions_pct': (positions_value / self.total_equity * 100) if self.total_equity > 0 else 0,
            'num_positions': len(self.positions),
            'total_pnl': self.total_pnl,
            'total_fees_paid': self.total_fees_paid,
            'return_pct': ((self.total_equity - self.starting_capital) /
                          self.starting_capital * 100) if self.starting_capital > 0 else 0
        }
