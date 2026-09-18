"""
Performance metrics calculations for the trading simulator.
Calculates Sharpe ratio, max drawdown, win rate, and other metrics.
"""

import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from database import SimulatorDatabase
import logging

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Tracks and calculates portfolio performance metrics."""

    def __init__(self, db: SimulatorDatabase, starting_capital: float = 100000):
        self.db = db
        self.starting_capital = starting_capital
        logger.info("Performance tracker initialized")

    def calculate_sharpe_ratio(self, periods: int = None) -> Optional[float]:
        """
        Calculate Sharpe ratio using portfolio equity variations.

        Args:
            periods: Number of periods to look back (default None = all history)

        Returns:
            Sharpe ratio or None if insufficient data
        """
        try:
            equity_curve = self.db.get_equity_curve()

            if len(equity_curve) < 2:
                return None

            # Calculate returns based on equity variations
            returns = []
            for i in range(1, len(equity_curve)):
                prev_value = equity_curve[i-1][1]
                curr_value = equity_curve[i][1]
                if prev_value > 0:
                    period_return = (curr_value - prev_value) / prev_value
                    returns.append(period_return)

            if len(returns) < 2:
                logger.debug(f"Insufficient data for Sharpe ratio: {len(returns)} < 2")
                return None

            # Use all returns or limit to recent periods if specified
            if periods is not None and len(returns) > periods:
                returns_to_use = returns[-periods:]
            else:
                returns_to_use = returns

            mean_return = np.mean(returns_to_use)
            std_return = np.std(returns_to_use, ddof=1)

            if std_return == 0:
                return 0.0

            # Calculate Sharpe ratio (not annualized) assuming risk-free rate of 10%
            sharpe = (mean_return - 0.1)/ std_return

            period_text = f"{len(returns_to_use)}-period" if periods else "all history"
            logger.debug(f"Sharpe ratio: {sharpe:.4f} ({period_text})")
            return sharpe

        except Exception as e:
            logger.error(f"Error calculating Sharpe ratio: {e}")
            return None

    def calculate_max_drawdown(self) -> float:
        """
        Calculate maximum drawdown from peak equity.

        Returns:
            Max drawdown as percentage (e.g., 0.05 = 5% drawdown)
        """
        try:
            equity_curve = self.db.get_equity_curve()

            if len(equity_curve) < 2:
                return 0.0

            equity_values = [val for _, val in equity_curve]
            peak = equity_values[0]
            max_dd = 0.0

            for value in equity_values:
                if value > peak:
                    peak = value

                dd = (peak - value) / peak if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd

            logger.debug(f"Max drawdown: {max_dd*100:.2f}%")
            return max_dd

        except Exception as e:
            logger.error(f"Error calculating max drawdown: {e}")
            return 0.0

    def calculate_win_rate(self) -> float:
        """
        Calculate win rate from closed trades.

        Returns:
            Win rate as decimal (e.g., 0.583 = 58.3%)
        """
        try:
            closed_trades = self.db.get_closed_trades()

            if not closed_trades:
                return 0.0

            wins = sum(1 for trade in closed_trades if trade['pnl'] and trade['pnl'] > 0)
            total = len(closed_trades)

            win_rate = wins / total if total > 0 else 0.0

            logger.debug(f"Win rate: {win_rate*100:.1f}% ({wins}/{total})")
            return win_rate

        except Exception as e:
            logger.error(f"Error calculating win rate: {e}")
            return 0.0

    def calculate_avg_win_loss(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Calculate average win and average loss from closed trades.

        Returns:
            (avg_win, avg_loss) or (None, None) if no data
        """
        try:
            closed_trades = self.db.get_closed_trades()

            if not closed_trades:
                return None, None

            wins = [trade['pnl'] for trade in closed_trades if trade['pnl'] and trade['pnl'] > 0]
            losses = [trade['pnl'] for trade in closed_trades if trade['pnl'] and trade['pnl'] < 0]

            avg_win = np.mean(wins) if wins else None
            avg_loss = np.mean(losses) if losses else None

            if avg_win:
                logger.debug(f"Avg win: ${avg_win:,.2f}")
            if avg_loss:
                logger.debug(f"Avg loss: ${avg_loss:,.2f}")

            return avg_win, avg_loss

        except Exception as e:
            logger.error(f"Error calculating avg win/loss: {e}")
            return None, None

    def calculate_profit_factor(self) -> Optional[float]:
        """
        Calculate profit factor (total wins / total losses).

        Returns:
            Profit factor or None if no losses
        """
        try:
            closed_trades = self.db.get_closed_trades()

            if not closed_trades:
                return None

            total_wins = sum(trade['pnl'] for trade in closed_trades
                           if trade['pnl'] and trade['pnl'] > 0)
            total_losses = abs(sum(trade['pnl'] for trade in closed_trades
                                  if trade['pnl'] and trade['pnl'] < 0))

            if total_losses == 0:
                # Return None instead of infinity for JSON compatibility
                return None

            profit_factor = total_wins / total_losses

            logger.debug(f"Profit factor: {profit_factor:.2f}")
            return profit_factor

        except Exception as e:
            logger.error(f"Error calculating profit factor: {e}")
            return None

    def calculate_all_metrics(self, current_equity: float,
                             total_pnl: float) -> Dict:
        """
        Calculate all performance metrics.

        Args:
            current_equity: Current portfolio value
            total_pnl: Total realized + unrealized P&L

        Returns:
            Dict with all metrics
        """
        return_pct = ((current_equity - self.starting_capital) /
                     self.starting_capital * 100)

        sharpe_ratio = self.calculate_sharpe_ratio()  # Uses all history
        max_drawdown = self.calculate_max_drawdown()
        win_rate = self.calculate_win_rate()
        avg_win, avg_loss = self.calculate_avg_win_loss()
        profit_factor = self.calculate_profit_factor()

        num_trades = self.db.get_trade_count()

        metrics = {
            'total_equity': current_equity,
            'total_pnl': total_pnl,
            'total_return_pct': return_pct,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown * 100,  # Convert to percentage
            'win_rate': win_rate * 100,  # Convert to percentage
            'num_trades': num_trades,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor
        }

        sharpe_str = f"{sharpe_ratio:.2f}" if sharpe_ratio is not None else 'N/A'
        logger.info(f"Performance metrics calculated: equity=${current_equity:,.2f}, "
                   f"return={return_pct:.2f}%, sharpe={sharpe_str}, "
                   f"max_dd={max_drawdown*100:.2f}%, win_rate={win_rate*100:.1f}%")

        return metrics

    def save_performance_snapshot(self, current_equity: float, total_pnl: float):
        """
        Calculate and save performance snapshot to database.

        Args:
            current_equity: Current portfolio value
            total_pnl: Total realized + unrealized P&L
        """
        try:
            metrics = self.calculate_all_metrics(current_equity, total_pnl)

            self.db.save_performance_snapshot(
                equity=current_equity,
                pnl=total_pnl,
                return_pct=metrics['total_return_pct'],
                sharpe_ratio=metrics['sharpe_ratio'],
                max_drawdown=metrics['max_drawdown'],
                win_rate=metrics['win_rate'],
                num_trades=metrics['num_trades'],
                avg_win=metrics['avg_win'],
                avg_loss=metrics['avg_loss']
            )

            logger.debug("Performance snapshot saved to database")

        except Exception as e:
            logger.error(f"Error saving performance snapshot: {e}")

    def get_equity_curve_for_chart(self) -> List[Dict]:
        """
        Get equity curve formatted for charting.

        Returns:
            List of {timestamp, equity} dicts
        """
        try:
            equity_curve = self.db.get_equity_curve()
            return [
                {
                    'timestamp': timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
                    'equity': equity
                }
                for timestamp, equity in equity_curve
            ]
        except Exception as e:
            logger.error(f"Error getting equity curve: {e}")
            return []

    def get_performance_summary(self) -> Dict:
        """Get latest performance summary from database."""
        try:
            latest = self.db.get_latest_performance()
            if latest:
                return dict(latest)
            return {}
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}")
            return {}
