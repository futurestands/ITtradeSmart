# ITTrader SmartHub v5 — MT5 Connection & Environment Diagnostic Report (Phase 1 & 2 Update)

**Date:** 2026-11-01  
**Project:** ITTrader SmartHub v5  
**Branch:** `fix/v5-broker-verified-research`  

---

## 1. Phase 1 — MT5 Environment & Terminal Diagnostic

- **Python Interpreter:** `C:\Users\MJ\AppData\Local\Python\pythoncore-3.14-64\python.exe` (Python 3.14.6 64-bit).
- **MetaTrader 5 Python Package:** Successfully installed (`MetaTrader5-5.0.6231`).
- **Exhaustive Search Results:** Registry uninstall records, user application folders, and accessible drives were thoroughly searched for `terminal64.exe` or `terminal.exe`. No genuine MetaTrader 5 terminal client installation exists on this machine.
- **Initialization Error Code:** `mt5.initialize()` fails with `(-10003, 'IPC initialize failed, MetaTrader 5 x64 not found')`.

### Official Installation Required:
To enable live terminal communication and historical data feeds, please download and install the official MetaTrader 5 terminal client:
👉 [Official MetaTrader 5 Download](https://www.metatrader5.com/en/download)

---

## 2. Phase 2 — Security & Risk Defect Remediations

- **Fallback Defaults Removed:** All fallback broker symbol defaults removed from risk-critical paths.
- **Broker-Authoritative Calculation Enforcement:** `RiskGuardian` requires valid `order_calc_profit()` and `order_calc_margin()` results when connected to a broker terminal.
- **Public Quote Ingestion Removed:** The public/admin HTTP quote-ingestion route was removed. Quotes are read exclusively from trusted local Windows-side MT5 services.
- **Endpoint Authorization:** All v5 bot endpoints (`/api/v5/bot/*`) require strict `admin` authorization. Ordinary device tokens receive `403 Forbidden`.
- **Fail-Closed Telemetry Stress:** Risk Guardian fails closed when telemetry stress is missing or invalid.
- **Demo Execution Safeguards:** Demo order execution remains strictly disabled (`enabled = False`).

---

## 3. Test Results & Validation Status

- **Python Backend Pytest:** **35/35 PASSED** (`python -m pytest -v tests`).
- **Android Gradle Unit Tests:** **16/16 PASSED** (`.\gradlew.bat test`).
- **Strategy Performance Claims:** Marked **UNVERIFIED** pending live MT5 terminal connectivity and actual historical ingestion.
- **Native MQL5 Strategy Tester:** **BLOCKED** due to absence of MetaTrader 5 terminal executable.

---

## 4. Final Eligibility Decision

- **Eligible for Paper Forward Testing?** **YES** ✅ (All security controls, authorization barriers, fail-closed freshness checks, and risk guardian invariants are verified and passing unit tests).
- **Eligible for Live Money Trading?** **NO** ❌ (Real account execution is strictly disabled and prohibited).
