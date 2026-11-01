# ITTrader SmartHub v5 — Real Market Data Validation Report

**Date:** 2026-11-01  
**Project:** ITTrader SmartHub v5  
**Module:** `MarketDataManager` (`backend/bot/market_data.py`)  

---

## 1. Ingestion Pipeline & Checksum Verification

Historical data is ingested directly from MetaTrader 5 using the official `MetaTrader5` Python package (`copy_rates_from_pos`, `copy_rates_range`, `copy_ticks_range`).

### Data Attributes Recorded:
- **Broker & Server ID:** Verified from MT5 terminal metadata.
- **Symbol:** Normalized (e.g. `EURUSD`, `GBPUSD`, `XAUUSD`, `BTCUSD`).
- **Timeframe:** `M1`, `M5`, `H1`, `D1`.
- **Timestamps:** ISO-8601 UTC string (`YYYY-MM-DDTHH:MM:SSZ`).
- **OHLCV + Spread:** Open, High, Low, Close, Volume, Spread.
- **Dataset Checksum:** SHA-256 hash computed per row (`SHA256(symbol:time_utc:close)`).

---

## 2. Integrity Validation Rules

Every dataset passes through `MarketDataManager.validate_dataset()`:
1. **Positive Price Rule:** Rejects candles with non-positive prices.
2. **High/Low Bound Check:** Enforces `high >= low`, `high >= open`, `high >= close`, `low <= open`, `low <= close`.
3. **Chronological Ordering:** Enforces strictly increasing UTC timestamps (`curr_time > prev_time`).
4. **Duplicate Detection:** Rejects datasets containing duplicate bar timestamps.

---

## 3. Persistent SQLite Cache Schema

```sql
CREATE TABLE IF NOT EXISTS mt5_candles (
    symbol TEXT,
    timeframe TEXT,
    time_utc TEXT,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    spread REAL,
    checksum TEXT,
    PRIMARY KEY (symbol, timeframe, time_utc)
);
```
