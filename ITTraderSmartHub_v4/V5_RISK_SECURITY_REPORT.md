# ITTrader SmartHub v5 — Risk Guardian & Security Audit Report

**Date:** 2026-11-01  
**Project:** ITTrader SmartHub v5  

---

## 1. Risk Guardian Rules & Boundaries

1. **Max Trade Risk:** `0.5%` of verified account equity per trade.
2. **Daily Loss Stop:** `2.0%` of starting-day equity.
3. **Max Concurrent Open Positions:** `3`.
4. **Infrastructure Stress Formula:** `EffectiveRisk = BaselineRisk * (1 - 0.5 * InfrastructureStress / 100)`.
5. **Volume Step Rounding Down:** Fractional lot volume stepping with `floor()` rounding down to nearest `lot_step` (e.g. `0.01`).
6. **Minimum Lot Rejection:** Rejects any trade signal where `min_lot * cash_risk_per_lot` exceeds the maximum allowed trade risk (`MIN_LOT_EXCEEDS_RISK_LIMIT`).
7. **Fail-Closed Data Freshness:** Rejects trades if market data is older than 120 seconds (`FAIL_CLOSED_STALE_MARKET_DATA`).

---

## 2. Demo Execution Safeguards (`demo_execution.py`)

1. **Disabled by Default:** `enabled = False`. Requires explicit admin enablement (`enable_demo_mode`).
2. **Strict DEMO Mode Check:** Rejects non-DEMO accounts (`account.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO`). Real accounts trigger **Emergency Stop**.
3. **Allowlist Enforcement:** Verifies login and server against `MT5_DEMO_ALLOWLIST_LOGINS` and `MT5_DEMO_ALLOWLIST_SERVERS`.
4. **Idempotency:** SHA-256 order ID tracking prevents duplicated orders.
