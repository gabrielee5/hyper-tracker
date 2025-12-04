"""
Database layer for Phase 3 contrarian signal system.

Handles:
1. Read-only access to Phase 2 analyzed_traders.db
2. Storage of contrarian signals and position snapshots
"""

import aiosqlite
import logging
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager


logger = logging.getLogger(__name__)


class Phase2Reader:
    """
    Read-only access to Phase 2 analyzed traders database.

    Queries bad traders based on score threshold.
    """

    def __init__(self, db_path: str):
        """
        Initialize Phase 2 database reader.

        Args:
            db_path: Path to analyzed_traders.db from Phase 2
        """
        self.db_path = Path(db_path)

        if not self.db_path.exists():
            raise FileNotFoundError(f"Phase 2 database not found: {self.db_path}")

    @asynccontextmanager
    async def _get_connection(self):
        """Get read-only connection to Phase 2 database."""
        # Open in read-only mode to prevent accidental writes
        uri = f"file:{self.db_path}?mode=ro"
        conn = await aiosqlite.connect(uri, uri=True)
        try:
            yield conn
        finally:
            await conn.close()

    async def get_bad_traders(
        self,
        score_threshold: int = 5,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get traders with exceptionally bad performance.

        Args:
            score_threshold: Maximum score to include (default: 5)
            limit: Maximum number of results

        Returns:
            List of trader dictionaries with address and metrics
        """
        query = """
            SELECT
                address,
                score,
                total_pnl,
                num_trades,
                win_rate,
                sharpe_ratio,
                account_balance
            FROM scored_traders
            WHERE score <= ? AND is_statistically_bad = 1
            ORDER BY score ASC, total_pnl ASC
        """

        if limit:
            query += f" LIMIT {limit}"

        async with self._get_connection() as db:
            async with db.execute(query, (score_threshold,)) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def get_trader_count(self, score_threshold: int = 5) -> int:
        """
        Get count of bad traders matching threshold.

        Args:
            score_threshold: Maximum score to include

        Returns:
            Count of bad traders
        """
        query = """
            SELECT COUNT(*) FROM scored_traders
            WHERE score <= ? AND is_statistically_bad = 1
        """

        async with self._get_connection() as db:
            async with db.execute(query, (score_threshold,)) as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0


class ContrarianDatabase:
    """
    Manages the Phase 3 database for contrarian signals.

    Stores:
    - Historical signals by coin/timestamp
    - Position snapshots for analysis
    """

    def __init__(self, db_path: str, connection_timeout: int = 30):
        """
        Initialize contrarian database.

        Args:
            db_path: Path to contrarian_signals.db
            connection_timeout: Database connection timeout in seconds
        """
        self.db_path = Path(db_path)
        self.connection_timeout = connection_timeout

        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """
        Initialize database schema.

        Creates tables and indexes if they don't exist.
        """
        async with self._get_connection() as db:
            # Contrarian signals table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS contrarian_signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    coin TEXT NOT NULL,
                    signal_direction TEXT NOT NULL,  -- 'LONG', 'SHORT', 'NEUTRAL'
                    signal_strength TEXT NOT NULL,   -- 'STRONG', 'MODERATE', 'WEAK', 'NONE'

                    -- Count-based metrics
                    bad_traders_total INTEGER NOT NULL,
                    long_count INTEGER NOT NULL,
                    short_count INTEGER NOT NULL,
                    long_percentage REAL NOT NULL,
                    short_percentage REAL NOT NULL,

                    -- Size-weighted metrics
                    long_usd_value REAL,
                    short_usd_value REAL,
                    long_usd_percentage REAL,
                    short_usd_percentage REAL,

                    -- Confidence
                    confidence_score REAL NOT NULL,

                    -- Which metric drove the signal
                    primary_metric TEXT NOT NULL DEFAULT 'count'  -- 'count' or 'size'
                )
            """)

            # Position snapshots table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS position_snapshot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    address TEXT NOT NULL,
                    coin TEXT NOT NULL,
                    side TEXT NOT NULL,  -- 'LONG' or 'SHORT'
                    size REAL NOT NULL,
                    position_value_usd REAL,
                    entry_price REAL,
                    leverage_value REAL,
                    unrealized_pnl REAL
                )
            """)

            # Create indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_signals_timestamp
                ON contrarian_signals(timestamp)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_signals_coin
                ON contrarian_signals(coin)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_signals_coin_time
                ON contrarian_signals(coin, timestamp)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshot_timestamp
                ON position_snapshot(timestamp)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshot_coin
                ON position_snapshot(coin)
            """)

            await db.commit()

        logger.info(f"Contrarian database initialized at {self.db_path}")

    @asynccontextmanager
    async def _get_connection(self):
        """Get database connection as async context manager."""
        conn = await aiosqlite.connect(
            self.db_path,
            timeout=self.connection_timeout
        )
        try:
            await conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        finally:
            await conn.close()

    async def save_signal(self, signal: Dict):
        """
        Save a contrarian signal to the database.

        Args:
            signal: Signal dictionary with all metrics
        """
        async with self._get_connection() as db:
            await db.execute("""
                INSERT INTO contrarian_signals (
                    coin, signal_direction, signal_strength,
                    bad_traders_total, long_count, short_count,
                    long_percentage, short_percentage,
                    long_usd_value, short_usd_value,
                    long_usd_percentage, short_usd_percentage,
                    confidence_score, primary_metric
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal['coin'],
                signal['signal_direction'],
                signal['signal_strength'],
                signal['bad_traders_total'],
                signal['long_count'],
                signal['short_count'],
                signal['long_percentage'],
                signal['short_percentage'],
                signal.get('long_usd_value'),
                signal.get('short_usd_value'),
                signal.get('long_usd_percentage'),
                signal.get('short_usd_percentage'),
                signal['confidence_score'],
                signal.get('primary_metric', 'count')
            ))

            await db.commit()

    async def save_position_snapshot(self, positions: List[Dict]):
        """
        Save position snapshots for multiple traders.

        Args:
            positions: List of position dictionaries
        """
        if not positions:
            return

        async with self._get_connection() as db:
            await db.executemany("""
                INSERT INTO position_snapshot (
                    address, coin, side, size, position_value_usd,
                    entry_price, leverage_value, unrealized_pnl
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, [
                (
                    p['address'],
                    p['coin'],
                    p['side'],
                    p['size'],
                    p.get('position_value_usd'),
                    p.get('entry_price'),
                    p.get('leverage_value'),
                    p.get('unrealized_pnl')
                )
                for p in positions
            ])

            await db.commit()

        logger.debug(f"Saved {len(positions)} position snapshots")

    async def get_recent_signals(
        self,
        coin: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get recent signals, optionally filtered by coin.

        Args:
            coin: Filter by coin (None for all)
            limit: Maximum number of results

        Returns:
            List of signal dictionaries
        """
        if coin:
            query = """
                SELECT * FROM contrarian_signals
                WHERE coin = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            params = (coin, limit)
        else:
            query = """
                SELECT * FROM contrarian_signals
                ORDER BY timestamp DESC
                LIMIT ?
            """
            params = (limit,)

        async with self._get_connection() as db:
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in rows]

    async def get_previous_signal(self, coin: str) -> Optional[Dict]:
        """
        Get the previous signal for a specific coin (second most recent).

        Args:
            coin: Coin symbol to query

        Returns:
            Previous signal dictionary or None if not found
        """
        query = """
            SELECT * FROM contrarian_signals
            WHERE coin = ?
            ORDER BY timestamp DESC
            LIMIT 1 OFFSET 1
        """

        async with self._get_connection() as db:
            async with db.execute(query, (coin,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None

    async def get_signal_statistics(self, coin: Optional[str] = None) -> Dict:
        """
        Get statistics about historical signals.

        Args:
            coin: Filter by coin (None for all)

        Returns:
            Dictionary with statistics
        """
        where_clause = "WHERE coin = ?" if coin else ""
        params = (coin,) if coin else ()

        async with self._get_connection() as db:
            # Total signals
            query = f"SELECT COUNT(*) FROM contrarian_signals {where_clause}"
            async with db.execute(query, params) as cursor:
                total_signals = (await cursor.fetchone())[0]

            # Signal breakdown
            query = f"""
                SELECT
                    signal_direction,
                    signal_strength,
                    COUNT(*) as count
                FROM contrarian_signals
                {where_clause}
                GROUP BY signal_direction, signal_strength
            """
            async with db.execute(query, params) as cursor:
                breakdown = await cursor.fetchall()

            # Average confidence
            query = f"""
                SELECT AVG(confidence_score)
                FROM contrarian_signals
                {where_clause}
            """
            async with db.execute(query, params) as cursor:
                avg_confidence = (await cursor.fetchone())[0] or 0

            return {
                'total_signals': total_signals,
                'breakdown': [
                    {'direction': row[0], 'strength': row[1], 'count': row[2]}
                    for row in breakdown
                ],
                'avg_confidence': avg_confidence
            }

    async def cleanup_old_snapshots(self, days_to_keep: int = 7):
        """
        Delete position snapshots older than specified days.

        Args:
            days_to_keep: Keep snapshots from last N days
        """
        async with self._get_connection() as db:
            await db.execute("""
                DELETE FROM position_snapshot
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (days_to_keep,))

            deleted = db.total_changes
            await db.commit()

        logger.info(f"Cleaned up {deleted} old position snapshots")

    def _shorten_address(self, address: str) -> str:
        """Shorten address for logging."""
        if len(address) > 10:
            return f"{address[:6]}...{address[-4:]}"
        return address
