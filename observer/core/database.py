"""
Database layer for Observer dashboard.

Handles storage and retrieval of approved and rejected traders.
"""

import aiosqlite
import logging
from typing import List, Dict, Optional, Set
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from contextlib import asynccontextmanager


logger = logging.getLogger(__name__)


class ApprovedTradersDatabase:
    """
    Manages the Observer database for approved and rejected traders.

    This database stores decisions made during the manual review process.
    """

    def __init__(self, db_path: str, connection_timeout: int = 30, timezone: str = "Europe/Rome"):
        """
        Initialize database connection.

        Args:
            db_path: Path to the SQLite database file
            connection_timeout: Database connection timeout in seconds
            timezone: Timezone for datetime operations (default: Europe/Rome)
        """
        self.db_path = Path(db_path)
        self.connection_timeout = connection_timeout
        self.timezone = timezone

        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def initialize(self):
        """
        Initialize database schema.

        Creates tables and indexes if they don't exist.
        """
        async with self._get_connection() as db:
            # Main table: approved_traders
            await db.execute("""
                CREATE TABLE IF NOT EXISTS approved_traders (
                    address TEXT PRIMARY KEY,

                    -- Metrics from analyzed_traders (snapshot at approval time)
                    score INTEGER NOT NULL CHECK(score >= 0 AND score <= 100),
                    total_pnl REAL NOT NULL,
                    mean_pnl_per_trade REAL NOT NULL,
                    std_dev REAL NOT NULL,
                    sharpe_ratio REAL,
                    expected_value REAL NOT NULL,
                    t_statistic REAL NOT NULL,
                    p_value REAL NOT NULL,
                    monte_carlo_percentile REAL NOT NULL,
                    num_trades INTEGER NOT NULL,
                    win_rate REAL NOT NULL CHECK(win_rate >= 0 AND win_rate <= 1),
                    avg_win REAL,
                    avg_loss REAL,
                    account_balance REAL,
                    first_trade_time INTEGER,

                    -- Approval metadata
                    approved_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    approval_reason TEXT,
                    notes TEXT
                )
            """)

            # Rejection log table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS rejected_traders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    rejection_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    rejection_reason TEXT,

                    -- Snapshot metrics at rejection
                    total_pnl REAL,
                    num_trades INTEGER,
                    win_rate REAL
                )
            """)

            # Create indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_approved_timestamp
                ON approved_traders(approved_timestamp)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_approved_score
                ON approved_traders(score)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_rejected_timestamp
                ON rejected_traders(rejection_timestamp)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_rejected_address
                ON rejected_traders(address)
            """)

            await db.commit()

        logger.info(f"Observer database initialized at {self.db_path}")

    @asynccontextmanager
    async def _get_connection(self):
        """Get database connection as async context manager."""
        conn = await aiosqlite.connect(
            self.db_path,
            timeout=self.connection_timeout
        )
        try:
            # Enable foreign keys
            await conn.execute("PRAGMA foreign_keys = ON")
            yield conn
        finally:
            await conn.close()

    async def approve_trader(
        self,
        address: str,
        metrics: Dict,
        reason: Optional[str] = None,
        notes: Optional[str] = None
    ):
        """
        Approve a trader and store in database.

        Args:
            address: Trader's Ethereum address
            metrics: Dictionary with all trader metrics
            reason: Optional approval reason
            notes: Optional notes about the trader
        """
        async with self._get_connection() as db:
            await db.execute("""
                INSERT INTO approved_traders (
                    address, score, total_pnl, mean_pnl_per_trade, std_dev,
                    sharpe_ratio, expected_value, t_statistic, p_value,
                    monte_carlo_percentile, num_trades, win_rate, avg_win,
                    avg_loss, account_balance, first_trade_time,
                    approved_timestamp, approval_reason, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(address) DO UPDATE SET
                    score = excluded.score,
                    total_pnl = excluded.total_pnl,
                    mean_pnl_per_trade = excluded.mean_pnl_per_trade,
                    std_dev = excluded.std_dev,
                    sharpe_ratio = excluded.sharpe_ratio,
                    expected_value = excluded.expected_value,
                    t_statistic = excluded.t_statistic,
                    p_value = excluded.p_value,
                    monte_carlo_percentile = excluded.monte_carlo_percentile,
                    num_trades = excluded.num_trades,
                    win_rate = excluded.win_rate,
                    avg_win = excluded.avg_win,
                    avg_loss = excluded.avg_loss,
                    account_balance = excluded.account_balance,
                    first_trade_time = excluded.first_trade_time,
                    approved_timestamp = excluded.approved_timestamp,
                    approval_reason = excluded.approval_reason,
                    notes = excluded.notes
            """, (
                address,
                metrics.get('score'),
                metrics.get('total_pnl'),
                metrics.get('mean_pnl_per_trade'),
                metrics.get('std_dev'),
                metrics.get('sharpe_ratio'),
                metrics.get('expected_value'),
                metrics.get('t_statistic'),
                metrics.get('p_value'),
                metrics.get('monte_carlo_percentile'),
                metrics.get('num_trades'),
                metrics.get('win_rate'),
                metrics.get('avg_win'),
                metrics.get('avg_loss'),
                metrics.get('account_balance'),
                metrics.get('first_trade_time'),
                datetime.now(ZoneInfo(self.timezone)).isoformat(),
                reason,
                notes
            ))

            await db.commit()

        logger.info(f"Approved trader: {self._shorten_address(address)}")

    async def reject_trader(
        self,
        address: str,
        score: int,
        reason: Optional[str] = None,
        metrics: Optional[Dict] = None
    ):
        """
        Reject a trader and log in database.

        Args:
            address: Trader's Ethereum address
            score: Trader's score at rejection time
            reason: Optional rejection reason
            metrics: Optional dictionary with trader metrics
        """
        async with self._get_connection() as db:
            await db.execute("""
                INSERT INTO rejected_traders (
                    address, score, rejection_timestamp, rejection_reason,
                    total_pnl, num_trades, win_rate
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                address,
                score,
                datetime.now(ZoneInfo(self.timezone)).isoformat(),
                reason,
                metrics.get('total_pnl') if metrics else None,
                metrics.get('num_trades') if metrics else None,
                metrics.get('win_rate') if metrics else None
            ))

            await db.commit()

        logger.info(f"Rejected trader: {self._shorten_address(address)}")

    async def is_already_approved(self, address: str) -> bool:
        """
        Check if a trader has already been approved.

        Args:
            address: Trader's Ethereum address

        Returns:
            True if approved, False otherwise
        """
        async with self._get_connection() as db:
            async with db.execute("""
                SELECT 1 FROM approved_traders WHERE address = ?
            """, (address,)) as cursor:
                row = await cursor.fetchone()
                return row is not None

    async def is_already_rejected(self, address: str) -> bool:
        """
        Check if a trader has already been rejected.

        Args:
            address: Trader's Ethereum address

        Returns:
            True if rejected, False otherwise
        """
        async with self._get_connection() as db:
            async with db.execute("""
                SELECT 1 FROM rejected_traders WHERE address = ?
            """, (address,)) as cursor:
                row = await cursor.fetchone()
                return row is not None

    async def get_approved_trader(self, address: str) -> Optional[Dict]:
        """
        Get approved trader information.

        Args:
            address: Trader's Ethereum address

        Returns:
            Dictionary with trader data, or None if not found
        """
        async with self._get_connection() as db:
            async with db.execute("""
                SELECT * FROM approved_traders WHERE address = ?
            """, (address,)) as cursor:
                row = await cursor.fetchone()

                if row:
                    return self._row_to_dict(cursor, row)
                return None

    async def get_all_approved_addresses(self) -> Set[str]:
        """
        Get all approved trader addresses.

        Returns:
            Set of approved addresses
        """
        async with self._get_connection() as db:
            async with db.execute("""
                SELECT address FROM approved_traders
            """) as cursor:
                rows = await cursor.fetchall()
                return {row[0] for row in rows}

    async def get_all_rejected_addresses(self) -> Set[str]:
        """
        Get all rejected trader addresses.

        Returns:
            Set of rejected addresses
        """
        async with self._get_connection() as db:
            async with db.execute("""
                SELECT DISTINCT address FROM rejected_traders
            """) as cursor:
                rows = await cursor.fetchall()
                return {row[0] for row in rows}

    async def get_approval_statistics(self) -> Dict:
        """
        Get approval/rejection statistics.

        Returns:
            Dictionary with statistics
        """
        async with self._get_connection() as db:
            stats = {}

            # Approved count
            async with db.execute("""
                SELECT COUNT(*) FROM approved_traders
            """) as cursor:
                stats['approved_count'] = (await cursor.fetchone())[0]

            # Rejected count (distinct addresses)
            async with db.execute("""
                SELECT COUNT(DISTINCT address) FROM rejected_traders
            """) as cursor:
                stats['rejected_count'] = (await cursor.fetchone())[0]

            # Recent approvals (last 24h)
            async with db.execute("""
                SELECT COUNT(*) FROM approved_traders
                WHERE approved_timestamp > datetime('now', '-1 day')
            """) as cursor:
                stats['approved_last_24h'] = (await cursor.fetchone())[0]

            # Recent rejections (last 24h)
            async with db.execute("""
                SELECT COUNT(*) FROM rejected_traders
                WHERE rejection_timestamp > datetime('now', '-1 day')
            """) as cursor:
                stats['rejected_last_24h'] = (await cursor.fetchone())[0]

            # Average score of approved traders
            async with db.execute("""
                SELECT AVG(score) FROM approved_traders
            """) as cursor:
                avg_score = (await cursor.fetchone())[0]
                stats['avg_approved_score'] = avg_score if avg_score else 0

            return stats

    async def get_approved_traders(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: str = 'approved_timestamp'
    ) -> List[Dict]:
        """
        Get list of approved traders.

        Args:
            limit: Maximum number of results
            offset: Offset for pagination
            order_by: Column to order by (default: approved_timestamp)

        Returns:
            List of approved trader dictionaries
        """
        query = f"""
            SELECT * FROM approved_traders
            ORDER BY {order_by} DESC
        """

        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"

        async with self._get_connection() as db:
            async with db.execute(query) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_dict(cursor, row) for row in rows]

    def _row_to_dict(self, cursor, row) -> Dict:
        """Convert database row to dictionary."""
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, row))

    def _shorten_address(self, address: str) -> str:
        """Shorten address for logging."""
        if len(address) > 10:
            return f"{address[:6]}...{address[-4:]}"
        return address


class Phase2Reader:
    """
    Read-only access to analyzed_traders.db (Phase 2 database).

    This class ensures we never modify the analyzer database.
    """

    def __init__(self, db_path: str):
        """
        Initialize Phase 2 database reader.

        Args:
            db_path: Path to analyzed_traders.db
        """
        self.db_path = Path(db_path)

        if not self.db_path.exists():
            logger.warning(f"analyzed_traders.db not found at {self.db_path}")

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

    async def get_traders_by_score_range(
        self,
        min_score: int,
        max_score: int,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Get traders within a score range.

        Args:
            min_score: Minimum score (inclusive)
            max_score: Maximum score (inclusive)
            limit: Maximum number of results

        Returns:
            List of trader dictionaries
        """
        query = """
            SELECT * FROM scored_traders
            WHERE score >= ? AND score <= ?
            ORDER BY score DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        async with self._get_connection() as db:
            async with db.execute(query, (min_score, max_score)) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_dict(cursor, row) for row in rows]

    async def get_trader(self, address: str) -> Optional[Dict]:
        """
        Get a specific trader's data.

        Args:
            address: Trader's Ethereum address

        Returns:
            Dictionary with trader data, or None if not found
        """
        async with self._get_connection() as db:
            async with db.execute("""
                SELECT * FROM scored_traders WHERE address = ?
            """, (address,)) as cursor:
                row = await cursor.fetchone()

                if row:
                    return self._row_to_dict(cursor, row)
                return None

    def _row_to_dict(self, cursor, row) -> Dict:
        """Convert database row to dictionary."""
        columns = [description[0] for description in cursor.description]
        return dict(zip(columns, row))
