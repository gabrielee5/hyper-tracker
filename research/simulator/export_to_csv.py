"""
Export simulator database data to CSV files.

This script exports all tables from the simulator database to CSV files
in the exports/ directory for analysis.

Usage:
    python export_to_csv.py                    # Export from default three-asset DB
    python export_to_csv.py --db simulator.db  # Export from specific DB
    python export_to_csv.py --all              # Export all tables
    python export_to_csv.py --table trades     # Export specific table only
"""

import sqlite3
import pandas as pd
import argparse
import os
from datetime import datetime
from pathlib import Path


class SimulatorExporter:
    """Export simulator database tables to CSV files."""

    def __init__(self, db_path: str):
        """
        Initialize exporter.

        Args:
            db_path: Path to simulator database
        """
        self.db_path = db_path
        self.conn = None
        self.export_dir = Path(__file__).resolve().parents[2] / 'exports' / 'simulator'

        # Create exports/simulator directory if it doesn't exist
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def connect(self):
        """Connect to database."""
        self.conn = sqlite3.connect(self.db_path)
        print(f"✓ Connected to database: {self.db_path}")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            print("✓ Database connection closed")

    def get_table_names(self):
        """Get list of all tables in database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [row[0] for row in cursor.fetchall()]

    def export_table(self, table_name: str, timestamp_suffix: bool = True) -> str:
        """
        Export a single table to CSV.

        Args:
            table_name: Name of table to export
            timestamp_suffix: Add timestamp to filename

        Returns:
            Path to exported CSV file
        """
        try:
            # Read table into DataFrame
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", self.conn)

            if df.empty:
                print(f"⚠ Table '{table_name}' is empty, skipping export")
                return None

            # Generate filename
            if timestamp_suffix:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{table_name}_{timestamp}.csv"
            else:
                filename = f"{table_name}.csv"

            filepath = self.export_dir / filename

            # Export to CSV
            df.to_csv(filepath, index=False)

            print(f"✓ Exported {table_name}: {len(df)} rows → {filepath}")
            return str(filepath)

        except Exception as e:
            print(f"✗ Error exporting {table_name}: {e}")
            return None

    def export_all(self, timestamp_suffix: bool = True) -> dict:
        """
        Export all tables to CSV files.

        Args:
            timestamp_suffix: Add timestamp to filenames

        Returns:
            Dictionary mapping table names to export paths
        """
        tables = self.get_table_names()
        print(f"\nFound {len(tables)} tables to export: {', '.join(tables)}\n")

        exports = {}
        for table in tables:
            path = self.export_table(table, timestamp_suffix)
            if path:
                exports[table] = path

        return exports

    def export_portfolio_summary(self, timestamp_suffix: bool = True) -> str:
        """
        Export a comprehensive portfolio summary combining multiple tables.

        Returns:
            Path to exported CSV file
        """
        try:
            # Get portfolio state history with equity curve
            query = """
                SELECT
                    ps.timestamp,
                    ps.total_equity,
                    ps.cash_balance,
                    ps.total_pnl,
                    ps.total_return_pct,
                    ps.num_open_positions,
                    ps.total_fees_paid
                FROM portfolio_state ps
                ORDER BY ps.timestamp
            """
            df = pd.read_sql_query(query, self.conn)

            if df.empty:
                print("⚠ No portfolio data to export")
                return None

            # Generate filename
            if timestamp_suffix:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"portfolio_summary_{timestamp}.csv"
            else:
                filename = "portfolio_summary.csv"

            filepath = self.export_dir / filename
            df.to_csv(filepath, index=False)

            print(f"✓ Exported portfolio summary: {len(df)} snapshots → {filepath}")
            return str(filepath)

        except Exception as e:
            print(f"✗ Error exporting portfolio summary: {e}")
            return None

    def export_trade_analysis(self, timestamp_suffix: bool = True) -> str:
        """
        Export detailed trade analysis with P&L calculations.

        Returns:
            Path to exported CSV file
        """
        try:
            # Get all trades with additional calculated fields
            query = """
                SELECT
                    trade_id,
                    timestamp,
                    pair,
                    direction,
                    action,
                    price,
                    quantity,
                    usd_value,
                    fees,
                    slippage,
                    signal_confidence,
                    reason,
                    pnl,
                    CASE
                        WHEN pnl > 0 THEN 'WIN'
                        WHEN pnl < 0 THEN 'LOSS'
                        ELSE 'NEUTRAL'
                    END as outcome,
                    CASE
                        WHEN usd_value > 0 THEN (pnl / usd_value) * 100
                        ELSE NULL
                    END as pnl_pct
                FROM trades
                ORDER BY timestamp
            """
            df = pd.read_sql_query(query, self.conn)

            if df.empty:
                print("⚠ No trade data to export")
                return None

            # Generate filename
            if timestamp_suffix:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"trade_analysis_{timestamp}.csv"
            else:
                filename = "trade_analysis.csv"

            filepath = self.export_dir / filename
            df.to_csv(filepath, index=False)

            print(f"✓ Exported trade analysis: {len(df)} trades → {filepath}")
            return str(filepath)

        except Exception as e:
            print(f"✗ Error exporting trade analysis: {e}")
            return None

    def export_performance_metrics(self, timestamp_suffix: bool = True) -> str:
        """
        Export performance metrics over time.

        Returns:
            Path to exported CSV file
        """
        try:
            query = """
                SELECT
                    timestamp,
                    total_equity,
                    total_pnl,
                    total_return_pct,
                    sharpe_ratio,
                    max_drawdown,
                    win_rate,
                    num_trades,
                    avg_win,
                    avg_loss
                FROM performance_history
                ORDER BY timestamp
            """
            df = pd.read_sql_query(query, self.conn)

            if df.empty:
                print("⚠ No performance data to export")
                return None

            # Generate filename
            if timestamp_suffix:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"performance_metrics_{timestamp}.csv"
            else:
                filename = "performance_metrics.csv"

            filepath = self.export_dir / filename
            df.to_csv(filepath, index=False)

            print(f"✓ Exported performance metrics: {len(df)} snapshots → {filepath}")
            return str(filepath)

        except Exception as e:
            print(f"✗ Error exporting performance metrics: {e}")
            return None

    def print_summary(self):
        """Print database summary statistics."""
        print("\n" + "="*80)
        print("DATABASE SUMMARY")
        print("="*80)

        try:
            # Portfolio state
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM portfolio_state")
            portfolio_count = cursor.fetchone()[0]
            print(f"Portfolio snapshots: {portfolio_count}")

            # Positions
            cursor.execute("SELECT COUNT(*) FROM positions")
            positions_count = cursor.fetchone()[0]
            print(f"Open positions: {positions_count}")

            # Trades
            cursor.execute("SELECT COUNT(*) FROM trades")
            trades_count = cursor.fetchone()[0]
            cursor.execute("SELECT SUM(fees) FROM trades")
            total_fees = cursor.fetchone()[0] or 0
            print(f"Total trades: {trades_count}")
            print(f"Total fees paid: ${total_fees:.2f}")

            # Closed trades with P&L
            cursor.execute("SELECT COUNT(*), SUM(pnl) FROM trades WHERE action='CLOSE' AND pnl IS NOT NULL")
            closed_trades, total_pnl = cursor.fetchone()
            print(f"Closed trades: {closed_trades or 0}")
            print(f"Total realized P&L: ${total_pnl or 0:.2f}")

            # Latest equity
            cursor.execute("SELECT total_equity, total_return_pct FROM portfolio_state ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                equity, return_pct = row
                print(f"Latest equity: ${equity:.2f} ({return_pct:+.2f}%)")

            # Rebalances
            cursor.execute("SELECT COUNT(*) FROM rebalance_history")
            rebalance_count = cursor.fetchone()[0]
            print(f"Rebalancing events: {rebalance_count}")

            print("="*80 + "\n")

        except Exception as e:
            print(f"Error generating summary: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Export simulator database to CSV files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python export_to_csv.py                          # Export all from default DB
  python export_to_csv.py --db simulator.db        # Export from specific DB
  python export_to_csv.py --table trades           # Export specific table only
  python export_to_csv.py --no-timestamp           # Don't add timestamp to filenames
  python export_to_csv.py --summary                # Export summary reports only
        """
    )

    parser.add_argument(
        '--db',
        default='../../data/simulator_three_asset.db',
        help='Path to simulator database (default: ../../data/simulator_three_asset.db)'
    )

    parser.add_argument(
        '--table',
        help='Export specific table only (e.g., trades, positions, portfolio_state)'
    )

    parser.add_argument(
        '--no-timestamp',
        action='store_true',
        help='Do not add timestamp suffix to filenames'
    )

    parser.add_argument(
        '--summary',
        action='store_true',
        help='Export summary reports only (portfolio_summary, trade_analysis, performance_metrics)'
    )

    args = parser.parse_args()

    # Check if database exists
    if not os.path.exists(args.db):
        print(f"✗ Database not found: {args.db}")
        print("Available databases in ../../data/:")
        data_dir = Path(args.db).parent
        if data_dir.exists():
            for db_file in data_dir.glob('*.db'):
                print(f"  - {db_file.name}")
        return

    # Create exporter
    exporter = SimulatorExporter(args.db)

    try:
        exporter.connect()
        exporter.print_summary()

        timestamp_suffix = not args.no_timestamp

        if args.summary:
            # Export summary reports only
            print("\nExporting summary reports...\n")
            exporter.export_portfolio_summary(timestamp_suffix)
            exporter.export_trade_analysis(timestamp_suffix)
            exporter.export_performance_metrics(timestamp_suffix)

        elif args.table:
            # Export specific table
            print(f"\nExporting table: {args.table}\n")
            exporter.export_table(args.table, timestamp_suffix)

        else:
            # Export all tables
            print("\nExporting all tables...\n")
            exports = exporter.export_all(timestamp_suffix)

            # Also export summary reports
            print("\nExporting summary reports...\n")
            exporter.export_portfolio_summary(timestamp_suffix)
            exporter.export_trade_analysis(timestamp_suffix)
            exporter.export_performance_metrics(timestamp_suffix)

        print(f"\n✓ Export complete! Files saved to: {exporter.export_dir}")

    except Exception as e:
        print(f"✗ Export failed: {e}")

    finally:
        exporter.close()


if __name__ == "__main__":
    main()
