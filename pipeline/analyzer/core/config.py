"""
Configuration management for Phase 2 analyzer.

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
    max_retries: int
    retry_delay_on_429: int = 30  # Default 30 seconds for rate limit cooldown


@dataclass
class AnalysisConfig:
    """Analysis configuration."""
    min_trades: int
    p_value_threshold: float
    alert_score_threshold: int
    monte_carlo_iterations: int
    reanalysis_interval_days: int
    min_first_trade_age_days: int = 5  # Minimum age of first trade in days
    min_account_balance: float = 500  # Minimum account balance in USD


@dataclass
class DatabaseConfig:
    """Database configuration."""
    phase1_db_path: str
    phase2_db_path: str
    batch_size: int
    connection_timeout: int


@dataclass
class ProcessingConfig:
    """Processing configuration."""
    concurrent_traders: int
    batch_processing_interval: int
    priority_recent_active_days: int


@dataclass
class DashboardConfig:
    """Dashboard configuration."""
    enabled: bool
    host: str
    port: int
    auto_refresh_seconds: int
    timezone: str = "Europe/Rome"


@dataclass
class AlertsConfig:
    """Alerts configuration."""
    console_enabled: bool
    log_file_enabled: bool
    log_path: str
    dashboard_enabled: bool


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str
    file: str
    max_bytes: int
    backup_count: int


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
            self.analysis = AnalysisConfig(**data.get('analysis', {}))
            self.database = DatabaseConfig(**data.get('database', {}))
            self.processing = ProcessingConfig(**data.get('processing', {}))
            self.dashboard = DashboardConfig(**data.get('dashboard', {}))
            self.alerts = AlertsConfig(**data.get('alerts', {}))
            self.logging = LoggingConfig(**data.get('logging', {}))

            logger.info(f"Configuration loaded from {self.config_path}")

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise

    def get_phase1_db_absolute_path(self) -> Path:
        """
        Get absolute path to Phase 1 database.

        Returns:
            Absolute Path object
        """
        path = Path(self.database.phase1_db_path)

        if not path.is_absolute():
            # Make relative to analyzer directory (parent of config)
            analyzer_dir = self.config_path.parent.parent
            path = (analyzer_dir / path).resolve()

        return path

    def get_phase2_db_absolute_path(self) -> Path:
        """
        Get absolute path to Phase 2 database.

        Returns:
            Absolute Path object
        """
        path = Path(self.database.phase2_db_path)

        if not path.is_absolute():
            # Make relative to analyzer directory (parent of config)
            analyzer_dir = self.config_path.parent.parent
            path = (analyzer_dir / path).resolve()

        return path

    def get_log_file_absolute_path(self) -> Path:
        """
        Get absolute path to log file.

        Returns:
            Absolute Path object
        """
        path = Path(self.logging.file)

        if not path.is_absolute():
            # Make relative to analyzer directory (parent of config)
            analyzer_dir = self.config_path.parent.parent
            path = (analyzer_dir / path).resolve()

        return path

    def get_alert_log_absolute_path(self) -> Path:
        """
        Get absolute path to alert log file.

        Returns:
            Absolute Path object
        """
        path = Path(self.alerts.log_path)

        if not path.is_absolute():
            # Make relative to analyzer directory (parent of config)
            analyzer_dir = self.config_path.parent.parent
            path = (analyzer_dir / path).resolve()

        return path

    def validate(self):
        """
        Validate configuration values.

        Raises:
            ValueError: If configuration is invalid
        """
        # Validate analysis parameters
        if self.analysis.min_trades < 1:
            raise ValueError("min_trades must be at least 1")

        if not (0 < self.analysis.p_value_threshold < 1):
            raise ValueError("p_value_threshold must be between 0 and 1")

        if not (0 <= self.analysis.alert_score_threshold <= 100):
            raise ValueError("alert_score_threshold must be between 0 and 100")

        if self.analysis.monte_carlo_iterations < 100:
            raise ValueError("monte_carlo_iterations should be at least 100")

        # Validate processing parameters
        if self.processing.concurrent_traders < 1:
            raise ValueError("concurrent_traders must be at least 1")

        # Validate API parameters
        if self.api.rate_limit_calls < 1:
            raise ValueError("rate_limit_calls must be at least 1")

        # Validate database paths
        phase1_path = self.get_phase1_db_absolute_path()
        if not phase1_path.exists():
            logger.warning(
                f"Phase 1 database not found at {phase1_path}. "
                "Make sure Phase 1 is running and has created the database."
            )

        logger.info("Configuration validation passed")

    def __repr__(self) -> str:
        """String representation of configuration."""
        return f"Config(api={self.api}, analysis={self.analysis})"


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
