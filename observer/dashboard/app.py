"""
Web dashboard for Observer - Trader Review System.

Provides sequential review workflow for approving/rejecting traders.
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import Config
from core.database import ApprovedTradersDatabase
from core.trader_loader import TraderQueueManager
from core.live_data_fetcher import LiveTraderDataFetcher


logger = logging.getLogger(__name__)


class ObserverDashboardApp:
    """Flask dashboard application for Observer."""

    def __init__(self, config: Config):
        """
        Initialize dashboard app.

        Args:
            config: Configuration object
        """
        self.config = config

        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_dir = os.path.join(current_dir, 'templates')

        # Create Flask app with template directory
        self.app = Flask(__name__, template_folder=template_dir)
        CORS(self.app)

        # Initialize databases
        self.approved_db = ApprovedTradersDatabase(
            db_path=str(config.get_approved_traders_db_absolute_path()),
            connection_timeout=config.database.connection_timeout
        )

        # Initialize trader queue manager
        self.queue_manager = TraderQueueManager(
            phase2_db_path=str(config.get_analyzed_traders_db_absolute_path()),
            approved_db=self.approved_db
        )

        # Initialize database schema
        asyncio.run(self.approved_db.initialize())

        # Register routes
        self._register_routes()

    def _register_routes(self):
        """Register Flask routes."""

        @self.app.route('/')
        def index():
            """Main observer dashboard page."""
            return render_template(
                'observer.html',
                config={
                    'best_min': self.config.filters.best_traders_min_score,
                    'best_max': self.config.filters.best_traders_max_score,
                    'worst_min': self.config.filters.worst_traders_min_score,
                    'worst_max': self.config.filters.worst_traders_max_score,
                    'default_view': self.config.filters.default_view
                }
            )

        @self.app.route('/api/queue')
        def get_queue():
            """Get list of traders for review with filters."""
            min_score = request.args.get('min_score', 0, type=int)
            max_score = request.args.get('max_score', 100, type=int)
            limit = request.args.get('limit', None, type=int)

            try:
                traders = asyncio.run(
                    self.queue_manager.get_traders_for_review(
                        min_score=min_score,
                        max_score=max_score,
                        limit=limit
                    )
                )
                return jsonify({
                    'traders': traders,
                    'count': len(traders)
                })
            except Exception as e:
                logger.error(f"Error fetching queue: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/trader/<address>')
        def get_trader_details(address):
            """Get complete trader data (DB + live API)."""
            async def fetch_data():
                # Get trader from Phase 2 database
                trader_data = await self.queue_manager.phase2_reader.get_trader(address)

                if not trader_data:
                    return None

                # Create a fresh LiveTraderDataFetcher for this request
                live_fetcher = LiveTraderDataFetcher(
                    base_url=self.config.api.base_url,
                    rate_limit_calls=self.config.api.rate_limit_calls,
                    rate_limit_period=self.config.api.rate_limit_period,
                    timeout=self.config.api.timeout,
                    cache_ttl_seconds=self.config.api.cache_ttl_seconds
                )

                try:
                    # Get live API data
                    live_data = await live_fetcher.fetch_trader_complete_data(address)

                    # Check if already approved or rejected
                    is_approved = await self.approved_db.is_already_approved(address)
                    is_rejected = await self.approved_db.is_already_rejected(address)

                    # Combine all data
                    return {
                        'trader': trader_data,
                        'live': live_data,
                        'status': {
                            'approved': is_approved,
                            'rejected': is_rejected,
                            'pending': not (is_approved or is_rejected)
                        }
                    }
                finally:
                    # Close the fetcher's API client
                    await live_fetcher.close()

            try:
                response = asyncio.run(fetch_data())

                if not response:
                    return jsonify({'error': 'Trader not found'}), 404

                return jsonify(response)

            except Exception as e:
                logger.error(f"Error fetching trader details for {address}: {e}", exc_info=True)
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/trader/<address>/approve', methods=['POST'])
        def approve_trader(address):
            """Approve a trader."""
            data = request.get_json() or {}
            reason = data.get('reason')
            notes = data.get('notes')

            async def do_approve():
                # Get trader metrics from Phase 2 database
                trader_data = await self.queue_manager.phase2_reader.get_trader(address)

                if not trader_data:
                    return None

                # Save approval
                await self.approved_db.approve_trader(
                    address=address,
                    metrics=trader_data,
                    reason=reason,
                    notes=notes
                )

                return True

            try:
                result = asyncio.run(do_approve())

                if not result:
                    return jsonify({'error': 'Trader not found'}), 404

                return jsonify({
                    'success': True,
                    'message': f'Trader {address} approved'
                })

            except Exception as e:
                logger.error(f"Error approving trader {address}: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/trader/<address>/reject', methods=['POST'])
        def reject_trader(address):
            """Reject a trader."""
            data = request.get_json() or {}
            reason = data.get('reason')

            async def do_reject():
                # Get trader metrics from Phase 2 database
                trader_data = await self.queue_manager.phase2_reader.get_trader(address)

                if not trader_data:
                    return None

                # Save rejection
                await self.approved_db.reject_trader(
                    address=address,
                    score=trader_data.get('score', 0),
                    reason=reason,
                    metrics=trader_data
                )

                return True

            try:
                result = asyncio.run(do_reject())

                if not result:
                    return jsonify({'error': 'Trader not found'}), 404

                return jsonify({
                    'success': True,
                    'message': f'Trader {address} rejected'
                })

            except Exception as e:
                logger.error(f"Error rejecting trader {address}: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/navigation/<address>/next')
        def get_next_trader(address):
            """Get next trader in queue."""
            min_score = request.args.get('min_score', 0, type=int)
            max_score = request.args.get('max_score', 100, type=int)

            try:
                next_trader = asyncio.run(
                    self.queue_manager.get_next_trader(
                        current_address=address,
                        min_score=min_score,
                        max_score=max_score
                    )
                )

                if not next_trader:
                    return jsonify({'error': 'No more traders in queue'}), 404

                return jsonify(next_trader)

            except Exception as e:
                logger.error(f"Error getting next trader: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/navigation/<address>/previous')
        def get_previous_trader(address):
            """Get previous trader in queue."""
            min_score = request.args.get('min_score', 0, type=int)
            max_score = request.args.get('max_score', 100, type=int)

            try:
                prev_trader = asyncio.run(
                    self.queue_manager.get_previous_trader(
                        current_address=address,
                        min_score=min_score,
                        max_score=max_score
                    )
                )

                if not prev_trader:
                    return jsonify({'error': 'No previous trader in queue'}), 404

                return jsonify(prev_trader)

            except Exception as e:
                logger.error(f"Error getting previous trader: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/stats')
        def get_statistics():
            """Get approval statistics."""
            min_score = request.args.get('min_score', 0, type=int)
            max_score = request.args.get('max_score', 100, type=int)

            async def get_stats():
                # Get approval stats
                approval_stats = await self.approved_db.get_approval_statistics()

                # Get pending count for current filter
                pending_count = await self.queue_manager.get_trader_count(
                    min_score=min_score,
                    max_score=max_score
                )

                return {
                    **approval_stats,
                    'pending_count': pending_count,
                    'current_filter': {
                        'min_score': min_score,
                        'max_score': max_score
                    }
                }

            try:
                stats = asyncio.run(get_stats())
                return jsonify(stats)

            except Exception as e:
                logger.error(f"Error fetching statistics: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/approved')
        def get_approved_traders():
            """Get list of all approved traders."""
            limit = request.args.get('limit', 50, type=int)
            offset = request.args.get('offset', 0, type=int)

            try:
                traders = asyncio.run(
                    self.approved_db.get_approved_traders(
                        limit=limit,
                        offset=offset
                    )
                )

                return jsonify({
                    'traders': traders,
                    'count': len(traders)
                })

            except Exception as e:
                logger.error(f"Error fetching approved traders: {e}")
                return jsonify({'error': str(e)}), 500

    def run(self):
        """Run the Flask development server."""
        logger.info(
            f"Starting Observer Dashboard on "
            f"http://{self.config.dashboard.host}:{self.config.dashboard.port}"
        )

        self.app.run(
            host=self.config.dashboard.host,
            port=self.config.dashboard.port,
            debug=False
        )


def create_app(config: Config) -> ObserverDashboardApp:
    """
    Create and configure dashboard app.

    Args:
        config: Configuration object

    Returns:
        ObserverDashboardApp instance
    """
    return ObserverDashboardApp(config)
