#!/usr/bin/env python3
"""
Main entry point for the Paper Trading Simulator.
Starts both the simulator and the web dashboard.
"""

import sys
import time
import logging
import os
from pathlib import Path

# Add the script directory to Python path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))
os.chdir(script_dir)

from config import Config
from simulator import TradingSimulator
from dashboard import start_dashboard_thread

logger = logging.getLogger(__name__)


def main():
    """Main entry point."""
    print("=" * 80)
    print("PAPER TRADING SIMULATOR - Phase 4")
    print("=" * 80)
    print()

    try:
        # Load configuration
        config = Config("config.json")
        print(f"✓ Configuration loaded")
        print(f"  - Starting capital: ${config.starting_capital:,.2f}")
        print(f"  - Rebalance interval: {config.rebalance_interval_seconds}s")
        print(f"  - Min confidence: {config.min_confidence_threshold*100:.0f}%")
        print(f"  - Max positions: {config.max_positions}")
        print()

        # Initialize simulator
        print("Initializing simulator...")
        simulator = TradingSimulator()
        print("✓ Simulator initialized")
        print()

        # Start dashboard in background thread
        print("Starting web dashboard...")
        dashboard_thread = start_dashboard_thread(config, simulator)
        print(f"✓ Dashboard available at: http://localhost:{config.dashboard_port}")
        print()

        # Start simulator
        print("Starting trading simulator...")
        simulator.start()
        print()

        print("=" * 80)
        print("SIMULATOR IS NOW RUNNING")
        print("=" * 80)
        print()
        print(f"Dashboard: http://localhost:{config.dashboard_port}")
        print("Press Ctrl+C to stop")
        print()

        # Keep main thread alive
        while simulator.running:
            time.sleep(1)

    except KeyboardInterrupt:
        print()
        print("=" * 80)
        print("SHUTTING DOWN...")
        print("=" * 80)
        logger.info("Received shutdown signal (Ctrl+C)")

    except FileNotFoundError as e:
        print()
        print(f"ERROR: {e}")
        print()
        print("Make sure config.json exists and signals database is accessible.")
        sys.exit(1)

    except Exception as e:
        print()
        print(f"FATAL ERROR: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        if 'simulator' in locals():
            simulator.stop()

        print()
        print("Simulator stopped successfully")
        print("=" * 80)


if __name__ == "__main__":
    main()
