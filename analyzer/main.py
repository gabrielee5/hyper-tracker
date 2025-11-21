"""
Main entry point for the Hyperliquid Trader Analyzer (Phase 2).

This analyzer runs independently from Phase 1 and performs statistical
analysis on trader performance to identify those performing significantly
worse than random chance.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.core.config import load_config
from analyzer.services.analyzer_service import AnalyzerService
from analyzer.dashboard.app import DashboardApp


# Global service instance for signal handling
service_instance = None
dashboard_thread = None


def setup_logging(config):
    """
    Set up logging configuration.

    Args:
        config: Configuration object
    """
    log_path = config.get_log_file_absolute_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # File handler (rotating)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=config.logging.max_bytes,
        backupCount=config.logging.backup_count
    )
    file_handler.setLevel(getattr(logging, config.logging.level))
    file_handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.logging.level))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Reduce noise from libraries
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    logging.info("=" * 60)
    logging.info("Hyperliquid Trader Analyzer - Phase 2")
    logging.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info("=" * 60)


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global service_instance

    logging.info(f"\nReceived signal {signum}, shutting down gracefully...")

    if service_instance:
        service_instance.stop()

    sys.exit(0)


async def run_analyzer(mode: str = 'continuous', limit: int = None):
    """
    Run the analyzer.

    Args:
        mode: 'continuous' or 'once'
        limit: Maximum number of traders to analyze (for 'once' mode)
    """
    global service_instance, dashboard_thread

    try:
        # Load configuration
        logging.info("Loading configuration...")
        config = load_config()

        # Create and initialize service
        logging.info("Initializing analyzer service...")
        service = AnalyzerService(config)
        service_instance = service
        await service.initialize()

        # Start dashboard if enabled
        if config.dashboard.enabled:
            logging.info("Starting web dashboard...")
            dashboard = DashboardApp(config, service.alert_service)
            dashboard_thread = dashboard.run_in_thread()
            logging.info(
                f"Dashboard available at http://{config.dashboard.host}:"
                f"{config.dashboard.port}"
            )

        # Run analyzer
        if mode == 'continuous':
            logging.info("Starting continuous analysis mode...")
            logging.info("Press Ctrl+C to stop")
            await service.run_continuous()
        else:
            logging.info(f"Running one-time analysis (limit: {limit or 'all'})...")
            await service.run_once(limit=limit)

    except KeyboardInterrupt:
        logging.info("\nKeyboard interrupt received")
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
    finally:
        if service_instance:
            logging.info("Shutting down analyzer service...")
            await service_instance.shutdown()

        logging.info("=" * 60)
        logging.info("Analyzer stopped")
        logging.info(f"Stopped at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logging.info("=" * 60)


def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Hyperliquid Trader Analyzer - Phase 2'
    )
    parser.add_argument(
        '--mode',
        choices=['continuous', 'once'],
        default='continuous',
        help='Analysis mode: continuous (default) or once'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Maximum number of traders to analyze (for once mode)'
    )
    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to config.yaml file'
    )

    args = parser.parse_args()

    # Load config first to set up logging
    try:
        config = load_config(args.config)
        setup_logging(config)
    except Exception as e:
        print(f"Error loading configuration: {e}")
        sys.exit(1)

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run analyzer
    try:
        asyncio.run(run_analyzer(mode=args.mode, limit=args.limit))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
