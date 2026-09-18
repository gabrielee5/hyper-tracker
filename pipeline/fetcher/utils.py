"""Utility functions and logging setup."""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(log_level: str, log_file: Path):
    """
    Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Path to log file
    """
    # Create logs directory if it doesn't exist
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )

    # Setup file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_handler.setFormatter(console_formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Reduce noise from hyperliquid SDK
    logging.getLogger("hyperliquid").setLevel(logging.WARNING)
    logging.getLogger("websocket").setLevel(logging.WARNING)

    logging.info(f"Logging initialized - Level: {log_level}, File: {log_file}")


def format_number(num: float, decimals: int = 2) -> str:
    """
    Format a number with thousands separators.

    Args:
        num: Number to format
        decimals: Number of decimal places

    Returns:
        Formatted string
    """
    if num >= 1_000_000:
        return f"{num / 1_000_000:.{decimals}f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.{decimals}f}K"
    else:
        return f"{num:.{decimals}f}"


def format_address(address: str, chars: int = 6) -> str:
    """
    Format an address for display (e.g., 0x1234...5678).

    Args:
        address: Full address
        chars: Number of characters to show on each side

    Returns:
        Shortened address
    """
    if len(address) <= chars * 2:
        return address
    return f"{address[:chars]}...{address[-chars:]}"


def calculate_uptime(start_time: datetime) -> str:
    """
    Calculate uptime from start time.

    Args:
        start_time: When the application started (timezone-aware datetime)

    Returns:
        Formatted uptime string
    """
    # Use the same timezone as start_time for consistency
    current_time = datetime.now(start_time.tzinfo) if start_time.tzinfo else datetime.now()
    delta = current_time - start_time
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if delta.days > 0:
        return f"{delta.days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m {seconds}s"
