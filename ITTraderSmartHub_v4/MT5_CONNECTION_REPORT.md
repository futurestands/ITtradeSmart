# ITTrader SmartHub v5 — MT5 Connection & Environment Diagnostic Report

**Date:** 2026-11-01  
**Project:** ITTrader SmartHub v5  
**Branch:** `fix/v5-broker-verified-research`  

---

## 1. Phase 1 Environment Diagnostic Findings

- **Python Interpreter:** `C:\Users\MJ\AppData\Local\Python\pythoncore-3.14-64\python.exe` (Python 3.14.6 64-bit).
- **MetaTrader 5 Python Package:** Successfully installed (`MetaTrader5-5.0.6231`).
- **Terminal Executable Status:** **ABSENT**. 
- **Initialization Error Code:** `(-10003, 'IPC initialize failed, MetaTrader 5 x64 not found')`.

### Required Installation Steps for Live MT5 Integration:
1. Download and install the official MetaTrader 5 x64 terminal client from MetaQuotes or a supported broker.
2. Launch the MT5 terminal and log into a verified DEMO or REAL trading account.
3. Enable DLL imports and algorithmic trading in MT5 settings if executing live orders.
4. Ensure the MT5 terminal is running when executing live gateway services.

---

## 2. Phase 2 Security & Risk Defect Remediations

- **Broker Symbol Specifications:** Removed all fallback default tick values. `MarketDataManager.get_spec()` obtains authoritative symbol info from `mt5.symbol_info()` or injected mock test adapters.
- **Broker-Authenticated Quote Provider:** Implemented `AuthenticatedQuote` requiring source, account login, bid/ask pricing, and strict <10s timestamp freshness. Rejecting unauthenticated or stale price feeds.
- **Risk Calculation Accuracy:** Integrated broker `order_calc_profit()` simulation where supported, incorporating spread, commissions, volume step rounding down (`floor`), and verified account equity.
- **Daily-Loss Baseline Persistence:** Persisted daily equity baseline in SQLite with zero hardcoded $10,000 fallback.
- **Strict v5 Endpoint Authorization:** `@app.before_request` restricts all v5 bot endpoints (`/api/v5/bot/*`) to `admin` role. Ordinary device tokens receive `403 Forbidden`.
- **Fail-Closed Telemetry Stress:** Risk Guardian fails closed (`FAIL_CLOSED_MISSING_OR_INVALID_TELEMETRY_STRESS`) when infrastructure telemetry stress is missing or invalid.
- **Demo Execution Safeguards:** Demo order execution remains strictly disabled (`enabled = False`).

---

## 3. Test Suite Results

- **Python Backend Pytest:** **35/35 PASSED** (`python -m pytest -v tests`).
- **Android Gradle Unit Tests:** **16/16 PASSED** (`.\gradlew.bat test`).

---

## 4. Final Eligibility Decision

- **Eligible for Paper Forward Testing?** **YES** ✅ (All security controls, fail-closed freshness checks, authorization barriers, and risk guardian invariants are verified and passing unit tests).
- **Eligible for Live Money Trading?** **NO** ❌ (Real account execution is strictly disabled and prohibited).
