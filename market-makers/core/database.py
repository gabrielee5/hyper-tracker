"""Database layer for market maker monitor."""

import aiosqlite
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import asynccontextmanager


logger = logging.getLogger(__name__)


class AnalyzerDatabaseReader:
    """Read-only access to analyzer database for market makers."""

    def __init__(self, db_path: str):
        """
        Initialize analyzer database reader.

        Args:
            db_path: Path to analyzer database
        """
        self.db_path = Path(db_path)

        if not self.db_path.exists():
            raise FileNotFoundError(f"Analyzer DB not found: {self.db_path}")

    @asynccontextmanager
    async def _get_connection(self):
        """Get read-only connection."""
        uri = f"file:{self.db_path}?mode=ro"
        conn = await aiosqlite.connect(uri, uri=True)
        try:
            yield conn
        finally:
            await conn.close()

    async def get_market_makers(
        self,
        min_balance: float = 50000,
        max_age_hours: float = 24,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get active market makers from analyzer database.

        Args:
            min_balance: Minimum account balance (default: $50k)
            max_age_hours: Maximum age of last_seen (default: 24h)
            limit: Maximum number of results

        Returns:
            List of market maker dictionaries
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        query = """
            SELECT
                address,
                trade_count,
                account_balance,
                first_trade_time,
                first_trade_age_hours,
                total_volume_usd,
                last_seen,
                detection_count
            FROM market_makers
            WHERE account_balance >= ?
            AND last_seen > ?
            ORDER BY account_balance DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        async with self._get_connection() as db:
            async with db.execute(
                query,
                (min_balance, cutoff_time.isoformat())
            ) as cursor:
                rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def get_market_maker_count(self, min_balance: float = 50000) -> int:
        """Get total count of market makers."""
        query = """
            SELECT COUNT(*) FROM market_makers
            WHERE account_balance >= ?
        """

        async with self._get_connection() as db:
            async with db.execute(query, (min_balance,)) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0

    async def get_market_maker(self, address: str) -> Optional[Dict]:
        """
        Get specific market maker information.

        Args:
            address: Market maker address

        Returns:
            Market maker dictionary or None
        """
        query = """
            SELECT
                address,
                trade_count,
                account_balance,
                first_trade_time,
                first_trade_age_hours,
                total_volume_usd,
                last_seen,
                detection_count
            FROM market_makers
            WHERE address = ?
        """

        async with self._get_connection() as db:
            async with db.execute(query, (address,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None


class MMPositionDatabase:
    """Local database for market maker positions and bias history."""

    def __init__(self, db_path: str, connection_timeout: int = 30):
        """
        Initialize position database.

        Args:
            db_path: Path to local database
            connection_timeout: Database connection timeout in seconds
        """
        self.db_path = Path(db_path)
        self.connection_timeout = connection_timeout

        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """Initialize database schema."""
        async with self._get_connection() as db:
            # Position snapshots table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS position_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    mm_address TEXT NOT NULL,
                    coin TEXT NOT NULL,
                    side TEXT NOT NULL CHECK(side IN ('LONG', 'SHORT')),
                    size REAL NOT NULL,
                    position_value_usd REAL NOT NULL,
                    entry_price REAL,
                    leverage REAL,
                    unrealized_pnl REAL
                )
            """)

            # Bias history table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS bias_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    coin TEXT NOT NULL,
                    mm_count INTEGER NOT NULL,
                    long_count INTEGER NOT NULL,
                    short_count INTEGER NOT NULL,
                    long_value_usd REAL NOT NULL,
                    short_value_usd REAL NOT NULL,
                    total_value_usd REAL NOT NULL,
                    net_bias_usd REAL NOT NULL,
                    bias_percentage REAL NOT NULL,
                    direction TEXT NOT NULL CHECK(direction IN ('BULLISH', 'BEARISH', 'NEUTRAL')),
                    strength TEXT NOT NULL CHECK(strength IN ('STRONG', 'MODERATE', 'WEAK')),
                    current_price REAL
                )
            """)

            # MM activity tracking table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS mm_activity (
                    mm_address TEXT PRIMARY KEY,
                    first_seen TIMESTAMP NOT NULL,
                    last_seen TIMESTAMP NOT NULL,
                    total_checks INTEGER NOT NULL DEFAULT 1,
                    times_with_positions INTEGER NOT NULL DEFAULT 0,
                    times_without_positions INTEGER NOT NULL DEFAULT 0,
                    last_position_count INTEGER DEFAULT 0,
                    is_currently_active BOOLEAN NOT NULL DEFAULT 1
                )
            """)

            # Create indexes
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshot_timestamp "
                "ON position_snapshots(timestamp)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshot_address "
                "ON position_snapshots(mm_address)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshot_coin "
                "ON position_snapshots(coin)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshot_coin_time "
                "ON position_snapshots(coin, timestamp)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_bias_timestamp "
                "ON bias_history(timestamp)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_bias_coin "
                "ON bias_history(coin)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_bias_coin_time "
                "ON bias_history(coin, timestamp)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_last_seen "
                "ON mm_activity(last_seen)"
            )
            await db.execute(
                "CREATE INDEX IF NOT EXISTS idx_activity_active "
                "ON mm_activity(is_currently_active)"
            )

            await db.commit()

        logger.info(f"MM Position database initialized at {self.db_path}")

    @asynccontextmanager
    async def _get_connection(self):
        """Get database connection."""
        conn = await aiosqlite.connect(
            self.db_path,
            timeout=self.connection_timeout
        )
        try:
            await conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        finally:
            await conn.close()

    async def save_position_snapshots(self, positions: List[Dict]):
        """
        Save position snapshots.

        Args:
            positions: List of position dictionaries
        """
        if not positions:
            return

        async with self._get_connection() as db:
            await db.executemany("""
                INSERT INTO position_snapshots (
                    mm_address, coin, side, size, position_value_usd,
                    entry_price, leverage, unrealized_pnl
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    p['address'],
                    p['coin'],
                    p['side'],
                    p['size'],
                    p['position_value_usd'],
                    p.get('entry_price'),
                    p.get('leverage_value'),
                    p.get('unrealized_pnl')
                )
                for p in positions
            ])
            await db.commit()

        logger.debug(f"Saved {len(positions)} position snapshots")

    async def save_bias(self, bias: Dict):
        """
        Save calculated bias data.

        Args:
            bias: Bias dictionary
        """
        async with self._get_connection() as db:
            await db.execute("""
                INSERT INTO bias_history (
                    coin, mm_count, long_count, short_count,
                    long_value_usd, short_value_usd, total_value_usd,
                    net_bias_usd, bias_percentage, direction, strength,
                    current_price
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                bias['coin'],
                bias['mm_count'],
                bias['long_count'],
                bias['short_count'],
                bias['long_value_usd'],
                bias['short_value_usd'],
                bias['total_value_usd'],
                bias['net_bias_usd'],
                bias['bias_percentage'],
                bias['direction'],
                bias['strength'],
                bias.get('current_price')
            ))
            await db.commit()

    async def update_mm_activity(
        self,
        mm_address: str,
        has_positions: bool,
        position_count: int
    ):
        """
        Update market maker activity tracking.

        Args:
            mm_address: Market maker address
            has_positions: Whether MM currently has positions
            position_count: Number of positions
        """
        async with self._get_connection() as db:
            await db.execute("""
                INSERT INTO mm_activity (
                    mm_address, first_seen, last_seen, total_checks,
                    times_with_positions, times_without_positions,
                    last_position_count, is_currently_active
                ) VALUES (?, ?, ?, 1, ?, ?, ?, 1)
                ON CONFLICT(mm_address) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    total_checks = total_checks + 1,
                    times_with_positions = times_with_positions + excluded.times_with_positions,
                    times_without_positions = times_without_positions + excluded.times_without_positions,
                    last_position_count = excluded.last_position_count,
                    is_currently_active = 1
            """, (
                mm_address,
                datetime.now().isoformat(),
                datetime.now().isoformat(),
                1 if has_positions else 0,
                0 if has_positions else 1,
                position_count
            ))
            await db.commit()

    async def get_bias_history(
        self,
        coin: str,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get historical bias data for a coin.

        Args:
            coin: Coin symbol
            hours: Look back this many hours
            limit: Maximum number of results

        Returns:
            List of bias dictionaries
        """
        cutoff = datetime.now() - timedelta(hours=hours)

        async with self._get_connection() as db:
            async with db.execute("""
                SELECT * FROM bias_history
                WHERE coin = ? AND timestamp > ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (coin, cutoff.isoformat(), limit)) as cursor:
                rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def get_latest_bias(self, coin: Optional[str] = None) -> List[Dict]:
        """
        Get most recent bias for each coin (or specific coin).

        Args:
            coin: Optional coin filter

        Returns:
            List of latest bias dictionaries
        """
        if coin:
            query = """
                SELECT * FROM bias_history
                WHERE coin = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """
            params = (coin,)
        else:
            # Get latest bias for each unique coin
            query = """
                SELECT bh1.* FROM bias_history bh1
                INNER JOIN (
                    SELECT coin, MAX(timestamp) as max_ts
                    FROM bias_history
                    GROUP BY coin
                ) bh2 ON bh1.coin = bh2.coin AND bh1.timestamp = bh2.max_ts
                ORDER BY bh1.total_value_usd DESC
            """
            params = ()

        async with self._get_connection() as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def get_active_mm_count(self) -> int:
        """Get count of currently active market makers."""
        query = """
            SELECT COUNT(*) FROM mm_activity
            WHERE is_currently_active = 1
        """

        async with self._get_connection() as db:
            async with db.execute(query) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0

    async def get_mm_activity(self, mm_address: str) -> Optional[Dict]:
        """
        Get activity tracking for a specific market maker.

        Args:
            mm_address: Market maker address

        Returns:
            Activity dictionary or None
        """
        query = """
            SELECT * FROM mm_activity
            WHERE mm_address = ?
        """

        async with self._get_connection() as db:
            async with db.execute(query, (mm_address,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, row))
                return None

    async def cleanup_old_data(
        self,
        snapshots_days: int = 7,
        bias_days: int = 30
    ):
        """
        Clean up old data based on retention policy.

        Args:
            snapshots_days: Delete snapshots older than this
            bias_days: Delete bias history older than this
        """
        async with self._get_connection() as db:
            # Delete old snapshots
            await db.execute("""
                DELETE FROM position_snapshots
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (snapshots_days,))

            snapshots_deleted = db.total_changes

            # Delete old bias history
            await db.execute("""
                DELETE FROM bias_history
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (bias_days,))

            bias_deleted = db.total_changes

            await db.commit()

        logger.info(
            f"Cleanup: removed {snapshots_deleted} snapshots, "
            f"{bias_deleted} bias records"
        )

    async def get_statistics(self) -> Dict:
        """
        Get database statistics.

        Returns:
            Dictionary with statistics
        """
        async with self._get_connection() as db:
            stats = {}

            # Total snapshots
            async with db.execute(
                "SELECT COUNT(*) FROM position_snapshots"
            ) as cursor:
                stats['total_snapshots'] = (await cursor.fetchone())[0]

            # Total bias records
            async with db.execute(
                "SELECT COUNT(*) FROM bias_history"
            ) as cursor:
                stats['total_bias_records'] = (await cursor.fetchone())[0]

            # Active MMs
            async with db.execute(
                "SELECT COUNT(*) FROM mm_activity WHERE is_currently_active = 1"
            ) as cursor:
                stats['active_mm_count'] = (await cursor.fetchone())[0]

            # Total tracked MMs
            async with db.execute(
                "SELECT COUNT(*) FROM mm_activity"
            ) as cursor:
                stats['total_mm_count'] = (await cursor.fetchone())[0]

            # Unique coins
            async with db.execute(
                "SELECT COUNT(DISTINCT coin) FROM bias_history"
            ) as cursor:
                stats['unique_coins'] = (await cursor.fetchone())[0]

            return stats
