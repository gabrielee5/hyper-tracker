# Track Role Configuration Guide

## Overview

The tracker now supports filtering addresses based on their role in trades (maker vs. taker). This allows you to focus on specific types of traders based on your analysis needs.

## Configuration

Add the `TRACK_ROLE` setting to your `.env` file:

```bash
TRACK_ROLE=both  # Options: 'maker', 'taker', or 'both'
```

### Options

- **`both`** (default): Track both maker and taker addresses from all trades
- **`maker`**: Only track addresses that placed limit orders (makers)
- **`taker`**: Only track addresses that took liquidity from the order book (takers)

## How It Works

### Trade Mechanics

In Hyperliquid's WebSocket trade data:
- `users` array contains `[buyer, seller]`
- `side` field indicates which side took liquidity:
  - **`"A"` (Ask)**: Seller is the taker (buyer hit the ask price)
  - **`"B"` (Bid)**: Buyer is the taker (seller hit the bid price)

### Role Determination

| Trade Side | Maker       | Taker       |
|-----------|-------------|-------------|
| `"A"` (Ask) | Buyer       | Seller      |
| `"B"` (Bid) | Seller      | Buyer       |

### Examples

#### Example 1: Ask Trade (side="A")
```json
{
  "coin": "BTC",
  "side": "A",
  "px": "50000",
  "sz": "1.0",
  "users": ["0xBUYER123", "0xSELLER456"]
}
```

- **Maker**: `0xBUYER123` (placed a limit buy order)
- **Taker**: `0xSELLER456` (sold into the limit order)

#### Example 2: Bid Trade (side="B")
```json
{
  "coin": "ETH",
  "side": "B",
  "px": "3000",
  "sz": "2.0",
  "users": ["0xBUYER789", "0xSELLER012"]
}
```

- **Maker**: `0xSELLER012` (placed a limit sell order)
- **Taker**: `0xBUYER789` (bought from the limit order)

## Use Cases

### Track Makers Only
```bash
TRACK_ROLE=maker
```

**Why?** Makers typically represent more sophisticated traders who provide liquidity and may have stronger directional convictions.

### Track Takers Only
```bash
TRACK_ROLE=taker
```

**Why?** Takers are often more reactive and may represent momentum-based trading activity or urgent market orders.

### Track Both
```bash
TRACK_ROLE=both
```

**Why?** Get a complete view of all market participants for comprehensive analysis.

## Implementation Details

### Files Modified

1. **`.env.example`**: Added `TRACK_ROLE` configuration option
2. **`fetcher/config.py`**: Added `track_role` field with validation
3. **`fetcher/address_tracker.py`**: Updated `process_trade_event()` to filter addresses based on role
4. **`fetcher/main.py`**: Pass `track_role` from config to tracker

### Key Code Changes

The address filtering logic in `fetcher/address_tracker.py:70-90`:

```python
if self.track_role == "both":
    addresses_to_track = [buyer, seller]
elif self.track_role == "taker":
    # Side "A" means seller is taker, Side "B" means buyer is taker
    taker = seller if side == "A" else buyer
    addresses_to_track = [taker]
elif self.track_role == "maker":
    # Side "A" means buyer is maker, Side "B" means seller is maker
    maker = buyer if side == "A" else seller
    addresses_to_track = [maker]
```

## Testing

Run the test suite to verify the implementation:

```bash
python3 test_track_role.py
```

This will validate that:
- `both` mode tracks all addresses
- `taker` mode only tracks takers
- `maker` mode only tracks makers

## Monitoring

When the tracker starts, it will log the current tracking mode:

```
INFO - Starting Hyperliquid Tracker
INFO - Network: mainnet
INFO - Database: data/addresses.db
INFO - Tracking role: both
```

## Notes

- The default value is `both` to maintain backward compatibility
- Invalid values will raise a `ValueError` on startup
- Volume attribution is divided equally among tracked addresses (e.g., if tracking both, each gets 50% of trade value)
