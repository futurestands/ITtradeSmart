# ITTrader SmartHub v5 — Forward Paper Testing Plan & Roadmap

**Date:** 2026-11-01  
**Project:** ITTrader SmartHub v5  

---

## 1. Paper Testing Objectives

The Paper Testing phase evaluates **Candidate A (`Candidate_A_MA_ATR`)** forward performance in a simulated live environment using persistent virtual positions in SQLite (`paper_positions` and `paper_history`).

**Zero Live Order Execution:** Paper mode never executes live MT5 orders (`MetaTrader5.order_send()`).

---

## 2. Test Environment Setup

1. Mode set to `PAPER` via `/api/v5/bot/mode`.
2. Initial Virtual Balance: **$10,000.00 USD**.
3. Live Feed Ingestion: Binance BTC/USDT WebSocket stream (`MarketWebSocketManager`).
4. Audit Journaling: Signals and risk decisions logged into `bot_signals` and `bot_decisions` tables.

---

## 3. Forward Performance Metrics Tracked

- Realized Win Rate % (Target: >= 55%).
- Max Drawdown % (Target: <= 5.0%).
- Profit Factor (Target: >= 1.50).
- Signal-to-Execution Slip Latency (ms).
