"""
Rich-based console dashboard for contrarian signals.

Beautiful, real-time terminal UI showing bad trader positioning and contrarian signals.
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional
from rich.console import Console
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import BarColumn, Progress, TextColumn
from rich import box


logger = logging.getLogger(__name__)


class ContrarianDashboard:
    """
    Live-updating console dashboard for contrarian signals.

    Displays:
    - Overall statistics
    - Signal breakdown by coin
    - Count-based and size-weighted metrics
    - Visual indicators for signal strength
    """

    def __init__(
        self,
        show_size_weighted: bool = True,
        top_signals_limit: int = 15,
        enable_colors: bool = True,
        priority_coins: List[str] = None
    ):
        """
        Initialize dashboard.

        Args:
            show_size_weighted: Show size-weighted metrics alongside count-based
            top_signals_limit: Maximum number of signals to display
            enable_colors: Enable colored output
            priority_coins: List of coin symbols to display first in the table
        """
        self.show_size_weighted = show_size_weighted
        self.top_signals_limit = top_signals_limit
        self.enable_colors = enable_colors
        self.priority_coins = priority_coins or []

        self.console = Console()

    def _sort_signals_with_priority(self, signals: List[Dict]) -> List[Dict]:
        """
        Sort signals with priority coins first, then by confidence.

        Args:
            signals: List of signal dictionaries

        Returns:
            Sorted list with priority coins at the top
        """
        if not self.priority_coins:
            return signals

        priority_signals = []
        other_signals = []

        for signal in signals:
            if signal['coin'] in self.priority_coins:
                priority_signals.append(signal)
            else:
                other_signals.append(signal)

        # Sort priority coins in the order specified in config
        priority_signals.sort(key=lambda s: self.priority_coins.index(s['coin']))

        # Combine: priority coins first, then all others sorted by confidence
        return priority_signals + other_signals

    def render(
        self,
        signals: List[Dict],
        bad_traders_count: int,
        traders_with_positions: int,
        last_update: datetime
    ) -> Layout:
        """
        Render complete dashboard layout.

        Args:
            signals: List of signal dictionaries
            bad_traders_count: Total number of bad traders analyzed
            traders_with_positions: Number of traders with open positions
            last_update: Timestamp of last update

        Returns:
            Rich Layout object
        """
        layout = Layout()

        # Create header
        header = self._create_header(
            bad_traders_count,
            traders_with_positions,
            len(signals),
            last_update
        )

        # Create signal table
        if signals:
            # Sort signals with priority coins first
            sorted_signals = self._sort_signals_with_priority(signals)
            signal_table = self._create_signal_table(sorted_signals[:self.top_signals_limit])
        else:
            signal_table = Panel(
                "[yellow]No signals generated yet.\nWaiting for position data...[/yellow]",
                title="Status",
                border_style="yellow"
            )

        # Combine into layout
        layout.split_column(
            Layout(header, size=5),
            Layout(signal_table)
        )

        return layout

    def _create_header(
        self,
        bad_traders_count: int,
        traders_with_positions: int,
        active_signals: int,
        last_update: datetime
    ) -> Panel:
        """Create header panel with overall statistics."""
        timestamp = last_update.strftime("%Y-%m-%d %H:%M:%S")

        header_text = Text()
        header_text.append("CONTRARIAN SIGNALS - Bad Traders Analysis\n", style="bold cyan")
        header_text.append(f"Updated: {timestamp}\n\n", style="dim")
        header_text.append(f"Total Bad Traders: {bad_traders_count}  |  ", style="white")
        header_text.append(f"With Open Positions: {traders_with_positions}  |  ", style="green")
        header_text.append(f"Active Signals: {active_signals}", style="yellow")

        return Panel(
            header_text,
            border_style="blue",
            box=box.DOUBLE
        )

    def _create_signal_table(self, signals: List[Dict]) -> Table:
        """
        Create table displaying all signals.

        Args:
            signals: List of signal dictionaries (sorted by confidence)

        Returns:
            Rich Table object
        """
        table = Table(
            title="Contrarian Trading Signals",
            title_style="bold cyan",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta"
        )

        # Define columns
        table.add_column("Coin", style="cyan", width=8)
        table.add_column("Signal", width=12)
        table.add_column("Strength", width=10)
        table.add_column("Conf", justify="right", width=6)
        table.add_column("Traders", justify="right", width=12)

        if self.show_size_weighted:
            table.add_column("Count-Based", width=25)
            table.add_column("Size-Weighted", width=25)
        else:
            table.add_column("Positioning", width=50)

        # Add rows for each signal
        for signal in signals:
            coin = signal['coin']
            direction = signal['signal_direction']
            strength = signal['signal_strength']
            confidence = signal['confidence_score']
            total_traders = signal['bad_traders_total']

            # Get change values (default to 0 if not present)
            total_change = signal.get('total_traders_change', 0)
            long_change = signal.get('long_count_change', 0)
            short_change = signal.get('short_count_change', 0)

            # Format signal direction with emoji/color
            signal_text = self._format_signal_direction(direction, strength)

            # Format strength
            strength_text = self._format_strength(strength)

            # Format confidence
            conf_text = self._format_confidence(confidence)

            # Format traders count with change indicator
            traders_text = f"{total_traders} {self._format_change(total_change)}"

            # Create positioning visualizations with change info
            if self.show_size_weighted:
                count_viz = self._create_position_bar(
                    signal['long_percentage'],
                    signal['short_percentage'],
                    signal['long_count'],
                    signal['short_count']
                )
                # Add change indicators to count-based positioning
                count_viz += f"\n L{self._format_change(long_change)} S{self._format_change(short_change)}"

                size_viz = self._create_position_bar(
                    signal['long_usd_percentage'],
                    signal['short_usd_percentage'],
                    signal['long_usd_value'],
                    signal['short_usd_value'],
                    is_usd=True
                )
                table.add_row(
                    coin,
                    signal_text,
                    strength_text,
                    conf_text,
                    traders_text,
                    count_viz,
                    size_viz
                )
            else:
                position_viz = self._create_position_bar(
                    signal['long_percentage'],
                    signal['short_percentage'],
                    signal['long_count'],
                    signal['short_count']
                )
                # Add change indicators to positioning
                position_viz += f"\n L{self._format_change(long_change)} S{self._format_change(short_change)}"

                table.add_row(
                    coin,
                    signal_text,
                    strength_text,
                    conf_text,
                    traders_text,
                    position_viz
                )

        return table

    def _format_signal_direction(self, direction: str, strength: str) -> Text:
        """Format signal direction with color and emoji."""
        if direction == 'SHORT':
            if strength == 'STRONG':
                return Text("🔴 SHORT", style="bold red")
            else:
                return Text("🟠 SHORT", style="red")
        elif direction == 'LONG':
            if strength == 'STRONG':
                return Text("🟢 LONG", style="bold green")
            else:
                return Text("🟡 LONG", style="green")
        else:
            return Text("⚪ NEUTRAL", style="dim")

    def _format_strength(self, strength: str) -> Text:
        """Format signal strength with color."""
        if strength == 'STRONG':
            return Text(strength, style="bold red")
        elif strength == 'MODERATE':
            return Text(strength, style="yellow")
        elif strength == 'WEAK':
            return Text(strength, style="dim")
        else:
            return Text(strength, style="dim")

    def _format_confidence(self, confidence: float) -> Text:
        """Format confidence score with color."""
        conf_str = f"{confidence:.2f}"

        if confidence >= 0.75:
            return Text(conf_str, style="bold green")
        elif confidence >= 0.50:
            return Text(conf_str, style="yellow")
        else:
            return Text(conf_str, style="dim")

    def _format_change(self, change: int) -> str:
        """
        Format change value with +/- indicator and color.

        Args:
            change: Change value (positive or negative)

        Returns:
            Formatted string with color codes
        """
        if change == 0:
            return "[dim](±0)[/dim]"
        elif change > 0:
            return f"[green](+{change})[/green]"
        else:
            return f"[red]({change})[/red]"

    def _create_position_bar(
        self,
        long_pct: float,
        short_pct: float,
        long_value: float,
        short_value: float,
        is_usd: bool = False
    ) -> str:
        """
        Create ASCII progress bar showing long/short distribution.

        Args:
            long_pct: Long percentage (0-100)
            short_pct: Short percentage (0-100)
            long_value: Long count or USD value
            short_value: Short count or USD value
            is_usd: Whether values are USD amounts

        Returns:
            Formatted string with bar and labels
        """
        # Create bar (20 characters total)
        bar_length = 20
        long_bars = int((long_pct / 100) * bar_length)
        short_bars = bar_length - long_bars

        # Color codes
        if long_pct > 70:
            bar = f"[red]{'█' * long_bars}[/red][dim]{'░' * short_bars}[/dim]"
        elif short_pct > 70:
            bar = f"[dim]{'░' * long_bars}[/dim][green]{'█' * short_bars}[/green]"
        else:
            bar = f"[yellow]{'█' * long_bars}[/yellow][blue]{'█' * short_bars}[/blue]"

        # Format values
        if is_usd:
            long_label = f"${long_value/1000:.0f}K" if long_value >= 1000 else f"${long_value:.0f}"
            short_label = f"${short_value/1000:.0f}K" if short_value >= 1000 else f"${short_value:.0f}"
        else:
            long_label = f"{int(long_value)}"
            short_label = f"{int(short_value)}"

        return f"{bar} L:{long_pct:.0f}%({long_label}) S:{short_pct:.0f}%({short_label})"

    def print_static(
        self,
        signals: List[Dict],
        bad_traders_count: int,
        traders_with_positions: int,
        last_update: datetime
    ):
        """
        Print static snapshot of dashboard (no live updates).

        Args:
            signals: List of signal dictionaries
            bad_traders_count: Total bad traders
            traders_with_positions: Traders with positions
            last_update: Last update timestamp
        """
        layout = self.render(
            signals,
            bad_traders_count,
            traders_with_positions,
            last_update
        )

        self.console.clear()
        self.console.print(layout)

    def print_summary(self, signals: List[Dict]):
        """
        Print concise summary of actionable signals.

        Args:
            signals: List of signal dictionaries
        """
        actionable = [
            s for s in signals
            if s['signal_strength'] in ['STRONG', 'MODERATE']
            and s['signal_direction'] != 'NEUTRAL'
        ]

        if not actionable:
            self.console.print("[yellow]No actionable signals at this time.[/yellow]")
            return

        self.console.print(f"\n[bold cyan]📊 {len(actionable)} Actionable Signals:[/bold cyan]\n")

        for signal in actionable[:10]:  # Top 10
            coin = signal['coin']
            direction = signal['signal_direction']
            strength = signal['signal_strength']
            confidence = signal['confidence_score']
            long_pct = signal['long_percentage']
            short_pct = signal['short_percentage']

            # Determine what bad traders are doing
            if direction == 'SHORT':
                reason = f"{long_pct:.0f}% of bad traders are LONG"
                style = "red"
            else:
                reason = f"{short_pct:.0f}% of bad traders are SHORT"
                style = "green"

            self.console.print(
                f"  [{style}]{coin:6} → {strength:8} {direction:5}[/{style}] "
                f"(conf: {confidence:.2f}) - {reason}"
            )

        self.console.print()

    def print_error(self, error_message: str):
        """
        Print error message.

        Args:
            error_message: Error description
        """
        self.console.print(f"[bold red]Error:[/bold red] {error_message}")

    def print_status(self, message: str):
        """
        Print status message.

        Args:
            message: Status message
        """
        self.console.print(f"[cyan]ℹ[/cyan] {message}")


# Example usage for testing
if __name__ == "__main__":
    # Create sample signals for testing
    sample_signals = [
        {
            'coin': 'BTC',
            'signal_direction': 'SHORT',
            'signal_strength': 'STRONG',
            'confidence_score': 0.85,
            'bad_traders_total': 45,
            'long_count': 37,
            'short_count': 8,
            'long_percentage': 82.2,
            'short_percentage': 17.8,
            'long_usd_value': 890000,
            'short_usd_value': 180000,
            'long_usd_percentage': 83.2,
            'short_usd_percentage': 16.8,
            'primary_metric': 'count'
        },
        {
            'coin': 'ETH',
            'signal_direction': 'SHORT',
            'signal_strength': 'MODERATE',
            'confidence_score': 0.62,
            'bad_traders_total': 31,
            'long_count': 20,
            'short_count': 11,
            'long_percentage': 64.5,
            'short_percentage': 35.5,
            'long_usd_value': 320000,
            'short_usd_value': 170000,
            'long_usd_percentage': 65.3,
            'short_usd_percentage': 34.7,
            'primary_metric': 'count'
        }
    ]

    dashboard = ContrarianDashboard()
    dashboard.print_static(
        sample_signals,
        277,
        142,
        datetime.now()
    )

    print("\n" + "="*80 + "\n")

    dashboard.print_summary(sample_signals)
