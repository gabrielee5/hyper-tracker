"""
Web dashboard for monitoring trader analysis.

Provides real-time view of:
- Analysis statistics
- Recent alerts
- Score distribution
- Worst performers
"""

from flask import Flask, render_template_string, jsonify
from flask_cors import CORS
import asyncio
import logging
from typing import Optional
from threading import Thread

from ..core.config import Config
from ..core.database import AnalyzerDatabase
from ..services.alert_service import AlertService


logger = logging.getLogger(__name__)


# HTML template for dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hyperliquid Trader Analyzer - Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
            min-height: 100vh;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }

        .stat-card:hover {
            transform: translateY(-5px);
        }

        .stat-label {
            font-size: 0.9em;
            color: #666;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }

        .stat-value.danger {
            color: #e74c3c;
        }

        .stat-value.success {
            color: #27ae60;
        }

        .content-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }

        @media (max-width: 968px) {
            .content-grid {
                grid-template-columns: 1fr;
            }
        }

        .panel {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .panel h2 {
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }

        .alert-item {
            background: #fee;
            border-left: 4px solid #e74c3c;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 8px;
        }

        .alert-item .address {
            font-family: monospace;
            font-weight: bold;
            color: #e74c3c;
            margin-bottom: 5px;
        }

        .alert-item .details {
            font-size: 0.9em;
            color: #666;
        }

        .trader-item {
            background: #f8f9fa;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }

        .trader-item .address {
            font-family: monospace;
            font-weight: bold;
            margin-bottom: 5px;
        }

        .trader-item .score {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: bold;
            color: white;
            margin-right: 10px;
        }

        .score.bad {
            background: #e74c3c;
        }

        .score.poor {
            background: #e67e22;
        }

        .score.average {
            background: #95a5a6;
        }

        .score.good {
            background: #27ae60;
        }

        .distribution-chart {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }

        .distribution-item {
            text-align: center;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }

        .distribution-item .count {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
        }

        .distribution-item .label {
            font-size: 0.8em;
            color: #666;
            margin-top: 5px;
        }

        .no-data {
            text-align: center;
            padding: 40px;
            color: #999;
            font-style: italic;
        }

        .refresh-info {
            text-align: center;
            color: white;
            margin-top: 20px;
            font-size: 0.9em;
            opacity: 0.8;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #999;
        }

        .timestamp {
            font-size: 0.8em;
            color: #999;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Hyperliquid Trader Analyzer</h1>
            <p>Real-time Statistical Analysis Dashboard</p>
        </div>

        <div class="stats-grid" id="stats-grid">
            <div class="loading">Loading statistics...</div>
        </div>

        <div class="content-grid">
            <div class="panel">
                <h2>🚨 Recent Alerts</h2>
                <div id="alerts-container">
                    <div class="loading">Loading alerts...</div>
                </div>
            </div>

            <div class="panel">
                <h2>📊 Score Distribution</h2>
                <div id="distribution-container">
                    <div class="loading">Loading distribution...</div>
                </div>
            </div>
        </div>

        <div class="panel">
            <h2>⚠️ Worst Performers</h2>
            <div id="worst-traders-container">
                <div class="loading">Loading traders...</div>
            </div>
        </div>

        <div class="refresh-info">
            Auto-refresh every {{ refresh_seconds }} seconds | Last updated: <span id="last-update">Never</span>
        </div>
    </div>

    <script>
        const REFRESH_INTERVAL = {{ refresh_seconds }} * 1000;

        async function fetchData(endpoint) {
            try {
                const response = await fetch('/api/' + endpoint);
                return await response.json();
            } catch (error) {
                console.error('Error fetching ' + endpoint + ':', error);
                return null;
            }
        }

        function formatNumber(num) {
            if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
            return num.toString();
        }

        function formatMoney(amount) {
            return '$' + amount.toFixed(2).replace(/\\d(?=(\\d{3})+\\.)/g, '$&,');
        }

        function shortenAddress(address) {
            return address.substring(0, 6) + '...' + address.substring(address.length - 4);
        }

        function getScoreClass(score) {
            if (score < 15) return 'bad';
            if (score < 40) return 'poor';
            if (score < 60) return 'average';
            return 'good';
        }

        async function updateStats() {
            const stats = await fetchData('stats');
            if (!stats) return;

            const statsGrid = document.getElementById('stats-grid');
            statsGrid.innerHTML = `
                <div class="stat-card">
                    <div class="stat-label">Total Analyzed</div>
                    <div class="stat-value">${formatNumber(stats.total_analyzed)}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Bad Traders</div>
                    <div class="stat-value danger">${formatNumber(stats.bad_traders_count)}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Analyzed Today</div>
                    <div class="stat-value success">${formatNumber(stats.analyzed_last_24h)}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Average Score</div>
                    <div class="stat-value">${stats.averages.score.toFixed(1)}</div>
                </div>
            `;
        }

        async function updateAlerts() {
            const alerts = await fetchData('alerts');
            if (!alerts) return;

            const container = document.getElementById('alerts-container');

            if (alerts.length === 0) {
                container.innerHTML = '<div class="no-data">No recent alerts</div>';
                return;
            }

            container.innerHTML = alerts.map(alert => `
                <div class="alert-item">
                    <div class="address">${shortenAddress(alert.address)}</div>
                    <div class="details">
                        Score: ${alert.score}/100 |
                        PnL: ${formatMoney(alert.total_pnl)} |
                        Trades: ${alert.num_trades}
                    </div>
                    <div class="timestamp">${new Date(alert.timestamp).toLocaleString()}</div>
                </div>
            `).join('');
        }

        async function updateDistribution() {
            const stats = await fetchData('stats');
            if (!stats || !stats.distribution) return;

            const dist = stats.distribution;
            const container = document.getElementById('distribution-container');

            container.innerHTML = `
                <div class="distribution-chart">
                    <div class="distribution-item">
                        <div class="count">${dist.exceptionally_bad}</div>
                        <div class="label">Exceptionally Bad<br>(&lt;5)</div>
                    </div>
                    <div class="distribution-item">
                        <div class="count">${dist.very_poor}</div>
                        <div class="label">Very Poor<br>(5-15)</div>
                    </div>
                    <div class="distribution-item">
                        <div class="count">${dist.below_average}</div>
                        <div class="label">Below Avg<br>(15-40)</div>
                    </div>
                    <div class="distribution-item">
                        <div class="count">${dist.average}</div>
                        <div class="label">Average<br>(40-60)</div>
                    </div>
                    <div class="distribution-item">
                        <div class="count">${dist.above_average}</div>
                        <div class="label">Above Avg<br>(60-85)</div>
                    </div>
                    <div class="distribution-item">
                        <div class="count">${dist.very_good}</div>
                        <div class="label">Very Good<br>(85-95)</div>
                    </div>
                    <div class="distribution-item">
                        <div class="count">${dist.exceptional}</div>
                        <div class="label">Exceptional<br>(&gt;95)</div>
                    </div>
                </div>
            `;
        }

        async function updateWorstTraders() {
            const traders = await fetchData('worst-traders');
            if (!traders) return;

            const container = document.getElementById('worst-traders-container');

            if (traders.length === 0) {
                container.innerHTML = '<div class="no-data">No traders analyzed yet</div>';
                return;
            }

            container.innerHTML = traders.map(trader => `
                <div class="trader-item">
                    <span class="score ${getScoreClass(trader.score)}">${trader.score}</span>
                    <span class="address">${shortenAddress(trader.address)}</span>
                    <div class="details">
                        Total PnL: ${formatMoney(trader.total_pnl)} |
                        Avg/Trade: ${formatMoney(trader.mean_pnl_per_trade)} |
                        Win Rate: ${(trader.win_rate * 100).toFixed(1)}% |
                        Trades: ${trader.num_trades}
                    </div>
                </div>
            `).join('');
        }

        async function updateAll() {
            await Promise.all([
                updateStats(),
                updateAlerts(),
                updateDistribution(),
                updateWorstTraders()
            ]);

            document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
        }

        // Initial load
        updateAll();

        // Auto-refresh
        setInterval(updateAll, REFRESH_INTERVAL);
    </script>
</body>
</html>
"""


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

        # Create Flask app
        self.app = Flask(__name__)
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
            return render_template_string(
                DASHBOARD_HTML,
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
