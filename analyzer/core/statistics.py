"""
Statistical analysis engine for trader performance evaluation.

This module implements rigorous statistical methods to determine if a trader
is performing significantly worse (or better) than random chance.
"""

import numpy as np
from scipy import stats
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class TraderMetrics:
    """Complete statistical analysis of a trader's performance."""

    # Basic statistics
    total_pnl: float
    mean_pnl_per_trade: float
    std_dev: float
    num_trades: int

    # Win/Loss analysis
    win_rate: float
    avg_win: float
    avg_loss: float

    # Statistical measures
    expected_value: float
    sharpe_ratio: float
    t_statistic: float
    p_value: float
    monte_carlo_percentile: float

    # Final score
    score: int  # 0-100
    is_statistically_bad: bool


class StatisticalAnalyzer:
    """
    Analyzes trader performance using multiple statistical methods.

    The scoring system:
    - 0-5: Significantly worse than random (p < 0.01)
    - 5-15: Probably worse than random (p < 0.05)
    - 15-40: Below average but not significant
    - 40-60: Random performance (no edge)
    - 60-85: Above average but not significant
    - 85-95: Probably better than random (p < 0.05)
    - 95-100: Significantly better than random (p < 0.01)
    """

    def __init__(self, min_trades: int = 30, p_value_threshold: float = 0.01,
                 monte_carlo_iterations: int = 1000):
        """
        Initialize the statistical analyzer.

        Args:
            min_trades: Minimum number of trades required for analysis
            p_value_threshold: Threshold for statistical significance
            monte_carlo_iterations: Number of Monte Carlo simulations
        """
        self.min_trades = min_trades
        self.p_value_threshold = p_value_threshold
        self.monte_carlo_iterations = monte_carlo_iterations

    def analyze_trader(self, fills: List[Dict]) -> Optional[TraderMetrics]:
        """
        Perform complete statistical analysis on a trader's fills.

        Args:
            fills: List of trade fills from Hyperliquid API
                   Each fill must have 'closedPnl' field

        Returns:
            TraderMetrics object with complete analysis, or None if insufficient data
        """
        if len(fills) < self.min_trades:
            return None

        # Extract PnL values from fills
        pnl_values = self._extract_pnl(fills)

        if len(pnl_values) < self.min_trades:
            return None

        # Calculate all metrics
        basic_stats = self._calculate_basic_statistics(pnl_values)
        win_loss_stats = self._calculate_win_loss_statistics(pnl_values)
        statistical_tests = self._perform_statistical_tests(pnl_values)
        monte_carlo_result = self._run_monte_carlo_simulation(pnl_values)

        # Calculate final score
        score = self._calculate_score(
            statistical_tests['t_statistic'],
            statistical_tests['p_value'],
            monte_carlo_result
        )

        return TraderMetrics(
            total_pnl=basic_stats['total_pnl'],
            mean_pnl_per_trade=basic_stats['mean_pnl'],
            std_dev=basic_stats['std_dev'],
            num_trades=len(pnl_values),
            win_rate=win_loss_stats['win_rate'],
            avg_win=win_loss_stats['avg_win'],
            avg_loss=win_loss_stats['avg_loss'],
            expected_value=win_loss_stats['expected_value'],
            sharpe_ratio=statistical_tests['sharpe_ratio'],
            t_statistic=statistical_tests['t_statistic'],
            p_value=statistical_tests['p_value'],
            monte_carlo_percentile=monte_carlo_result,
            score=score,
            is_statistically_bad=(score < 5 and statistical_tests['p_value'] < self.p_value_threshold)
        )

    def _extract_pnl(self, fills: List[Dict]) -> np.ndarray:
        """
        Extract PnL values from fills.

        Args:
            fills: List of fill dictionaries

        Returns:
            Numpy array of PnL values
        """
        pnl_values = []

        for fill in fills:
            # closedPnl is the realized PnL from the trade
            if 'closedPnl' in fill and fill['closedPnl'] is not None:
                try:
                    pnl = float(fill['closedPnl'])
                    pnl_values.append(pnl)
                except (ValueError, TypeError):
                    continue

        return np.array(pnl_values)

    def _calculate_basic_statistics(self, pnl_values: np.ndarray) -> Dict[str, float]:
        """Calculate basic statistical measures."""
        return {
            'total_pnl': float(np.sum(pnl_values)),
            'mean_pnl': float(np.mean(pnl_values)),
            'std_dev': float(np.std(pnl_values, ddof=1)),  # Sample std dev
            'median_pnl': float(np.median(pnl_values))
        }

    def _calculate_win_loss_statistics(self, pnl_values: np.ndarray) -> Dict[str, float]:
        """
        Calculate win rate, average win, average loss, and expected value.
        """
        wins = pnl_values[pnl_values > 0]
        losses = pnl_values[pnl_values < 0]

        num_wins = len(wins)
        num_losses = len(losses)
        total_trades = len(pnl_values)

        win_rate = num_wins / total_trades if total_trades > 0 else 0
        avg_win = float(np.mean(wins)) if num_wins > 0 else 0
        avg_loss = float(np.mean(losses)) if num_losses > 0 else 0

        # Expected Value = (Avg Win × Win%) - (|Avg Loss| × Loss%)
        expected_value = (avg_win * win_rate) - (abs(avg_loss) * (1 - win_rate))

        return {
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'expected_value': expected_value,
            'num_wins': num_wins,
            'num_losses': num_losses
        }

    def _perform_statistical_tests(self, pnl_values: np.ndarray) -> Dict[str, float]:
        """
        Perform statistical tests to determine if performance differs from zero.
        """
        # One-sample t-test against zero
        # H0: mean PnL = 0 (random performance)
        # H1: mean PnL ≠ 0 (significant edge/disadvantage)
        t_statistic, p_value = stats.ttest_1samp(pnl_values, 0)

        # Sharpe Ratio (risk-adjusted returns)
        # Annualized assuming ~250 trading days
        mean_pnl = np.mean(pnl_values)
        std_pnl = np.std(pnl_values, ddof=1)

        if std_pnl > 0:
            sharpe_ratio = (mean_pnl / std_pnl) * np.sqrt(250)
        else:
            sharpe_ratio = 0

        return {
            't_statistic': float(t_statistic),
            'p_value': float(p_value),
            'sharpe_ratio': float(sharpe_ratio)
        }

    def _run_monte_carlo_simulation(self, pnl_values: np.ndarray) -> float:
        """
        Run Monte Carlo simulation to compare trader against random performance.

        This simulates 1000 random traders who make the same number of trades,
        with each trade drawn from a distribution centered at 0 (truly random).

        Returns:
            Percentile rank (0-100) - what % of random traders did worse?
        """
        actual_mean_pnl = np.mean(pnl_values)
        num_trades = len(pnl_values)
        std_pnl = np.std(pnl_values, ddof=1)

        # Run simulations - each simulation draws from normal(0, std_pnl)
        # This represents a truly random trader with same volatility
        simulated_means = []
        for _ in range(self.monte_carlo_iterations):
            # Random trader: mean=0, same std dev
            random_trades = np.random.normal(0, std_pnl, num_trades)
            simulated_mean = np.mean(random_trades)
            simulated_means.append(simulated_mean)

        # Calculate percentile rank
        # If actual mean PnL = -50 and only 5% of simulations did worse,
        # then percentile = 5 (bottom 5th percentile)
        percentile = stats.percentileofscore(simulated_means, actual_mean_pnl)

        return float(percentile)

    def _calculate_score(self, t_statistic: float, p_value: float,
                        monte_carlo_percentile: float) -> int:
        """
        Calculate final score (0-100) combining statistical tests.

        The Monte Carlo percentile is the primary score, adjusted by
        statistical significance from the t-test using symmetric adjustments.

        Args:
            t_statistic: T-test statistic
            p_value: P-value from t-test
            monte_carlo_percentile: Percentile from Monte Carlo (0-100)

        Returns:
            Score from 0-100 where:
            - Lower scores indicate worse than random performance
            - 50 indicates random performance
            - Higher scores indicate better than random performance
        """
        # Start with Monte Carlo percentile as base score
        base_score = monte_carlo_percentile

        # Calculate distance from median (50)
        distance_from_50 = base_score - 50

        # Apply symmetric adjustments based on statistical significance
        # Only amplify if the result is already notably different from random (|distance| > 10)
        if abs(distance_from_50) > 10:
            if p_value < 0.01:  # Highly significant (99% confidence)
                # Amplify distance from 50 by 30%
                adjusted_distance = distance_from_50 * 1.3
            elif p_value < 0.05:  # Moderately significant (95% confidence)
                # Amplify distance from 50 by 15%
                adjusted_distance = distance_from_50 * 1.15
            else:
                # No amplification for non-significant results
                adjusted_distance = distance_from_50
        else:
            # Don't amplify scores close to 50 (random performance)
            # Even if statistically significant, they're practically random
            adjusted_distance = distance_from_50

        # Calculate final score
        final_score = 50 + adjusted_distance

        # Clip to valid range
        score = max(0, min(100, final_score))

        return int(round(score))


class TraderComparator:
    """Utility class for comparing traders and generating insights."""

    @staticmethod
    def compare_traders(trader1: TraderMetrics, trader2: TraderMetrics) -> Dict:
        """
        Compare two traders and provide insights.

        Returns:
            Dictionary with comparison metrics
        """
        return {
            'score_diff': trader1.score - trader2.score,
            'pnl_diff': trader1.total_pnl - trader2.total_pnl,
            'sharpe_diff': trader1.sharpe_ratio - trader2.sharpe_ratio,
            'better_trader': 1 if trader1.score > trader2.score else 2,
            'confidence': abs(trader1.p_value - trader2.p_value)
        }

    @staticmethod
    def get_performance_category(score: int) -> str:
        """Get human-readable performance category."""
        if score < 5:
            return "Exceptionally Bad (Significantly worse than random)"
        elif score < 15:
            return "Very Poor (Likely worse than random)"
        elif score < 40:
            return "Below Average"
        elif score < 60:
            return "Average (Random performance)"
        elif score < 85:
            return "Above Average"
        elif score < 95:
            return "Very Good (Likely better than random)"
        else:
            return "Exceptional (Significantly better than random)"

    @staticmethod
    def format_metrics_summary(metrics: TraderMetrics) -> str:
        """Format trader metrics as a readable summary."""
        category = TraderComparator.get_performance_category(metrics.score)

        return f"""
Trader Performance Summary
═══════════════════════════════════════════════
Score:           {metrics.score}/100
Category:        {category}

Performance Metrics:
  Total PnL:     ${metrics.total_pnl:,.2f}
  Avg per trade: ${metrics.mean_pnl_per_trade:,.2f}
  Std Dev:       ${metrics.std_dev:,.2f}

Statistical Analysis:
  P-Value:       {metrics.p_value:.6f}
  T-Statistic:   {metrics.t_statistic:.4f}
  Sharpe Ratio:  {metrics.sharpe_ratio:.4f}
  Monte Carlo %: {metrics.monte_carlo_percentile:.2f}

Trade Statistics:
  Total Trades:  {metrics.num_trades}
  Win Rate:      {metrics.win_rate*100:.1f}%
  Avg Win:       ${metrics.avg_win:,.2f}
  Avg Loss:      ${metrics.avg_loss:,.2f}
  Expected Val:  ${metrics.expected_value:,.2f}

Status: {'🚨 STATISTICALLY BAD' if metrics.is_statistically_bad else '✓ Normal'}
═══════════════════════════════════════════════
"""
