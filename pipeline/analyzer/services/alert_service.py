"""
Alert service for notifying about exceptionally bad traders.

Supports multiple alert channels: console, log file, and dashboard.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional
from collections import deque

from ..core.statistics import TraderMetrics, TraderComparator


logger = logging.getLogger(__name__)


class Alert:
    """Represents a trader alert."""

    def __init__(self, address: str, metrics: TraderMetrics, timezone: str = "Europe/Rome"):
        """
        Create a new alert.

        Args:
            address: Trader's Ethereum address
            metrics: TraderMetrics with analysis results
            timezone: Timezone for timestamp (default: Europe/Rome)
        """
        self.address = address
        self.metrics = metrics
        self.timestamp = datetime.now(ZoneInfo(timezone))

    def to_dict(self) -> dict:
        """Convert alert to dictionary for serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'address': self.address,
            'score': self.metrics.score,
            'total_pnl': self.metrics.total_pnl,
            'mean_pnl_per_trade': self.metrics.mean_pnl_per_trade,
            'p_value': self.metrics.p_value,
            'num_trades': self.metrics.num_trades,
            'win_rate': self.metrics.win_rate,
            'expected_value': self.metrics.expected_value,
            'sharpe_ratio': self.metrics.sharpe_ratio,
            'alert_reason': 'score_below_threshold'
        }


class AlertService:
    """
    Manages alerts for exceptionally bad traders.

    Triggers alerts when traders are performing significantly worse
    than random chance (score < threshold and p < 0.01).
    """

    def __init__(
        self,
        score_threshold: int = 5,
        console_enabled: bool = True,
        log_file_enabled: bool = True,
        log_file_path: Optional[str] = None,
        dashboard_enabled: bool = True,
        timezone: str = "Europe/Rome"
    ):
        """
        Initialize alert service.

        Args:
            score_threshold: Score below which to trigger alerts
            console_enabled: Enable console alerts
            log_file_enabled: Enable log file alerts
            log_file_path: Path to alert log file
            dashboard_enabled: Enable dashboard alerts
            timezone: Timezone for timestamps (default: Europe/Rome)
        """
        self.score_threshold = score_threshold
        self.console_enabled = console_enabled
        self.log_file_enabled = log_file_enabled
        self.log_file_path = Path(log_file_path) if log_file_path else None
        self.dashboard_enabled = dashboard_enabled
        self.timezone = timezone

        # Recent alerts for dashboard (keep last 100)
        self.recent_alerts: deque = deque(maxlen=100)

        # Initialize log file
        if self.log_file_enabled and self.log_file_path:
            self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Alert log file: {self.log_file_path}")

    def should_alert(self, metrics: TraderMetrics) -> bool:
        """
        Determine if metrics warrant an alert.

        Args:
            metrics: TraderMetrics to evaluate

        Returns:
            True if alert should be triggered
        """
        return (
            metrics.score <= self.score_threshold and
            metrics.is_statistically_bad and
            metrics.num_trades >= 50  # Extra confidence requirement
        )

    async def trigger_alert(self, address: str, metrics: TraderMetrics):
        """
        Trigger alert for an exceptionally bad trader.

        Args:
            address: Trader's Ethereum address
            metrics: TraderMetrics with analysis results
        """
        if not self.should_alert(metrics):
            return

        alert = Alert(address, metrics, timezone=self.timezone)

        # Store for dashboard
        if self.dashboard_enabled:
            self.recent_alerts.append(alert)

        # Console alert
        if self.console_enabled:
            self._console_alert(alert)

        # Log file alert
        if self.log_file_enabled and self.log_file_path:
            await self._log_file_alert(alert)

        logger.info(
            f"Alert triggered for {self._shorten_address(address)} "
            f"(score: {metrics.score})"
        )

    def _console_alert(self, alert: Alert):
        """Print alert to console with formatting."""
        category = TraderComparator.get_performance_category(alert.metrics.score)

        print("\n" + "=" * 60)
        print("🚨 ALERT: Exceptionally Bad Trader Detected!")
        print("=" * 60)
        print(f"Timestamp:     {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Address:       {alert.address}")
        print(f"Score:         {alert.metrics.score}/100")
        print(f"Category:      {category}")
        print()
        print("Performance Metrics:")
        print(f"  Total PnL:       ${alert.metrics.total_pnl:,.2f}")
        print(f"  Avg per trade:   ${alert.metrics.mean_pnl_per_trade:,.2f}")
        print(f"  Std Dev:         ${alert.metrics.std_dev:,.2f}")
        print()
        print("Statistical Analysis:")
        print(f"  P-Value:         {alert.metrics.p_value:.6f}")
        print(f"  T-Statistic:     {alert.metrics.t_statistic:.4f}")
        print(f"  Sharpe Ratio:    {alert.metrics.sharpe_ratio:.4f}")
        print(f"  Monte Carlo %:   {alert.metrics.monte_carlo_percentile:.2f}")
        print()
        print("Trade Statistics:")
        print(f"  Total Trades:    {alert.metrics.num_trades}")
        print(f"  Win Rate:        {alert.metrics.win_rate*100:.1f}%")
        print(f"  Avg Win:         ${alert.metrics.avg_win:,.2f}")
        print(f"  Avg Loss:        ${alert.metrics.avg_loss:,.2f}")
        print(f"  Expected Value:  ${alert.metrics.expected_value:,.2f}")
        print()
        print("⚠️  This trader is performing significantly worse than random chance.")
        print("=" * 60 + "\n")

    async def _log_file_alert(self, alert: Alert):
        """Append alert to log file in JSON format."""
        try:
            # Append as JSON line
            with open(self.log_file_path, 'a') as f:
                f.write(json.dumps(alert.to_dict()) + '\n')

        except Exception as e:
            logger.error(f"Failed to write alert to log file: {e}")

    def get_recent_alerts(self, limit: Optional[int] = None) -> List[Alert]:
        """
        Get recent alerts for dashboard.

        Args:
            limit: Maximum number of alerts to return

        Returns:
            List of Alert objects (newest first)
        """
        alerts = list(self.recent_alerts)
        alerts.reverse()  # Newest first

        if limit:
            alerts = alerts[:limit]

        return alerts

    def get_alert_count(self) -> int:
        """Get total number of recent alerts."""
        return len(self.recent_alerts)

    def clear_alerts(self):
        """Clear all recent alerts."""
        self.recent_alerts.clear()

    def _shorten_address(self, address: str) -> str:
        """Shorten address for logging."""
        if len(address) > 10:
            return f"{address[:6]}...{address[-4:]}"
        return address


class AlertStats:
    """Statistics about alerts for monitoring."""

    def __init__(self):
        """Initialize alert statistics."""
        self.total_alerts = 0
        self.alerts_by_hour = {}
        self.worst_score = 100
        self.worst_address = None

    def record_alert(self, alert: Alert):
        """
        Record an alert for statistics.

        Args:
            alert: Alert object
        """
        self.total_alerts += 1

        # Track alerts by hour
        hour_key = alert.timestamp.strftime('%Y-%m-%d %H:00')
        self.alerts_by_hour[hour_key] = self.alerts_by_hour.get(hour_key, 0) + 1

        # Track worst trader
        if alert.metrics.score < self.worst_score:
            self.worst_score = alert.metrics.score
            self.worst_address = alert.address

    def get_hourly_rate(self) -> float:
        """Get average alerts per hour."""
        if not self.alerts_by_hour:
            return 0.0

        return sum(self.alerts_by_hour.values()) / len(self.alerts_by_hour)

    def to_dict(self) -> dict:
        """Convert statistics to dictionary."""
        return {
            'total_alerts': self.total_alerts,
            'hourly_rate': self.get_hourly_rate(),
            'worst_score': self.worst_score,
            'worst_address': self.worst_address,
            'hours_tracked': len(self.alerts_by_hour)
        }


def format_alert_summary(alerts: List[Alert]) -> str:
    """
    Format a summary of multiple alerts.

    Args:
        alerts: List of Alert objects

    Returns:
        Formatted string summary
    """
    if not alerts:
        return "No alerts to display."

    output = []
    output.append(f"\n{'=' * 60}")
    output.append(f"Alert Summary: {len(alerts)} Bad Traders Detected")
    output.append(f"{'=' * 60}\n")

    for i, alert in enumerate(alerts, 1):
        output.append(f"{i}. {alert.address}")
        output.append(f"   Score: {alert.metrics.score}/100")
        output.append(f"   Total PnL: ${alert.metrics.total_pnl:,.2f}")
        output.append(f"   Trades: {alert.metrics.num_trades}")
        output.append(f"   Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        output.append("")

    return "\n".join(output)
