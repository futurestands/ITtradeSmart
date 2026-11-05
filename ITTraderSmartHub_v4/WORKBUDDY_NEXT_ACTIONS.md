# WORKBUDDY NEXT ACTIONS

**Date:** 2026-11-05  
**Agent:** WorkBuddy Master Agent (R0 Coordinator)  
**Branch:** `feature/workbuddy-master-agent-baseline-audit-20261105`

> **M1 STATUS UPDATE (2026-11-05).** Section 2A was written from the first audit
> edition and contains **obsolete defect claims carried over from a 2026-11-02
> handover**. Do NOT implement those "fixes": the `/analyze` NameError and
> BotController `last_price` claims are not reproducible at `0c0624f`, and the
> `analyse_dst_transitions` item was an audit caller error. Sections 2B/2C/2D
> were delivered in M1 on `feature/workbuddy-m1-offline-engineering-20261105`
> (SmartHub `7003781`, AI Lab `28892bd`, reports `e6dfc30`). **Priority 1
> blockers remain open.** See `WORKBUDDY_M1_OFFLINE_ENGINEERING_REPORT.md`.

---

## Priority 1: Operator Actions Required (BLOCKERS)

These actions require the operator (you) to perform manual configuration. No code change can resolve them.

### 1A. Configure Investor-Only DEMO Terminal

**Problem:** The MT5 export gate diagnostic shows two failing gates:
- `account_expert_disabled`: `trade_expert=true` (expert trading enabled)
- `terminal_trading_disabled`: `trade_allowed=true` (terminal allows trading)

**Action needed:**
1. Open MetaTrader 5 terminal
2. Go to Tools → Options → Expert Advisors
3. Uncheck "Allow automated trading" (this disables `trade_expert`)
4. Ensure the terminal is in investor/read-only mode (not master/trading mode)
5. Confirm the account is a DEMO account with trading disabled at the broker level

**After configuration, re-run:**
```powershell
cd C:\Users\MJ\Documents\ITtradeSmart-NAS100-Integration\ITTraderSmartHub_v4\backend
.\.venv-gateway\Scripts\python.exe tools\diagnose_mt5_export_gates.py
```
Or the direct SDK diagnostic used in this audit.

**Safety:** Do NOT change credentials, switch accounts programmatically, or weaken any gate. The terminal must be configured by the operator, not by code.

### 1B. Obtain Broker Server-Time/DST Policy

**Problem:** The timebase is UNVERIFIED because no independent UTC comparison was performed and no broker policy documentation exists.

**Action needed:**
1. Contact the broker (MetaQuotes-Demo) or check their documentation
2. Obtain the official server timezone (expected: EET = UTC+2 winter / UTC+3 summer with EU DST)
3. Obtain the DST transition schedule
4. Obtain trading session calendars and holiday schedules
5. Document the source and date of this information

**Alternative:** Once the export gates pass (1A), perform a simultaneous NTP-bracketed quote capture:
- Start NTP clock reference (`capture_clock_reference.py`)
- Capture fresh MT5 quotes with per-call Windows UTC before/after
- Compare raw broker epoch vs independent UTC
- Repeat across a DST transition boundary

### 1C. Complete Historical Data Export (After 1A and 1B)

**Problem:** M5 is a partial interrupted capture (1,795 of 5,000 rows). M1 was never exported. All existing data is TIMEBASE_UNVERIFIED.

**Action needed (after gates pass and timebase verified):**
1. Export complete M1 and M5 datasets (non-partial)
2. Export with per-call observation brackets
3. Record all export metadata (symbol, timeframe, count, hashes)
4. Verify closed-bar availability and grid alignment
5. Create provenance dossiers with verified timebase evidence

---

## Priority 2: Safe Offline Engineering Tasks (No Blockers)

These tasks can proceed immediately without broker access or operator action.

### 2A. Known Defect Claims — Reconciled (DO NOT "FIX")

| Original claim | Verified reality at `0c0624f` | Action |
|---|---|---|
| `/analyze` NameError in `trade_analysis.py` | **RETRACTED.** `backend/app.py:363` has the valid `any(key in body for key in (...))`; authenticated reproduction returns `200 DEAL_HEURISTICS` | None — pinned by `test_m1_baseline_reconciliation.py` |
| BotController `last_price` AttributeError | **RETRACTED.** Current controller is fail-closed PAPER/DEMO by design | None — **never unlock trading** |
| `diagnose_mt5_export_gates.py` terminal detection | **ROOT-CAUSED.** Running `terminal64.exe` exposes an empty `Get-Process.Path` and empty CIM `ExecutablePath`/`CommandLine`; exact-path matching cannot succeed | Do not relax the exact-terminal invariant; use the direct read-only SDK diagnostic |
| AI Lab `analyse_dst_transitions` API mismatch | **RETRACTED (caller error).** API expects a normalized `pd.DataFrame` with `_t`; `cli.py:299` and 5 existing tests use it correctly | None — do not change the function signature |

### 2B. Enhance Backtesting Engine Validation

**Status: COMPLETED in M1** — `backend/tests/test_m1_simulator_and_causality.py`
(28 tests: stop-first ambiguity, adverse gaps, no favourable target improvement,
entry-bar collision, spread/slippage/commission stress, HTF as-of boundaries).

- Add explicit test for stop-first ambiguous exit with intrabar stop and target collision
- Add test for gap-stop worse-open fill
- Add test for target limit fill with no favorable gap improvement
- Add test for entry-bar collision skip
- Reconcile limit-entry simulator with next-open entry assumptions
- Add cost-stress sensitivity test (+50% spread/slippage)

### 2C. Improve Leakage Detection Tests

**Status: COMPLETED in M1** — AI Lab `test_m1_htf_asof.py` (6),
`test_m1_walkforward_boundaries.py` (13), `test_m1_calibration_isolation.py` (6).
Feature stationarity across regime changes remains a post-eligibility research
item, not a correctness defect.

- Add explicit test for HTF feature availability boundary (as-of join correctness)
- Add test for label-overlap purging with edge cases (label exactly at embargo boundary)
- Add test for calibration fold isolation (calibrator never sees test fold data)
- Add test for feature stationarity across regime changes

### 2D. Reproducibility Infrastructure

**Status: COMPLETED in M1** — `src/nas100lab/reproducibility.py` supplies scoped
`config_hash()`, immutable dataset manifests, a fail-closed model-card template
and a hash-chained variant log; `src/nas100lab/training_pipeline.py` supplies
nine acceptance gates with training unconditionally disabled.

- Create a deterministic data-split freezer that records:
  - Data hash
  - Split boundaries (train/calibration/test/holdout)
  - Feature version hash
  - Engine config hash
  - Git commit
- Create a model-card template for future trained models
- Create a variant log for recording every tried configuration

### 2E. Android Validation (When Device Available)

**Owner-verified:** the phone was previously paired and its gateway connection
was verified by the owner. ADB non-detection during this audit does **not**
invalidate that result. No change requested.

- Connect physical device via wireless debugging
- Verify `com.ittrader.smarthub.research` package installation
- Test phone-to-gateway connectivity via `adb reverse tcp:5000 tcp:5000`
- Verify NAS100 Research, AI Status, Risk and MT5 Accounts screens
- Record which screens respond (no credentials in screenshots)

---

## Priority 3: Research Progression (After Data Eligibility)

These tasks are BLOCKED until data eligibility is established (Priority 1 complete).

### 3A. Freeze Rules and Costs

- Freeze engine configuration (swing L/R, ATR multiples, FVG parameters)
- Freeze cost assumptions (spread, slippage, commission)
- Record all frozen values in a versioned config file with hash

### 3B. Build Causal Features from Verified Data

- Compute structure/session/sweep/FVG features from closed bars
- Use as-of joins for HTF context
- Separate no-fill labels from completed outcomes
- Labels start after decision close, include wait + hold horizons and costs

### 3C. Establish Base-Rate Controls

- Rules-only baseline (no ML)
- Random entries with identical stops/targets (permutation test)
- Cost sensitivity analysis

### 3D. Train Interpretable Logistic Baseline

- L2 logistic regression on causal features
- Fit preprocessing only inside chronological training folds
- Do not tune thresholds to force signals

### 3E. Purged Walk-Forward Evaluation

- Use `walkforward.py` with full label-overlap removal
- Embargo = `max_wait + max_hold` bars
- Untouched final holdout (opened once, after all choices frozen)
- Assess regime/session stability and cost stress

### 3F. Calibration

- Fit calibrator on calibration fold (strictly before test)
- Report Brier score, log loss, ECE with bootstrap CIs
- Per session and regime
- Show probability to user only if pre-registered criteria pass

### 3G. Acceptance Gate Evaluation

- Evaluate pre-registered gates from ML_DESIGN.md section 7
- Open holdout only once
- Failing gates → model not shipped; not retuned on holdout

### 3H. Android Presentation (After Model Ships)

- Authenticated versioned analysis contract
- Explicit model/data freshness and invalidation state
- BUY/SELL/NO TRADE with probability (only if calibrated)
- Offline device features remain useful
- No Trade remains default when evidence missing

---

## Priority 4: Architecture Improvements (Low Priority)

### 4A. Centralize MT5 Account Identity

- Serialized account identity management
- Fix controller/market-data/RiskGuardian interfaces
- Broker equity/free margin integration
- Persistent daily baseline
- Journal IDs and paper cash accounting

### 4B. Independent Risk Guardian

- Configurable rule profiles with reset timezone
- Static/trailing equity floor
- Daily/weekly loss, high-water mark
- Unrealized P&L/costs
- Total/correlated exposure
- Streak/duplicate/session/news/overnight limits
- Margin and infrastructure breakers
- Persist decisions transactionally in SQLite

### 4C. Fix URL Validation

- Replace string-prefix loopback check with parsed-host equality
- Verify WebSocket lifecycle/reconnect overflow handling

---

## Decision Points Requiring User Approval

| Decision | Trigger | What to ask |
|---|---|---|
| Install statsmodels | When statistical modeling requires it | "Install statsmodels in the AI Lab venv?" |
| Install vectorbt | When independent backtesting comparison needed | "Install vectorbt for simulation comparison?" |
| Install Optuna | After baseline exists and hyperparameter search needed | "Install Optuna for hyperparameter optimization?" |
| Install MLflow | If experiment volume justifies tracking | "Install MLflow for experiment tracking?" |
| Push to remote | When deliverables are ready for sharing | "Push the WorkBuddy branch to origin?" |
| Merge to integration | When changes are reviewed | "Merge to integration branch?" |
| Supabase migration | When cloud integration is needed | "Apply Supabase migration to target project?" |
| Broker switching | If current broker cannot provide suitable DEMO | "Switch to a different broker? (requires credentials)" |

---

## Checkpoint and Resume Instructions

If context or tool limits are exhausted, resume with:

1. Read `MASTER_AGENT_TASK_LEDGER.md` for task status
2. Read `WORKBUDDY_BASELINE_AUDIT.md` for system state
3. Read `MT5_DATA_ELIGIBILITY_AND_TIMEBASE_REPORT.md` for M0 status
4. Check git branch: `git branch --show-current` (should be `feature/workbuddy-master-agent-baseline-audit-20261105`)
5. Run test suites to verify state:
   ```bash
   cd backend && ./.venv-gateway/Scripts/python.exe -m pytest -q --basetemp=<writable-dir> tests
   cd ../../NAS100-AI-Lab-Phase1B && ./.venv/Scripts/python.exe -m pytest -q --basetemp=<writable-dir> tests
   ```
6. Check MT5 gate status:
   ```bash
   cd backend && ./.venv-gateway/Scripts/python.exe -c "import MetaTrader5 as mt5; mt5.initialize(timeout=10000); a=mt5.account_info(); t=mt5.terminal_info(); print(f'connected={t.connected}, demo={a.trade_mode==0}, trade_allowed={a.trade_allowed}, trade_expert={a.trade_expert}, terminal_trade={t.trade_allowed}'); mt5.shutdown()"
   ```
7. Continue with Priority 2 (safe offline tasks) or Priority 3 (if data eligible)
