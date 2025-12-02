"""
Test script for contrarian signal system.

Tests individual components and the complete pipeline with real data.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from contrarian.core.config import ConrarianConfig
from contrarian.core.database import Phase2Reader, ContrarianDatabase
from contrarian.core.position_fetcher import HyperliquidPositionFetcher, parse_positions
from contrarian.core.aggregator import PositionAggregator
from contrarian.core.signal_generator import ContrarianSignalGenerator
from contrarian.core.dashboard import ContrarianDashboard
from datetime import datetime


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_phase2_reader():
    """Test reading bad traders from Phase 2 database."""
    print("\n" + "="*80)
    print("TEST 1: Phase 2 Database Reader")
    print("="*80)

    config = ConrarianConfig()
    reader = Phase2Reader(config.database.phase2_path)

    # Get bad traders
    bad_traders = await reader.get_bad_traders(score_threshold=5, limit=10)

    print(f"Found {len(bad_traders)} bad traders (limit: 10)")
    print("\nSample bad traders:")
    for trader in bad_traders[:5]:
        print(f"  {trader['address'][:10]}... - Score: {trader['score']}, "
              f"PnL: ${trader['total_pnl']:.2f}, Trades: {trader['num_trades']}")

    return bad_traders


async def test_position_fetcher(addresses):
    """Test fetching positions from Hyperliquid."""
    print("\n" + "="*80)
    print("TEST 2: Position Fetcher")
    print("="*80)

    config = ConrarianConfig()
    fetcher = HyperliquidPositionFetcher(
        base_url=config.api.base_url,
        rate_limit_calls=config.api.rate_limit_calls
    )

    try:
        # Test with first 5 addresses
        test_addresses = addresses[:5]
        print(f"Testing with {len(test_addresses)} addresses...")

        positions_by_address = await fetcher.batch_fetch_positions(
            test_addresses,
            concurrency=3
        )

        # Parse positions
        all_positions = []
        for address, user_state in positions_by_address.items():
            if user_state:
                positions = parse_positions(user_state)
                all_positions.extend(positions)
                if positions:
                    print(f"\n{address[:10]}... has {len(positions)} positions:")
                    for pos in positions:
                        print(f"  {pos['coin']}: {pos['side']} ${pos['position_value_usd']:.2f}")

        print(f"\nTotal positions found: {len(all_positions)}")

        return all_positions

    finally:
        await fetcher.close()


async def test_aggregation(positions):
    """Test position aggregation."""
    print("\n" + "="*80)
    print("TEST 3: Position Aggregation")
    print("="*80)

    aggregator = PositionAggregator(min_traders_for_signal=2)  # Lower for testing

    aggregated = aggregator.aggregate_positions(positions)

    print(f"Aggregated {len(aggregated)} coins")

    for coin, agg in sorted(aggregated.items(), key=lambda x: x[1]['total_traders'], reverse=True):
        print(f"\n{coin}:")
        print(f"  Total traders: {agg['total_traders']}")
        print(f"  Long: {agg['long_count']} ({agg['long_percentage']:.1f}%)")
        print(f"  Short: {agg['short_count']} ({agg['short_percentage']:.1f}%)")
        print(f"  Long USD: ${agg['long_usd_value']:.2f}")
        print(f"  Short USD: ${agg['short_usd_value']:.2f}")
        print(f"  Min sample size: {agg['has_min_sample_size']}")

    return aggregated


async def test_signal_generation(aggregated):
    """Test signal generation."""
    print("\n" + "="*80)
    print("TEST 4: Signal Generation")
    print("="*80)

    config = ConrarianConfig()
    generator = ContrarianSignalGenerator(
        thresholds=config.signal_thresholds,
        min_traders_for_signal=2  # Lower for testing
    )

    signals = generator.generate_signals(aggregated)

    print(f"Generated {len(signals)} signals")

    for signal in signals[:10]:
        print(f"\n{signal['coin']}:")
        print(f"  Signal: {signal['signal_direction']} ({signal['signal_strength']})")
        print(f"  Confidence: {signal['confidence_score']:.2f}")
        print(f"  Bad traders: {signal['bad_traders_total']}")
        print(f"  Count-based: {signal['long_percentage']:.1f}% L / {signal['short_percentage']:.1f}% S")
        print(f"  Size-weighted: {signal['long_usd_percentage']:.1f}% L / {signal['short_usd_percentage']:.1f}% S")

    return signals


async def test_dashboard(signals):
    """Test dashboard display."""
    print("\n" + "="*80)
    print("TEST 5: Dashboard Display")
    print("="*80)

    dashboard = ContrarianDashboard(
        show_size_weighted=True,
        top_signals_limit=10
    )

    dashboard.print_static(
        signals,
        bad_traders_count=277,
        traders_with_positions=len(set(s['coin'] for s in signals)),
        last_update=datetime.now()
    )

    print("\n" + "="*80)
    print("Summary View:")
    print("="*80)

    dashboard.print_summary(signals)


async def test_database_storage(signals, positions):
    """Test database storage."""
    print("\n" + "="*80)
    print("TEST 6: Database Storage")
    print("="*80)

    config = ConrarianConfig()
    db = ContrarianDatabase(config.database.contrarian_path)

    await db.initialize()

    # Save signals
    for signal in signals[:5]:  # Save first 5
        await db.save_signal(signal)

    print(f"Saved {min(5, len(signals))} signals to database")

    # Save position snapshots
    await db.save_position_snapshot(positions[:10])
    print(f"Saved {min(10, len(positions))} position snapshots")

    # Read back recent signals
    recent = await db.get_recent_signals(limit=5)
    print(f"\nRead back {len(recent)} recent signals from database")

    for sig in recent:
        print(f"  {sig['coin']}: {sig['signal_direction']} ({sig['signal_strength']})")


async def run_all_tests():
    """Run all tests in sequence."""
    print("\n" + "="*80)
    print("CONTRARIAN SIGNAL SYSTEM - TEST SUITE")
    print("="*80)

    try:
        # Test 1: Phase 2 Reader
        bad_traders = await test_phase2_reader()

        if not bad_traders:
            print("\n⚠️  No bad traders found. Cannot continue tests.")
            return

        addresses = [t['address'] for t in bad_traders]

        # Test 2: Position Fetcher
        positions = await test_position_fetcher(addresses)

        if not positions:
            print("\n⚠️  No positions found. Using mock data for remaining tests.")
            # Could add mock data here if needed
            return

        # Test 3: Aggregation
        aggregated = await test_aggregation(positions)

        # Test 4: Signal Generation
        signals = await test_signal_generation(aggregated)

        # Test 5: Dashboard
        await test_dashboard(signals)

        # Test 6: Database Storage
        await test_database_storage(signals, positions)

        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*80)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        logger.error("Test failed", exc_info=True)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
