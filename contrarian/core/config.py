"""
Configuration management for contrarian signal system.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


logger = logging.getLogger(__name__)


@dataclass
class SignalThresholds:
    """Signal strength thresholds."""
    strong: float = 0.70
    moderate: float = 0.60


@dataclass
class APIConfig:
    """API configuration."""
    base_url: str = "https://api.hyperliquid.xyz"
    rate_limit_calls: int = 15
    rate_limit_period: float = 1.0
    timeout: int = 10
    max_retries: int = 3
    concurrency_limit: int = 10


@dataclass
class DatabaseConfig:
    """Database paths."""
    phase2_path: str = "../data/analyzed_traders.db"
    contrarian_path: str = "../data/contrarian_signals.db"


@dataclass
class DashboardConfig:
    """Dashboard display settings."""
    refresh_rate: int = 5
    show_size_weighted: bool = True
    top_signals_limit: int = 15
    enable_colors: bool = True
    priority_coins: list = None
    timezone: str = "Europe/Rome"

    def __post_init__(self):
        if self.priority_coins is None:
            self.priority_coins = []


class ConrarianConfig:
    """
    Central configuration for the contrarian signal system.

    Loads from config.json and provides typed access to all settings.
    """

    def __init__(self, config_path: str = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to config.json (defaults to ./contrarian/config.json)
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config.json"

        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}

        self.load()

    def load(self):
        """Load configuration from JSON file."""
        if not self.config_path.exists():
            logger.warning(f"Config file not found at {self.config_path}, using defaults")
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
            "bad_trader_score_threshold": 5,
            "min_traders_for_signal": 10,
            "signal_thresholds": {
                "strong": 0.70,
                "moderate": 0.60
            },
            "update_interval_seconds": 90,
            "api": {
                "base_url": "https://api.hyperliquid.xyz",
                "rate_limit_calls": 15,
                "rate_limit_period": 1.0,
                "timeout": 10,
                "max_retries": 3,
                "concurrency_limit": 10
            },
            "database": {
                "phase2_path": "../data/analyzed_traders.db",
                "contrarian_path": "../data/contrarian_signals.db"
            },
            "dashboard": {
                "refresh_rate": 5,
                "show_size_weighted": True,
                "top_signals_limit": 15,
                "enable_colors": True,
                "priority_coins": [],
                "timezone": "Europe/Rome"
            }
        }

    @property
    def bad_trader_score_threshold(self) -> int:
        """Score threshold for identifying bad traders (default: 5)."""
        return self._config.get("bad_trader_score_threshold", 5)

    @property
    def min_traders_for_signal(self) -> int:
        """Minimum number of traders required to generate a signal (default: 10)."""
        return self._config.get("min_traders_for_signal", 10)

    @property
    def update_interval_seconds(self) -> int:
        """How often to poll for position updates (default: 90 seconds)."""
        return self._config.get("update_interval_seconds", 90)

    @property
    def signal_thresholds(self) -> SignalThresholds:
        """Signal strength thresholds."""
        thresholds = self._config.get("signal_thresholds", {})
        return SignalThresholds(
            strong=thresholds.get("strong", 0.70),
            moderate=thresholds.get("moderate", 0.60)
        )

    @property
    def api(self) -> APIConfig:
        """API configuration."""
        api_config = self._config.get("api", {})
        return APIConfig(
            base_url=api_config.get("base_url", "https://api.hyperliquid.xyz"),
            rate_limit_calls=api_config.get("rate_limit_calls", 15),
            rate_limit_period=api_config.get("rate_limit_period", 1.0),
            timeout=api_config.get("timeout", 10),
            max_retries=api_config.get("max_retries", 3),
            concurrency_limit=api_config.get("concurrency_limit", 10)
        )

    @property
    def database(self) -> DatabaseConfig:
        """Database configuration."""
        db_config = self._config.get("database", {})
        return DatabaseConfig(
            phase2_path=db_config.get("phase2_path", "../data/analyzed_traders.db"),
            contrarian_path=db_config.get("contrarian_path", "../data/contrarian_signals.db")
        )

    @property
    def dashboard(self) -> DashboardConfig:
        """Dashboard configuration."""
        dash_config = self._config.get("dashboard", {})
        return DashboardConfig(
            refresh_rate=dash_config.get("refresh_rate", 5),
            show_size_weighted=dash_config.get("show_size_weighted", True),
            top_signals_limit=dash_config.get("top_signals_limit", 15),
            enable_colors=dash_config.get("enable_colors", True),
            priority_coins=dash_config.get("priority_coins", []),
            timezone=dash_config.get("timezone", "Europe/Rome")
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
        return f"ConrarianConfig(path={self.config_path})"
