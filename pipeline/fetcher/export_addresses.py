#!/usr/bin/env python3
"""Export addresses from database to CSV."""

import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from config import Config
from storage import AddressStorage


def main():
    """Export addresses to CSV."""
    # Ensure we're working from the script's directory (fetcher/)
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    # Load configuration
    config = Config.from_env()

    # Initialize storage
    storage = AddressStorage(config.database_path)

    # Determine main project directory and exports folder
    main_dir = script_dir.parent
    exports_dir = main_dir / "exports"

    # Create exports directory if it doesn't exist
    exports_dir.mkdir(exist_ok=True)

    # Generate timestamped filename
    timestamp = datetime.now(ZoneInfo("Europe/Rome")).strftime("%Y%m%d_%H%M%S")
    output_file = exports_dir / f"addresses_export_{timestamp}.csv"

    storage.export_addresses(output_file)
    print(f"✓ Exported addresses to {output_file}")

    # Print statistics
    stats = storage.get_statistics()
    print(f"\nDatabase Statistics:")
    print(f"  Total Addresses: {stats['total_addresses']}")
    print(f"  Active (1h): {stats['active_last_1h']}")
    print(f"  Active (24h): {stats['active_last_24h']}")
    print(f"  Total Volume: ${stats['total_volume_usd']:,.2f}")


if __name__ == "__main__":
    main()
