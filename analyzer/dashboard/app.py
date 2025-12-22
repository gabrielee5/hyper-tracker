"""
Web dashboard for monitoring trader analysis.

Provides real-time view of:
- Analysis statistics
- Recent alerts
- Score distribution
- Worst performers
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
import asyncio
import logging
from typing import Optional
from threading import Thread
import os

from ..core.config import Config
from ..core.database import AnalyzerDatabase
from ..services.alert_service import AlertService


logger = logging.getLogger(__name__)


class DashboardApp:
    """Flask dashboard application."""

    def __init__(self, config: Config, alert_service: AlertService):
        """
        Initialize dashboard app.

        Args:
            config: Configuration object
            alert_service: Alert service for recent alerts
        """
        self.config = config
        self.alert_service = alert_service

        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_dir = os.path.join(current_dir, 'templates')

        # Create Flask app with template directory
        self.app = Flask(__name__, template_folder=template_dir)
        CORS(self.app)

        # Database connection
        self.database = AnalyzerDatabase(
            db_path=str(config.get_phase2_db_absolute_path()),
            connection_timeout=config.database.connection_timeout
        )

        # Register routes
        self._register_routes()

    def _register_routes(self):
        """Register Flask routes."""

        @self.app.route('/')
        def index():
            """Main dashboard page."""
            return render_template(
                'dashboard.html',
                refresh_seconds=self.config.dashboard.auto_refresh_seconds
            )

        @self.app.route('/api/stats')
        def get_stats():
            """Get overall statistics."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                stats = loop.run_until_complete(self.database.get_statistics())
                return jsonify(stats)
            finally:
                loop.close()

        @self.app.route('/api/alerts')
        def get_alerts():
            """Get recent alerts."""
            alerts = self.alert_service.get_recent_alerts(limit=10)
            return jsonify([alert.to_dict() for alert in alerts])

        @self.app.route('/api/worst-traders')
        def get_worst_traders():
            """Get worst performing traders."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                traders = loop.run_until_complete(
                    self.database.get_worst_traders(limit=10)
                )
                return jsonify(traders)
            finally:
                loop.close()

        @self.app.route('/api/top-traders')
        def get_top_traders():
            """Get top performing traders."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                traders = loop.run_until_complete(
                    self.database.get_top_traders(limit=10)
                )
                return jsonify(traders)
            finally:
                loop.close()

        @self.app.route('/api/trader/<address>')
        def get_trader(address):
            """Get specific trader analysis."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                trader = loop.run_until_complete(
                    self.database.get_trader_analysis(address)
                )
                if trader:
                    return jsonify(trader)
                else:
                    return jsonify({'error': 'Trader not found'}), 404
            finally:
                loop.close()

    def run(self):
        """Run the Flask app."""
        logger.info(
            f"Starting dashboard on {self.config.dashboard.host}:"
            f"{self.config.dashboard.port}"
        )

        self.app.run(
            host=self.config.dashboard.host,
            port=self.config.dashboard.port,
            debug=False,
            threaded=True
        )

    def run_in_thread(self) -> Thread:
        """
        Run dashboard in a background thread.

        Returns:
            Thread object
        """
        thread = Thread(target=self.run, daemon=True)
        thread.start()
        logger.info("Dashboard started in background thread")
        return thread
