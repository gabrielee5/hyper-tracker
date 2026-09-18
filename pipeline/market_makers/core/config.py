"""Configuration management for market maker monitor."""

import json
import logging
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Dict, Any


logger = logging.getLogger(__name__)


@dataclass
class APIConfig:
    """API configuration."""
    base_url: str = "https://api.hyperliquid.xyz"
    rate_limit_calls: int = 15
    rate_limit_period: float = 1.0
    timeout: int = 10
    max_retries: int = 3


@dataclass
class DatabaseConfig:
    """Database paths."""
    analyzer_db_path: str = "../../data/analyzed_traders.db"
    local_db_path: str = "./data/mm_positions.db"


@dataclass
class MonitoringConfig:
    """Monitoring settings."""
    fetch_interval_seconds: int = 60
    position_snapshot_enabled: bool = True
    min_position_value_usd: float = 100.0
    concurrency_limit: int = 10
    min_mm_balance: float = 50000.0
    max_mm_age_hours: float = 24.0


@dataclass
class BiasAnalysisConfig:
    """Bias calculation settings."""
    neutral_threshold_percent: float = 10.0
    strong_bias_threshold_percent: float = 30.0
    weight_by_account_size: bool = False


@dataclass
class DashboardConfig:
    """Dashboard settings."""
    enabled: bool = True
    host: str = "localhost"
    port: int = 5003
    auto_refresh_seconds: int = 30
    timezone: str = "Europe/Rome"


@dataclass
class RetentionConfig:
    """Data retention settings."""
    position_snapshots_days: int = 7
    bias_history_days: int = 30


class MMMonitorConfig:
    """Central configuration for market maker monitor."""

    def __init__(self, config_path: str = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to config.json (defaults to ./config.json)
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.json"

        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self):
        """Load configuration from JSON."""
        if not self.config_path.exists():
            logger.warning(f"Config not found at {self.config_path}, using defaults")
            self._config = self._get_defaults()
            return

        try:
            with open(self.config_path, 'r') as f:
                self._config = json.load(f)
            logger.info(f"Configuration loaded from {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}, using defaults")
            self._config = self._get_defaults()

    def _get_defaults(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "analyzer_db_path": "../../data/analyzed_traders.db",
            "local_db_path": "./data/mm_positions.db",
            "api": {
                "base_url": "https://api.hyperliquid.xyz",
                "rate_limit_calls": 15,
                "rate_limit_period": 1.0,
                "timeout": 10,
                "max_retries": 3
            },
            "monitoring": {
                "fetch_interval_seconds": 60,
                "position_snapshot_enabled": True,
                "min_position_value_usd": 100,
                "concurrency_limit": 10,
                "min_mm_balance": 50000,
                "max_mm_age_hours": 24
            },
            "bias_analysis": {
                "neutral_threshold_percent": 10,
                "strong_bias_threshold_percent": 30,
                "weight_by_account_size": False
            },
            "dashboard": {
                "enabled": True,
                "host": "localhost",
                "port": 5003,
                "auto_refresh_seconds": 30,
                "timezone": "Europe/Rome"
            },
            "retention": {
                "position_snapshots_days": 7,
                "bias_history_days": 30
            }
        }

    @property
    def api(self) -> APIConfig:
        """API configuration."""
        api_cfg = self._config.get("api", {})
        return APIConfig(
            base_url=api_cfg.get("base_url", "https://api.hyperliquid.xyz"),
            rate_limit_calls=api_cfg.get("rate_limit_calls", 15),
            rate_limit_period=api_cfg.get("rate_limit_period", 1.0),
            timeout=api_cfg.get("timeout", 10),
            max_retries=api_cfg.get("max_retries", 3)
        )

    @property
    def database(self) -> DatabaseConfig:
        """Database configuration."""
        return DatabaseConfig(
            analyzer_db_path=self._config.get("analyzer_db_path", "../../data/analyzed_traders.db"),
            local_db_path=self._config.get("local_db_path", "./data/mm_positions.db")
        )

    @property
    def monitoring(self) -> MonitoringConfig:
        """Monitoring configuration."""
        mon_cfg = self._config.get("monitoring", {})
        return MonitoringConfig(
            fetch_interval_seconds=mon_cfg.get("fetch_interval_seconds", 60),
            position_snapshot_enabled=mon_cfg.get("position_snapshot_enabled", True),
            min_position_value_usd=mon_cfg.get("min_position_value_usd", 100),
            concurrency_limit=mon_cfg.get("concurrency_limit", 10),
            min_mm_balance=mon_cfg.get("min_mm_balance", 50000),
            max_mm_age_hours=mon_cfg.get("max_mm_age_hours", 24)
        )

    @property
    def bias_analysis(self) -> BiasAnalysisConfig:
        """Bias analysis configuration."""
        bias_cfg = self._config.get("bias_analysis", {})
        return BiasAnalysisConfig(
            neutral_threshold_percent=bias_cfg.get("neutral_threshold_percent", 10),
            strong_bias_threshold_percent=bias_cfg.get("strong_bias_threshold_percent", 30),
            weight_by_account_size=bias_cfg.get("weight_by_account_size", False)
        )

    @property
    def dashboard(self) -> DashboardConfig:
        """Dashboard configuration."""
        dash_cfg = self._config.get("dashboard", {})
        return DashboardConfig(
            enabled=dash_cfg.get("enabled", True),
            host=dash_cfg.get("host", "localhost"),
            port=dash_cfg.get("port", 5003),
            auto_refresh_seconds=dash_cfg.get("auto_refresh_seconds", 30),
            timezone=dash_cfg.get("timezone", "Europe/Rome")
        )

    @property
    def retention(self) -> RetentionConfig:
        """Data retention configuration."""
        ret_cfg = self._config.get("retention", {})
        return RetentionConfig(
            position_snapshots_days=ret_cfg.get("position_snapshots_days", 7),
            bias_history_days=ret_cfg.get("bias_history_days", 30)
        )

    def save(self):
        """Save current configuration to file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get_now(self) -> datetime:
        """Get current datetime with configured timezone."""
        return datetime.now(ZoneInfo(self.dashboard.timezone))

    def __repr__(self) -> str:
        return f"MMMonitorConfig(path={self.config_path})"
