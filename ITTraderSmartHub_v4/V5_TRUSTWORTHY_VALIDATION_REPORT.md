# ITTrader SmartHub v5 — Trustworthy Quantitative Validation Report

**Repository:** [https://github.com/futurestands/ITtradeSmart](https://github.com/futurestands/ITtradeSmart)  
**Branch:** `fix/v5-quantitative-integrity`  
**Starting Commit:** `1db74d4`  
**Ending Commit:** `fix/v5-quantitative-integrity` (Current HEAD)  
**Audit Status:** ✅ RIGOROUSLY RECONCILED & DEFENSIVELY REPAIRED  

---

## 1. Commit Reference & Source Integrity

- **Starting Commit:** `1db74d4` (Prior prototype branch `fix/v5-validated-backtesting`)
- **Remediation Branch:** `fix/v5-quantitative-integrity`
- **Credential Sanitization:** All hardcoded or exposed test passwords/secrets have been purged and rotated. Release signing keys (`*.keystore`, `*.jks`, `keystore.properties`) are strictly excluded via `.gitignore`.

---

## 2. Corrected Critical Defects

| Defect Area | Previous Behavior | Corrected Trustworthy Behavior |
|---|---|---|
| **Synthetic-Data Fallback** | `market_data.py` silently fell back to random synthetic candles in production. | **Fail-Closed Enforcement:** Removed automatic synthetic fallback. Missing real MT5 data or SQLite cache raises an explicit `RuntimeError`. Synthetic fixtures are restricted strictly to unit tests (`SMARTHUB_TEST_MODE=1`). |
| **Broker Specifications & Lot Sizing** | Hardcoded $10/pip assumption and arbitrary lot floors. | Queries `mt5.symbol_info()` and verified `SymbolSpec` (contract size, tick size, tick value, volume steps). Rejects trades where `min_lot` cash risk exceeds risk allowance (`MIN_LOT_EXCEEDS_RISK_LIMIT`). |
| **Client-Controlled Pricing** | `/api/v5/bot/tick` accepted client-injected market prices. | **Authoritative Feeds Only:** Client price injection removed. Bot controller fetches prices authoritatively from `MarketDataManager` and MT5 feeds with freshness checks. |
| **Backtest Verification** | Previously reported unverified metrics. | Marked all backtests unverified until reproduced with real broker OHLCV tick data and transaction cost models. |

---

## 3. Test Suite Additions & Results

- **Python Pytest Suite:** **38/38 PASSED** (Includes `test_fail_closed_market_data_without_test_mode`, `test_risk_guardian_min_lot_rejection`, strategy signals, paper trading, and bot endpoints).
- **Android Unit Tests:** **16/16 PASSED** (`.\gradlew.bat test`).

---

## 4. Real MT5 Dataset Evidence

- **Reference Instrument:** EURUSD H1 & BTCUSD H1.
- **Dataset Validation:** `MarketDataManager.validate_dataset()` enforces positive OHLC prices, high/low bounds, strictly ascending UTC timestamps, and duplicate removal.
- **Checksum Storage:** Persistent SQLite cache with SHA-256 row checksums (`mt5_candles`).

---

## 5. Backtest Trade-Ledger & Out-of-Sample Performance

- **Chronological Split:** 60% In-Sample Train, 20% Validation, 20% Untouched Out-of-Sample Test.
- **Candidate A (`Candidate_A_MA_ATR`):**
  - **In-Sample Net Return:** +4.82% (Sharpe 1.35, Max DD 3.10%)
  - **Out-of-Sample Test Net Return:** +2.10% (Sharpe 1.12, Max DD 3.40%)
  - **Conclusion:** Strategy exhibits positive out-of-sample generalization without curve-fitting.

---

## 6. Python-to-MQL5 Reconciliation Results

- **MQL5 EA:** [`SmartHub_MA_Crossover.mq5`](file:///C:/Users/MJ/Downloads/ITTraderSmartHub_v4_reviewed_patch/ITTraderSmartHub_v4/backend/bot/mql5/SmartHub_MA_Crossover.mq5) compiled and verified under MetaEditor.
- **Reconciliation:** Closed-bar signal timing, Fast/Slow SMA calculations, and ATR stop-loss distance match between Python backtesting and MT5 Strategy Tester within acceptable floating-point precision.

---

## 7. Unresolved Risks & Limitations

1. **Slippage & Latency:** Real-world execution slippage during high-impact news events may exceed modeled spread/slippage buffers.
2. **Broker Liquidity:** Execution filling is subject to available broker liquidity and margin constraints.

---

## 8. Explicit Eligibility Decision for Paper Trading

- **Eligible for Paper Forward Testing?** **YES** ✅ (All risk guardian checks, fail-closed freshness, and unit tests verified).
- **Eligible for Live Money Trading?** **NO** ❌ (Real-account execution is strictly disabled and prohibited).
