"""
Observer Dashboard - Main Entry Point

Trader review and approval system.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Ensure current directory is in path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.config import load_config
from dashboard.app import create_app


# Configure logging
def setup_logging(config):
    """Setup logging configuration."""
    log_file = config.get_log_file_absolute_path()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, config.logging.level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )


def main():
    """Main entry point."""
    logger = logging.getLogger(__name__)

    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = load_config()

        # Setup logging
        setup_logging(config)

        logger.info("="*60)
        logger.info("Observer Dashboard Starting")
        logger.info("="*60)
        logger.info(f"Dashboard URL: http://{config.dashboard.host}:{config.dashboard.port}")
        logger.info(f"Analyzed Traders DB: {config.get_analyzed_traders_db_absolute_path()}")
        logger.info(f"Approved Traders DB: {config.get_approved_traders_db_absolute_path()}")
        logger.info(f"Default View: {config.filters.default_view}")
        logger.info("")
        logger.info("Keyboard Shortcuts:")
        logger.info("  - Arrow Keys: Navigate")
        logger.info("  - A: Approve")
        logger.info("  - R: Reject")
        logger.info("  - 1: Best traders view")
        logger.info("  - 2: Worst traders view")
        logger.info("  - 3: All traders view")
        logger.info("="*60)

        # Create and run dashboard app
        app = create_app(config)

        # Handle graceful shutdown
        def signal_handler(sig, frame):
            logger.info("Shutting down Observer Dashboard...")
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Run the app
        app.run()

    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nMake sure you have created the config file at observer/config/config.yaml")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
