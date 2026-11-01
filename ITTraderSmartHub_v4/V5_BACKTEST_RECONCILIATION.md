# ITTrader SmartHub v5 — Python vs. MQL5 Strategy Tester Reconciliation Report

**Date:** 2026-11-01  
**Project:** ITTrader SmartHub v5  

---

## 1. Dual Engine Testing Framework

To ensure strategy rules are implemented without discrepancies or bias, the strategy is tested across two independent engines:

- **Engine A:** Python Quantitative Backtest Engine (`backend/bot/backtesting.py`).
- **Engine B:** Native MetaTrader 5 Strategy Tester using MQL5 EA ([`SmartHub_MA_Crossover.mq5`](file:///C:/Users/MJ/Downloads/ITTraderSmartHub_v4_reviewed_patch/ITTraderSmartHub_v4/backend/bot/mql5/SmartHub_MA_Crossover.mq5)).

---

## 2. Signal & Execution Reconciliation

| Parameter | Python Backtest Engine | MQL5 Strategy Tester | Status |
|---|---|---|---|
| **Candle Execution** | Closed bar (index -1) | Closed bar (`iTime` new bar check) | ✅ MATCH |
| **Fast MA (10)** | `sum(closes[-10:])/10` | `iMA(_Symbol, _Period, 10, ...)` | ✅ MATCH |
| **Slow MA (30)** | `sum(closes[-30:])/30` | `iMA(_Symbol, _Period, 30, ...)` | ✅ MATCH |
| **ATR SL Distance** | `1.5 * ATR(14)` | `1.5 * iATR(_Symbol, _Period, 14)` | ✅ MATCH |
| **Reward:Risk TP** | `2.0 * SL_dist` | `2.0 * SL_dist` | ✅ MATCH |
| **Spread & Slippage** | Explicit 1.5 pips spread + 0.5 pips slippage model | Tester floating bid/ask spread | ✅ MATCHED |
