"""
Test script to manually verify position fetching and processing flow.

Shows raw data at each step:
1. Raw API response from Hyperliquid
2. Parsed positions
3. Aggregated data by coin
4. Generated signals
5. Data to be stored in database

Usage:
    python test_position_flow.py
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from contrarian.core.config import ConrarianConfig
from contrarian.core.database import Phase2Reader, ContrarianDatabase
from contrarian.core.position_fetcher import HyperliquidPositionFetcher, parse_positions
from contrarian.core.aggregator import PositionAggregator
from contrarian.core.signal_generator import ContrarianSignalGenerator


def print_separator(title: str, char: str = "="):
    """Print a formatted section separator."""
    print(f"\n{char * 80}")
    print(f" {title}")
    print(f"{char * 80}\n")


def print_json(data, indent: int = 2):
    """Pretty print JSON data."""
    print(json.dumps(data, indent=indent, default=str))


def print_trader_header(index: int, address: str, total: int):
    """Print trader info header."""
    short_addr = f"{address[:6]}...{address[-4:]}"
    print(f"\n{'─' * 80}")
    print(f"TRADER {index + 1}/{total}: {short_addr}")
    print(f"{'─' * 80}")


async def test_position_flow():
    """Test the complete position fetching and processing flow."""

    # Configuration
    config = ConrarianConfig()
    NUM_TRADERS_TO_TEST = 5  # Test with 5 traders

    print_separator("CONTRARIAN POSITION FLOW TEST", "=")
    print(f"Testing with {NUM_TRADERS_TO_TEST} traders")
    print(f"Bad trader threshold: score <= {config.bad_trader_score_threshold}")
    print(f"Min traders for signal: {config.min_traders_for_signal}")

    # Initialize components
    phase2_reader = Phase2Reader(config.database.phase2_path)
    position_fetcher = HyperliquidPositionFetcher(
        base_url=config.api.base_url,
        rate_limit_calls=config.api.rate_limit_calls,
        rate_limit_period=config.api.rate_limit_period,
        timeout=config.api.timeout
    )
    aggregator = PositionAggregator(
        min_traders_for_signal=config.min_traders_for_signal
    )
    signal_generator = ContrarianSignalGenerator(
        thresholds=config.signal_thresholds,
        min_traders_for_signal=config.min_traders_for_signal
    )

    try:
        # ====================================================================
        # STEP 1: Fetch bad traders from Phase 2 database
        # ====================================================================
        print_separator("STEP 1: Fetching Bad Traders from Phase 2 Database")

        bad_traders = await phase2_reader.get_bad_traders(
            score_threshold=config.bad_trader_score_threshold,
            limit=NUM_TRADERS_TO_TEST
        )

        print(f"Found {len(bad_traders)} bad traders")
        print("\nBad Traders Sample:")
        for i, trader in enumerate(bad_traders[:3]):  # Show first 3
            print(f"\n  Trader {i + 1}:")
            print(f"    Address: {trader['address']}")
            print(f"    Score: {trader['score']}")
            print(f"    Total PnL: ${trader['total_pnl']:.2f}")
            print(f"    Win Rate: {trader['win_rate']:.2%}")
            print(f"    Num Trades: {trader['num_trades']}")

        if len(bad_traders) > 3:
            print(f"\n  ... and {len(bad_traders) - 3} more")

        addresses = [trader['address'] for trader in bad_traders]

        # ====================================================================
        # STEP 2: Fetch positions from Hyperliquid API
        # ====================================================================
        print_separator("STEP 2: Fetching Positions from Hyperliquid API")

        print("Fetching positions (this may take a few seconds)...\n")

        positions_by_address = {}
        all_positions = []

        for i, address in enumerate(addresses):
            print_trader_header(i, address, len(addresses))

            # Fetch raw API response
            user_state = await position_fetcher.fetch_positions(address)
            positions_by_address[address] = user_state

            # Show raw API response
            print("\n📥 RAW API RESPONSE:")
            if user_state:
                # Show structure but truncate large fields
                display_state = {
                    'address': user_state.get('address'),
                    'assetPositions': user_state.get('assetPositions', []),
                    'marginSummary': user_state.get('marginSummary', {}),
                    'withdrawable': user_state.get('withdrawable'),
                    'time': user_state.get('time')
                }

                # If there are positions, show them
                if display_state['assetPositions']:
                    print(f"  Found {len(display_state['assetPositions'])} asset positions")
                    print("\n  Asset Positions:")
                    for j, asset_pos in enumerate(display_state['assetPositions'][:3]):  # Show first 3
                        pos_data = asset_pos.get('position', asset_pos)
                        print(f"\n    Position {j + 1}:")
                        print(f"      Coin: {pos_data.get('coin')}")
                        print(f"      Size (szi): {pos_data.get('szi')}")
                        print(f"      Entry Price: {pos_data.get('entryPx')}")
                        print(f"      Position Value: {pos_data.get('positionValue')}")
                        print(f"      Unrealized PnL: {pos_data.get('unrealizedPnl')}")
                        print(f"      Leverage: {pos_data.get('leverage')}")

                    if len(display_state['assetPositions']) > 3:
                        print(f"\n    ... and {len(display_state['assetPositions']) - 3} more positions")
                else:
                    print("  No open positions")

                print(f"\n  Margin Summary:")
                margin = display_state['marginSummary']
                print(f"    Account Value: {margin.get('accountValue', 'N/A')}")
                print(f"    Total Margin Used: {margin.get('totalMarginUsed', 'N/A')}")
            else:
                print("  ❌ No data returned (trader may have no positions)")

            # Parse positions
            if user_state:
                parsed = parse_positions(user_state)
                all_positions.extend(parsed)

                print("\n🔄 PARSED POSITIONS:")
                if parsed:
                    print(f"  Parsed {len(parsed)} positions")
                    for j, pos in enumerate(parsed):
                        print(f"\n    Position {j + 1}:")
                        print(f"      Coin: {pos['coin']}")
                        print(f"      Side: {pos['side']}")
                        print(f"      Size: {pos['size']}")
                        print(f"      USD Value: ${pos['position_value_usd']:.2f}")
                        print(f"      Entry Price: ${pos['entry_price']:.4f}")
                        print(f"      Leverage: {pos['leverage_value']}x")
                        print(f"      Unrealized PnL: ${pos['unrealized_pnl']:.2f}")
                else:
                    print("  No positions to parse")

        # ====================================================================
        # STEP 3: Aggregate positions by coin
        # ====================================================================
        print_separator("STEP 3: Aggregating Positions by Coin")

        print(f"Total positions across all traders: {len(all_positions)}\n")

        aggregated = aggregator.aggregate_positions(all_positions)

        print(f"Aggregated data for {len(aggregated)} unique coins:\n")

        # Sort by total traders for display
        sorted_coins = sorted(
            aggregated.items(),
            key=lambda x: x[1]['total_traders'],
            reverse=True
        )

        for coin, agg_data in sorted_coins:
            print(f"  📊 {coin}:")
            print(f"      Total Traders: {agg_data['total_traders']}")
            print(f"      Long Count: {agg_data['long_count']} ({agg_data['long_percentage']:.1f}%)")
            print(f"      Short Count: {agg_data['short_count']} ({agg_data['short_percentage']:.1f}%)")
            print(f"      Long USD Value: ${agg_data['long_usd_value']:.2f}")
            print(f"      Short USD Value: ${agg_data['short_usd_value']:.2f}")
            print(f"      Has Min Sample Size: {agg_data['has_min_sample_size']}")

            # Show individual positions for this coin
            coin_positions = agg_data['positions']
            print(f"      Individual Positions ({len(coin_positions)}):")
            for pos in coin_positions:
                side_emoji = "📈" if pos['side'] == 'LONG' else "📉"
                short_addr = f"{pos['address'][:6]}...{pos['address'][-4:]}"
                print(f"        {side_emoji} {short_addr}: {pos['side']} ${pos['position_value_usd']:.2f}")
            print()

        # ====================================================================
        # STEP 4: Generate signals
        # ====================================================================
        print_separator("STEP 4: Generating Contrarian Signals")

        signals = signal_generator.generate_signals(
            aggregated,
            use_size_weighted=False  # Use count-based
        )

        print(f"Generated {len(signals)} signals\n")

        if signals:
            for i, signal in enumerate(signals, 1):
                print(f"  🎯 Signal {i}: {signal['coin']}")
                print(f"      Direction: {signal['signal_direction']}")
                print(f"      Strength: {signal['signal_strength']}")
                print(f"      Confidence Score: {signal['confidence_score']:.3f}")
                print(f"      Primary Metric: {signal['primary_metric']}")
                print(f"\n      Bad Traders Positioning:")
                print(f"        Total: {signal['bad_traders_total']}")
                print(f"        Long: {signal['long_count']} ({signal['long_percentage']:.1f}%)")
                print(f"        Short: {signal['short_count']} ({signal['short_percentage']:.1f}%)")
                print(f"\n      Size-Weighted:")
                print(f"        Long USD: ${signal['long_usd_value']:.2f} ({signal['long_usd_percentage']:.1f}%)")
                print(f"        Short USD: ${signal['short_usd_value']:.2f} ({signal['short_usd_percentage']:.1f}%)")

                # Explain the signal
                print(f"\n      📝 Explanation:")
                explanation = signal_generator.explain_signal(signal)
                for line in explanation.split('\n'):
                    print(f"        {line}")
                print()
        else:
            print("  ℹ️  No signals generated (insufficient data or no coins meet threshold)")

        # ====================================================================
        # STEP 5: Show what would be stored in database
        # ====================================================================
        print_separator("STEP 5: Data to be Stored in Database")

        print("📁 CONTRARIAN_SIGNALS Table:\n")
        if signals:
            for i, signal in enumerate(signals, 1):
                print(f"  Record {i}:")
                print(f"    coin: {signal['coin']}")
                print(f"    signal_direction: {signal['signal_direction']}")
                print(f"    signal_strength: {signal['signal_strength']}")
                print(f"    bad_traders_total: {signal['bad_traders_total']}")
                print(f"    long_count: {signal['long_count']}")
                print(f"    short_count: {signal['short_count']}")
                print(f"    long_percentage: {signal['long_percentage']:.2f}")
                print(f"    short_percentage: {signal['short_percentage']:.2f}")
                print(f"    long_usd_value: {signal['long_usd_value']:.2f}")
                print(f"    short_usd_value: {signal['short_usd_value']:.2f}")
                print(f"    long_usd_percentage: {signal['long_usd_percentage']:.2f}")
                print(f"    short_usd_percentage: {signal['short_usd_percentage']:.2f}")
                print(f"    confidence_score: {signal['confidence_score']:.3f}")
                print(f"    primary_metric: {signal['primary_metric']}")
                print()
        else:
            print("  No signals to store")

        print("\n📁 POSITION_SNAPSHOT Table:\n")
        print(f"  Total records to insert: {len(all_positions)}")

        if all_positions:
            print("\n  Sample records (first 5):")
            for i, pos in enumerate(all_positions[:5], 1):
                short_addr = f"{pos['address'][:6]}...{pos['address'][-4:]}"
                print(f"\n    Record {i}:")
                print(f"      address: {short_addr}")
                print(f"      coin: {pos['coin']}")
                print(f"      side: {pos['side']}")
                print(f"      size: {pos['size']}")
                print(f"      position_value_usd: {pos['position_value_usd']:.2f}")
                print(f"      entry_price: {pos['entry_price']:.4f}")
                print(f"      leverage_value: {pos['leverage_value']}")
                print(f"      unrealized_pnl: {pos['unrealized_pnl']:.2f}")

            if len(all_positions) > 5:
                print(f"\n    ... and {len(all_positions) - 5} more records")
        else:
            print("  No positions to store")

        # ====================================================================
        # SUMMARY
        # ====================================================================
        print_separator("TEST SUMMARY", "=")

        traders_with_positions = sum(
            1 for user_state in positions_by_address.values()
            if user_state and user_state.get('assetPositions')
        )

        print(f"✅ Bad traders fetched: {len(bad_traders)}")
        print(f"✅ Traders with open positions: {traders_with_positions}")
        print(f"✅ Total positions found: {len(all_positions)}")
        print(f"✅ Unique coins: {len(aggregated)}")
        print(f"✅ Signals generated: {len(signals)}")
        print(f"✅ Database records (signals): {len(signals)}")
        print(f"✅ Database records (snapshots): {len(all_positions)}")

        print("\n" + "=" * 80)
        print("Test completed successfully!")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up
        await position_fetcher.close()


if __name__ == "__main__":
    asyncio.run(test_position_flow())
