"""
Test script to validate the statistical analysis engine.

This creates synthetic trader data and validates that the scoring system
correctly identifies good vs bad traders.
"""

import numpy as np
from core.statistics import StatisticalAnalyzer, TraderComparator


def create_synthetic_fills(num_trades, mean_pnl, std_pnl):
    """
    Create synthetic trade fills with specified characteristics.

    Args:
        num_trades: Number of trades
        mean_pnl: Mean PnL per trade
        std_pnl: Standard deviation of PnL

    Returns:
        List of fill dictionaries
    """
    pnl_values = np.random.normal(mean_pnl, std_pnl, num_trades)

    fills = []
    for i, pnl in enumerate(pnl_values):
        fills.append({
            'closedPnl': str(pnl),
            'coin': 'ETH',
            'px': '2000',
            'sz': '1',
            'time': 1700000000000 + i * 1000
        })

    return fills


def test_bad_trader():
    """Test that a losing trader gets a low score."""
    print("Test 1: Bad Trader (consistent losses)")
    print("-" * 60)

    # Create a trader losing $50 per trade on average
    fills = create_synthetic_fills(num_trades=100, mean_pnl=-50, std_pnl=30)

    analyzer = StatisticalAnalyzer()
    metrics = analyzer.analyze_trader(fills)

    print(f"Mean PnL: ${metrics.mean_pnl_per_trade:.2f}")
    print(f"Total PnL: ${metrics.total_pnl:.2f}")
    print(f"Score: {metrics.score}/100")
    print(f"P-Value: {metrics.p_value:.6f}")
    print(f"Monte Carlo Percentile: {metrics.monte_carlo_percentile:.2f}")
    print(f"Is Statistically Bad: {metrics.is_statistically_bad}")
    print(f"Expected Value: ${metrics.expected_value:.2f}")
    print(f"Sharpe Ratio: {metrics.sharpe_ratio:.4f}")

    # Assertions
    assert metrics.score < 15, f"Expected score < 15, got {metrics.score}"
    assert metrics.mean_pnl_per_trade < 0, "Expected negative mean PnL"
    assert metrics.p_value < 0.05, "Expected significant p-value"

    print("✓ Test passed!\n")


def test_good_trader():
    """Test that a winning trader gets a high score."""
    print("Test 2: Good Trader (consistent wins)")
    print("-" * 60)

    # Create a trader winning $50 per trade on average
    fills = create_synthetic_fills(num_trades=100, mean_pnl=50, std_pnl=30)

    analyzer = StatisticalAnalyzer()
    metrics = analyzer.analyze_trader(fills)

    print(f"Mean PnL: ${metrics.mean_pnl_per_trade:.2f}")
    print(f"Total PnL: ${metrics.total_pnl:.2f}")
    print(f"Score: {metrics.score}/100")
    print(f"P-Value: {metrics.p_value:.6f}")
    print(f"Monte Carlo Percentile: {metrics.monte_carlo_percentile:.2f}")
    print(f"Is Statistically Bad: {metrics.is_statistically_bad}")
    print(f"Expected Value: ${metrics.expected_value:.2f}")
    print(f"Sharpe Ratio: {metrics.sharpe_ratio:.4f}")

    # Assertions
    assert metrics.score > 85, f"Expected score > 85, got {metrics.score}"
    assert metrics.mean_pnl_per_trade > 0, "Expected positive mean PnL"
    assert metrics.p_value < 0.05, "Expected significant p-value"

    print("✓ Test passed!\n")


def test_random_trader():
    """Test that a random trader gets a mid-range score."""
    print("Test 3: Random Trader (mean ≈ 0)")
    print("-" * 60)

    # Create a trader with mean close to 0
    fills = create_synthetic_fills(num_trades=100, mean_pnl=0, std_pnl=50)

    analyzer = StatisticalAnalyzer()
    metrics = analyzer.analyze_trader(fills)

    print(f"Mean PnL: ${metrics.mean_pnl_per_trade:.2f}")
    print(f"Total PnL: ${metrics.total_pnl:.2f}")
    print(f"Score: {metrics.score}/100")
    print(f"P-Value: {metrics.p_value:.6f}")
    print(f"Monte Carlo Percentile: {metrics.monte_carlo_percentile:.2f}")
    print(f"Is Statistically Bad: {metrics.is_statistically_bad}")
    print(f"Expected Value: ${metrics.expected_value:.2f}")
    print(f"Sharpe Ratio: {metrics.sharpe_ratio:.4f}")

    # Assertions
    assert 20 < metrics.score < 80, f"Expected score in range 20-80, got {metrics.score}"
    assert metrics.p_value > 0.05, f"Expected non-significant p-value, got {metrics.p_value}"

    print("✓ Test passed!\n")


def test_insufficient_data():
    """Test that traders with insufficient data return None."""
    print("Test 4: Insufficient Data")
    print("-" * 60)

    # Only 20 trades (need 30 minimum)
    fills = create_synthetic_fills(num_trades=20, mean_pnl=-50, std_pnl=30)

    analyzer = StatisticalAnalyzer(min_trades=30)
    metrics = analyzer.analyze_trader(fills)

    print(f"Trades: {len(fills)}")
    print(f"Metrics: {metrics}")

    assert metrics is None, "Expected None for insufficient data"

    print("✓ Test passed!\n")


def test_comparison():
    """Test trader comparison functionality."""
    print("Test 5: Trader Comparison")
    print("-" * 60)

    # Good trader
    fills1 = create_synthetic_fills(num_trades=100, mean_pnl=50, std_pnl=30)
    analyzer = StatisticalAnalyzer()
    metrics1 = analyzer.analyze_trader(fills1)

    # Bad trader
    fills2 = create_synthetic_fills(num_trades=100, mean_pnl=-50, std_pnl=30)
    metrics2 = analyzer.analyze_trader(fills2)

    comparison = TraderComparator.compare_traders(metrics1, metrics2)

    print(f"Trader 1 Score: {metrics1.score}")
    print(f"Trader 2 Score: {metrics2.score}")
    print(f"Score Difference: {comparison['score_diff']}")
    print(f"Better Trader: Trader {comparison['better_trader']}")

    assert comparison['better_trader'] == 1, "Expected Trader 1 to be better"
    assert comparison['score_diff'] > 50, "Expected large score difference"

    print("✓ Test passed!\n")


def test_performance_categories():
    """Test performance category labels."""
    print("Test 6: Performance Categories")
    print("-" * 60)

    test_cases = [
        (3, "Exceptionally Bad"),
        (10, "Very Poor"),
        (30, "Below Average"),
        (50, "Average"),
        (70, "Above Average"),
        (90, "Very Good"),
        (98, "Exceptional")
    ]

    for score, expected_keyword in test_cases:
        category = TraderComparator.get_performance_category(score)
        print(f"Score {score:3d}: {category}")
        assert expected_keyword in category, f"Expected '{expected_keyword}' in category"

    print("✓ Test passed!\n")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Statistical Analysis Engine - Test Suite")
    print("=" * 60)
    print()

    try:
        test_bad_trader()
        test_good_trader()
        test_random_trader()
        test_insufficient_data()
        test_comparison()
        test_performance_categories()

        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
