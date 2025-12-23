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

        html {
            font-size: 14px;
        }

        body {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
            background: #fff;
            color: #000;
            padding: 2.5rem 1.25rem;
            min-height: 100vh;
            line-height: 1.5;
        }

        .container {
            max-width: 80rem;
            margin: 0 auto;
        }

        .header {
            background: #fff;
            padding: 1.875rem 1.25rem;
            border: 0.85px solid #e5e7eb;
            margin-bottom: 1.25rem;
            text-align: center;
            transition: all 0.15s;
        }

        .header:hover {
            border-color: #9ca3af;
        }

        .header h1 {
            color: #000;
            font-size: 2.25rem;
            font-weight: 600;
            line-height: 2.5rem;
            margin-bottom: 0.625rem;
        }

        .header .subtitle {
            color: #6b7280;
            font-size: 1rem;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.25rem;
            margin-bottom: 1.25rem;
        }

        .stat-card {
            background: #fff;
            padding: 1.25rem;
            border: 0.85px solid #e5e7eb;
            transition: all 0.15s;
        }

        .stat-card:hover {
            border-color: #9ca3af;
        }

        .stat-label {
            color: #6b7280;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.025em;
            margin-bottom: 0.625rem;
            font-weight: 500;
        }

        .stat-value {
            color: #000;
            font-size: 1.875rem;
            font-weight: 600;
            line-height: 2.25rem;
        }

        .stat-subvalue {
            color: #9ca3af;
            font-size: 0.875rem;
            margin-top: 0.375rem;
        }

        .content-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1.25rem;
        }

        .card {
            background: #fff;
            padding: 1.25rem;
            border: 0.85px solid #e5e7eb;
            transition: all 0.15s;
        }

        .card:hover {
            border-color: #9ca3af;
        }

        .card h2 {
            color: #000;
            font-size: 1.125rem;
            font-weight: 600;
            margin-bottom: 1.25rem;
            border-bottom: 0.85px solid #e5e7eb;
            padding-bottom: 0.9375rem;
        }

        .table {
            width: 100%;
            border-collapse: collapse;
        }

        .table th {
            text-align: left;
            padding: 0.9375rem 1.25rem;
            background: #f9fafb;
            color: #6b7280;
            font-weight: 500;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.025em;
            border-bottom: 0.85px solid #e5e7eb;
        }

        .table td {
            padding: 1.25rem;
            border-bottom: 0.85px solid #e5e7eb;
            font-size: 0.875rem;
        }

        .table tbody tr:hover {
            background: #f9fafb;
        }

        .table tbody tr:last-child td {
            border-bottom: none;
        }

        .address {
            font-family: inherit;
            color: #000;
            font-size: 0.875rem;
        }

        .badge {
            display: inline-block;
            padding: 0.125rem 0.625rem;
            font-size: 0.75rem;
            font-weight: 500;
            border: 0.85px solid;
        }

        .badge-success {
            background: #f0fdf4;
            color: #166534;
            border-color: #bbf7d0;
        }

        .badge-info {
            background: #f9fafb;
            color: #6b7280;
            border-color: #e5e7eb;
        }

        .timestamp {
            color: #9ca3af;
            font-size: 0.75rem;
        }

        .footer {
            text-align: center;
            color: #6b7280;
            margin-top: 2.5rem;
            padding: 1.25rem;
            font-size: 0.75rem;
        }

        .status-indicator {
            display: inline-block;
            width: 0.375rem;
            height: 0.375rem;
            border-radius: 9999px;
            background: #22c55e;
            animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
            margin-right: 0.5rem;
        }

        @keyframes pulse {
            50% { opacity: 0.5; }
        }

        @media (max-width: 640px) {
            body {
                padding: 1.25rem;
            }

            .header h1 {
                font-size: 1.5rem;
                line-height: 2rem;
            }

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
            <h1>Hyperliquid Tracker</h1>
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
                <h2>Tracking Status</h2>
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
                <h2>Trades by Coin</h2>
                <table class="table">
                    <thead>
                        <tr>
                            <th>Coin</th>
                            <th style="text-align: right;">Trades</th>
                        </tr>
                    </thead>
                    <tbody id="tradesByCoin">
                        <tr><td colspan="2" style="text-align: center; color: #9ca3af;">No data yet</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <div class="card" style="margin-top: 1.25rem;">
            <h2>Recent Addresses</h2>
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
                    <tr><td colspan="4" style="text-align: center; color: #9ca3af;">No addresses yet</td></tr>
                </tbody>
            </table>
        </div>

        <div class="footer">
            <p>Auto-refreshes every 5 seconds</p>
            <p style="margin-top: 0.625rem;">Powered by Hyperliquid Python SDK</p>
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
                        tbody.innerHTML = '<tr><td colspan="2" style="text-align: center; color: #9ca3af;">No trades yet</td></tr>';
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
                        addressTbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #9ca3af;">No addresses yet</td></tr>';
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

            # Calculate uptime (use same timezone as start_time)
            current_time = datetime.now(tracker.start_time.tzinfo) if tracker.start_time.tzinfo else datetime.now()
            uptime_delta = current_time - tracker.start_time
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


def start_dashboard(tracker, config, stop_event=None):
    """
    Start the dashboard server.

    Args:
        tracker: HyperliquidTracker instance
        config: Application configuration
        stop_event: Optional threading.Event to signal shutdown
    """
    from werkzeug.serving import make_server
    import threading

    app = create_dashboard_app(tracker, config)

    # Disable Flask's default logging
    import logging as flask_logging
    flask_log = flask_logging.getLogger('werkzeug')
    flask_log.setLevel(flask_logging.ERROR)

    server = None
    try:
        # Create server with proper shutdown capability
        server = make_server(
            config.dashboard_host,
            config.dashboard_port,
            app,
            threaded=True
        )

        logger.info(f"Dashboard server ready on {config.dashboard_host}:{config.dashboard_port}")

        # Store server reference for shutdown
        tracker._dashboard_server = server

        # If stop_event is provided, monitor it in a separate thread
        if stop_event:
            def monitor_shutdown():
                stop_event.wait()
                if server:
                    logger.info("Stop event triggered, shutting down dashboard...")
                    server.shutdown()

            monitor_thread = threading.Thread(target=monitor_shutdown, daemon=True)
            monitor_thread.start()

        # Run server (will block until shutdown() is called)
        server.serve_forever()

    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
    finally:
        if server:
            server.server_close()
        logger.info("Dashboard server stopped")
