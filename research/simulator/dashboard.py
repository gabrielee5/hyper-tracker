"""
Flask web dashboard for the trading simulator.
Provides real-time portfolio monitoring and performance visualization.
"""

from flask import Flask, render_template, jsonify
from flask_cors import CORS
import threading
import logging
from datetime import datetime

from config import Config
from simulator import TradingSimulator

logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
CORS(app)

# Global simulator instance
simulator = None


def init_dashboard(sim: TradingSimulator):
    """Initialize dashboard with simulator instance."""
    global simulator
    simulator = sim
    logger.info("Dashboard initialized with simulator")


@app.route('/')
def index():
    """Serve main dashboard page."""
    response = app.make_response(render_template('index.html'))
    # Prevent caching to ensure users get the latest version
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/status')
def api_status():
    """Get current simulator status."""
    try:
        if not simulator:
            return jsonify({'error': 'Simulator not initialized'}), 500

        status = simulator.get_status()
        return jsonify(status)

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolio')
def api_portfolio():
    """Get portfolio summary."""
    try:
        if not simulator:
            return jsonify({'error': 'Simulator not initialized'}), 500

        # Calculate current values
        portfolio_value = simulator.portfolio.calculate_portfolio_value()
        return_pct = ((portfolio_value - simulator.config.starting_capital) /
                     simulator.config.starting_capital * 100)

        # Get performance metrics
        metrics = simulator.performance.calculate_all_metrics(
            current_equity=portfolio_value,
            total_pnl=simulator.portfolio.total_pnl
        )

        data = {
            'current_value': portfolio_value,
            'starting_capital': simulator.config.starting_capital,
            'total_pnl': simulator.portfolio.total_pnl,
            'total_return_pct': return_pct,
            'num_positions': len(simulator.portfolio.positions),
            'total_trades': simulator.db.get_trade_count(),
            'total_fees_paid': simulator.portfolio.total_fees_paid,
            'metrics': metrics
        }

        # Add cash tracking if portfolio supports it (three-asset strategy)
        if hasattr(simulator.portfolio, 'get_cash_balance'):
            cash_balance = simulator.portfolio.get_cash_balance()
            positions_value = simulator.portfolio.get_positions_value()
            data['cash_balance'] = cash_balance
            data['cash_balance_pct'] = (cash_balance / portfolio_value * 100) if portfolio_value > 0 else 0
            data['positions_value'] = positions_value
            data['positions_value_pct'] = (positions_value / portfolio_value * 100) if portfolio_value > 0 else 0

        return jsonify(data)

    except Exception as e:
        logger.error(f"Error getting portfolio: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/positions')
def api_positions():
    """Get all open positions."""
    try:
        if not simulator:
            return jsonify({'error': 'Simulator not initialized'}), 500

        positions = simulator.portfolio.get_positions_summary()

        # Convert to list format for frontend
        positions_list = []
        for pair, pos in positions.items():
            positions_list.append({
                'pair': pair,
                'direction': pos['direction'],
                'entry_price': pos['entry_price'],
                'current_price': pos['current_price'],
                'entry_size_usd': pos['entry_size_usd'],
                'current_size_usd': pos['current_size_usd'],
                'quantity': pos['quantity'],
                'unrealized_pnl': pos['unrealized_pnl'],
                'unrealized_pnl_pct': pos['unrealized_pnl_pct'],
                'signal_confidence': pos['signal_confidence'],
                'entry_timestamp': pos['entry_timestamp'].isoformat() if isinstance(pos['entry_timestamp'], datetime) else pos['entry_timestamp'],
                'total_fees_paid': pos['total_fees_paid']
            })

        # Sort by size (largest first)
        positions_list.sort(key=lambda x: x['current_size_usd'], reverse=True)

        return jsonify(positions_list)

    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/trades')
def api_trades():
    """Get recent trade history."""
    try:
        if not simulator:
            return jsonify({'error': 'Simulator not initialized'}), 500

        trades = simulator.db.get_recent_trades(limit=100)

        # Format for frontend
        trades_list = []
        for trade in trades:
            trades_list.append({
                'trade_id': trade['trade_id'],
                'timestamp': trade['timestamp'],
                'pair': trade['pair'],
                'direction': trade['direction'],
                'action': trade['action'],
                'price': trade['price'],
                'quantity': trade['quantity'],
                'usd_value': trade['usd_value'],
                'fees': trade['fees'],
                'slippage': trade['slippage'],
                'signal_confidence': trade['signal_confidence'],
                'reason': trade['reason'],
                'pnl': trade['pnl']
            })

        return jsonify(trades_list)

    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/equity_curve')
def api_equity_curve():
    """Get equity curve data for charting."""
    try:
        if not simulator:
            return jsonify({'error': 'Simulator not initialized'}), 500

        equity_data = simulator.performance.get_equity_curve_for_chart()
        return jsonify(equity_data)

    except Exception as e:
        logger.error(f"Error getting equity curve: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/performance')
def api_performance():
    """Get performance metrics."""
    try:
        if not simulator:
            return jsonify({'error': 'Simulator not initialized'}), 500

        portfolio_value = simulator.portfolio.calculate_portfolio_value()
        metrics = simulator.performance.calculate_all_metrics(
            current_equity=portfolio_value,
            total_pnl=simulator.portfolio.total_pnl
        )

        return jsonify(metrics)

    except Exception as e:
        logger.error(f"Error getting performance: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/rebalances')
def api_rebalances():
    """Get recent rebalancing events."""
    try:
        if not simulator:
            return jsonify({'error': 'Simulator not initialized'}), 500

        rebalances = simulator.db.get_recent_rebalances(limit=20)

        rebalances_list = []
        for rb in rebalances:
            rebalances_list.append({
                'rebalance_id': rb['rebalance_id'],
                'timestamp': rb['timestamp'],
                'num_adjustments': rb['num_adjustments'],
                'total_fees': rb['total_fees'],
                'portfolio_value_before': rb['portfolio_value_before'],
                'portfolio_value_after': rb['portfolio_value_after'],
                'signals_used': rb['signals_used']
            })

        return jsonify(rebalances_list)

    except Exception as e:
        logger.error(f"Error getting rebalances: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/activity')
def api_activity():
    """Get recent activity log."""
    try:
        if not simulator:
            return jsonify({'error': 'Simulator not initialized'}), 500

        # Get recent trades and rebalances, combine and sort
        trades = simulator.db.get_recent_trades(limit=20)
        rebalances = simulator.db.get_recent_rebalances(limit=10)

        activity = []

        # Add trades
        for trade in trades:
            pnl_text = f" (P&L: ${trade['pnl']:,.2f})" if trade['pnl'] else ''
            activity.append({
                'timestamp': trade['timestamp'],
                'type': 'trade',
                'message': f"{trade['action']} {trade['pair']} {trade['direction']}: "
                          f"${trade['usd_value']:,.2f}{pnl_text}"
            })

        # Add rebalances
        for rb in rebalances:
            activity.append({
                'timestamp': rb['timestamp'],
                'type': 'rebalance',
                'message': f"Rebalanced portfolio: {rb['num_adjustments']} adjustments, "
                          f"${rb['total_fees']:.2f} fees"
            })

        # Sort by timestamp (newest first)
        activity.sort(key=lambda x: x['timestamp'], reverse=True)

        return jsonify(activity[:30])  # Return top 30 items

    except Exception as e:
        logger.error(f"Error getting activity: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/config')
def api_config():
    """Get dashboard configuration."""
    try:
        if not simulator:
            return jsonify({'error': 'Simulator not initialized'}), 500

        return jsonify({
            'update_interval_seconds': simulator.config.dashboard_update_interval_seconds
        })

    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({'error': str(e)}), 500


def run_dashboard(config: Config, sim: TradingSimulator):
    """Run the Flask dashboard in a separate thread."""
    init_dashboard(sim)

    # Run Flask in non-debug mode for production
    app.run(
        host='0.0.0.0',
        port=config.dashboard_port,
        debug=False,
        threaded=True
    )


def start_dashboard_thread(config: Config, sim: TradingSimulator):
    """Start dashboard in a background thread."""
    dashboard_thread = threading.Thread(
        target=run_dashboard,
        args=(config, sim),
        daemon=True
    )
    dashboard_thread.start()
    logger.info(f"Dashboard started on http://localhost:{config.dashboard_port}")
    return dashboard_thread
