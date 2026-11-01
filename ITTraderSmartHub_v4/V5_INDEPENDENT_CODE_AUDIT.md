# ITTrader SmartHub v5 — Independent Quantitative Code & Security Audit

**Date:** 2026-11-01  
**Project:** ITTrader SmartHub v5 — Automated Trading & Risk Intelligence  
**Branch:** `fix/v5-validated-backtesting`  
**Package:** `com.ittrader.smarthub`  

---

## 1. Executive Summary

An independent quantitative, software architecture, and trading-security audit of the SmartHub v5 prototype was conducted. Unsafe assumptions, synthetic data leaks in production paths, unverified pip value approximations, and bypassable risk boundaries were identified and corrected.

---

## 2. Corrected Unsafe Assumptions & Defects

| Defect / Unsafe Assumption | Audit Finding | Correction Applied | Status |
|---|---|---|---|
| **Synthetic Candle Leaks in Production** | `MarketDataManager` generated random candles in production trading loops. | Removed synthetic generation from production paths. Retained `generate_test_candles()` exclusively for unit tests. | ✅ RESOLVED |
| **Invented Pip Value & Lot Floor** | Assumed hardcoded $10/pip and forced 0.01 lot floor regardless of cash risk. | Integrated `SymbolSpec` with exact broker contract sizes, tick sizes, tick values, and lot steps. Added rejection when `min_lot` cash risk > max allowed risk. | ✅ RESOLVED |
| **Signal Timestamp Repainting** | Signals used `utcnow()` rather than the timestamp of the closed candle. | Enforced closed-candle signal timestamping (`candle.time_utc`). | ✅ RESOLVED |
| **Bypassable Risk Guardian** | Bot controller could bypass Risk Guardian decisions. | Enforced mandatory `RiskGuardian.validate_trade_signal()` routing in all modes. | ✅ RESOLVED |
| **Client-Supplied Price Injection** | Android client could submit arbitrary price triggers to `/api/v5/bot/tick`. | Bot controller fetches prices authoritatively from `MarketDataManager` and MT5. | ✅ RESOLVED |

---

## 3. Architecture Overview (`backend/bot/`)

- `market_data.py`: Handles real MT5 historical data ingestion, UTC normalization, dataset checksums, and fail-closed staleness checking.
- `strategies.py`: Contains 3 transparent candidate strategies (`Candidate_A_MA_ATR`, `Candidate_B_Donchian_Breakout`, `Candidate_C_RSI_MeanReversion`) and a Buy-and-Hold benchmark.
- `risk_guardian.py`: Enforces 0.5% max equity risk, 2% daily loss limit, broker volume steps, and lot-size rejection rules.
- `backtesting.py`: Historical market replay, walk-forward splits, and 50-iteration Monte Carlo robustness testing.
- `paper_trading.py`: Persistent paper trading portfolio with zero calls to live order execution.
- `demo_execution.py`: Restricted MT5 Demo-only execution adapter (disabled by default, strict DEMO account checks).
- `bot_controller.py`: Mode state machine (`OFF`, `BACKTEST`, `PAPER`, `DEMO`) and emergency stop handler.
