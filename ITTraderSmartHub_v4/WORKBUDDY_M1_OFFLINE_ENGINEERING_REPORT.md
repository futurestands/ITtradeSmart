# WORKBUDDY M1 OFFLINE ENGINEERING REPORT

**Date:** 2026-11-05  
**Agent:** WorkBuddy Master Agent (R0 Coordinator; logical roles R1–R7)  
**Scope:** Milestone M1 — audit reconciliation first, then offline correctness improvements  
**SmartHub branch:** `feature/workbuddy-m1-offline-engineering-20261105`  
**AI Lab branch:** `feature/workbuddy-m1-offline-engineering-20261105`  
**SmartHub base commit:** `0c0624fcc91ce78e4d35d06e66c0edb6c1005e6f`  
**AI Lab base commit:** `6d0cc8f`  
**M1 code commits:** SmartHub `7003781`, AI Lab `28892bd`  
**M1 reports commit:** SmartHub `e6dfc30`  
**Project root:** `C:\Users\MJ\Documents\ITtradeSmart-NAS100-Integration\ITTraderSmartHub_v4`  
**AI Lab root:** `C:\Users\MJ\Documents\NAS100-AI-Lab-Phase1B`

> **Verdict:** All requested M1 offline work is complete. **No model was trained on
> real data, no predictive performance was evaluated, no timestamp was certified,
> no broker permission was changed, no order was placed, and no push/merge/deploy
> was performed.** The historical dataset remains `TIMEBASE_UNVERIFIED` /
> `research_eligible=false`. Synthetic fixtures and demonstrations are software
> correctness checks only — never evidence of a profitable NAS100 strategy.

---

## 1. Order of Work (Owner Instruction Honoured)

The owner explicitly required: *"Proceed with the audit reconciliation first,
then offline correctness improvements."* The reconciliation (Section 2) was
completed and pinned by 14 regression tests **before** any other M1 code was
written. No defect was "fixed" from an obsolete report.

---

## 2. Audit Reconciliation — Reproductions and Findings

All five checks were performed against the actual baseline commit
`0c0624fcc91ce78e4d35d06e66c0edb6c1005e6f`. Git tree note: paths must be
referenced as `0c0624f:./backend/app.py` (or the full
`ITTraderSmartHub_v4/...` prefix); `0c0624f:backend/app.py` fails.

### 2.1 `/analyze` NameError — OBSOLETE, NOT REPRODUCIBLE

| Step | Command / evidence | Result |
|---|---|---|
| Baseline source | `git show 0c0624f:./backend/app.py` | Line 363: `if any(key in body for key in ('password', 'login', 'server')):` — valid Python; generator variable `key` is bound |
| Second expression | working tree `backend/app.py:294` | `any(k in body for k in (...))` — also valid, matching variable |
| `trade_analysis.py` | `git show 0c0624f:./backend/trade_analysis.py` | Contains only `analyze_deals(deals)`; no `any(key in body ...)` expression |
| Unauthenticated reproduction | `POST /analyze json={}` | `401 {'error': 'Missing Bearer token'}` — no NameError |
| Authenticated reproduction | test fixture `ADMIN` bearer + mocked `FakeMT5`, empty body | `200`, `analysis_type='DEAL_HEURISTICS'`, `timebase_status='TIMEBASE_UNVERIFIED'`; no NameError; `FakeMT5.calls` populated with read-only calls only, no `order_send` |

**Action:** claim retracted, no production code changed. Regression:
`test_baseline_analyze_route_has_valid_generator_expression`,
`test_analyze_empty_body_has_no_nameerror_and_never_submits_orders`.

### 2.2 BotController `last_price` AttributeError — OBSOLETE; FAIL-CLOSED CONFIRMED

Current `backend/bot/bot_controller.py` has **no** `last_price`,
`is_data_fresh` or `order_send`. Verified behaviour:

```python
PAPER_BLOCKERS = (
    "VERIFIED_EXACT_INSTRUMENT_AND_ECONOMICS_REQUIRED",
    "AUTHORITATIVE_ACCOUNT_IDENTITY_EQUITY_FREE_MARGIN_AND_DAILY_STATE_REQUIRED",
    "AUTHORITATIVE_QUOTE_AND_CLOSED_CANDLE_TIMEBASE_REQUIRED",
    "VERIFIED_RISK_INPUT_ADAPTER_REQUIRED",
    "ACCURATE_PAPER_VALUATION_AND_RESTART_PERSISTENCE_NOT_IMPLEMENTED",
)
```

- `set_mode('PAPER', ...)` → `PaperSafetyError("PAPER_BLOCKED: ...")`; mode stays `BotMode.OFF`.
- `set_mode('DEMO', ...)` → `PermissionError("RESEARCH_ONLY_EXECUTION_LOCK: DEMO execution is prohibited.")`; mode stays `BotMode.OFF`.
- `tick()` → `PaperSafetyError("TRADING_CYCLE_BLOCKED: ...")`.
- `get_status()['execution_policy'] == 'RESEARCH_ONLY_LOCKED'`, `paper_trading['eligible'] is False`.
- `backend/bot/demo_execution.py::execute_demo_order()` → `PermissionError("RESEARCH_ONLY_EXECUTION_LOCK: MT5 order submission prohibited.")`.

**Action:** claim retracted. **No trading unlocked, no older controller revived,
no unsafe execution path reintroduced.** Regression:
`test_controller_paper_and_demo_modes_fail_closed`,
`test_no_order_send_call_sites_in_production_python`.

### 2.3 `feature/v5-demo-trading-bot` — PRESENT ON REMOTE

```
git ls-remote --heads origin
093956d9c22e9d0f80ad0193f119b9783d394667 refs/heads/feature/v5-demo-trading-bot
```

- Remote blob at that tip contains `import MetaTrader5 as mt5` and `res = mt5.order_send(req)`.
- Current HEAD `bot/demo_execution.py` blob contains neither.
- Historical commit `ae707c0` (`fix(research): lock execution and repair explicit backtest accounting`) removed `order_send`.
- The excluded tip **is** a historical ancestor; the correct interpretation is that unsafe code was inherited and later removed — **not** that the branch never existed. It is excluded from **all** future merges and bases.

**Action:** wording corrected; exclusion pinned by constants `EXCLUDED_BRANCH_TIP`, `EXCLUDED_ADAPTER_BLOB`, `EXECUTION_LOCK_COMMIT`.

### 2.4 Android Pairing — OWNER-VERIFIED, NOT INVALIDATED BY ADB

Evidence in `V4_HANDOVER.md`, `RELEASE_READINESS_REPORT.md`,
`NAS100_APK_RESEARCH_INTEGRATION.md`, `ANDROID_MULTISCREEN_NAVIGATION.md`
includes "Install to the paired Android device", "For a phone already paired
with wireless ADB, use `adb reverse tcp:5000 tcp:5000`" and owner confirmation
after physical device connection. This audit's inability to enumerate an ADB
device does not invalidate those results.

**Action:** audit corrected. No Android source, resource, manifest or config changed.

### 2.5 ML Safety Gate — INDIVIDUAL CHECK RESULTS

Measured directly against
`NAS100-AI-Lab-Phase1B/data/quarantine/USTECH100M_M5_raw.csv` and its
`.provenance.json`:

| # | Check | Evidence | Result |
|---|---|---|---|
| 0 | Provenance dossier exists | `.provenance.json` present and parseable | **PASS** |
| 1 | SHA-256 integrity | `aecb75f4efe2c1a80042ac2bc9ad78537feaa05b5c7cfeae2be48a3ae0c5e44f`, 100,002 rows, matches dossier | **PASS** |
| 2 | `research_eligible` | `false`, `status: QUARANTINED` | **FAIL** → `RESEARCH_INELIGIBLE` |
| 3 | Timebase verified | `verified: false`, `verification_audit_digest: null` | **FAIL** → `TIMEBASE_UNVERIFIED` |
| 4 | Contract certified | `contract_certified: false`, `certification_proof_hash: null` | **FAIL** → `CONTRACT_UNCERTIFIED` |
| 5 | Quarantine location | path contains `data/quarantine/` | **FAIL/BLOCKED** → `DATASET_IN_QUARANTINE` |

`check_training_safety(...)` raises `TrainingSafetyError: TRAINING_BLOCKED` with
exactly four reasons; the hash and dossier checks contributed **no** blocking
reason. Eligibility conclusion is unchanged.

**Action:** `NAS100_RESEARCH_VALIDATION_STATUS.md` §3.1 rewritten with the
per-check table; ledger corrected.

---

## 3. Exact Files Changed

### SmartHub (`C:\Users\MJ\Documents\ITtradeSmart-NAS100-Integration\ITTraderSmartHub_v4`)

| File | Type | Lines added | Purpose |
|---|---|---:|---|
| `backend/tests/test_m1_baseline_reconciliation.py` | NEW (committed `7003781`) | ~180 | 14 adversarial regressions pinning the five corrections + AST `order_send` scan |
| `backend/tests/test_m1_simulator_and_causality.py` | NEW (committed `7003781`) | ~345 | 28 simulator/cost/HTF causality regressions |
| `WORKBUDDY_BASELINE_AUDIT.md` | CORRECTED | — | Retracted 4 claims, added §11 reconciliation table, M1 branches/result rows |
| `NAS100_RESEARCH_VALIDATION_STATUS.md` | CORRECTED | — | §3.1 per-check gate results; new §8A M1 work and full-suite results |
| `MASTER_AGENT_TASK_LEDGER.md` | CORRECTED | — | TASK-010…015, corrected U-003/U-004/U-006/U-009/U-011/U-012, branches, verified commits, safety checklist |
| `WORKBUDDY_M1_OFFLINE_ENGINEERING_REPORT.md` | NEW | — | This report |
| `backend/tests/test_m1_documentation_integrity.py` | NEW (finalization, 18 tests) | ~130 | Pins verified commit IDs, absence of placeholders, excluded branch tip, fail-closed verdict and obsolete-defect corrections |
| `WORKBUDDY_NEXT_ACTIONS.md` | CORRECTED (finalization) | — | Removed obsolete "fix these defects" instructions; marked 2B/2C/2D delivered, 2E owner-verified |
| `WORKBUDDY_BASELINE_AUDIT.md`, `NAS100_RESEARCH_VALIDATION_STATUS.md`, `MASTER_AGENT_TASK_LEDGER.md` | CORRECTED (finalization) | — | U-005 root cause, U-006 retraction, verified commit IDs, final suite counts |

**Production source files changed: ZERO.** No Flask route, Android file, risk
formula, database, MT5 tool, or NAS100 engine module was modified at any point
in M1 or its finalization.

### AI Lab (`C:\Users\MJ\Documents\NAS100-AI-Lab-Phase1B`) — all committed `28892bd`

| File | Type | Purpose |
|---|---|---|
| `src/nas100lab/reproducibility.py` | NEW | Canonical hashing, config hashes, immutable dataset manifests, model cards, experiment-variant log |
| `src/nas100lab/training_pipeline.py` | NEW | Nine acceptance gates, prepared-but-unconditionally-disabled real-data training |
| `tests/test_m1_reproducibility.py` | NEW (34 tests) | Manifest/config-hash/model-card/variant-log adversarial tests |
| `tests/test_m1_training_pipeline.py` | NEW (7 tests) | Fail-closed gate and lock tests |
| `tests/test_m1_walkforward_boundaries.py` | NEW (13 tests) | Purged walk-forward off-by-one boundaries |
| `tests/test_m1_calibration_isolation.py` | NEW (6 tests) | Calibration-fold label isolation spy tests |
| `tests/test_m1_htf_asof.py` | NEW (6 tests) | HTF as-of alignment and future-bar leakage |
| `tests/test_m1_timebase_api_reconciliation.py` | NEW (finalization, 5 tests) | Pins the DataFrame-based DST API contract, the audit caller error, heuristic-only output and quarantine provenance |

**Existing AI Lab production modules changed: ZERO.** The two pre-existing
untracked synthetic report JSONs (`reports/synthetic_candidate_walkforward.json`,
`reports/synthetic_confluence_stress.json`) were left untouched and uncommitted.

---

## 4. Offline Correctness Improvements — What Each Test Pins

### 4.1 SmartHub simulator (28 tests)

| Requirement | Pinned behaviour |
|---|---|
| Stop-first ambiguous-bar accounting | Both barriers touched → `STOP`, `exit_price = min/max(stop, open)`, `gross_r = -1.0`, `costs_r = 0.2` exactly once, `net_r = -1.2`; BUY and SELL mirrors; a high far beyond target never grants improvement |
| Adverse gap-fill | Gap-down/gap-up on the fill bar and later bars exits at the worse of stop and open; limit still fills at the specified entry (no favourable improvement) |
| No-fill / incomplete separation | `NO_FILL` only when the entire `max_wait_bars` window was observed; `INCOMPLETE` for truncated series (no fill, `costs_r=None`) and for a filled-but-open position (`entry_index` set, `net_r=None`); `summarize` counts them separately with zero wins/losses |
| Spread / slippage / commission stress | `costs_r = point_size × (spread + 2×slippage + commission) / risk`, charged once; parameterised 5 scenarios; wide exit-bar spread can only widen the floor; extreme costs turn `gross +2.0R` into a net loss with no clamping; small observed spreads cannot reduce the configured floor |
| HTF as-of alignment | `htf_closed_by` inclusive-at-close boundary; uses target timeframe, not candle timeframe; `resample` never publishes an unfinished bucket; `analyze_multitimeframe` guarantees `htf.as_of <= ltf.as_of` |
| Future-data leakage | Future clock → `FUTURE_DATA` NO TRADE; unclosed/future HTF → `HTF_BAR_NOT_CLOSED` NO TRADE; completed outcomes invariant to appended future bars; decision timestamp must equal signal candle close |

All tests are synthetic OHLC fixtures. **No real or quarantined CSV was read by
any new test.**

### 4.2 AI Lab reproducibility primitives

`reproducibility.py`:
- `canonical_bytes()` — sorted-key, fixed-separator, UTF-8 JSON with `allow_nan=False`; rejects sets, paths, NaN/Infinity instead of silently normalising.
- `config_hash()` — scoped/versioned SHA-256, order-independent; non-string keys rejected.
- `create_dataset_manifest()` / `verify_dataset_manifest()` — per-file SHA-256 + size + self-digest; detects altered, missing and unmanifested files; **hard-codes** `research_eligible=False`, `training_enabled=False`, `timebase_status=TIMEBASE_UNVERIFIED`, so a manifest can never self-certify eligibility or training.
- `model_card_template()` / `validate_model_card()` — deliberately incomplete template rejected until filled; refuses `research_eligible=True`, certified timebase/contract, `real_market_model_trained=True`, market-edge/profitability claims, deployment authorisation, or missing limitations.
- `append_variant()` / `verify_variant_log()` — append-only JSONL with hash chain, sequence numbers, `prev_digest`, config-hash binding, duplicate detection, tamper/reorder/truncation detection (truncation requires an externally stored `expected_count` anchor, explicitly documented).

`training_pipeline.py`:
- Nine named acceptance gates; unknown gate names rejected; truthy strings never count as a pass.
- `REAL_DATA_TRAINING_DISABLED = True` is an unconditional module constant, **not** a parameter.
- `training_acceptance_gates()` returns `NO_GO` and `training_enabled=False` even when all nine gates are documented.
- `prepare_real_data_training()` **always** raises `TrainingDisabledError`; no model, dataset or broker SDK is imported on that path.

### 4.3 Walk-forward / calibration / HTF boundary tests

- 13 tests pin exact purge boundaries: train event ending at `ca_start` purged, at `ca_start-1` retained; calibration event ending at `te_start` purged; test event ending at `te_end` included, one bar past withheld; `embargo_bars=0` still purges; partitions disjoint and strictly chronological; NaN labels excluded (not mis-counted as purged); `step_bars` changes fold count only; prior baseline ignores calibration labels.
- 6 tests pin calibration isolation: the API signature has **no** test-label parameter; a recording sklearn estimator spy proves exactly two `fit` calls (base on `y_train`, Platt sigmoid on `y_cal`), none of length `len(x_test)`; inputs are never mutated; single-class calibration fails instead of faking probabilities.
- 6 tests pin AI Lab HTF as-of: the last unclosed M5 bar is excluded; bars beyond `asof_time` cannot change derived bars; `dropped_incomplete_bins` reported; derived hash binds the returned table bytes; metadata stays `TIMEBASE_UNVERIFIED` / `research_eligible=false`; `asof_time` must be timezone-naive broker-clock.

---

## 5. Actual Test Results

### 5.1 Reproductions of the reconciliation (targeted)

| Command | Result |
|---|---|
| `./.venv-gateway/Scripts/python.exe -m pytest tests/test_m1_baseline_reconciliation.py tests/test_m1_simulator_and_causality.py -q` | **42 passed in 3.44s** |
| `./.venv/Scripts/python.exe -m pytest tests/test_m1_*.py -q` (AI Lab, 5 files) | **66 passed in 6.21s** |
| `./.venv-gateway/Scripts/python.exe -m pytest tests/test_m1_documentation_integrity.py -q` (finalization) | **18 passed in 0.53s** |
| `./.venv/Scripts/python.exe -m pytest tests/test_m1_timebase_api_reconciliation.py -q` (finalization) | **5 passed in 0.22s** |

### 5.2 Complete suites

| Suite | Command | Baseline | M1 milestone | Finalization re-run |
|---|---|---|---|---|
| SmartHub backend | `cd backend && ./.venv-gateway/Scripts/python.exe -m pytest -q --basetemp=<writable>` | 600 passed, 2 skipped | **642 passed, 2 skipped, 0 failed** (19.84s, +42) | **660 passed, 2 skipped, 0 failed** (20.99s, +18) |
| AI Lab | `cd NAS100-AI-Lab-Phase1B && ./.venv/Scripts/python.exe -m pytest -q --basetemp=<writable>` | 426 passed | **492 passed, 0 failed, 0 errors** (43.24s, +66) | **497 passed, 0 failed, 0 errors** (44.54s, +5) |

The finalization re-run is the current state of both branches: `642 + 18 = 660`
and `492 + 5 = 497`, with no test removed, skipped or weakened.

Environment note (unchanged from baseline): Windows default temp
`C:\Users\MJ\AppData\Local\Temp\pytest-of-MJ` is denied, so
`TMPDIR/TMP/TEMP` and `--basetemp` are pointed at the workspace-writable
`pytest-tmp` directory. The 2 SmartHub skips are pre-existing Windows symlink
privilege skips. One benign `PytestCacheWarning` about `.pytest_cache` remains.
`tzdata==2026.6` remains installed only in `backend/.venv-gateway`.

Python environments were kept isolated: SmartHub gateway Python 3.14.6, AI Lab
Python 3.12.10. **No new library was installed for M1**; all new modules use the
standard library plus already-installed pandas/numpy/scikit-learn.

### 5.3 Test-side failures found and fixed during development

| Failure | Cause | Fix |
|---|---|---|
| Initial reconciliation test: `2 failed, 11 passed` | (a) assumed excluded remote tip is not an ancestor; (b) naive `order_send(` substring scan matched docstrings, then included `.venv-gateway/Lib/site-packages/MetaTrader5/__init__.py` | Replaced with AST `ast.Call` detection excluding `tests`, `__pycache__`, `site-packages`, `.venv*`; corrected branch semantics to "historical ancestor, unsafe code removed by `ae707c0`" |
| `test_variant_log_rejects_unsafe_or_inconsistent_variants` expected 1 synthetic variant | Only a non-synthetic blocked variant had been appended | Append one synthetic and one blocked variant; assert `variants==2`, `synthetic_variants==1` |
| `test_variant_log_detects_local_tampering_and_chain_breaks` reported `VARIANT_LOG_TAMPERED` instead of `CHAIN_BROKEN` | Test helper stripped `manifest_digest` rather than `entry_digest` when recomputing a variant entry's digest | Use an entry-specific body filter excluding `entry_digest` |
| Finalization `test_quarantine_provenance_still_blocks_certification`: `1 failed, 4 passed` — `KeyError: 'contract_certified'` | Test assumed a top-level key; the provenance dossier nests it under `contract_spec` | Test now asserts `contract_spec.contract_certified is False`, `status == QUARANTINED`, `timebase_evidence.verified is False` and `CONTRACT_NOT_CERTIFIED` in `quarantine_reasons`. **No data or production code changed** |

No production defect was exposed by the new tests; consequently **no tested
component was replaced** (owner instruction: "Avoid replacing tested components
unnecessarily").

---

## 6. Source Commits and Branch State

| Repo | Commit | Description |
|---|---|---|
| SmartHub | `0c0624fcc91ce78e4d35d06e66c0edb6c1005e6f` | Verified user-specified baseline (`feature/smarthub-icon-and-mt5-gate-diagnostics-20261105`) |
| SmartHub | `ae707c0` (historical ancestor) | `fix(research): lock execution and repair explicit backtest accounting` — removed `order_send` |
| SmartHub | `7003781` | **M1** — 2 new test files (42 tests), no production changes |
| SmartHub | `e6dfc30` | **M1** — all 6 handover documents (3 corrected reports + this new report + 2 carried forward) |
| AI Lab | `6d0cc8f` | Verified baseline (`feature/chatgpt-walkforward-research`) |
| AI Lab | `28892bd` | **M1** — 2 new modules + 5 new test files (66 tests) |
| Remote only | `093956d9c22e9d0f80ad0193f119b9783d394667` | `feature/v5-demo-trading-bot` — **EXCLUDED** from all bases/merges |

**Verified full commit IDs** (from `git rev-parse` / `git log --format='%h %H %s'`,
resolved against the local repositories on 2026-11-05):

| Short | Full | Repo |
|---|---|---|
| `0c0624f` | `0c0624fcc91ce78e4d35d06e66c0edb6c1005e6f` | SmartHub (owner-specified baseline) |
| `ae707c0` | `ae707c0ba1c050beab209cff5b4676873e82d262` | SmartHub (historical execution-lock commit) |
| `7003781` | `7003781d93ab0fb994c4ec4ef1a93409fc05c5d1` | SmartHub (M1 tests) |
| `e6dfc30` | `e6dfc3049b25c5c9462d96e1861ad941ab492cc1` | SmartHub (M1 reports) |
| `6d0cc8f` | `6d0cc8fbde71e2d6637cc8a03bbe7fc6028a2127` | AI Lab (baseline) |
| `28892bd` | `28892bdafdaba56add2fd9d207af3c724288c769` | AI Lab (M1 modules + tests) |

The handover-finalization commit that follows `e6dfc30` contains only the
commit-ID corrections, the tooling reconciliations in Section 7 and the two
adversarial regression files; its ID is recorded in the handover message rather
than inside the document it belongs to (avoids a self-referential hash).

Both M1 branches are local and isolated. **No push, merge, rebase, reset,
force-push, branch deletion, or deployment.** Working application codebases are
preserved.

---

## 7. Unresolved Defects, Tooling Issues and Blockers

| ID | Item | Status | Owner / next action |
|---|---|---|---|
| U-001 | MT5 export gates fail: `account_expert_disabled=false` (`account_trade_expert=true`) and `terminal_trading_disabled=false` (`terminal_trade_allowed=true`) | **OPEN BLOCKER** | Operator: configure an investor/read-only terminal with expert + trading disabled. **Not touched by M1.** |
| U-002 | Dataset `TIMEBASE_UNVERIFIED`, `research_eligible=false` | **OPEN BLOCKER** | Operator + R1: official broker DST/session documentation plus independent simultaneous UTC clock evidence bound to the dataset digest |
| U-005 | `diagnose_mt5_export_gates.py` returns `TERMINAL_NOT_ALREADY_RUNNING` although `terminal64.exe` is running | **OPEN TOOLING — root cause identified** | Read-only probe: `Get-Process terminal64 -ExpandProperty Path` returns an **empty** `Path` and `Get-CimInstance Win32_Process` returns empty `ExecutablePath`/`CommandLine` (PID 19796). `terminal_already_running()` therefore cannot match the expected path. Not a logic bug and **not changed**: relaxing to "any terminal64 process" would weaken the exact-terminal safety invariant. Direct read-only SDK diagnostic remains the supported path |
| U-006 | ~~AI Lab `analyse_dst_transitions` caller/API mismatch~~ | **RETRACTED — caller error** | Signature is `analyse_dst_transitions(norm_df: pd.DataFrame, ...)`; it requires a normalized DataFrame with a `_t` column. `src/nas100lab/cli.py:299` calls it correctly with `norm`, and 5 existing `test_phase2b_timebase.py` tests cover it. Passing a CSV path string was our audit-script error, not a defect. **No production code changed.** |
| U-010 | Supabase live connection UNVERIFIED | OPEN INFO | R6: only when cloud integration is explicitly requested. **No cloud/live DB changes made** |
| U-011 | `feature/v5-demo-trading-bot` exists remotely with historical unsafe adapter | GUARDED | R5: permanently exclude from bases/merges; regression constants enforce |
| U-012 | Nine real-data training acceptance gates NO-GO | **OPEN BLOCKER** | Operator: supply independent timebase/contract evidence, then a separate reviewed authorisation |
| — | Variant-log tail truncation is undetectable from the file alone | DESIGN LIMIT | Store `expected_count` / `head_digest` in an external anchor when the log becomes operational |

**Resolved/retracted:** U-003 (`/analyze` NameError) and U-004 (BotController
`last_price`) are obsolete at baseline; U-009 (Android pairing) is corrected by
owner evidence; U-007 (`tzdata`) resolved at audit time; **U-006 is retracted as
an audit caller error** (the DataFrame-based API is already tested). U-005 is
now root-caused to OS-level process-path visibility, with the safety-critical
exact-terminal check deliberately left intact. Neither reconciliation changes
production code.

---

## 8. Eligibility Gates — Current State

`NAS100-AI-Lab-Phase1B/src/nas100lab/training_pipeline.py` documents nine gates.
Current measurement:

| Gate | Status |
|---|---|
| `dataset_manifest_verified` | FAIL (M1 manifest primitives exist, but the quarantined dataset has not been promoted) |
| `mt5_export_gates_passed` | FAIL — two terminal/account flags block export |
| `timebase_verified` | FAIL — `TIMEBASE_UNVERIFIED` |
| `contract_certified` | FAIL — no certified spread/commission/contract history |
| `independent_clock_evidence` | FAIL — no dataset-bound independent UTC audit |
| `broker_documentation_verified` | FAIL — no official broker DST/session policy |
| `model_card_valid` | FAIL — template only, deliberately incomplete |
| `variant_log_verified` | FAIL — no real experiment run has been logged |
| `explicit_owner_approval_id` | FAIL — none supplied |

`overall_decision = NO_GO`, `training_enabled = False`,
`execution_lock = UNCONDITIONAL`, `models_trained_on_real_data = 0`,
`real_market_performance_evaluated = False`.

**Data safety boundary honoured:** no bypass of MT5 checks, no credential access,
no terminal permission change, no trade, no timestamp certification from the
UTC+2/+3 DST heuristic (`reports/dst_analysis.json` remains hypothesis-only),
original CSVs immutable, no predictive model trained from that hypothesis.

---

## 9. Safety Confirmations

- [x] No `order_send` call sites in production Python (AST-verified, not substring scan)
- [x] Execution interlock unconditional; PAPER/DEMO fail closed; `BotMode.OFF` retained
- [x] No trading enabled; MT5 gates blocked and untouched
- [x] No broker credentials, tokens or signing keys read, logged or committed
- [x] No raw broker data added to any commit
- [x] No Supabase/cloud/live database change; no SQLite migration
- [x] Android package, branding, launcher icon, enrollment/auth untouched
- [x] Flask API contracts, risk formula, compliance/drawdown guards unchanged
- [x] Read-only MT5 architecture preserved
- [x] Both full test suites re-run after changes; no tests weakened
- [x] All commit references verified against `git rev-parse`; no unresolved placeholders
- [x] U-005/U-006 reconciled without modifying safety-critical production code
- [x] Synthetic results labelled as software checks, not market-edge evidence
- [x] No paid tools, subscriptions or external accounts used
- [x] No push, merge, force-push, reset, branch deletion or deployment

---

## 10. Next Actions (Require Owner / Operator Action)

1. **Unblock M0:** configure an investor/read-only MT5 terminal so
   `account_expert_disabled` and `terminal_trading_disabled` both pass. Do not
   change credentials or permissions from code.
2. **Obtain independent timebase evidence:** official broker DST/session policy
   plus a simultaneous NTP/HTTPS UTC comparison bound to the dataset SHA-256
   across EU/US DST transitions. No fixed UTC+2/+3 offset assumption.
3. **Certify contract economics:** exact instrument symbol, point size, spread
   units, commission and historical contract changes.
4. **Only then** re-run the nine acceptance gates on a separate reviewed branch;
   real-data training remains disabled until explicit owner approval.
5. Optional offline follow-ups: resolve U-005 by obtaining a process-path
   source that is visible to the diagnostic's execution context (or an
   owner-approved, still exact-terminal detection design) — **do not** relax the
   exact-match invariant; add an external anchor for the variant-log head
   digest. U-006 is closed (caller error, no fix required).

**Full detail:** `WORKBUDDY_BASELINE_AUDIT.md` §11,
`NAS100_RESEARCH_VALIDATION_STATUS.md` §3.1/§8A,
`MASTER_AGENT_TASK_LEDGER.md` TASK-010…015,
`MT5_DATA_ELIGIBILITY_AND_TIMEBASE_REPORT.md`,
`WORKBUDDY_NEXT_ACTIONS.md`.
