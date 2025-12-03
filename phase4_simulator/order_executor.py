"""
Order executor with simulated fees and slippage.
Simulates trade execution without actual orders to Hyperliquid.
"""

from typing import Dict, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a simulated trade execution."""
    pair: str
    direction: str  # 'LONG' or 'SHORT'
    action: str  # 'OPEN', 'CLOSE', 'INCREASE', 'DECREASE'
    market_price: float
    execution_price: float
    quantity: float
    usd_value: float
    fees: float
    slippage: float
    success: bool
    error_message: Optional[str] = None


class OrderExecutor:
    """Simulates order execution with realistic fees and slippage."""

    def __init__(self, maker_fee: float = 0.0002, taker_fee: float = 0.0005,
                 slippage_config: Dict = None):
        """
        Initialize order executor.

        Args:
            maker_fee: Maker fee rate (default 0.0002 = 0.02%)
            taker_fee: Taker fee rate (default 0.0005 = 0.05%)
            slippage_config: Slippage model configuration
        """
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee  # Using taker fees for market orders

        # Slippage model
        if slippage_config is None:
            slippage_config = {
                'type': 'linear',
                'base_bps': 0,
                'size_impact': 0.00001
            }
        self.slippage_config = slippage_config

        logger.info(f"Order executor initialized (taker_fee={taker_fee*100:.2f}%)")

    def calculate_slippage(self, position_size_usd: float) -> float:
        """
        Calculate slippage based on position size.

        Model:
        - $10k = 0.1 bps (0.00001)
        - $100k = 1 bps (0.0001)
        - $1M = 5 bps (0.0005) - capped

        Args:
            position_size_usd: Size of position in USD

        Returns:
            Slippage rate as decimal (e.g., 0.0001 = 0.01% = 1 bps)
        """
        if self.slippage_config['type'] == 'linear':
            # Linear model: slippage_bps = position_size / 100000 * 1
            slippage_bps = min(5, position_size_usd / 100000 * 1)
            slippage = slippage_bps / 10000  # Convert bps to decimal
            return slippage

        return 0.0  # Default no slippage

    def execute_order(self, pair: str, direction: str, action: str,
                     market_price: float, usd_value: float) -> ExecutionResult:
        """
        Simulate order execution.

        Args:
            pair: Trading pair (e.g., 'BTC')
            direction: 'LONG' or 'SHORT'
            action: 'OPEN', 'CLOSE', 'INCREASE', 'DECREASE'
            market_price: Current market price
            usd_value: Target USD value of the order

        Returns:
            ExecutionResult with execution details
        """
        try:
            # Calculate slippage
            slippage = self.calculate_slippage(usd_value)

            # Calculate fees
            fees = usd_value * self.taker_fee

            # Calculate execution price
            if direction == 'LONG':
                # Buying: pay slippage and fees
                execution_price = market_price * (1 + slippage + self.taker_fee)
            else:  # SHORT
                # Selling: receive less due to slippage and fees
                execution_price = market_price * (1 - slippage - self.taker_fee)

            # Calculate quantity
            # For simplicity, quantity is based on market price
            quantity = usd_value / market_price

            logger.info(f"Executed {action} {direction} {pair}: "
                       f"${usd_value:,.2f} @ ${execution_price:.2f} "
                       f"(market=${market_price:.2f}, qty={quantity:.6f}, "
                       f"fees=${fees:.2f}, slippage={slippage*10000:.2f}bps)")

            return ExecutionResult(
                pair=pair,
                direction=direction,
                action=action,
                market_price=market_price,
                execution_price=execution_price,
                quantity=quantity,
                usd_value=usd_value,
                fees=fees,
                slippage=slippage,
                success=True
            )

        except Exception as e:
            error_msg = f"Error executing order: {e}"
            logger.error(error_msg)
            return ExecutionResult(
                pair=pair,
                direction=direction,
                action=action,
                market_price=market_price,
                execution_price=0,
                quantity=0,
                usd_value=usd_value,
                fees=0,
                slippage=0,
                success=False,
                error_message=error_msg
            )

    def calculate_pnl(self, direction: str, entry_price: float,
                     exit_price: float, quantity: float) -> float:
        """
        Calculate P&L for a closed position.

        Args:
            direction: 'LONG' or 'SHORT'
            entry_price: Entry execution price
            exit_price: Exit execution price
            quantity: Position size in base asset

        Returns:
            P&L in USD
        """
        if direction == 'LONG':
            # Long P&L = (exit_price - entry_price) * quantity
            pnl = (exit_price - entry_price) * quantity
        else:  # SHORT
            # Short P&L = (entry_price - exit_price) * quantity
            pnl = (entry_price - exit_price) * quantity

        return pnl

    def calculate_unrealized_pnl(self, direction: str, entry_price: float,
                                 current_price: float, quantity: float) -> float:
        """
        Calculate unrealized P&L for an open position.

        Args:
            direction: 'LONG' or 'SHORT'
            entry_price: Entry execution price
            current_price: Current market price
            quantity: Position size in base asset

        Returns:
            Unrealized P&L in USD
        """
        return self.calculate_pnl(direction, entry_price, current_price, quantity)

    def calculate_position_value(self, direction: str, entry_price: float,
                                current_price: float, entry_size_usd: float,
                                quantity: float) -> float:
        """
        Calculate current USD value of a position (including unrealized P&L).

        Args:
            direction: 'LONG' or 'SHORT'
            entry_price: Entry execution price
            current_price: Current market price
            entry_size_usd: Initial USD value at entry
            quantity: Position size in base asset

        Returns:
            Current position value in USD
        """
        unrealized_pnl = self.calculate_unrealized_pnl(
            direction, entry_price, current_price, quantity
        )
        return entry_size_usd + unrealized_pnl

    def validate_order(self, pair: str, market_price: float,
                      usd_value: float, min_trade_size: float = 100) -> tuple:
        """
        Validate order parameters.

        Returns:
            (is_valid: bool, error_message: Optional[str])
        """
        if market_price <= 0:
            return False, f"Invalid market price: {market_price}"

        if usd_value < min_trade_size:
            return False, f"Order size ${usd_value:.2f} below minimum ${min_trade_size:.2f}"

        if not pair:
            return False, "Pair name is required"

        return True, None
