# NAS100 RESEARCH VALIDATION STATUS

**Date:** 2026-11-05 (M1 revision applied after owner review)  
**Agent:** WorkBuddy Master Agent (R2 Market structure/ICT + R3 ML training + R4 Independent validation)  
**Audit branch:** `feature/workbuddy-master-agent-baseline-audit-20261105`  
**M1 branches:** `feature/workbuddy-m1-offline-engineering-20261105` (SmartHub and AI Lab)  

> **CORRECTION NOTICE (M1).** Section 3.1 previously stated that all five ML
> safety-gate checks fail. That was imprecise: the dataset SHA-256 matches and the
> provenance dossier exists, so those two checks **PASS**. Each individual check
> result is now reported below. No eligibility conclusion changed: real-data
> training remains blocked and no model was trained.

---

## 1. Executive Summary

**No model has been trained. No strategy has been validated. No profitability is claimed. No market edge is established.**

The NAS100 research system has a well-structured deterministic engine (structure, ICT, sessions, backtesting) and a comprehensive ML design document. However, all real data remains `TIMEBASE_UNVERIFIED` and `research_eligible=false`. The system correctly fails closed: no training, no evaluation, no performance claims are produced on real data.

---

## 2. Deterministic Engine Status

### 2.1 Market Structure Analysis (SmartHub `backend/nas100/`)

| Module | Capabilities | Test Status |
|---|---|---|
| `structure.py` | Close-based BOS/CHoCH detection | VERIFIED |
| `swings.py` | Confirmed fractal swings, HH/HL/LH/LL labels | VERIFIED |
| `fvg.py` | Fair Value Gap detection and fill state | VERIFIED |
| `liquidity.py` | Liquidity sweep detection | VERIFIED |
| `sessions.py` | DST-aware London/NY/Asia session conventions | VERIFIED |
| `volatility.py` | ATR regimes, consolidation detection | VERIFIED |
| `decision.py` | BUY/SELL/NO TRADE with explainable provenance | VERIFIED |
| `backtest.py` | Next-bar-or-later limit-fill proxy, stop-first exits, additive R summaries | VERIFIED |
| `research.py` | Prefix-only analysis, deduplication, single-position proxy | VERIFIED |
| `timeframes.py` | Closed-bar MTF resampling | VERIFIED |
| `candles.py` | MT5 numpy structured array conversion | VERIFIED |
| `tz.py` | IANA timezone resolution (requires tzdata) | VERIFIED |

### 2.2 Integration Guards

The following safety guards are implemented and tested:

- Reject future data as fresh
- Reject naive observation timestamps
- Require current, genuinely higher, closed HTF context
- Block recent HTF gaps
- Preserve every unknown gap as a fault (never infer market closure)
- Block unknown spreads when configured
- Require FVG formation at/after the setup's structure shift
- Validate resampling order, grid and fill fraction
- Preserve official MT5 Python UTC epochs
- Reject nonexistent DST wall times

### 2.3 Backtesting Engine

The `backtest.py` module implements:

- **Entry:** Limit at FVG midpoint, filled only if a later candle trades through it within `max_wait` bars
- **Exits:** Stop-first ambiguous exits, worse-open gap stops, bounded holding periods
- **Costs:** Spread charged once, slippage on each side, commission once
- **Outcomes:** Additive R-multiples, no lots or USD return inferred
- **Incomplete outcomes:** Unfilled setups counted but excluded from outcome training
- **Synthetic validation:** 1,000 randomized scenarios passed

**Limitations:** No margin liquidation, no funded compliance simulation, fixed within-bar spreads, per-bar financing assumption. Tick ordering, latency, historical commission/swap tables, and strategy-ledger reconciliation are NOT implemented.

---

## 3. ML Training Infrastructure Status (AI Lab)

### 3.1 Safety Gate — Individual Check Results (M1 Corrected)

The `safety_gate.check_training_safety()` implementation in
`NAS100-AI-Lab-Phase1B/src/nas100lab/safety_gate.py` performs one structural
precondition (provenance dossier must exist), then five blocking checks. Measured
directly against `data/quarantine/USTECH100M_M5_raw.csv` and
`USTECH100M_M5_raw.provenance.json`:

| # | Check | Evidence measured | Result |
|---|---|---|---|
| 0 | Provenance dossier exists | `USTECH100M_M5_raw.provenance.json` present, parseable JSON | **PASS** |
| 1 | Byte-for-byte SHA-256 integrity | Current file `aecb75f4efe2c1a80042ac2bc9ad78537feaa05b5c7cfeae2be48a3ae0c5e44f` equals dossier `file_sha256`; 100,002 rows | **PASS** |
| 2 | Research eligibility | `research_eligible: false`, `status: QUARANTINED` | **FAIL** — `RESEARCH_INELIGIBLE` |
| 3 | Independently verified UTC timebase | `timebase_evidence.verified: false`, `verification_audit_digest: null`, `timebase_status: TIMEBASE_UNVERIFIED` | **FAIL** — `TIMEBASE_UNVERIFIED` |
| 4 | Documented contract / transaction-cost specification | `contract_spec.contract_certified: false`, `certification_proof_hash: null` | **FAIL** — `CONTRACT_UNCERTIFIED` |
| 5 | Dataset location | Path contains `data/quarantine/` | **FAIL/BLOCKED** — `DATASET_IN_QUARANTINE` |

**Actual gate invocation result:** `TrainingSafetyError: TRAINING_BLOCKED` with
four reasons — `RESEARCH_INELIGIBLE`, `TIMEBASE_UNVERIFIED`,
`CONTRACT_UNCERTIFIED`, `DATASET_IN_QUARANTINE`. The SHA-256 and dossier checks
did not contribute blocking reasons.

This corrects the earlier wording: **two checks PASS, four blocking conditions
FAIL**. Training is correctly blocked; `TIMEBASE_UNVERIFIED` and
`research_eligible=false` are unchanged. No timestamp was certified and no model
was trained. Integrity of a file is not evidence of its clock or its contract.

### 3.2 Walk-Forward Validation

The `walkforward.py` module implements:

- **Purged, embargoed chronological folds** — Labels crossing split boundaries are purged; embargo period = `max_wait + max_hold` bars
- **Train/calibration/test separation** — Three-way split with embargo gaps
- **Prior baseline benchmark** — Class-prior benchmark on untouched test blocks (not a market edge claim)
- **Withheld test events** — Events whose labels exit beyond the test window are withheld

### 3.3 Label Engineering

The `labels.py` module implements:

- **Triple-barrier method** — Engine stop, engine target, time barrier
- **Candidate-conditioned** — Outcomes evaluated only at setup trigger bars
- **Ambiguous outcome handling** — `WIN`, `LOSS`, `AMBIGUOUS`, `EXPIRED_PROFIT`, `EXPIRED_LOSS`, `INCOMPLETE`
- **Stop-first conservative assumption** — If stop and target both inside one candle, assume stop first

### 3.4 Feature Engineering

The `features.py` module specifies stationary features (no raw price levels):

- Structure: LTF/HTF trend state, BOS/CHoCH counts, swing sequences, sweep depth, displacement, FVG metrics
- Volatility: ATR percentile, efficiency ratio, consolidation flag
- Session: London/NY/overlap flags, minutes since session open, weekday
- Execution: Spread/ATR ratio
- Context: Position within prior-day range, distance to untouched liquidity

### 3.5 Model Ladder (Designed, Not Trained)

| Level | Model | Status |
|---|---|---|
| 0 | Base rate / rules-only | DESIGNED |
| 1 | L2 logistic regression | DESIGNED |
| 2 | Shallow gradient-boosted trees | DESIGNED |
| 3 | Random forest cross-check | DESIGNED |

### 3.6 Calibration Design

- Out-of-fold probabilities → reliability curve, Brier score, log loss, ECE with bootstrap CIs
- Calibrator fitted on calibration segment strictly before test segment
- Probability shown to user only if calibration meets pre-registered criteria on every holdout fold
- Otherwise UI shows no number

### 3.7 Synthetic-Only Results

All existing "results" are explicitly synthetic:

| Report | Content | Label |
|---|---|---|
| `synthetic_training_report.json` | Synthetic logistic regression training | SYNTHETIC |
| `synthetic_trade_intelligence_demo.json` | Full pipeline demonstration | SYNTHETIC |
| `synthetic_candidate_walkforward.json` | Walk-forward on synthetic data | SYNTHETIC |
| `synthetic_confluence_stress.json` | Multi-seed cost stress | SYNTHETIC |
| CLI synthetic smoke | 22 inspected: BUY 0, SELL 0, NO TRADE 22; expectancy null | SYNTHETIC |

**None of these are market edge evidence. They are software correctness checks.**

---

## 4. Research Roadmap Status

### SmartHub Milestones

| Milestone | Description | Status |
|---|---|---|
| Phase 1 | Broker discovery, baseline audit, backtesting repair | COMPLETED |
| Time integrity | UTC clock evidence, timeframe alignment, DST analysis | COMPLETED (TIMEBASE_UNVERIFIED) |
| Phase 1 integration | NAS100 structure/ICT/sessions/decision modules | COMPLETED (520 tests) |
| Phase 2 integration | Simulator, exporter, research CLI | COMPLETED (591 tests) |
| MT5 read-only probe | Fail-closed account inspector | COMPLETED (31 tests) |
| Observation ledger | Append-only SQLite research ledger | COMPLETED (31 tests) |
| Compliance engine | Loss limits, drawdown guards | COMPLETED |
| Launcher icon | Adaptive branded icon | COMPLETED |

### AI Lab Milestones

| Milestone | Description | Status |
|---|---|---|
| Baseline | Branch setup & regression | COMPLETED (335 passed) |
| M1 | Security & correctness hardening | COMPLETED (344 passed) |
| M2 | ML integrity audit & fixes | COMPLETED (350 passed) |
| M3 | MT5 timebase evidence collection | COMPLETED (AUDITED) — TIMEBASE_UNVERIFIED |
| M4 | Historical data & multi-TF preparation | IN PROGRESS |
| M5 | Research-grade ML training & walk-forward | PENDING (blocked on data eligibility) |
| M6 | Real-data training eligibility review | PENDING (blocked on M0 gates) |
| M7 | SmartHub integration readiness | PENDING |
| M8 | End-to-end research validation | PENDING |
| M9 | Git backup & morning handover | PENDING |

---

## 5. Leakage Detection Assessment

### Implemented Controls

| Control | Location | Status |
|---|---|---|
| Prefix-only analysis | `nas100/research.py` | VERIFIED — scanner does not read held-out suffix |
| Closed-bar availability | `nas100/candles.py`, `bot/time_integrity.py` | VERIFIED — decision uses only bars closed at decision time |
| Purged walk-forward | `nas100lab/walkforward.py` | VERIFIED — label-overlap purging with embargo |
| Feature timing | `nas100lab/features.py` (designed) | DESIGNED — all features from candles closed at t0 |
| Label timing | `nas100lab/labels.py` | VERIFIED — labels start after decision close, include wait+hold horizons |
| HTF causality | `nas100lab/htf_aggregation.py` | VERIFIED — exact candle availability boundaries |
| Synthetic/training isolation | `nas100lab/trade_demo.py` | VERIFIED — independent seed and disjoint chronological start |

### Test Coverage

The test suite includes explicit leakage detection tests:

- `test_scanner_does_not_validate_or_read_the_held_out_suffix` — VERIFIED
- `test_reference_scanner_has_no_future_dependency` — VERIFIED
- `test_raw_decision_counts_are_separate_from_deduplicated_proxy_signals` — VERIFIED
- `test_current_unclosed_bar_is_excluded_and_disclosed` — VERIFIED
- `test_future_dated_ltf_bar_is_never_fresh_and_blocks_buy` — VERIFIED
- `test_stale_htf_does_not_authorize_buy` — VERIFIED

---

## 6. Risk Calculation Tests

| Test Area | Status | Notes |
|---|---|---|
| Broker sizing fail-closed | VERIFIED | `test_broker_sizing_fail_closed.py` |
| Compliance engine | VERIFIED | `test_compliance_engine.py` — loss limits, drawdown guards |
| Research accounting | VERIFIED | `test_research_accounting.py` — tick values, volume bounds, adverse fills |
| Paper controller safety | VERIFIED | `test_paper_controller_safety.py` — execution interlock |
| V5 bot safety | VERIFIED | `test_v5_bot.py` — forced-enabled rejection |

### Risk Formula

The pre-existing infrastructure-adjusted risk formula remains unchanged:
```
EffectiveRisk = BaseRisk × (1 - 0.5 × InfrastructureStress / 100)
```

---

## 7. Independent Review Assessment

### Code Review

| Area | Reviewed by | Status |
|---|---|---|
| Phase 1 baseline | Claude (prior session) | Comprehensive — component inventory, defects, safety |
| Time integrity | Claude (prior session) | Comprehensive — NTP, cross-TF, DST, gaps |
| Phase 1/2 integration | Codex (prior session) | Comprehensive — 591 tests, APK, database |
| Security remediation | Claude (prior session) | Comprehensive — execution lock, credential safety |
| ML integrity | ChatGPT (prior session) | Comprehensive — model trust, leakage, calibration |
| This audit | WorkBuddy | Independent verification of all above claims |

### Discrepancies Found

1. **`tzdata` not installed in gateway venv** — The lock file declared it but it was not installed. Fixed by WorkBuddy. This was an environment setup issue, not a code defect.
2. **`diagnose_mt5_export_gates.py` terminal detection** — The script's `terminal_already_running` check failed to detect the running terminal. **M1 root cause (read-only probe, PID 19796):** `Get-Process.Path` and CIM `ExecutablePath`/`CommandLine` are empty for the running `terminal64.exe`, so exact-path matching cannot succeed. This is OS process-path visibility, not a logic bug; the exact-terminal invariant was deliberately **not** relaxed. The direct SDK approach works. This is a tooling issue, not a safety concern.
3. ~~**`analyse_dst_transitions` API mismatch**~~ — **RETRACTED (M1): caller error, not a defect.** The function signature `analyse_dst_transitions(norm_df: pd.DataFrame, ...)` requires a normalized DataFrame with `_t`; `src/nas100lab/cli.py:299` calls it correctly with `norm`, and 5 existing `test_phase2b_timebase.py` tests cover it. Our audit script passed a CSV path string. The existing `reports/dst_analysis.json` remains hypothesis-only evidence. No production code changed.

---

## 8. Acceptance Gates (Pre-Registered)

From `ML_DESIGN.md`, the following gates must pass before any model is shipped:

1. **Net expectancy** — Lower CI bound above zero in a stated majority of folds
2. **Calibration criteria** — Met on every holdout fold
3. **Cost stress** — Results survive +50% spread/slippage
4. **Config perturbation** — Results survive engine config changes
5. **Sample size** — Sufficient events per fold/regime
6. **Multiple testing** — Log of every variant tried; deflated-Sharpe adjustment

**None of these gates have been evaluated. No holdout has been opened.**

---

## 8A. M1 Offline Correctness and Reproducibility (New Work)

All work below is offline, synthetic-fixture based and reversible. No eligible
broker data was used, no predictive model was trained, and no performance metric
was computed on market data.

### 8A.1 Conservative simulator and causality regressions (SmartHub)

`backend/tests/test_m1_simulator_and_causality.py` — 28 tests, all pass. Pins:

- **Stop-first ambiguous-bar accounting:** exact `gross_r = -1.0`, one-off
  `costs_r = 0.2`, `net_r = -1.2`, `exit_price = 98` when both barriers are
  touched; BUY and SELL mirrors; a high far beyond the target never grants price
  improvement.
- **Adverse gap fills:** gap-down/open-worse stops on the fill bar and on later
  bars exit at `min(stop, open)` / `max(stop, open)`; favourable gaps beyond a
  target still exit **at the target price**, never at the open.
- **NO_FILL / INCOMPLETE separation:** `NO_FILL` only when the whole
  `max_wait_bars` window was observed; `INCOMPLETE` when the series ends early
  (no fill) or when a filled position is still open; `summarize` counts these
  separately and never books them as wins or losses.
- **Cost stress:** spread floor, slippage per side, commission per round trip and
  `point_size` scale `costs_r` exactly once; a wide exit-bar spread can only
  widen the floor; a gross `+2.0R` win becomes a net loss under extreme costs
  with no clamping.
- **HTF as-of / leakage:** `htf_closed_by` inclusive-at-close boundary,
  `resample` never emits an unfinished bucket, `analyze_multitimeframe` HTF
  `as_of <= ltf.as_of`, future clock → `FUTURE_DATA` NO TRADE, future HTF →
  `HTF_BAR_NOT_CLOSED` NO TRADE, completed outcomes invariant to appended future
  bars.

`backend/tests/test_m1_baseline_reconciliation.py` — 14 adversarial regression
tests pinning the five audit corrections (see baseline audit §11), including an
AST-based scan that finds **zero `order_send` call sites** in production Python
(docstring mentions are not call sites).

### 8A.2 Walk-forward boundary and calibration isolation (AI Lab)

- `tests/test_m1_walkforward_boundaries.py` — 13 tests on the exact off-by-one
  purge semantics: an event ending exactly at the next split start is purged,
  one ending one bar earlier is retained; a test event ending at `te_end` is
  included, one bar later is withheld; `embargo_bars=0` still purges crossing
  events; partitions are disjoint and strictly chronological; unresolved labels
  are excluded (not counted as purged); `step_bars` changes fold count but not
  split widths; prior baseline ignores calibration labels.
- `tests/test_m1_calibration_isolation.py` — 6 tests. The calibration API has no
  test-label parameter. A recording estimator spy proves exactly two `fit`
  calls: base on `y_train` only, Platt sigmoid on `y_cal` only, none of length
  `len(x_test)`. Inputs are never mutated; single-class calibration fails rather
  than faking a probability.

### 8A.3 Reproducibility infrastructure (AI Lab, new modules)

- `src/nas100lab/reproducibility.py` — canonical UTF-8 JSON hashing
  (`allow_nan=False`, sorted keys), scoped `config_hash`, immutable dataset
  manifests (per-file SHA-256 + size + self-digest, verified against disk,
  detects altered/missing/unmanifested files and refuses to self-certify
  eligibility), a model-card template with fail-closed validation, and an
  append-only hash-chained experiment-variant log with tamper/reorder/duplicate/
  truncation detection.
- `src/nas100lab/training_pipeline.py` — nine explicit acceptance gates,
  `training_acceptance_gates()` / `pipeline_status()` /
  `prepare_real_data_training()`. `REAL_DATA_TRAINING_DISABLED` is an
  unconditional module constant; `prepare_real_data_training()` **always** raises
  `TrainingDisabledError`, even when all nine gates are documented. Zero models
  fitted on real data; zero performance evaluations.
- `tests/test_m1_htf_asof.py` — 6 tests proving the AI Lab's
  `resample_m5_to_timeframe` excludes the last unclosed M5 bar, cannot be changed
  by bars beyond `asof_time`, records `dropped_incomplete_bins`, and keeps
  metadata `TIMEBASE_UNVERIFIED` / `research_eligible=false`.
- `tests/test_m1_reproducibility.py` (34 tests) and
  `tests/test_m1_training_pipeline.py` (7 tests) cover the new modules.

### 8A.4 Verified full-suite results after M1 and finalization

| Suite | Baseline | After M1 | After finalization (current) |
|---|---|---|---|
| SmartHub backend | 600 passed, 2 skipped | **642 passed, 2 skipped, 0 failed** | **660 passed, 2 skipped, 0 failed** (+18) |
| AI Lab | 426 passed | **492 passed, 0 failed, 0 errors** | **497 passed, 0 failed, 0 errors** (+5) |

The finalization tests pin commit-ID accuracy, absence of unresolved
placeholders, the fail-closed verdict, the retracted U-006 caller error and the
DataFrame-based DST API contract. No existing test was weakened or removed. No
existing production component was replaced. Synthetic demonstrations remain
software checks only.

---

## 9. Honest Limits

- Markets are non-stationary; demo data and fills differ from live
- A model can look good in backtest and fail live
- Few setups per month limit statistical power
- "No reliable edge found" is a possible, acceptable outcome
- Current broker (MetaQuotes-Demo) may not represent a real funded-account broker
- Session timing is heuristic until broker policy is documented
- Historical contract/cost changes are unknown

---

## 10. BUY/SELL/NO TRADE Status

The deterministic engine produces BUY/SELL/NO TRADE assessments based on:
- Sweep → structure shift → open FVG confluence
- HTF context alignment
- Session and volatility regime filters

**On real data:** All assessments are blocked because data is ineligible. The CLI correctly returns null counts and null statistics.

**On synthetic data:** The smoke test produced 22 NO TRADE assessments with null expectancy. This is correct behavior — synthetic data is not market evidence.

**Important distinction:** These are rule-based signals, NOT validated AI predictions. The app correctly labels them as "rule-based, unvalidated" until model gates pass.
