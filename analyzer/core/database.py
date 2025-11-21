"""
Database layer for Phase 2 analyzer.

Handles storage and retrieval of analyzed trader data in a separate database
from Phase 1, ensuring complete isolation.
"""

import aiosqlite
import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from contextlib import asynccontextmanager

from .statistics import TraderMetrics


logger = logging.getLogger(__name__)


class AnalyzerDatabase:
    """
    Manages the Phase 2 database for analyzed traders.

    This database is completely separate from Phase 1 (addresses.db)
    and stores the results of statistical analysis.
    """

    def __init__(self, db_path: str, connection_timeout: int = 30):
        """
        Initialize database connection.

        Args:
            db_path: Path to the SQLite database file
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
            # Main table: scored_traders
            await db.execute("""
                CREATE TABLE IF NOT EXISTS scored_traders (
                    address TEXT PRIMARY KEY,
                    score INTEGER NOT NULL CHECK(score >= 0 AND score <= 100),

                    -- Performance metrics
                    total_pnl REAL NOT NULL,
                    mean_pnl_per_trade REAL NOT NULL,
                    std_dev REAL NOT NULL,

                    -- Statistical indicators
                    sharpe_ratio REAL,
                    expected_value REAL NOT NULL,
                    t_statistic REAL NOT NULL,
                    p_value REAL NOT NULL,
                    monte_carlo_percentile REAL NOT NULL,

                    -- Trade statistics
                    num_trades INTEGER NOT NULL CHECK(num_trades >= 30),
                    win_rate REAL NOT NULL CHECK(win_rate >= 0 AND win_rate <= 1),
                    avg_win REAL,
                    avg_loss REAL,

                    -- Metadata
                    last_analyzed TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    is_statistically_bad BOOLEAN NOT NULL DEFAULT 0
                )
            """)

            # Analysis log table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS analysis_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    trades_fetched INTEGER
                )
            """)

            # Create indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_score
                ON scored_traders(score)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_bad_traders
                ON scored_traders(is_statistically_bad)
                WHERE is_statistically_bad = 1
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_last_analyzed
                ON scored_traders(last_analyzed)
            """)

            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_log_timestamp
                ON analysis_log(timestamp)
            """)

            await db.commit()

        logger.info(f"Database initialized at {self.db_path}")

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

    async def save_trader_analysis(self, address: str, metrics: TraderMetrics):
        """
        Save or update trader analysis results.

        Args:
            address: Trader's Ethereum address
            metrics: TraderMetrics object with complete analysis
        """
        async with self._get_connection() as db:
            await db.execute("""
                INSERT INTO scored_traders (
                    address, score, total_pnl, mean_pnl_per_trade, std_dev,
                    sharpe_ratio, expected_value, t_statistic, p_value,
                    monte_carlo_percentile, num_trades, win_rate, avg_win,
                    avg_loss, last_analyzed, is_statistically_bad
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    last_analyzed = excluded.last_analyzed,
                    is_statistically_bad = excluded.is_statistically_bad
            """, (
                address,
                metrics.score,
                metrics.total_pnl,
                metrics.mean_pnl_per_trade,
                metrics.std_dev,
                metrics.sharpe_ratio,
                metrics.expected_value,
                metrics.t_statistic,
                metrics.p_value,
                metrics.monte_carlo_percentile,
                metrics.num_trades,
                metrics.win_rate,
                metrics.avg_win,
                metrics.avg_loss,
                datetime.now().isoformat(),
                metrics.is_statistically_bad
            ))

            await db.commit()

        logger.debug(f"Saved analysis for {self._shorten_address(address)}")

    async def log_analysis(
        self,
        address: str,
        status: str,
        trades_fetched: Optional[int] = None,
        error_message: Optional[str] = None
    ):
        """
        Log an analysis attempt.

        Args:
            address: Trader's Ethereum address
            status: 'success', 'insufficient_data', 'api_error', etc.
            trades_fetched: Number of trades fetched
            error_message: Error message if failed
        """
        async with self._get_connection() as db:
            await db.execute("""
                INSERT INTO analysis_log (address, status, trades_fetched, error_message)
                VALUES (?, ?, ?, ?)
            """, (address, status, trades_fetched, error_message))

            await db.commit()

    async def get_trader_analysis(self, address: str) -> Optional[Dict]:
        """
        Get analysis results for a specific trader.

        Args:
            address: Trader's Ethereum address

        Returns:
            Dictionary with analysis results, or None if not found
        """
        async with self._get_connection() as db:
            async with db.execute("""
                SELECT * FROM scored_traders WHERE address = ?
            """, (address,)) as cursor:
                row = await cursor.fetchone()

                if row:
                    return self._row_to_dict(cursor, row)
                return None

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
            List of trader dictionaries sorted by score (worst first)
        """
        query = """
            SELECT * FROM scored_traders
            WHERE score <= ? AND is_statistically_bad = 1
            ORDER BY score ASC, total_pnl ASC
        """

        if limit:
            query += f" LIMIT {limit}"

        async with self._get_connection() as db:
            async with db.execute(query, (score_threshold,)) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_dict(cursor, row) for row in rows]

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

    async def get_stale_analyses(
        self,
        days_old: int = 7,
        limit: Optional[int] = None
    ) -> List[str]:
        """
        Get addresses that need re-analysis.

        Args:
            days_old: How many days old is considered stale
            limit: Maximum number of addresses to return

        Returns:
            List of addresses needing re-analysis
        """
        cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()

        query = """
            SELECT address FROM scored_traders
            WHERE last_analyzed < ?
            ORDER BY last_analyzed ASC
        """

        if limit:
            query += f" LIMIT {limit}"

        async with self._get_connection() as db:
            async with db.execute(query, (cutoff_date,)) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def get_statistics(self) -> Dict:
        """
        Get overall database statistics.

        Returns:
            Dictionary with statistics about analyzed traders
        """
        async with self._get_connection() as db:
            stats = {}

            # Total traders analyzed
            async with db.execute(
                "SELECT COUNT(*) FROM scored_traders"
            ) as cursor:
                stats['total_analyzed'] = (await cursor.fetchone())[0]

            # Bad traders count
            async with db.execute(
                "SELECT COUNT(*) FROM scored_traders WHERE is_statistically_bad = 1"
            ) as cursor:
                stats['bad_traders_count'] = (await cursor.fetchone())[0]

            # Score distribution
            async with db.execute("""
                SELECT
                    COUNT(CASE WHEN score < 5 THEN 1 END) as exceptionally_bad,
                    COUNT(CASE WHEN score >= 5 AND score < 15 THEN 1 END) as very_poor,
                    COUNT(CASE WHEN score >= 15 AND score < 40 THEN 1 END) as below_avg,
                    COUNT(CASE WHEN score >= 40 AND score < 60 THEN 1 END) as average,
                    COUNT(CASE WHEN score >= 60 AND score < 85 THEN 1 END) as above_avg,
                    COUNT(CASE WHEN score >= 85 AND score < 95 THEN 1 END) as very_good,
                    COUNT(CASE WHEN score >= 95 THEN 1 END) as exceptional
                FROM scored_traders
            """) as cursor:
                row = await cursor.fetchone()
                stats['distribution'] = {
                    'exceptionally_bad': row[0],
                    'very_poor': row[1],
                    'below_average': row[2],
                    'average': row[3],
                    'above_average': row[4],
                    'very_good': row[5],
                    'exceptional': row[6]
                }

            # Average metrics
            async with db.execute("""
                SELECT
                    AVG(score) as avg_score,
                    AVG(total_pnl) as avg_total_pnl,
                    AVG(sharpe_ratio) as avg_sharpe,
                    AVG(win_rate) as avg_win_rate
                FROM scored_traders
            """) as cursor:
                row = await cursor.fetchone()
                stats['averages'] = {
                    'score': row[0] or 0,
                    'total_pnl': row[1] or 0,
                    'sharpe_ratio': row[2] or 0,
                    'win_rate': row[3] or 0
                }

            # Recent analyses
            async with db.execute("""
                SELECT COUNT(*) FROM scored_traders
                WHERE last_analyzed > datetime('now', '-1 day')
            """) as cursor:
                stats['analyzed_last_24h'] = (await cursor.fetchone())[0]

            return stats

    async def get_top_traders(self, limit: int = 10) -> List[Dict]:
        """
        Get top performing traders by score.

        Args:
            limit: Number of traders to return

        Returns:
            List of top trader dictionaries
        """
        async with self._get_connection() as db:
            async with db.execute("""
                SELECT * FROM scored_traders
                ORDER BY score DESC, total_pnl DESC
                LIMIT ?
            """, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_dict(cursor, row) for row in rows]

    async def get_worst_traders(self, limit: int = 10) -> List[Dict]:
        """
        Get worst performing traders by score.

        Args:
            limit: Number of traders to return

        Returns:
            List of worst trader dictionaries
        """
        async with self._get_connection() as db:
            async with db.execute("""
                SELECT * FROM scored_traders
                ORDER BY score ASC, total_pnl ASC
                LIMIT ?
            """, (limit,)) as cursor:
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


class Phase1DatabaseReader:
    """
    Read-only access to Phase 1 database (addresses.db).

    This class ensures we never modify Phase 1 data.
    """

    def __init__(self, db_path: str):
        """
        Initialize Phase 1 database reader.

        Args:
            db_path: Path to Phase 1 addresses.db
        """
        self.db_path = Path(db_path)

        if not self.db_path.exists():
            logger.warning(f"Phase 1 database not found at {self.db_path}")

    @asynccontextmanager
    async def _get_connection(self):
        """Get read-only connection to Phase 1 database."""
        # Open in read-only mode to prevent accidental writes
        uri = f"file:{self.db_path}?mode=ro"
        conn = await aiosqlite.connect(uri, uri=True)
        try:
            yield conn
        finally:
            await conn.close()

    async def get_all_addresses(self) -> List[str]:
        """
        Get all unique trader addresses from Phase 1.

        Returns:
            List of Ethereum addresses
        """
        async with self._get_connection() as db:
            async with db.execute("SELECT address FROM addresses") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def get_recently_active_addresses(
        self,
        days: int = 7,
        limit: Optional[int] = None
    ) -> List[Tuple[str, str]]:
        """
        Get addresses that have been active recently.

        Args:
            days: Consider addresses active in last N days
            limit: Maximum number of addresses

        Returns:
            List of (address, last_seen) tuples, sorted by most recent
        """
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

        query = """
            SELECT address, last_seen FROM addresses
            WHERE last_seen > ?
            ORDER BY last_seen DESC
        """

        if limit:
            query += f" LIMIT {limit}"

        async with self._get_connection() as db:
            async with db.execute(query, (cutoff_date,)) as cursor:
                return await cursor.fetchall()

    async def get_address_info(self, address: str) -> Optional[Dict]:
        """
        Get information about a specific address from Phase 1.

        Args:
            address: Ethereum address

        Returns:
            Dictionary with address info or None if not found
        """
        async with self._get_connection() as db:
            async with db.execute("""
                SELECT * FROM addresses WHERE address = ?
            """, (address,)) as cursor:
                row = await cursor.fetchone()

                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
