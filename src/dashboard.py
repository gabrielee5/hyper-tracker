"""Simple web dashboard for monitoring the tracker."""

import logging
from datetime import datetime
from flask import Flask, render_template_string, jsonify
from flask_cors import CORS

logger = logging.getLogger(__name__)

# HTML template for the dashboard
DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hyperliquid Tracker Dashboard</title>
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
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            margin-bottom: 20px;
            text-align: center;
        }

        .header h1 {
            color: #667eea;
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .header .subtitle {
            color: #666;
            font-size: 1.1em;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }

        .stat-card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }

        .stat-card:hover {
            transform: translateY(-5px);
        }

        .stat-label {
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }

        .stat-value {
            color: #667eea;
            font-size: 2.5em;
            font-weight: bold;
        }

        .stat-subvalue {
            color: #999;
            font-size: 0.9em;
            margin-top: 5px;
        }

        .content-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }

        .card {
            background: white;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        .card h2 {
            color: #667eea;
            margin-bottom: 20px;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }

        .table {
            width: 100%;
            border-collapse: collapse;
        }

        .table th {
            text-align: left;
            padding: 12px;
            background: #f8f9fa;
            color: #666;
            font-weight: 600;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .table td {
            padding: 12px;
            border-bottom: 1px solid #eee;
        }

        .table tr:hover {
            background: #f8f9fa;
        }

        .address {
            font-family: 'Courier New', monospace;
            color: #667eea;
            font-size: 0.9em;
        }

        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: 600;
        }

        .badge-success {
            background: #d4edda;
            color: #155724;
        }

        .badge-info {
            background: #d1ecf1;
            color: #0c5460;
        }

        .timestamp {
            color: #999;
            font-size: 0.85em;
        }

        .footer {
            text-align: center;
            color: white;
            margin-top: 30px;
            padding: 20px;
        }

        .status-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #28a745;
            animation: pulse 2s infinite;
            margin-right: 8px;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        @media (max-width: 768px) {
            .content-grid {
                grid-template-columns: 1fr;
            }

            .stats-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Hyperliquid Tracker</h1>
            <p class="subtitle">
                <span class="status-indicator"></span>
                Real-time trader address monitoring
            </p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Addresses</div>
                <div class="stat-value" id="totalAddresses">-</div>
            </div>

            <div class="stat-card">
                <div class="stat-label">Total Trades</div>
                <div class="stat-value" id="totalTrades">-</div>
            </div>

            <div class="stat-card">
                <div class="stat-label">Total Volume</div>
                <div class="stat-value" id="totalVolume">-</div>
                <div class="stat-subvalue">USD</div>
            </div>

            <div class="stat-card">
                <div class="stat-label">Active (24h)</div>
                <div class="stat-value" id="active24h">-</div>
                <div class="stat-subvalue"><span id="active1h">-</span> in last hour</div>
            </div>
        </div>

        <div class="content-grid">
            <div class="card">
                <h2>📊 Tracking Status</h2>
                <table class="table">
                    <tr>
                        <td><strong>Network</strong></td>
                        <td><span class="badge badge-success" id="network">-</span></td>
                    </tr>
                    <tr>
                        <td><strong>Coins Tracked</strong></td>
                        <td id="coinsTracked">-</td>
                    </tr>
                    <tr>
                        <td><strong>Uptime</strong></td>
                        <td id="uptime">-</td>
                    </tr>
                    <tr>
                        <td><strong>Last Update</strong></td>
                        <td class="timestamp" id="lastUpdate">-</td>
                    </tr>
                </table>
            </div>

            <div class="card">
                <h2>📈 Trades by Coin</h2>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Coin</th>
                            <th style="text-align: right;">Trades</th>
                        </tr>
                    </thead>
                    <tbody id="tradesByCoin">
                        <tr><td colspan="2" style="text-align: center; color: #999;">No data yet</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="card" style="margin-top: 20px;">
            <h2>🆕 Recent Addresses</h2>
            <table class="table">
                <thead>
                    <tr>
                        <th>Address</th>
                        <th>First Seen</th>
                        <th style="text-align: right;">Trades</th>
                        <th style="text-align: right;">Volume (USD)</th>
                    </tr>
                </thead>
                <tbody id="recentAddresses">
                    <tr><td colspan="4" style="text-align: center; color: #999;">No addresses yet</td></tr>
                </tbody>
            </table>
        </div>

        <div class="footer">
            <p>Auto-refreshes every 5 seconds</p>
            <p style="margin-top: 10px; opacity: 0.8;">Powered by Hyperliquid Python SDK</p>
        </div>
    </div>

    <script>
        function formatNumber(num) {
            if (num >= 1000000) {
                return (num / 1000000).toFixed(2) + 'M';
            } else if (num >= 1000) {
                return (num / 1000).toFixed(2) + 'K';
            }
            return num.toLocaleString();
        }

        function formatAddress(addr) {
            if (addr.length <= 12) return addr;
            return addr.substring(0, 6) + '...' + addr.substring(addr.length - 4);
        }

        function formatDate(dateStr) {
            const date = new Date(dateStr);
            return date.toLocaleString();
        }

        function updateDashboard() {
            fetch('/api/stats')
                .then(response => response.json())
                .then(data => {
                    // Update statistics
                    document.getElementById('totalAddresses').textContent = formatNumber(data.db_stats.total_addresses);
                    document.getElementById('totalTrades').textContent = formatNumber(data.tracker_stats.total_trades_processed);
                    document.getElementById('totalVolume').textContent = '$' + formatNumber(data.db_stats.total_volume_usd);
                    document.getElementById('active24h').textContent = formatNumber(data.db_stats.active_last_24h);
                    document.getElementById('active1h').textContent = formatNumber(data.db_stats.active_last_1h);

                    // Update tracking status
                    document.getElementById('network').textContent = data.config.network.toUpperCase();
                    document.getElementById('coinsTracked').textContent = data.config.coins_tracked.join(', ');
                    document.getElementById('uptime').textContent = data.uptime;
                    document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();

                    // Update trades by coin
                    const tradesByCoin = data.tracker_stats.trades_by_coin;
                    const tbody = document.getElementById('tradesByCoin');

                    if (Object.keys(tradesByCoin).length === 0) {
                        tbody.innerHTML = '<tr><td colspan="2" style="text-align: center; color: #999;">No trades yet</td></tr>';
                    } else {
                        const sorted = Object.entries(tradesByCoin).sort((a, b) => b[1] - a[1]);
                        tbody.innerHTML = sorted.map(([coin, count]) => `
                            <tr>
                                <td><strong>${coin}</strong></td>
                                <td style="text-align: right;">${formatNumber(count)}</td>
                            </tr>
                        `).join('');
                    }

                    // Update recent addresses
                    const recentAddresses = data.recent_addresses;
                    const addressTbody = document.getElementById('recentAddresses');

                    if (recentAddresses.length === 0) {
                        addressTbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #999;">No addresses yet</td></tr>';
                    } else {
                        addressTbody.innerHTML = recentAddresses.slice(0, 10).map(addr => `
                            <tr>
                                <td><span class="address">${formatAddress(addr.address)}</span></td>
                                <td class="timestamp">${formatDate(addr.first_seen)}</td>
                                <td style="text-align: right;">${formatNumber(addr.trade_count)}</td>
                                <td style="text-align: right;">$${formatNumber(addr.total_volume_usd)}</td>
                            </tr>
                        `).join('');
                    }
                })
                .catch(error => {
                    console.error('Error fetching stats:', error);
                });
        }

        // Initial update
        updateDashboard();

        // Auto-refresh every 5 seconds
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>
"""


def create_dashboard_app(tracker, config):
    """
    Create Flask dashboard application.

    Args:
        tracker: HyperliquidTracker instance
        config: Application configuration

    Returns:
        Flask app instance
    """
    app = Flask(__name__)
    CORS(app)

    @app.route('/')
    def index():
        """Render the main dashboard."""
        return render_template_string(DASHBOARD_TEMPLATE)

    @app.route('/api/stats')
    def stats():
        """API endpoint for statistics."""
        try:
            # Get statistics from various components
            tracker_stats = tracker.tracker.get_statistics()
            db_stats = tracker.storage.get_statistics()
            recent_addresses = tracker.storage.get_recent_addresses(limit=20)

            # Calculate uptime
            uptime_delta = datetime.now() - tracker.start_time
            hours, remainder = divmod(uptime_delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            if uptime_delta.days > 0:
                uptime = f"{uptime_delta.days}d {hours}h {minutes}m"
            elif hours > 0:
                uptime = f"{hours}h {minutes}m"
            else:
                uptime = f"{minutes}m {seconds}s"

            return jsonify({
                "tracker_stats": tracker_stats,
                "db_stats": db_stats,
                "recent_addresses": recent_addresses,
                "uptime": uptime,
                "config": {
                    "network": config.network,
                    "coins_tracked": tracker.coins_tracked,
                }
            })
        except Exception as e:
            logger.error(f"Error generating stats: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route('/api/addresses')
    def addresses():
        """API endpoint for all addresses."""
        from flask import request
        try:
            limit = int(request.args.get('limit', 100))
            addresses = tracker.storage.get_recent_addresses(limit=limit)
            return jsonify(addresses)
        except Exception as e:
            logger.error(f"Error fetching addresses: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    @app.route('/api/top-traders')
    def top_traders():
        """API endpoint for top traders."""
        from flask import request
        try:
            limit = int(request.args.get('limit', 100))
            by = request.args.get('by', 'volume')  # 'volume' or 'trades'
            traders = tracker.storage.get_top_traders(limit=limit, by=by)
            return jsonify(traders)
        except Exception as e:
            logger.error(f"Error fetching top traders: {e}", exc_info=True)
            return jsonify({"error": str(e)}), 500

    return app


def start_dashboard(tracker, config):
    """
    Start the dashboard server.

    Args:
        tracker: HyperliquidTracker instance
        config: Application configuration
    """
    app = create_dashboard_app(tracker, config)

    # Disable Flask's default logging
    import logging as flask_logging
    flask_log = flask_logging.getLogger('werkzeug')
    flask_log.setLevel(flask_logging.ERROR)

    try:
        app.run(
            host=config.dashboard_host,
            port=config.dashboard_port,
            debug=False,
            use_reloader=False
        )
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
