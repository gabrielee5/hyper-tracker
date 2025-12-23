"""
Database operations for the paper trading simulator.
Manages portfolio state, positions, trades, and performance metrics.
"""

import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class SimulatorDatabase:
    """Manages all database operations for the simulator."""

    def __init__(self, db_path: str = "simulator.db"):
        self.db_path = db_path
        self.conn = None
        self._initialize_database()

    def _initialize_database(self):
        """Create database connection and initialize tables."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info(f"Database initialized at {self.db_path}")

    def _create_tables(self):
        """Create all required tables."""
        cursor = self.conn.cursor()

        # Portfolio state table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_state (
                timestamp TIMESTAMP PRIMARY KEY,
                total_equity REAL NOT NULL,
                cash_balance REAL NOT NULL DEFAULT 0,
                total_pnl REAL NOT NULL DEFAULT 0,
                total_return_pct REAL NOT NULL DEFAULT 0,
                num_open_positions INTEGER NOT NULL DEFAULT 0,
                total_fees_paid REAL NOT NULL DEFAULT 0
            )
        """)

        # Current positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                pair TEXT PRIMARY KEY,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                current_price REAL NOT NULL,
                entry_size_usd REAL NOT NULL,
                current_size_usd REAL NOT NULL,
                quantity REAL NOT NULL,
                entry_timestamp TIMESTAMP NOT NULL,
                last_updated TIMESTAMP NOT NULL,
                unrealized_pnl REAL NOT NULL DEFAULT 0,
                unrealized_pnl_pct REAL NOT NULL DEFAULT 0,
                signal_confidence REAL NOT NULL,
                total_fees_paid REAL NOT NULL DEFAULT 0
            )
        """)

        # Trade history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                pair TEXT NOT NULL,
                direction TEXT NOT NULL,
                action TEXT NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                usd_value REAL NOT NULL,
                fees REAL NOT NULL,
                slippage REAL NOT NULL,
                signal_confidence REAL,
                reason TEXT,
                pnl REAL
            )
        """)

        # Rebalancing events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rebalance_history (
                rebalance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP NOT NULL,
                num_adjustments INTEGER NOT NULL,
                total_fees REAL NOT NULL,
                portfolio_value_before REAL NOT NULL,
                portfolio_value_after REAL NOT NULL,
                signals_used INTEGER NOT NULL
            )
        """)

        # Performance history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_history (
                timestamp TIMESTAMP PRIMARY KEY,
                total_equity REAL NOT NULL,
                total_pnl REAL NOT NULL,
                total_return_pct REAL NOT NULL,
                sharpe_ratio REAL,
                max_drawdown REAL NOT NULL,
                win_rate REAL NOT NULL,
                num_trades INTEGER NOT NULL,
                avg_win REAL,
                avg_loss REAL
            )
        """)

        self.conn.commit()
        logger.info("Database tables created/verified")

    # Portfolio State Operations
    def save_portfolio_state(self, equity: float, cash: float, pnl: float,
                            return_pct: float, num_positions: int, total_fees: float):
        """Save current portfolio state."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO portfolio_state
            (timestamp, total_equity, cash_balance, total_pnl, total_return_pct,
             num_open_positions, total_fees_paid)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now(ZoneInfo("Europe/Rome")), equity, cash, pnl, return_pct, num_positions, total_fees))
        self.conn.commit()

    def get_latest_portfolio_state(self) -> Optional[Dict]:
        """Get the most recent portfolio state."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM portfolio_state
            ORDER BY timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_initial_capital(self) -> float:
        """Get initial capital (first portfolio state or default to 100k)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT total_equity FROM portfolio_state
            ORDER BY timestamp ASC LIMIT 1
        """)
        row = cursor.fetchone()
        return row[0] if row else 100000.0

    # Position Operations
    def upsert_position(self, pair: str, direction: str, entry_price: float,
                       current_price: float, entry_size_usd: float,
                       current_size_usd: float, quantity: float,
                       entry_timestamp: datetime, unrealized_pnl: float,
                       unrealized_pnl_pct: float, signal_confidence: float,
                       total_fees_paid: float = 0):
        """Insert or update a position."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO positions
            (pair, direction, entry_price, current_price, entry_size_usd,
             current_size_usd, quantity, entry_timestamp, last_updated,
             unrealized_pnl, unrealized_pnl_pct, signal_confidence, total_fees_paid)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (pair, direction, entry_price, current_price, entry_size_usd,
              current_size_usd, quantity, entry_timestamp, datetime.now(ZoneInfo("Europe/Rome")),
              unrealized_pnl, unrealized_pnl_pct, signal_confidence, total_fees_paid))
        self.conn.commit()

    def update_position_price(self, pair: str, current_price: float,
                             current_size_usd: float, unrealized_pnl: float,
                             unrealized_pnl_pct: float):
        """Update position's current price and P&L."""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE positions
            SET current_price = ?, current_size_usd = ?, unrealized_pnl = ?,
                unrealized_pnl_pct = ?, last_updated = ?
            WHERE pair = ?
        """, (current_price, current_size_usd, unrealized_pnl,
              unrealized_pnl_pct, datetime.now(ZoneInfo("Europe/Rome")), pair))
        self.conn.commit()

    def delete_position(self, pair: str):
        """Remove a position (when closed)."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM positions WHERE pair = ?", (pair,))
        self.conn.commit()

    def get_all_positions(self) -> List[Dict]:
        """Get all current open positions."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM positions")
        return [dict(row) for row in cursor.fetchall()]

    def get_position(self, pair: str) -> Optional[Dict]:
        """Get a specific position."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM positions WHERE pair = ?", (pair,))
        row = cursor.fetchone()
        return dict(row) if row else None

    # Trade Operations
    def log_trade(self, pair: str, direction: str, action: str, price: float,
                  quantity: float, usd_value: float, fees: float, slippage: float,
                  signal_confidence: Optional[float] = None, reason: Optional[str] = None,
                  pnl: Optional[float] = None) -> int:
        """Log a trade execution."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO trades
            (timestamp, pair, direction, action, price, quantity, usd_value,
             fees, slippage, signal_confidence, reason, pnl)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now(ZoneInfo("Europe/Rome")), pair, direction, action, price, quantity,
              usd_value, fees, slippage, signal_confidence, reason, pnl))
        self.conn.commit()
        return cursor.lastrowid

    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        """Get recent trades."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM trades
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_closed_trades(self) -> List[Dict]:
        """Get all closed trades (with P&L)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM trades
            WHERE action = 'CLOSE' AND pnl IS NOT NULL
            ORDER BY timestamp
        """)
        return [dict(row) for row in cursor.fetchall()]

    def get_trade_count(self) -> int:
        """Get total number of trades."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trades")
        return cursor.fetchone()[0]

    # Rebalancing Operations
    def log_rebalance(self, num_adjustments: int, total_fees: float,
                     value_before: float, value_after: float,
                     signals_used: int) -> int:
        """Log a rebalancing event."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO rebalance_history
            (timestamp, num_adjustments, total_fees, portfolio_value_before,
             portfolio_value_after, signals_used)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (datetime.now(ZoneInfo("Europe/Rome")), num_adjustments, total_fees, value_before,
              value_after, signals_used))
        self.conn.commit()
        return cursor.lastrowid

    def get_recent_rebalances(self, limit: int = 10) -> List[Dict]:
        """Get recent rebalancing events."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM rebalance_history
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    # Performance Operations
    def save_performance_snapshot(self, equity: float, pnl: float,
                                  return_pct: float, sharpe_ratio: Optional[float],
                                  max_drawdown: float, win_rate: float,
                                  num_trades: int, avg_win: Optional[float],
                                  avg_loss: Optional[float]):
        """Save performance metrics snapshot."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO performance_history
            (timestamp, total_equity, total_pnl, total_return_pct, sharpe_ratio,
             max_drawdown, win_rate, num_trades, avg_win, avg_loss)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now(ZoneInfo("Europe/Rome")), equity, pnl, return_pct, sharpe_ratio,
              max_drawdown, win_rate, num_trades, avg_win, avg_loss))
        self.conn.commit()

    def get_equity_curve(self) -> List[Tuple[datetime, float]]:
        """Get equity curve for charts."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT timestamp, total_equity
            FROM performance_history
            ORDER BY timestamp
        """)
        return [(row[0], row[1]) for row in cursor.fetchall()]

    def get_latest_performance(self) -> Optional[Dict]:
        """Get most recent performance snapshot."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM performance_history
            ORDER BY timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
