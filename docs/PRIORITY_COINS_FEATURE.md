# Priority Coins Feature

## Overview

The contrarian program now supports prioritizing specific coins in the signal table. When configured, these priority coins will always appear at the top of the table, regardless of their confidence score or signal strength.

## Configuration

Edit the `contrarian/config.json` file and add your preferred coins to the `priority_coins` array in the `dashboard` section:

```json
{
  "dashboard": {
    "refresh_rate": 5,
    "show_size_weighted": true,
    "top_signals_limit": 15,
    "enable_colors": true,
    "priority_coins": ["BTC", "ETH"]
  }
}
```

## Behavior

### Default Behavior (No Priority Coins)
Without priority coins configured, signals are sorted by **confidence score** (highest to lowest):

| Coin | Confidence | Signal |
|------|-----------|---------|
| SOL  | 0.95      | STRONG SHORT |
| DOGE | 0.75      | MODERATE SHORT |
| ETH  | 0.65      | MODERATE LONG |
| AVAX | 0.55      | WEAK SHORT |
| BTC  | 0.45      | NEUTRAL |

### With Priority Coins Configured
When you configure `"priority_coins": ["BTC", "ETH"]`, those coins appear first in the order specified, followed by all other coins sorted by confidence:

| Coin | Confidence | Signal | Note |
|------|-----------|---------|------|
| BTC  | 0.45      | NEUTRAL | ⭐ Priority |
| ETH  | 0.65      | MODERATE LONG | ⭐ Priority |
| SOL  | 0.95      | STRONG SHORT | - |
| DOGE | 0.75      | MODERATE SHORT | - |
| AVAX | 0.55      | WEAK SHORT | - |

## Use Cases

This feature is useful when you:

1. **Track specific coins**: Always want to see BTC and ETH at the top, regardless of signal strength
2. **Monitor your portfolio**: Prioritize coins you're currently holding or watching
3. **Focus on majors**: Keep major coins visible even when they have weak/neutral signals
4. **Quick reference**: Quickly check status of key coins without scrolling

## Key Points

- Priority coins appear in the **exact order** specified in the config
- Priority coins are shown even if they have **NEUTRAL** signals or **low confidence**
- If a priority coin has no signal (not in bad trader portfolios), it won't appear
- Non-priority coins continue to be sorted by confidence score
- Empty array `[]` or omitting the field disables the feature (default behavior)

## Examples

### Track BTC only
```json
"priority_coins": ["BTC"]
```

### Track multiple majors in specific order
```json
"priority_coins": ["BTC", "ETH", "SOL"]
```

### Disable priority (default)
```json
"priority_coins": []
```

## Testing

You can test the feature with the provided test scripts:

```bash
cd contrarian
python3 test_priority_coins.py       # Simple sorting test
python3 test_priority_display.py     # Visual dashboard comparison
```

## Implementation Details

- Configuration: `contrarian/config.json`
- Config class: `contrarian/core/config.py` (`DashboardConfig`)
- Sorting logic: `contrarian/core/dashboard.py` (`_sort_signals_with_priority`)
- Main integration: `contrarian/main.py` (passes config to dashboard)
