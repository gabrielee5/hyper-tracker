#!/usr/bin/env python3
"""Query addresses from database."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import Config
from storage import AddressStorage


def main():
    """Query and display addresses."""
    # Load configuration
    config = Config.from_env()

    # Initialize storage
    storage = AddressStorage(config.database_path)

    # Get statistics
    stats = storage.get_statistics()
    print("=" * 80)
    print("DATABASE STATISTICS")
    print("=" * 80)
    print(f"Total Addresses: {stats['total_addresses']}")
    print(f"Total Trades: {stats['total_trades']}")
    print(f"Active (1h): {stats['active_last_1h']}")
    print(f"Active (24h): {stats['active_last_24h']}")
    print(f"Total Volume: ${stats['total_volume_usd']:,.2f}")
    print()

    # Get top traders by volume
    print("=" * 80)
    print("TOP 10 TRADERS BY VOLUME")
    print("=" * 80)
    top_volume = storage.get_top_traders(limit=10, by="volume")
    for i, trader in enumerate(top_volume, 1):
        print(f"{i}. {trader['address'][:10]}...{trader['address'][-6:]}")
        print(f"   Volume: ${trader['total_volume_usd']:,.2f} | Trades: {trader['trade_count']}")
        print(f"   First: {trader['first_seen']} | Last: {trader['last_seen']}")
        print()

    # Get top traders by trade count
    print("=" * 80)
    print("TOP 10 TRADERS BY TRADE COUNT")
    print("=" * 80)
    top_trades = storage.get_top_traders(limit=10, by="trades")
    for i, trader in enumerate(top_trades, 1):
        print(f"{i}. {trader['address'][:10]}...{trader['address'][-6:]}")
        print(f"   Trades: {trader['trade_count']} | Volume: ${trader['total_volume_usd']:,.2f}")
        print(f"   First: {trader['first_seen']} | Last: {trader['last_seen']}")
        print()

    # Get recent addresses
    print("=" * 80)
    print("10 MOST RECENT ADDRESSES")
    print("=" * 80)
    recent = storage.get_recent_addresses(limit=10)
    for i, trader in enumerate(recent, 1):
        print(f"{i}. {trader['address'][:10]}...{trader['address'][-6:]}")
        print(f"   Last Seen: {trader['last_seen']} | Trades: {trader['trade_count']}")
        print()


if __name__ == "__main__":
    main()
