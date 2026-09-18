"""Configuration management for Hyperliquid Tracker."""

import os
from typing import List, Optional
from pathlib import Path
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config(BaseModel):
    """Application configuration."""

    # Hyperliquid Configuration
    network: str = Field(default="mainnet")
    api_url: str = Field(default="https://api.hyperliquid.xyz")
    ws_url: str = Field(default="wss://api.hyperliquid.xyz/ws")

    # Tracking Configuration
    track_all_coins: bool = Field(default=False)
    selected_coins: List[str] = Field(default_factory=list)
    track_role: str = Field(default="both")  # DEPRECATED: always tracks 'both' (public trade data lacks taker/maker info)

    # Database Configuration
    database_path: Path = Field(default=Path("../data/addresses.db"))

    # Batch Processing
    batch_size: int = Field(default=1000)
    dedup_interval: int = Field(default=60)

    # Web Dashboard
    dashboard_enabled: bool = Field(default=True)
    dashboard_port: int = Field(default=5000)
    dashboard_host: str = Field(default="0.0.0.0")

    # Logging
    log_level: str = Field(default="INFO")
    log_file: Path = Field(default=Path("logs/tracker.log"))

    # Timezone
    timezone: str = Field(default="Europe/Rome")

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""

        # Parse network configuration
        network = os.getenv("NETWORK", "mainnet").lower()

        # Set API URLs based on network
        if network == "testnet":
            api_url = "https://api.hyperliquid-testnet.xyz"
            ws_url = "wss://api.hyperliquid-testnet.xyz/ws"
        else:
            api_url = "https://api.hyperliquid.xyz"
            ws_url = "wss://api.hyperliquid.xyz/ws"

        # Parse tracking configuration
        track_all_coins = os.getenv("TRACK_ALL_COINS", "false").lower() == "true"
        selected_coins_str = os.getenv("SELECTED_COINS", "BTC,ETH,SOL,ARB")
        selected_coins = [coin.strip() for coin in selected_coins_str.split(",") if coin.strip()]
        track_role = os.getenv("TRACK_ROLE", "both").lower()

        # Note: track_role is deprecated and ignored - always tracks both addresses
        # Kept for backward compatibility only
        if track_role not in ["maker", "taker", "both"]:
            raise ValueError(f"Invalid TRACK_ROLE: {track_role}. Must be 'maker', 'taker', or 'both'")

        # Parse paths
        database_path = Path(os.getenv("DATABASE_PATH", "../data/addresses.db"))
        log_file = Path(os.getenv("LOG_FILE", "logs/tracker.log"))

        # Parse numeric values
        batch_size = int(os.getenv("BATCH_SIZE", "1000"))
        dedup_interval = int(os.getenv("DEDUP_INTERVAL", "60"))

        # Parse dashboard configuration
        dashboard_enabled = os.getenv("DASHBOARD_ENABLED", "true").lower() == "true"
        dashboard_port = int(os.getenv("DASHBOARD_PORT", "5000"))
        dashboard_host = os.getenv("DASHBOARD_HOST", "0.0.0.0")

        # Parse logging
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()

        # Parse timezone
        timezone = os.getenv("TIMEZONE", "Europe/Rome")

        return cls(
            network=network,
            api_url=api_url,
            ws_url=ws_url,
            track_all_coins=track_all_coins,
            selected_coins=selected_coins,
            track_role=track_role,
            database_path=database_path,
            batch_size=batch_size,
            dedup_interval=dedup_interval,
            dashboard_enabled=dashboard_enabled,
            dashboard_port=dashboard_port,
            dashboard_host=dashboard_host,
            log_level=log_level,
            log_file=log_file,
            timezone=timezone,
        )

    def get_coins_to_track(self, available_coins: List[str]) -> List[str]:
        """
        Get the list of coins to track based on configuration.

        Args:
            available_coins: List of all available coins from the exchange

        Returns:
            List of coin symbols to track
        """
        if self.track_all_coins:
            return available_coins
        else:
            # Validate that selected coins are available
            valid_coins = []
            for coin in self.selected_coins:
                if coin in available_coins:
                    valid_coins.append(coin)
            return valid_coins
