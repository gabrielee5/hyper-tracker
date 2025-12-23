"""
Main analyzer service orchestrating trader analysis.

Coordinates API fetching, statistical analysis, database storage,
and alerting with parallel processing.
"""

import asyncio
import logging
from typing import List, Optional, Set
from datetime import datetime, timedelta

from ..core.api_client import HyperliquidAPIClient, FillsCache, HyperliquidAPIError
from ..core.statistics import StatisticalAnalyzer
from ..core.database import AnalyzerDatabase, Phase1DatabaseReader, AnalyzerDatabaseReader
from ..core.config import Config
from .alert_service import AlertService


logger = logging.getLogger(__name__)


class AnalyzerService:
    """
    Main service for analyzing trader performance.

    Orchestrates the entire analysis pipeline:
    1. Read addresses from Phase 1 database
    2. Fetch trade history from Hyperliquid API
    3. Perform statistical analysis
    4. Save results to Phase 2 database
    5. Trigger alerts for bad traders
    """

    def __init__(self, config: Config):
        """
        Initialize analyzer service.

        Args:
            config: Configuration object
        """
        self.config = config

        # Initialize components
        self.api_client = HyperliquidAPIClient(
            base_url=config.api.base_url,
            rate_limit_calls=config.api.rate_limit_calls,
            rate_limit_period=config.api.rate_limit_period,
            timeout=config.api.timeout,
            max_retries=config.api.max_retries
        )

        self.analyzer = StatisticalAnalyzer(
            min_trades=config.analysis.min_trades,
            p_value_threshold=config.analysis.p_value_threshold,
            monte_carlo_iterations=config.analysis.monte_carlo_iterations
        )

        self.database = AnalyzerDatabase(
            db_path=str(config.get_phase2_db_absolute_path()),
            connection_timeout=config.database.connection_timeout,
            timezone=config.dashboard.timezone
        )

        self.phase1_db = Phase1DatabaseReader(
            db_path=str(config.get_phase1_db_absolute_path())
        )

        self.phase2_db_reader = AnalyzerDatabaseReader(
            db_path=str(config.get_phase2_db_absolute_path())
        )

        self.alert_service = AlertService(
            score_threshold=config.analysis.alert_score_threshold,
            console_enabled=config.alerts.console_enabled,
            log_file_enabled=config.alerts.log_file_enabled,
            log_file_path=str(config.get_alert_log_absolute_path()),
            dashboard_enabled=config.alerts.dashboard_enabled,
            timezone=config.dashboard.timezone
        )

        # Cache for API responses
        self.fills_cache = FillsCache(ttl_seconds=300)

        # Statistics
        self.stats = {
            'total_analyzed': 0,
            'successful': 0,
            'insufficient_data': 0,
            'api_errors': 0,
            'alerts_triggered': 0
        }

        # Running state
        self.is_running = False
        self._background_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize the service (create database tables, etc.)."""
        await self.database.initialize()
        logger.info("Analyzer service initialized")

    async def analyze_trader(self, address: str) -> bool:
        """
        Analyze a single trader.

        Args:
            address: Trader's Ethereum address

        Returns:
            True if analysis succeeded, False otherwise
        """
        try:
            # Check cache first
            fills = self.fills_cache.get(address)

            if fills is None:
                # Fetch from API
                fills = await self.api_client.fetch_user_fills(address)
                self.fills_cache.set(address, fills)

            # Log the fetch
            await self.database.log_analysis(
                address=address,
                status='fetched',
                trades_fetched=len(fills)
            )

            # Check if sufficient data
            if len(fills) < self.config.analysis.min_trades:
                logger.info(
                    f"Insufficient data for {self._shorten_address(address)}: "
                    f"{len(fills)} trades (need {self.config.analysis.min_trades})"
                )
                self.stats['insufficient_data'] += 1
                await self.database.log_analysis(
                    address=address,
                    status='insufficient_data',
                    trades_fetched=len(fills)
                )
                return False

            # Check if first trade is at least min_first_trade_age_days old
            # Do this BEFORE statistical analysis to save computation
            first_trade_time = self._extract_first_trade_time(fills)
            if first_trade_time is not None:
                current_time_ms = int(datetime.utcnow().timestamp() * 1000)
                min_age_days = self.config.analysis.min_first_trade_age_days
                min_age_ms = min_age_days * 24 * 60 * 60 * 1000  # Convert days to milliseconds
                first_trade_age_ms = current_time_ms - first_trade_time

                if first_trade_age_ms < min_age_ms:
                    days_old = first_trade_age_ms / (24 * 60 * 60 * 1000)
                    logger.info(
                        f"First trade too recent for {self._shorten_address(address)}: "
                        f"{days_old:.1f} days old (need {min_age_days} days)"
                    )
                    self.stats['insufficient_data'] += 1
                    await self.database.log_analysis(
                        address=address,
                        status='first_trade_too_recent',
                        trades_fetched=len(fills)
                    )
                    return False

            # Fetch account balance BEFORE statistical analysis to save computation
            # Do this early to filter out accounts with insufficient balance
            account_balance = None
            try:
                user_state = await self.api_client.fetch_user_state(address)
                logger.debug(f"User state keys: {list(user_state.keys()) if isinstance(user_state, dict) else 'Not a dict'}")

                # Extract account value from user state
                if isinstance(user_state, dict) and 'marginSummary' in user_state:
                    account_value = user_state['marginSummary'].get('accountValue')
                    if account_value is not None:
                        account_balance = float(account_value)
                        logger.info(f"Fetched balance for {self._shorten_address(address)}: ${account_balance:,.2f}")
                    else:
                        logger.debug(f"accountValue is None in marginSummary for {self._shorten_address(address)}")
                else:
                    logger.debug(f"marginSummary not found in user state for {self._shorten_address(address)}")
            except Exception as e:
                logger.warning(f"Failed to fetch account balance for {self._shorten_address(address)}: {e}")
                # Continue without balance - it's optional

            # Check minimum account balance BEFORE statistical analysis
            if account_balance is not None:
                if account_balance < self.config.analysis.min_account_balance:
                    logger.info(
                        f"Insufficient account balance for {self._shorten_address(address)}: "
                        f"${account_balance:,.2f} (need ${self.config.analysis.min_account_balance:,.2f})"
                    )
                    self.stats['insufficient_data'] += 1
                    await self.database.log_analysis(
                        address=address,
                        status='insufficient_balance',
                        trades_fetched=len(fills)
                    )
                    return False

            # NOW perform statistical analysis (only if all filters passed)
            metrics = self.analyzer.analyze_trader(fills)

            if metrics is None:
                self.stats['insufficient_data'] += 1
                await self.database.log_analysis(
                    address=address,
                    status='insufficient_data',
                    trades_fetched=len(fills)
                )
                return False

            # Attach account balance to metrics
            metrics.account_balance = account_balance

            # Save to database
            await self.database.save_trader_analysis(address, metrics)

            # Check for alerts
            if self.alert_service.should_alert(metrics):
                await self.alert_service.trigger_alert(address, metrics)
                self.stats['alerts_triggered'] += 1

            # Update statistics
            self.stats['successful'] += 1
            await self.database.log_analysis(
                address=address,
                status='success',
                trades_fetched=len(fills)
            )

            logger.info(
                f"✓ Analyzed {self._shorten_address(address)}: "
                f"score={metrics.score}, trades={metrics.num_trades}"
            )

            return True

        except HyperliquidAPIError as e:
            logger.error(f"API error for {self._shorten_address(address)}: {e}")
            self.stats['api_errors'] += 1
            await self.database.log_analysis(
                address=address,
                status='api_error',
                error_message=str(e)
            )
            return False

        except Exception as e:
            logger.error(
                f"Unexpected error analyzing {self._shorten_address(address)}: {e}",
                exc_info=True
            )
            self.stats['api_errors'] += 1
            await self.database.log_analysis(
                address=address,
                status='error',
                error_message=str(e)
            )
            return False

        finally:
            self.stats['total_analyzed'] += 1

    async def analyze_batch(self, addresses: List[str]) -> dict:
        """
        Analyze a batch of traders in parallel.

        Args:
            addresses: List of Ethereum addresses

        Returns:
            Dictionary with batch analysis results
        """
        logger.info(f"Analyzing batch of {len(addresses)} traders...")

        # Analyze with concurrency limit
        semaphore = asyncio.Semaphore(self.config.processing.concurrent_traders)

        async def analyze_with_semaphore(addr: str) -> bool:
            async with semaphore:
                return await self.analyze_trader(addr)

        # Run all analyses concurrently
        tasks = [analyze_with_semaphore(addr) for addr in addresses]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes
        successful = sum(1 for r in results if r is True)

        logger.info(
            f"Batch complete: {successful}/{len(addresses)} successful"
        )

        return {
            'total': len(addresses),
            'successful': successful,
            'failed': len(addresses) - successful
        }

    async def get_addresses_to_analyze(
        self,
        limit: Optional[int] = None
    ) -> List[str]:
        """
        Get list of addresses that need analysis.

        Prioritizes:
        1. New addresses (never analyzed)
        2. Recently active addresses
        3. Stale analyses (> reanalysis_interval_days old)

        Args:
            limit: Maximum number of addresses to return

        Returns:
            List of addresses to analyze
        """
        addresses_to_analyze: Set[str] = set()

        # Get all addresses from Phase 1
        all_addresses = await self.phase1_db.get_all_addresses()
        logger.info(f"Found {len(all_addresses)} total addresses in Phase 1")

        # Get recently active addresses (priority)
        recently_active = await self.phase1_db.get_recently_active_addresses(
            days=self.config.processing.priority_recent_active_days,
            limit=limit
        )
        recently_active_addrs = [addr for addr, _ in recently_active]
        logger.info(f"Found {len(recently_active_addrs)} recently active addresses")

        # Get already analyzed addresses (to exclude from new analysis)
        already_analyzed = await self.phase2_db_reader.get_all_analyzed_addresses()
        logger.info(f"Found {len(already_analyzed)} already analyzed addresses")

        # Get stale analyses (these need re-analysis even though already analyzed)
        stale_addresses = await self.database.get_stale_analyses(
            days_old=self.config.analysis.reanalysis_interval_days,
            limit=limit
        )
        stale_set = set(stale_addresses)
        logger.info(f"Found {len(stale_addresses)} stale analyses")

        # Priority 1: Recently active addresses (only if new or stale)
        for addr in recently_active_addrs:
            if addr not in already_analyzed or addr in stale_set:
                addresses_to_analyze.add(addr)

        # Priority 2: Stale analyses (these need re-analysis)
        addresses_to_analyze.update(stale_addresses)

        # Priority 3: Random sample of remaining addresses (exclude already analyzed)
        if limit and len(addresses_to_analyze) < limit:
            remaining = limit - len(addresses_to_analyze)
            import random
            unanalyzed = [
                addr for addr in all_addresses
                if addr not in addresses_to_analyze and addr not in already_analyzed
            ]
            if unanalyzed:
                sample_size = min(remaining, len(unanalyzed))
                sample = random.sample(unanalyzed, sample_size)
                addresses_to_analyze.update(sample)
                logger.info(f"Added {len(sample)} new unanalyzed addresses")

        result = list(addresses_to_analyze)
        if limit:
            result = result[:limit]

        return result

    async def run_continuous(self):
        """
        Run analyzer continuously in the background.

        Processes batches of traders at regular intervals.
        """
        self.is_running = True
        logger.info("Starting continuous analysis mode...")

        while self.is_running:
            try:
                # Get addresses to analyze
                addresses = await self.get_addresses_to_analyze(
                    limit=self.config.database.batch_size
                )

                if not addresses:
                    logger.info("No addresses to analyze, waiting...")
                    await asyncio.sleep(60)
                    continue

                # Analyze batch
                await self.analyze_batch(addresses)

                # Log statistics
                self._log_statistics()

                # Wait before next batch
                logger.info(
                    f"Waiting {self.config.processing.batch_processing_interval}s "
                    "before next batch..."
                )
                await asyncio.sleep(self.config.processing.batch_processing_interval)

            except Exception as e:
                logger.error(f"Error in continuous analysis loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retrying

    async def run_once(self, limit: Optional[int] = None):
        """
        Run analyzer once and exit.

        Args:
            limit: Maximum number of traders to analyze
        """
        logger.info("Running one-time analysis...")

        addresses = await self.get_addresses_to_analyze(limit=limit)

        if not addresses:
            logger.info("No addresses to analyze")
            return

        await self.analyze_batch(addresses)
        self._log_statistics()

    def stop(self):
        """Stop continuous analysis."""
        logger.info("Stopping analyzer service...")
        self.is_running = False

        if self._background_task:
            self._background_task.cancel()

    async def shutdown(self):
        """Shutdown the service and cleanup resources."""
        self.stop()
        await self.api_client.close()
        logger.info("Analyzer service shut down")

    def _log_statistics(self):
        """Log current statistics."""
        logger.info("=" * 60)
        logger.info("Analyzer Statistics:")
        logger.info(f"  Total analyzed:    {self.stats['total_analyzed']}")
        logger.info(f"  Successful:        {self.stats['successful']}")
        logger.info(f"  Insufficient data: {self.stats['insufficient_data']}")
        logger.info(f"  API errors:        {self.stats['api_errors']}")
        logger.info(f"  Alerts triggered:  {self.stats['alerts_triggered']}")
        logger.info(f"  Cache size:        {self.fills_cache.size()}")
        logger.info("=" * 60)

    def get_statistics(self) -> dict:
        """
        Get current statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            **self.stats,
            'cache_size': self.fills_cache.size(),
            'alert_count': self.alert_service.get_alert_count()
        }

    def _shorten_address(self, address: str) -> str:
        """Shorten address for logging."""
        if len(address) > 10:
            return f"{address[:6]}...{address[-4:]}"
        return address

    def _extract_first_trade_time(self, fills: List[dict]) -> Optional[int]:
        """
        Extract the timestamp of the first (oldest) trade from fills.

        Args:
            fills: List of fill dictionaries

        Returns:
            Timestamp in milliseconds of the first trade, or None if no valid timestamps
        """
        if not fills:
            return None

        oldest_time = None
        for fill in fills:
            if 'time' in fill and fill['time'] is not None:
                try:
                    time_ms = int(fill['time'])
                    if oldest_time is None or time_ms < oldest_time:
                        oldest_time = time_ms
                except (ValueError, TypeError):
                    continue

        return oldest_time


async def main():
    """Example usage of the analyzer service."""
    from ..core.config import load_config

    # Load configuration
    config = load_config()

    # Create and initialize service
    service = AnalyzerService(config)
    await service.initialize()

    try:
        # Run once
        await service.run_once(limit=10)

        # Or run continuously
        # await service.run_continuous()

    finally:
        await service.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
