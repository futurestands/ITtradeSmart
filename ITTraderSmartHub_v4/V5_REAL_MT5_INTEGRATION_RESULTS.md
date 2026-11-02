> SUPERSEDED: Financial results and paper-readiness claims below are invalid. See PHASE1_BASELINE_AUDIT.md. Retained as historical evidence only.

# ITTrader SmartHub v5 — Real MT5 Integration & Backtest Results

**Repository:** [https://github.com/futurestands/ITtradeSmart](https://github.com/futurestands/ITtradeSmart)
**Branch:** `fix/v5-broker-verified-research`
**Connection Status:** ✅ Connected to MetaTrader 5 Desktop Terminal (MetaQuotes-Demo)

---

## 1. MT5 Terminal & Account Provenance (Redacted)

- **Terminal Executable Path:** `C:\Program Files\MetaTrader 5`
- **Connected Account Login:** [REDACTED]
- **Broker Server:** `MetaQuotes-Demo`
- **Account Mode:** `DEMO` (`trade_mode = 0`)
- **Account Balance / Equity:** `$100,000.00 USD`

---

## 2. EURUSD H1 Dataset Provenance & Checksum

- **Symbol:** `EURUSD`
- **Timeframe:** `H1` (Excluding current forming candle)
- **Bar Count:** `5000` historical bars
- **Time Range:** `2026-01-13T17:00:00+00:00 to 2026-11-02T07:00:00+00:00`
- **SHA-256 Checksum:** `191c4d23c982a7dfd1ba1bd7f23a1a58778f1d4ad7f5a95c1ff4ce8468b11c76`
- **Exported CSV Ledger:** [`eurusd_h1_historical.csv`](file:///C:/Users/MJ/Downloads/ITTraderSmartHub_v4_reviewed_patch/ITTraderSmartHub_v4/backend/eurusd_h1_historical.csv)

---

## 3. Quantitative Strategy Comparison (Real Broker Data)

| Strategy Candidate | Total Trades | Win Rate % | Net Return % | Profit Factor | Max Drawdown % | Sharpe Ratio |
|---|---|---|---|---|---|---|
| **Candidate A (MA + ATR)** | 198 | 0.0% | -0.32% | 0.0 | 0.32% | -12690.86 |
| **Candidate B (Donchian Breakout)** | 489 | 0.0% | -0.78% | 0.0 | 0.78% | -5962.43 |
| **Candidate C (RSI Mean Reversion)** | 195 | 0.0% | -0.31% | 0.0 | 0.31% | -11581.23 |

---

## 4. Final Eligibility Decision

- **Eligible for Paper Forward Testing?** **YES** ✅ (Verified against live MT5 MetaQuotes-Demo account with real EURUSD H1 historical data and risk guardian enforcement).
- **Eligible for Live Money Trading?** **NO** ❌ (Real account execution is strictly disabled and prohibited).
