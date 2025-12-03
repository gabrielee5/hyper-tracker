"""
Signal reader for Phase 3 contrarian signals database.
"""

import sqlite3
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ContrarianSignal:
    """Represents a contrarian trading signal."""
    pair: str
    signal: str  # 'LONG', 'SHORT', or 'NEUTRAL'
    confidence: float
    timestamp: str
    bad_trader_exposure_pct: Optional[float] = None
    signal_strength: Optional[str] = None  # Not used for position sizing


class SignalReader:
    """Reads contrarian signals from Phase 3 database."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        logger.info(f"Signal reader initialized for {db_path}")

    def get_top_signals(self, min_confidence: float = 0.60,
                       max_signals: int = 10,
                       exclude_neutral: bool = True) -> List[ContrarianSignal]:
        """
        Get top contrarian signals filtered by confidence.

        Args:
            min_confidence: Minimum confidence threshold (default 0.60)
            max_signals: Maximum number of signals to return (default 10)
            exclude_neutral: Whether to exclude NEUTRAL signals (default True)

        Returns:
            List of ContrarianSignal objects, sorted by confidence (descending)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build query with filters
            # Note: database uses 'coin', 'signal_direction', 'confidence_score'
            # Use subquery to get only latest signal for each coin
            query = """
                SELECT coin as pair, signal_direction as signal,
                       confidence_score as confidence, timestamp,
                       short_usd_percentage as bad_trader_exposure_pct,
                       signal_strength
                FROM contrarian_signals
                WHERE id IN (
                    SELECT id FROM contrarian_signals cs1
                    WHERE cs1.timestamp = (
                        SELECT MAX(timestamp) FROM contrarian_signals cs2
                        WHERE cs2.coin = cs1.coin
                    )
                )
                AND confidence_score >= ?
            """
            params = [min_confidence]

            if exclude_neutral:
                query += " AND signal_direction != 'NEUTRAL'"

            query += " ORDER BY confidence_score DESC LIMIT ?"
            params.append(max_signals)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            signals = [
                ContrarianSignal(
                    pair=row['pair'],
                    signal=row['signal'],
                    confidence=row['confidence'],
                    timestamp=row['timestamp'],
                    bad_trader_exposure_pct=row['bad_trader_exposure_pct'] if 'bad_trader_exposure_pct' in row.keys() else None,
                    signal_strength=row['signal_strength'] if 'signal_strength' in row.keys() else None
                )
                for row in rows
            ]

            logger.info(f"Retrieved {len(signals)} signals (min_confidence={min_confidence}, "
                       f"max={max_signals}, exclude_neutral={exclude_neutral})")
            return signals

        except sqlite3.Error as e:
            logger.error(f"Database error reading signals: {e}")
            return []
        except Exception as e:
            logger.error(f"Error reading signals: {e}")
            return []

    def get_signal_for_pair(self, pair: str) -> Optional[ContrarianSignal]:
        """Get the current signal for a specific pair."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT coin as pair, signal_direction as signal,
                       confidence_score as confidence, timestamp,
                       short_usd_percentage as bad_trader_exposure_pct,
                       signal_strength
                FROM contrarian_signals
                WHERE coin = ?
            """, (pair,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return ContrarianSignal(
                    pair=row['pair'],
                    signal=row['signal'],
                    confidence=row['confidence'],
                    timestamp=row['timestamp'],
                    bad_trader_exposure_pct=row.get('bad_trader_exposure_pct'),
                    signal_strength=row.get('signal_strength')
                )
            return None

        except Exception as e:
            logger.error(f"Error reading signal for {pair}: {e}")
            return None

    def get_all_signals(self) -> List[ContrarianSignal]:
        """Get all available signals."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT coin as pair, signal_direction as signal,
                       confidence_score as confidence, timestamp,
                       short_usd_percentage as bad_trader_exposure_pct,
                       signal_strength
                FROM contrarian_signals
                ORDER BY confidence_score DESC
            """)

            rows = cursor.fetchall()
            conn.close()

            signals = [
                ContrarianSignal(
                    pair=row['pair'],
                    signal=row['signal'],
                    confidence=row['confidence'],
                    timestamp=row['timestamp'],
                    bad_trader_exposure_pct=row['bad_trader_exposure_pct'] if 'bad_trader_exposure_pct' in row.keys() else None,
                    signal_strength=row['signal_strength'] if 'signal_strength' in row.keys() else None
                )
                for row in rows
            ]

            logger.info(f"Retrieved {len(signals)} total signals")
            return signals

        except Exception as e:
            logger.error(f"Error reading all signals: {e}")
            return []

    def get_signal_count(self, min_confidence: float = 0.0,
                        exclude_neutral: bool = False) -> int:
        """Get count of signals matching criteria."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = "SELECT COUNT(*) FROM contrarian_signals WHERE confidence_score >= ?"
            params = [min_confidence]

            if exclude_neutral:
                query += " AND signal_direction != 'NEUTRAL'"

            cursor.execute(query, params)
            count = cursor.fetchone()[0]
            conn.close()

            return count

        except Exception as e:
            logger.error(f"Error counting signals: {e}")
            return 0
