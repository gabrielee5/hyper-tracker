"""
Configuration loader for the paper trading simulator.
"""

import json
import os
from typing import Any, Dict


class Config:
    """Configuration manager for simulator settings."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.data = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            return json.load(f)

    # Portfolio settings
    @property
    def starting_capital(self) -> float:
        return self.data['portfolio']['starting_capital']

    @property
    def leverage(self) -> float:
        return self.data['portfolio']['leverage']

    @property
    def cash_reserve_pct(self) -> float:
        return self.data['portfolio']['cash_reserve_pct']

    @property
    def max_position_pct(self) -> float:
        return self.data['portfolio']['max_position_pct']

    # Strategy settings
    @property
    def rebalance_interval_seconds(self) -> int:
        return self.data['strategy']['rebalance_interval_seconds']

    @property
    def min_confidence_threshold(self) -> float:
        return self.data['strategy']['min_confidence_threshold']

    @property
    def max_positions(self) -> int:
        return self.data['strategy']['max_positions']

    @property
    def min_trade_size_usd(self) -> float:
        return self.data['strategy']['min_trade_size_usd']

    # Execution settings
    @property
    def maker_fee(self) -> float:
        return self.data['execution']['maker_fee']

    @property
    def taker_fee(self) -> float:
        return self.data['execution']['taker_fee']

    @property
    def slippage_model(self) -> Dict[str, Any]:
        return self.data['execution']['slippage_model']

    # Database settings
    @property
    def signals_db_path(self) -> str:
        return self.data['database']['signals_db']

    @property
    def simulator_db_path(self) -> str:
        return self.data['database']['simulator_db']

    # API settings
    @property
    def hyperliquid_rest(self) -> str:
        return self.data['api']['hyperliquid_rest']

    @property
    def price_update_interval_seconds(self) -> int:
        return self.data['api']['price_update_interval_seconds']

    # Dashboard settings
    @property
    def dashboard_port(self) -> int:
        return self.data['dashboard']['port']

    @property
    def dashboard_update_interval_seconds(self) -> int:
        return self.data['dashboard']['update_interval_seconds']

    @property
    def timezone(self) -> str:
        return self.data['dashboard']['timezone']

    # Logging settings
    @property
    def log_level(self) -> str:
        return self.data['logging']['level']

    @property
    def log_file(self) -> str:
        return self.data['logging']['file']

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by dot notation (e.g., 'portfolio.starting_capital')."""
        keys = key.split('.')
        value = self.data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
