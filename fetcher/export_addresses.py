#!/usr/bin/env python3
"""Export addresses from database to CSV."""

import os
from pathlib import Path
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

    # Export to CSV in main data folder
    output_file = Path("../data/addresses_export.csv")
    output_file.parent.mkdir(parents=True, exist_ok=True)

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
