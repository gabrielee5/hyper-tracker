"""
Configuration management for Observer dashboard.

Loads configuration from YAML file and provides type-safe access.
"""

import yaml
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class APIConfig:
    """API configuration."""
    base_url: str
    rate_limit_calls: int
    rate_limit_period: float
    timeout: int
    cache_ttl_seconds: int


@dataclass
class DatabaseConfig:
    """Database configuration."""
    analyzed_traders_db: str  # Path to Phase 2 database (read-only)
    approved_traders_db: str  # Path to Observer database (read/write)
    connection_timeout: int


@dataclass
class DashboardConfig:
    """Dashboard configuration."""
    host: str
    port: int


@dataclass
class FiltersConfig:
    """Filter configuration."""
    best_traders_min_score: int
    best_traders_max_score: int
    worst_traders_min_score: int
    worst_traders_max_score: int
    default_view: str  # 'best', 'worst', or 'all'


@dataclass
class ReviewConfig:
    """Review workflow configuration."""
    enable_rejection_log: bool
    auto_advance_after_action: bool


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str
    file: str


class Config:
    """
    Main configuration class.

    Loads and validates configuration from YAML file.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to config.yaml file. If None, uses default location.
        """
        if config_path is None:
            # Default to config/config.yaml relative to this file
            config_dir = Path(__file__).parent.parent / "config"
            config_path = config_dir / "config.yaml"

        self.config_path = Path(config_path)

        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        self._load_config()

    def _load_config(self):
        """Load and parse configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f)

            # Parse each section
            self.api = APIConfig(**data.get('api', {}))
            self.database = DatabaseConfig(**data.get('database', {}))
            self.dashboard = DashboardConfig(**data.get('dashboard', {}))
            self.filters = FiltersConfig(**data.get('filters', {}))
            self.review = ReviewConfig(**data.get('review', {}))
            self.logging = LoggingConfig(**data.get('logging', {}))

            logger.info(f"Configuration loaded from {self.config_path}")

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def get_analyzed_traders_db_absolute_path(self) -> Path:
        """
        Get absolute path to analyzed_traders.db (Phase 2 database).

        Returns:
            Absolute Path object
        """
        path = Path(self.database.analyzed_traders_db)

        if not path.is_absolute():
            # Make relative to observer directory (parent of config)
            observer_dir = self.config_path.parent.parent
            path = (observer_dir / path).resolve()

        return path

    def get_approved_traders_db_absolute_path(self) -> Path:
        """
        Get absolute path to approved_traders.db (Observer database).

        Returns:
            Absolute Path object
        """
        path = Path(self.database.approved_traders_db)

        if not path.is_absolute():
            # Make relative to observer directory (parent of config)
            observer_dir = self.config_path.parent.parent
            path = (observer_dir / path).resolve()

        return path

    def get_log_file_absolute_path(self) -> Path:
        """
        Get absolute path to log file.

        Returns:
            Absolute Path object
        """
        path = Path(self.logging.file)

        if not path.is_absolute():
            # Make relative to observer directory (parent of config)
            observer_dir = self.config_path.parent.parent
            path = (observer_dir / path).resolve()

        return path

    def validate(self):
        """
        Validate configuration values.

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate filters
        if not (0 <= self.filters.best_traders_min_score <= 100):
            raise ValueError("best_traders_min_score must be between 0 and 100")

        if not (0 <= self.filters.best_traders_max_score <= 100):
            raise ValueError("best_traders_max_score must be between 0 and 100")

        if not (0 <= self.filters.worst_traders_min_score <= 100):
            raise ValueError("worst_traders_min_score must be between 0 and 100")

        if not (0 <= self.filters.worst_traders_max_score <= 100):
            raise ValueError("worst_traders_max_score must be between 0 and 100")

        if self.filters.best_traders_min_score > self.filters.best_traders_max_score:
            raise ValueError("best_traders_min_score cannot be greater than best_traders_max_score")

        if self.filters.worst_traders_min_score > self.filters.worst_traders_max_score:
            raise ValueError("worst_traders_min_score cannot be greater than worst_traders_max_score")

        if self.filters.default_view not in ['best', 'worst', 'all']:
            raise ValueError("default_view must be 'best', 'worst', or 'all'")

        # Validate API parameters
        if self.api.rate_limit_calls < 1:
            raise ValueError("rate_limit_calls must be at least 1")

        if self.api.cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds must be non-negative")

        # Validate database paths
        analyzed_db_path = self.get_analyzed_traders_db_absolute_path()
        if not analyzed_db_path.exists():
            logger.warning(
                f"analyzed_traders.db not found at {analyzed_db_path}. "
                "Make sure the analyzer has run and created the database."
            )

        logger.info("Configuration validation passed")

    def __repr__(self) -> str:
        """String representation of configuration."""
        return f"Config(api={self.api}, filters={self.filters})"


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from file.

    Args:
        config_path: Path to config.yaml file

    Returns:
        Config object
    """
    config = Config(config_path)
    config.validate()
    return config
