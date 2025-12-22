"""
Export analyzed_traders.db data to CSV files.

This script exports the scored_traders and analysis_log tables from the
analyzer database to CSV format for easy analysis and reporting.
"""

import sqlite3
import csv
import argparse
from pathlib import Path
from datetime import datetime
import sys


def export_table_to_csv(db_path: str, table_name: str, output_path: str):
    """
    Export a database table to CSV.

    Args:
        db_path: Path to the SQLite database
        table_name: Name of the table to export
        output_path: Path for the output CSV file
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Get all rows from table
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        # Get column names
        column_names = [description[0] for description in cursor.description]

        # Write to CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow(column_names)

            # Write data rows
            writer.writerows(rows)

        print(f"✓ Exported {len(rows)} rows from '{table_name}' to {output_path}")
        return len(rows)

    except sqlite3.Error as e:
        print(f"✗ Error exporting {table_name}: {e}")
        return 0
    finally:
        conn.close()


def get_table_info(db_path: str):
    """
    Get information about tables in the database.

    Args:
        db_path: Path to the SQLite database

    Returns:
        List of table names
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        return tables
    finally:
        conn.close()


def main():
    """Main entry point for the CSV export tool."""
    parser = argparse.ArgumentParser(
        description='Export analyzed_traders.db to CSV files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all tables to default output directory
  python export_to_csv.py

  # Specify custom database path
  python export_to_csv.py --db-path /path/to/analyzed_traders.db

  # Specify custom output directory
  python export_to_csv.py --output-dir ./exports

  # Export specific table only
  python export_to_csv.py --table scored_traders

  # List available tables
  python export_to_csv.py --list-tables
        """
    )

    parser.add_argument(
        '--db-path',
        type=str,
        default='./data/analyzed_traders.db',
        help='Path to analyzed_traders.db (default: ./data/analyzed_traders.db)'
    )

    parser.add_argument(
        '--output-dir',
        type=str,
        default='./exports',
        help='Output directory for CSV files (default: ./exports)'
    )

    parser.add_argument(
        '--table',
        type=str,
        choices=['scored_traders', 'analysis_log'],
        help='Export specific table only (default: export all)'
    )

    parser.add_argument(
        '--list-tables',
        action='store_true',
        help='List available tables and exit'
    )

    args = parser.parse_args()

    # Resolve database path
    db_path = Path(args.db_path)

    # Check if database exists
    if not db_path.exists():
        print(f"✗ Error: Database not found at {db_path}")
        print(f"  Make sure the analyzer has been run at least once to create the database.")
        sys.exit(1)

    # List tables if requested
    if args.list_tables:
        print(f"Tables in {db_path}:")
        tables = get_table_info(str(db_path))
        for table in tables:
            print(f"  - {table}")
        sys.exit(0)

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate timestamp for filenames
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    print(f"\nExporting from: {db_path}")
    print(f"Output directory: {output_dir}\n")

    total_rows = 0

    # Determine which tables to export
    if args.table:
        tables_to_export = [args.table]
    else:
        tables_to_export = ['scored_traders', 'analysis_log']

    # Export tables
    for table in tables_to_export:
        output_file = output_dir / f"{table}_{timestamp}.csv"
        rows = export_table_to_csv(str(db_path), table, str(output_file))
        total_rows += rows

    print(f"\n✓ Export complete! Total rows exported: {total_rows}")
    print(f"  Files saved in: {output_dir.absolute()}")


if __name__ == "__main__":
    main()
