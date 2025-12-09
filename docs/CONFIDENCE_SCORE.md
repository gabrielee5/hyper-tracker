# Confidence Score Calculation

## Overview

The confidence score is a metric (0.0 to 1.0) that indicates how reliable a contrarian trading signal is. It's calculated in the `ContrarianSignalGenerator._calculate_confidence()` method and combines two key factors:

1. **Positioning extremity** - How imbalanced is the trader positioning?
2. **Sample size** - Do we have enough data to trust this signal?

## Formula

```python
confidence = imbalance × sample_multiplier
```

Where:
- `imbalance` = How far positioning deviates from neutral (50/50)
- `sample_multiplier` = Reliability factor based on number of traders

## Component Breakdown

### 1. Positioning Imbalance (0.0 to 1.0)

Measures how far the positioning is from neutral:

```python
imbalance = abs(long_pct - 50.0) / 50.0
```

**Examples:**
- 50% long / 50% short → `imbalance = 0.0` (perfectly balanced, no signal)
- 60% long / 40% short → `imbalance = 0.2` (slight imbalance)
- 75% long / 25% short → `imbalance = 0.5` (moderate imbalance)
- 90% long / 10% short → `imbalance = 0.8` (strong imbalance)
- 100% long / 0% short → `imbalance = 1.0` (maximum imbalance)

### 2. Sample Size Multiplier (0.0 to 1.0)

Reduces confidence when sample size is small:

```python
sample_multiplier = min(1.0, total_traders / (min_traders_for_signal × 3))
```

With default `min_traders_for_signal = 10`:
- Full confidence threshold: **30+ traders**
- Scales linearly below 30 traders

**Examples:**
- 10 traders → `sample_multiplier = 0.333` (minimum sample)
- 15 traders → `sample_multiplier = 0.500`
- 20 traders → `sample_multiplier = 0.667`
- 30+ traders → `sample_multiplier = 1.000` (full reliability)

## Why Multiplicative?

The multiplicative approach ensures that:

1. **Weak positioning always yields low confidence**, regardless of sample size
   - Even with 100 traders, a 51/49 split gets ~0.02 confidence (not 0.30)

2. **Strong positioning is penalized by small samples**
   - An 80/20 split with only 10 traders gets 0.20 confidence (not 0.52)

3. **Both factors must be strong for high confidence**
   - You need BOTH extreme positioning AND sufficient sample size

## Practical Examples

### Example 1: Strong Signal, Good Sample
- **Positioning**: 80% long / 20% short
- **Sample**: 25 traders
- **Imbalance**: |80 - 50| / 50 = 0.6
- **Sample multiplier**: min(1.0, 25/30) = 0.833
- **Confidence**: 0.6 × 0.833 = **0.500**

### Example 2: Strong Signal, Small Sample
- **Positioning**: 80% long / 20% short
- **Sample**: 10 traders (minimum)
- **Imbalance**: 0.6
- **Sample multiplier**: min(1.0, 10/30) = 0.333
- **Confidence**: 0.6 × 0.333 = **0.200**
- *Interpretation: Good positioning but not enough data*

### Example 3: Weak Signal, Large Sample
- **Positioning**: 51% long / 49% short
- **Sample**: 40 traders
- **Imbalance**: |51 - 50| / 50 = 0.02
- **Sample multiplier**: 1.0
- **Confidence**: 0.02 × 1.0 = **0.020**
- *Interpretation: Lots of data but positioning is basically neutral*

### Example 4: Extreme Signal, Excellent Sample
- **Positioning**: 95% long / 5% short
- **Sample**: 50 traders
- **Imbalance**: |95 - 50| / 50 = 0.9
- **Sample multiplier**: 1.0
- **Confidence**: 0.9 × 1.0 = **0.900**
- *Interpretation: Very strong signal with solid data*

## Confidence Thresholds in Practice

When filtering actionable signals, typical thresholds:

- **≥ 0.70**: Very high confidence - most reliable signals
- **≥ 0.50**: Moderate confidence - reasonably reliable
- **≥ 0.30**: Low confidence - use with caution
- **< 0.30**: Very low confidence - probably not actionable

## Implementation Location

File: `contrarian/core/signal_generator.py:185-217`

The confidence score is:
1. Calculated for each coin's signal
2. Included in the signal dictionary as `confidence_score`
3. Used to sort signals (highest confidence first)
4. Used in `get_actionable_signals()` for filtering

## Related Concepts

- **Signal Direction**: LONG, SHORT, or NEUTRAL (contrarian to bad traders)
- **Signal Strength**: STRONG (≥70%), MODERATE (≥60%), WEAK, or NONE
- **Primary Metric**: Whether using count-based or size-weighted percentages

The confidence score works independently of signal strength - you can have a STRONG signal with low confidence (if sample is small) or a MODERATE signal with high confidence (if positioning is clear with good sample size).
