#!/usr/bin/env python3
"""
CSV Export Tool for Contrarian Signals Database

Exports signals from contrarian_signals.db to CSV format.
Can export both contrarian signals and position snapshots.
"""

import sqlite3
import csv
import sys
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse


def export_signals_to_csv(db_path: str, output_path: str, limit: int = None, coin: str = None):
    """
    Export contrarian signals to CSV.

    Args:
        db_path: Path to contrarian_signals.db
        output_path: Output CSV file path
        limit: Maximum number of records (None for all)
        coin: Filter by specific coin (None for all)
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Access columns by name
    cursor = conn.cursor()

    # Build query
    query = "SELECT * FROM contrarian_signals"
    params = []

    if coin:
        query += " WHERE coin = ?"
        params.append(coin.upper())

    query += " ORDER BY timestamp DESC"

    if limit:
        query += f" LIMIT {limit}"

    # Execute query
    cursor.execute(query, params)
    rows = cursor.fetchall()

    if not rows:
        print(f"No signals found in database.")
        conn.close()
        return 0

    # Write to CSV
    with open(output_path, 'w', newline='') as csvfile:
        # Get column names from first row
        fieldnames = rows[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        # Write header
        writer.writeheader()

        # Write data
        for row in rows:
            writer.writerow(dict(row))

    conn.close()

    print(f"✓ Exported {len(rows)} signals to: {output_path}")
    return len(rows)


def export_positions_to_csv(db_path: str, output_path: str, limit: int = None, coin: str = None):
    """
    Export position snapshots to CSV.

    Args:
        db_path: Path to contrarian_signals.db
        output_path: Output CSV file path
        limit: Maximum number of records (None for all)
        coin: Filter by specific coin (None for all)
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build query
    query = "SELECT * FROM position_snapshot"
    params = []

    if coin:
        query += " WHERE coin = ?"
        params.append(coin.upper())

    query += " ORDER BY timestamp DESC"

    if limit:
        query += f" LIMIT {limit}"

    # Execute query
    cursor.execute(query, params)
    rows = cursor.fetchall()

    if not rows:
        print(f"No position snapshots found in database.")
        conn.close()
        return 0

    # Write to CSV
    with open(output_path, 'w', newline='') as csvfile:
        fieldnames = rows[0].keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()

        for row in rows:
            writer.writerow(dict(row))

    conn.close()

    print(f"✓ Exported {len(rows)} position snapshots to: {output_path}")
    return len(rows)


def show_database_stats(db_path: str):
    """
    Show statistics about the database contents.

    Args:
        db_path: Path to contrarian_signals.db
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("DATABASE STATISTICS")
    print("=" * 60)

    # Signals count
    cursor.execute("SELECT COUNT(*) FROM contrarian_signals")
    signals_count = cursor.fetchone()[0]
    print(f"\nTotal Signals: {signals_count}")

    if signals_count > 0:
        # Date range
        cursor.execute("""
            SELECT
                MIN(timestamp) as first_signal,
                MAX(timestamp) as last_signal
            FROM contrarian_signals
        """)
        first, last = cursor.fetchone()
        print(f"Date Range: {first} to {last}")

        # Signal breakdown
        cursor.execute("""
            SELECT
                signal_direction,
                signal_strength,
                COUNT(*) as count
            FROM contrarian_signals
            GROUP BY signal_direction, signal_strength
            ORDER BY count DESC
        """)
        print("\nSignal Breakdown:")
        for direction, strength, count in cursor.fetchall():
            print(f"  {direction:8} {strength:10}: {count:4} signals")

        # Top coins
        cursor.execute("""
            SELECT coin, COUNT(*) as count
            FROM contrarian_signals
            GROUP BY coin
            ORDER BY count DESC
            LIMIT 10
        """)
        print("\nTop 10 Coins by Signal Count:")
        for coin, count in cursor.fetchall():
            print(f"  {coin:8}: {count:4} signals")

    # Position snapshots
    cursor.execute("SELECT COUNT(*) FROM position_snapshot")
    positions_count = cursor.fetchone()[0]
    print(f"\nTotal Position Snapshots: {positions_count}")

    if positions_count > 0:
        cursor.execute("""
            SELECT
                MIN(timestamp) as first_snapshot,
                MAX(timestamp) as last_snapshot
            FROM position_snapshot
        """)
        first, last = cursor.fetchone()
        print(f"Date Range: {first} to {last}")

    print("=" * 60 + "\n")

    conn.close()


def main():
    """Main entry point with command-line interface."""
    parser = argparse.ArgumentParser(
        description="Export contrarian signals database to CSV format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all signals
  python export_signals_csv.py

  # Export only BTC signals
  python export_signals_csv.py --coin BTC

  # Export last 100 signals
  python export_signals_csv.py --limit 100

  # Export positions instead of signals
  python export_signals_csv.py --type positions

  # Show database statistics
  python export_signals_csv.py --stats

  # Custom output file
  python export_signals_csv.py --output my_signals.csv
        """
    )

    parser.add_argument(
        '--db',
        default='../data/contrarian_signals.db',
        help='Path to contrarian_signals.db (default: ../data/contrarian_signals.db)'
    )

    parser.add_argument(
        '--output', '-o',
        help='Output CSV file path (default: auto-generated with timestamp)'
    )

    parser.add_argument(
        '--type', '-t',
        choices=['signals', 'positions'],
        default='signals',
        help='Type of data to export (default: signals)'
    )

    parser.add_argument(
        '--limit', '-l',
        type=int,
        help='Maximum number of records to export'
    )

    parser.add_argument(
        '--coin', '-c',
        help='Filter by specific coin (e.g., BTC, ETH)'
    )

    parser.add_argument(
        '--stats', '-s',
        action='store_true',
        help='Show database statistics only (no export)'
    )

    args = parser.parse_args()

    # Resolve database path
    script_dir = Path(__file__).parent
    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = script_dir / db_path

    # Check if database exists
    if not db_path.exists():
        print(f"Error: Database not found at: {db_path}")
        print("\nMake sure the contrarian system has been run at least once.")
        sys.exit(1)

    # Show stats if requested
    if args.stats:
        show_database_stats(db_path)
        return

    # Determine output directory (data folder)
    data_dir = db_path.parent  # Same directory as the database

    # Generate output filename if not specified
    if args.output:
        output_path = Path(args.output)
        # If relative path, put it in data folder
        if not output_path.is_absolute():
            output_path = data_dir / output_path
    else:
        timestamp = datetime.now(ZoneInfo("Europe/Rome")).strftime("%Y%m%d_%H%M%S")
        coin_suffix = f"_{args.coin}" if args.coin else ""
        limit_suffix = f"_top{args.limit}" if args.limit else ""
        filename = f"contrarian_{args.type}{coin_suffix}{limit_suffix}_{timestamp}.csv"
        output_path = data_dir / filename

    print(f"\nExporting from: {db_path}")

    # Export based on type
    try:
        if args.type == 'signals':
            count = export_signals_to_csv(db_path, str(output_path), args.limit, args.coin)
        else:
            count = export_positions_to_csv(db_path, str(output_path), args.limit, args.coin)

        if count > 0:
            # Show file size
            file_size = Path(output_path).stat().st_size
            if file_size > 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.2f} MB"
            elif file_size > 1024:
                size_str = f"{file_size / 1024:.2f} KB"
            else:
                size_str = f"{file_size} bytes"

            print(f"File size: {size_str}")
            print("\nYou can now open this file in Excel, Google Sheets, or any CSV viewer.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
