"""Flask web dashboard for market maker monitor."""

from flask import Flask, render_template, jsonify
import logging
from threading import Thread
from datetime import datetime


logger = logging.getLogger(__name__)


class MMWebDashboard:
    """Web dashboard for market maker position monitoring."""

    def __init__(
        self,
        port: int = 5003,
        host: str = "localhost",
        timezone: str = "Europe/Rome"
    ):
        """
        Initialize web dashboard.

        Args:
            port: Server port
            host: Server host
            timezone: Timezone for display
        """
        self.port = port
        self.host = host
        self.timezone = timezone

        # State
        self.bias_data = []
        self.mm_count = 0
        self.active_mm_count = 0
        self.total_position_value = 0
        self.asset_count = 0
        self.last_update = None

        # Flask app
        self.app = Flask(
            __name__,
            template_folder='../dashboard/templates'
        )
        self._setup_routes()

        # Disable Flask logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

    def _setup_routes(self):
        """Setup Flask routes."""

        @self.app.route('/')
        def index():
            """Render main dashboard page."""
            return render_template(
                'dashboard.html',
                timezone=self.timezone,
                port=self.port
            )

        @self.app.route('/api/data')
        def get_data():
            """API endpoint for dashboard data."""
            return jsonify({
                'bias_data': self.bias_data,
                'stats': {
                    'total_mm_count': self.mm_count,
                    'active_mm_count': self.active_mm_count,
                    'total_position_value': self.total_position_value,
                    'asset_count': self.asset_count,
                    'last_update': self.last_update
                }
            })

        @self.app.route('/api/health')
        def health():
            """Health check endpoint."""
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.now().isoformat()
            })

    def update_data(
        self,
        bias_data: list,
        mm_count: int,
        active_mm_count: int
    ):
        """
        Update dashboard data.

        Args:
            bias_data: List of bias dictionaries
            mm_count: Total market maker count
            active_mm_count: Active market maker count
        """
        self.bias_data = bias_data
        self.mm_count = mm_count
        self.active_mm_count = active_mm_count

        # Calculate totals
        self.total_position_value = sum(
            b['total_value_usd'] for b in bias_data
        ) if bias_data else 0

        self.asset_count = len(bias_data)
        self.last_update = datetime.now().isoformat()

        logger.debug(
            f"Dashboard updated: {self.asset_count} assets, "
            f"${self.total_position_value:,.0f} total value"
        )

    def run_in_thread(self):
        """Run Flask app in background thread."""
        def run():
            self.app.run(
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False,
                threaded=True
            )

        thread = Thread(target=run, daemon=True)
        thread.start()
        logger.info(f"Web dashboard started on http://{self.host}:{self.port}")
