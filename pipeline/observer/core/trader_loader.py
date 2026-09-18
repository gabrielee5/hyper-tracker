"""
Trader queue management for Observer dashboard.

Handles loading, filtering, and navigation through traders for review.
"""

import logging
from typing import List, Dict, Optional, Set

from .database import Phase2Reader, ApprovedTradersDatabase


logger = logging.getLogger(__name__)


class TraderQueueManager:
    """
    Manages the queue of traders for sequential review.

    Handles filtering by score range and exclusion of already-reviewed traders.
    """

    def __init__(
        self,
        phase2_db_path: str,
        approved_db: ApprovedTradersDatabase
    ):
        """
        Initialize trader queue manager.

        Args:
            phase2_db_path: Path to analyzed_traders.db
            approved_db: ApprovedTradersDatabase instance
        """
        self.phase2_reader = Phase2Reader(phase2_db_path)
        self.approved_db = approved_db

    async def get_traders_for_review(
        self,
        min_score: int = 0,
        max_score: int = 100,
        limit: Optional[int] = None,
        exclude_approved: bool = True,
        exclude_rejected: bool = True
    ) -> List[Dict]:
        """
        Get traders matching filters for review.

        Args:
            min_score: Minimum score (inclusive)
            max_score: Maximum score (inclusive)
            limit: Maximum number of results
            exclude_approved: Exclude already approved traders
            exclude_rejected: Exclude already rejected traders

        Returns:
            List of trader dictionaries ready for review
        """
        # Get traders in score range from Phase 2 database
        traders = await self.phase2_reader.get_traders_by_score_range(
            min_score=min_score,
            max_score=max_score,
            limit=None  # Get all, we'll filter and limit later
        )

        # Get exclusion sets if needed
        approved_addresses = set()
        rejected_addresses = set()

        if exclude_approved:
            approved_addresses = await self.approved_db.get_all_approved_addresses()

        if exclude_rejected:
            rejected_addresses = await self.approved_db.get_all_rejected_addresses()

        # Filter out already-reviewed traders
        filtered_traders = [
            trader for trader in traders
            if trader['address'] not in approved_addresses
            and trader['address'] not in rejected_addresses
        ]

        # Apply limit if specified
        if limit:
            filtered_traders = filtered_traders[:limit]

        logger.info(
            f"Loaded {len(filtered_traders)} traders for review "
            f"(score {min_score}-{max_score}, "
            f"excluded {len(approved_addresses)} approved, "
            f"{len(rejected_addresses)} rejected)"
        )

        return filtered_traders

    async def get_next_trader(
        self,
        current_address: str,
        min_score: int = 0,
        max_score: int = 100,
        exclude_approved: bool = True,
        exclude_rejected: bool = True
    ) -> Optional[Dict]:
        """
        Get the next trader in the queue after the current one.

        Args:
            current_address: Current trader's address
            min_score: Minimum score for filtering
            max_score: Maximum score for filtering
            exclude_approved: Exclude approved traders
            exclude_rejected: Exclude rejected traders

        Returns:
            Next trader dictionary, or None if no more traders
        """
        # Get all traders in queue
        traders = await self.get_traders_for_review(
            min_score=min_score,
            max_score=max_score,
            exclude_approved=exclude_approved,
            exclude_rejected=exclude_rejected
        )

        if not traders:
            return None

        # Find current trader index
        current_index = None
        for i, trader in enumerate(traders):
            if trader['address'] == current_address:
                current_index = i
                break

        # Return next trader if exists
        if current_index is not None and current_index + 1 < len(traders):
            return traders[current_index + 1]

        # If current not found or is last, return first trader
        return traders[0] if traders else None

    async def get_previous_trader(
        self,
        current_address: str,
        min_score: int = 0,
        max_score: int = 100,
        exclude_approved: bool = True,
        exclude_rejected: bool = True
    ) -> Optional[Dict]:
        """
        Get the previous trader in the queue before the current one.

        Args:
            current_address: Current trader's address
            min_score: Minimum score for filtering
            max_score: Maximum score for filtering
            exclude_approved: Exclude approved traders
            exclude_rejected: Exclude rejected traders

        Returns:
            Previous trader dictionary, or None if at beginning
        """
        # Get all traders in queue
        traders = await self.get_traders_for_review(
            min_score=min_score,
            max_score=max_score,
            exclude_approved=exclude_approved,
            exclude_rejected=exclude_rejected
        )

        if not traders:
            return None

        # Find current trader index
        current_index = None
        for i, trader in enumerate(traders):
            if trader['address'] == current_address:
                current_index = i
                break

        # Return previous trader if exists
        if current_index is not None and current_index > 0:
            return traders[current_index - 1]

        # If current not found or is first, return last trader
        return traders[-1] if traders else None

    async def get_trader_count(
        self,
        min_score: int = 0,
        max_score: int = 100,
        exclude_approved: bool = True,
        exclude_rejected: bool = True
    ) -> int:
        """
        Get count of traders available for review.

        Args:
            min_score: Minimum score for filtering
            max_score: Maximum score for filtering
            exclude_approved: Exclude approved traders
            exclude_rejected: Exclude rejected traders

        Returns:
            Number of traders matching criteria
        """
        traders = await self.get_traders_for_review(
            min_score=min_score,
            max_score=max_score,
            exclude_approved=exclude_approved,
            exclude_rejected=exclude_rejected
        )

        return len(traders)

    async def get_trader_position(
        self,
        address: str,
        min_score: int = 0,
        max_score: int = 100,
        exclude_approved: bool = True,
        exclude_rejected: bool = True
    ) -> Optional[int]:
        """
        Get the position (index) of a trader in the current queue.

        Args:
            address: Trader's address
            min_score: Minimum score for filtering
            max_score: Maximum score for filtering
            exclude_approved: Exclude approved traders
            exclude_rejected: Exclude rejected traders

        Returns:
            1-based position in queue, or None if not found
        """
        traders = await self.get_traders_for_review(
            min_score=min_score,
            max_score=max_score,
            exclude_approved=exclude_approved,
            exclude_rejected=exclude_rejected
        )

        for i, trader in enumerate(traders):
            if trader['address'] == address:
                return i + 1  # 1-based position

        return None
