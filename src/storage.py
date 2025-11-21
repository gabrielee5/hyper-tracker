"""Database operations for address tracking."""

import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class AddressStorage:
    """SQLite-based storage for trader addresses."""

    def __init__(self, db_path: Path):
        """
        Initialize the storage.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def _initialize_database(self):
        """Create database tables if they don't exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create addresses table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS addresses (
                    address TEXT PRIMARY KEY,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    trade_count INTEGER DEFAULT 1,
                    total_volume_usd REAL DEFAULT 0.0
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_first_seen
                ON addresses(first_seen)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_last_seen
                ON addresses(last_seen)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_count
                ON addresses(trade_count)
            """)

            # Create trades table for Phase 2 preparation
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    coin TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    size REAL NOT NULL,
                    value_usd REAL NOT NULL,
                    trade_hash TEXT NOT NULL,
                    trade_id INTEGER NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    FOREIGN KEY (address) REFERENCES addresses(address)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_address
                ON trades(address)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_timestamp
                ON trades(timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_trades_coin
                ON trades(coin)
            """)

            logger.info(f"Database initialized at {self.db_path}")

    def batch_insert_addresses(self, addresses_data: List[Dict[str, Any]]) -> int:
        """
        Batch insert or update addresses.

        Args:
            addresses_data: List of dicts with keys: address, timestamp, volume

        Returns:
            Number of new addresses inserted
        """
        if not addresses_data:
            return 0

        new_count = 0

        with self._get_connection() as conn:
            cursor = conn.cursor()

            for data in addresses_data:
                address = data["address"]
                timestamp = data["timestamp"]
                volume = data.get("volume", 0.0)

                # Insert or update address
                cursor.execute("""
                    INSERT INTO addresses (address, first_seen, last_seen, trade_count, total_volume_usd)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(address) DO UPDATE SET
                        last_seen = ?,
                        trade_count = trade_count + 1,
                        total_volume_usd = total_volume_usd + ?
                """, (address, timestamp, timestamp, volume, timestamp, volume))

                # Check if this was a new address
                if cursor.rowcount == 1:
                    new_count += 1

        logger.info(f"Batch insert: {new_count} new addresses, {len(addresses_data) - new_count} updated")
        return new_count

    def insert_trade(self, trade_data: Dict[str, Any]):
        """
        Insert a trade record (for Phase 2 preparation).

        Args:
            trade_data: Dict with trade information
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO trades (
                    address, coin, side, price, size, value_usd,
                    trade_hash, trade_id, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_data["address"],
                trade_data["coin"],
                trade_data["side"],
                trade_data["price"],
                trade_data["size"],
                trade_data["value_usd"],
                trade_data["trade_hash"],
                trade_data["trade_id"],
                trade_data["timestamp"],
            ))

    def get_total_addresses(self) -> int:
        """Get total number of unique addresses."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM addresses")
            return cursor.fetchone()["count"]

    def get_recent_addresses(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get most recently seen addresses.

        Args:
            limit: Number of addresses to return

        Returns:
            List of address records
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT address, first_seen, last_seen, trade_count, total_volume_usd
                FROM addresses
                ORDER BY last_seen DESC
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_top_traders(self, limit: int = 100, by: str = "volume") -> List[Dict[str, Any]]:
        """
        Get top traders by volume or trade count.

        Args:
            limit: Number of traders to return
            by: Sort by 'volume' or 'trades'

        Returns:
            List of trader records
        """
        order_by = "total_volume_usd" if by == "volume" else "trade_count"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                SELECT address, first_seen, last_seen, trade_count, total_volume_usd
                FROM addresses
                ORDER BY {order_by} DESC
                LIMIT ?
            """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dictionary with various statistics
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total addresses
            cursor.execute("SELECT COUNT(*) as count FROM addresses")
            total_addresses = cursor.fetchone()["count"]

            # Total trades
            cursor.execute("SELECT COUNT(*) as count FROM trades")
            total_trades = cursor.fetchone()["count"]

            # Total volume
            cursor.execute("SELECT SUM(total_volume_usd) as volume FROM addresses")
            result = cursor.fetchone()
            total_volume = result["volume"] if result["volume"] else 0.0

            # Addresses in last 24 hours
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM addresses
                WHERE last_seen >= datetime('now', '-1 day')
            """)
            active_24h = cursor.fetchone()["count"]

            # Addresses in last hour
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM addresses
                WHERE last_seen >= datetime('now', '-1 hour')
            """)
            active_1h = cursor.fetchone()["count"]

            return {
                "total_addresses": total_addresses,
                "total_trades": total_trades,
                "total_volume_usd": round(total_volume, 2),
                "active_last_24h": active_24h,
                "active_last_1h": active_1h,
            }

    def get_address_details(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific address.

        Args:
            address: The address to look up

        Returns:
            Address details or None if not found
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT address, first_seen, last_seen, trade_count, total_volume_usd
                FROM addresses
                WHERE address = ?
            """, (address,))

            row = cursor.fetchone()
            if not row:
                return None

            return dict(row)

    def export_addresses(self, output_file: Path):
        """
        Export all addresses to a CSV file.

        Args:
            output_file: Path to output CSV file
        """
        import csv

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT address, first_seen, last_seen, trade_count, total_volume_usd
                FROM addresses
                ORDER BY last_seen DESC
            """)

            with open(output_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['address', 'first_seen', 'last_seen', 'trade_count', 'total_volume_usd'])

                for row in cursor.fetchall():
                    writer.writerow(row)

        logger.info(f"Exported addresses to {output_file}")
