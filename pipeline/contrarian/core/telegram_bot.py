"""
Simple Telegram bot for sending contrarian signal notifications.
"""

import logging
import requests
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Simple Telegram notifier for contrarian signals.

    Sends formatted messages with signal updates for watched coins.
    """

    def __init__(self, bot_token: str, chat_id: str, watched_coins: List[str]):
        """
        Initialize Telegram notifier.

        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID to send messages to
            watched_coins: List of coin symbols to monitor
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.watched_coins = [coin.upper() for coin in watched_coins]
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def send_signals(self, signals: List[Dict]) -> bool:
        """
        Send contrarian signals to Telegram.

        Args:
            signals: List of signal dictionaries

        Returns:
            True if message sent successfully, False otherwise
        """
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram bot token or chat_id not configured")
            return False

        # Filter signals for watched coins
        watched_signals = [
            s for s in signals
            if s['coin'] in self.watched_coins
        ]

        if not watched_signals:
            logger.debug("No signals for watched coins")
            return False

        # Format message
        message = self._format_message(watched_signals)

        # Send message
        try:
            response = requests.post(
                self.api_url,
                json={
                    'chat_id': self.chat_id,
                    'text': message,
                    'parse_mode': 'Markdown'
                },
                timeout=10
            )

            if response.status_code == 200:
                logger.info(f"Telegram message sent: {len(watched_signals)} signals")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def _format_message(self, signals: List[Dict]) -> str:
        """
        Format signals into a Telegram message.

        Args:
            signals: List of signal dictionaries

        Returns:
            Formatted message string
        """
        lines = ["*Contrarian Signals Update*\n"]

        for signal in signals:
            coin = signal['coin']
            direction = signal['signal_direction']
            confidence = signal['confidence_score']
            strength = signal['signal_strength']

            # Choose emoji based on direction
            emoji = "🟢" if direction == "LONG" else "🔴"

            # Format: 🟢 BTC LONG (0.85) STRONG
            line = f"{emoji} *{coin}* {direction} ({confidence:.2f})"
            if strength:
                line += f" _{strength}_"

            lines.append(line)

        return "\n".join(lines)
