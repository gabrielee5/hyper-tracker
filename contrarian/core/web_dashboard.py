"""
Web-based dashboard for contrarian signals using Flask.

Provides a real-time web interface showing bad trader positioning and contrarian signals.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional
from threading import Thread
from flask import Flask, render_template, jsonify
from flask_cors import CORS

logger = logging.getLogger(__name__)


class WebDashboard:
    """
    Web-based dashboard for contrarian signals.

    Provides REST API and serves HTML dashboard showing:
    - Overall statistics
    - Signal breakdown by coin
    - Count-based and size-weighted metrics
    - Real-time updates via polling
    """

    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 5000,
        priority_coins: List[str] = None
    ):
        """
        Initialize web dashboard.

        Args:
            host: Host address to bind to
            port: Port to listen on
            priority_coins: List of coin symbols to display first
        """
        self.host = host
        self.port = port
        self.priority_coins = priority_coins or []

        # State
        self.signals = []
        self.bad_traders_count = 0
        self.traders_with_positions = 0
        self.last_update = None

        # Create Flask app
        self.app = Flask(__name__,
                        template_folder='../templates',
                        static_folder='../static')
        CORS(self.app)

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup Flask routes."""

        @self.app.route('/')
        def index():
            """Serve main dashboard page."""
            return render_template('dashboard.html')

        @self.app.route('/api/signals')
        def get_signals():
            """Get current signals data."""
            return jsonify({
                'signals': self._sort_signals_with_priority(self.signals),
                'stats': {
                    'bad_traders_count': self.bad_traders_count,
                    'traders_with_positions': self.traders_with_positions,
                    'active_signals': len(self.signals),
                    'last_update': self.last_update.isoformat() if self.last_update else None
                }
            })

        @self.app.route('/api/health')
        def health():
            """Health check endpoint."""
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.now().isoformat()
            })

    def _sort_signals_with_priority(self, signals: List[Dict]) -> List[Dict]:
        """
        Sort signals with priority coins first, then by confidence.

        Args:
            signals: List of signal dictionaries

        Returns:
            Sorted list with priority coins at the top
        """
        if not self.priority_coins:
            return signals

        priority_signals = []
        other_signals = []

        for signal in signals:
            if signal['coin'] in self.priority_coins:
                priority_signals.append(signal)
            else:
                other_signals.append(signal)

        # Sort priority coins in the order specified in config
        priority_signals.sort(key=lambda s: self.priority_coins.index(s['coin']))

        # Combine: priority coins first, then all others sorted by confidence
        return priority_signals + other_signals

    def update_data(
        self,
        signals: List[Dict],
        bad_traders_count: int,
        traders_with_positions: int
    ):
        """
        Update dashboard data.

        Args:
            signals: List of signal dictionaries
            bad_traders_count: Total bad traders
            traders_with_positions: Traders with positions
        """
        self.signals = signals
        self.bad_traders_count = bad_traders_count
        self.traders_with_positions = traders_with_positions
        self.last_update = datetime.now()

        logger.debug(f"Dashboard data updated: {len(signals)} signals")

    def run(self):
        """Run the Flask web server."""
        logger.info(f"Starting web dashboard on http://{self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=False, use_reloader=False)

    def run_in_thread(self):
        """Run the Flask web server in a separate thread."""
        thread = Thread(target=self.run, daemon=True)
        thread.start()
        logger.info(f"Web dashboard running in background on http://{self.host}:{self.port}")
        return thread
