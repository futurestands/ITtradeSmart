# MT5 DATA ELIGIBILITY AND TIMEBASE REPORT

**Date:** 2026-11-05  
**Agent:** WorkBuddy Master Agent (R1 Market-data quality and provenance)  
**Milestone:** M0 — Data Quality and MT5 Timebase  
**Branch:** `feature/workbuddy-master-agent-baseline-audit-20261105`

---

## 1. Executive Summary

**VERDICT: DATA INELIGIBLE FOR RESEARCH. TIMEBASE_UNVERIFIED. NO MODEL TRAINING PERMITTED.**

The MT5 terminal is connected and in DEMO mode, but two of five read-only export gates fail because trading is enabled at both the account-expert and terminal levels. No historical data export occurred. All existing captured data remains quarantined with `TIMEBASE_UNVERIFIED` status. The broker-time discrepancy (~+7,200 seconds vs UTC) is empirically observed but not independently verified as a stable timezone rule.

---

## 2. MT5 Export Gate Diagnostic — Current State

**Inspection method:** Direct SDK query via `MetaTrader5` Python package, using the same non-sensitive flag checks as `tools/diagnose_mt5_export_gates.py`. No login, order, permission change, or credential access occurred.

**Inspection time:** 2026-11-05 ~23:30 UTC (local ~02:30+03:00)

| Gate | Required value | Observed value | Pass? |
|---|---|---|---|
| `terminal_connected` | `true` | `true` | ✅ |
| `demo_account` | `true` (trade_mode=0) | `true` (trade_mode=0) | ✅ |
| `account_trading_disabled` | `trade_allowed=false` | `false` | ✅ |
| `account_expert_disabled` | `trade_expert=false` | **`true`** | ❌ FAIL |
| `terminal_trading_disabled` | `trade_allowed=false` | **`true`** | ❌ FAIL |

**Terminal build:** 6296  
**Python package:** MetaTrader5 5.0.6231

### Failing Gates

1. **`account_expert_disabled`**: `account_info().trade_expert` is `true`, meaning expert (automated) trading is enabled on the account. The export gate requires this to be `false` to ensure the terminal is in a read-only, non-automated state.

2. **`terminal_trading_disabled`**: `terminal_info().trade_allowed` is `true`, meaning the terminal permits trading operations. The export gate requires this to be `false`.

### Prior Reports

The `NAS100_PHASE2_INTEGRATION_REPORT.md` records the prior export attempt returning:
```json
{"status":"BLOCKED_READ_ONLY_DEMO_EXPORT","reason":"TRADING_MUST_BE_DISABLED","research_eligible":false}
```

The current state matches: the demo-mode and account-trading-disabled gates pass, but the expert-disabled and terminal-trading-disabled gates fail. **No gates were relaxed. No permissions were changed.**

### Required Operator Action

The operator must configure the intended investor-only DEMO terminal with:
- Expert trading disabled in the terminal settings
- Terminal trading disabled (or the account set to read-only/investor mode)

This is a manual terminal configuration change, not a programmatic one. No code change can or should bypass these gates.

---

## 3. Broker-Time Discrepancy Investigation

### 3.1 Prior Evidence (from `NAS100_TIME_INTEGRITY_REPORT.md`)

The prior timebase investigation established:

| Question | Verdict |
|---|---|
| Is Windows two hours wrong? | **No.** NTP providers agree Windows is ~0.72s slow. |
| Does local timezone explain conversion? | Windows is UTC+03:00 (E. Africa). `datetime.fromtimestamp(raw, timezone.utc)` preserves input epoch. |
| What do fresh broker timestamps show? | Raw epoch labels are ~+7,200 seconds versus Windows UTC. Current data path behaves like UTC+02:00 wall-clock. |
| Are bars and ticks on unrelated clocks? | No. Fresh M15 OHLC reconciles exactly with historical Bid ticks in the same raw interval. |
| Is a universal -7,200s subtraction justified? | **No.** Historical broker timezone/DST rules not independently established. Shared raw-time offset is invisible to cross-timeframe price matching. |

### 3.2 Independent UTC Clock Evidence

Four NTP measurements (two providers, two captures) confirmed Windows is 0.72–0.73 seconds slow. HTTPS Date headers corroborated. `w32tm` service was stopped (`0x80070426`). No clock synchronization was attempted.

### 3.3 Cross-Timeframe Alignment

Relative price alignment was VERIFIED for all complete windows:

| Comparison | Complete windows / exact OHLC matches |
|---|---|
| M15 → M30 | 2,496 / 2,496 |
| M15 → H1 | 1,245 / 1,245 |
| M15 → H4 | 267 / 267 |
| M30 → H1 | 2,493 / 2,493 |
| H1 → H4 | 1,090 / 1,090 |

Fresh captures after position-zero exclusion: all match at zero relative offset. This confirms internal consistency of the raw timestamp system, but does not establish absolute UTC.

### 3.4 DST Transition Analysis (AI Lab)

The AI Lab's `analyse_dst_transitions` on the quarantined 100,002-row M5 dataset detected heuristic DST shifts at:

| Date | Label | Status | Shift hours |
|---|---|---|---:|
| 2025-10-26 | EU Autumn back | SHIFT_DETECTED | -1.0 |
| 2025-11-02 | US Autumn back | SHIFT_DETECTED | +1.0 |
| 2026-03-29 | EU Spring forward | SHIFT_DETECTED | +1.0 |
| 2026-10-25 | EU Autumn back | SHIFT_DETECTED | -1.0 |
| 2026-03-08 | US Spring forward | SHIFT_DETECTED | -1.0 |
| 2026-11-01 | US Autumn back | SHIFT_DETECTED | +1.0 |

**Interpretation:** The detected shifts are consistent with a broker server following EU DST conventions (UTC+2 winter / UTC+3 summer). However, the AI Lab's report explicitly cautions: "Observed shift is heuristic only — requires independent UTC clock comparison to confirm DST identity."

The divergence between EU and US DST transition dates (typically 1-2 weeks apart in autumn) is visible in the data. This is consistent with a broker server on EET (Eastern European Time = UTC+2/+3 with EU DST rules), which is the standard MetaQuotes-Demo configuration.

### 3.5 Critical Gap: Independent UTC Verification

The timebase remains UNVERIFIED because:

1. **No simultaneous independent UTC clock reading** was taken at the moment of historical data capture.
2. **No broker server-time/DST policy documentation** has been obtained from the broker.
3. **The ~+7,200s offset** is empirically observed in current quotes but is not independently established as a stable multi-year timezone rule.
4. **Historical DST transitions** are detected heuristically but not confirmed against an independent UTC reference.
5. **The Windows Time service** (`w32tm`) is stopped, so even the local clock's NTP synchronization is uncertified.

### 3.6 Timebase Evidence Gap Analysis (from AI Lab Milestone 3)

| Step | Description | Status |
|---|---|---|
| Step 1 | Windows UTC sync | BLOCKED: W32Time stopped |
| Step 2 | Live quote sync | BLOCKED: Terminal trading gates fail |
| Step 3 | Bar timestamp semantics | INCOMPLETE: Assumed bar-open, unconfirmed by live tick stream |
| Step 4 | Session boundaries | INCOMPLETE: Heuristic, unconfirmed by broker contract |
| Step 5 | DST transitions | INCOMPLETE: EU vs US divergence detected but unresolved |
| Step 6 | Gap classification | COMPLETE: 100,002 bars audited |
| Step 7 | HTF anchor alignment | INCOMPLETE: Requires genuine H4 export |
| Step 8 | Multi-TF consistency | INCOMPLETE: Requires genuine H1 export |

---

## 4. Data Eligibility Assessment

### 4.1 SmartHub Evidence CSVs

All five complete CSVs (D1, H4, H1, M30, M15) have been audited with `nas100_data_audit.py`:

| Property | Value |
|---|---|
| Invalid OHLC | 0 (all files) |
| Duplicate epochs | 0 (all files) |
| Off-grid bars | 0 (all files) |
| Strictly ordered | Yes (all files) |
| Timebase status | TIMEBASE_UNVERIFIED (all files) |
| Research eligible | **false** (all files) |
| Blockers | INDEPENDENT_TIMEBASE_AND_SESSION_EVIDENCE_REQUIRED, EXECUTION_COST_AND_CONTRACT_HISTORY_UNVERIFIED |

### 4.2 AI Lab Quarantined M5 Data

The 100,002-row M5 dataset has a provenance dossier with:

| Property | Value |
|---|---|
| Status | QUARANTINED |
| Research eligible | **false** |
| Contract certified | **false** |
| Timebase verified | **false** |
| Quarantine reasons | CONTRACT_NOT_CERTIFIED, RAW_BROKER_TIMESTAMPS_BROKER_SERVER_TIME, TIMEBASE_UNVERIFIED |
| Gaps | 407 total (70 weekend-like, 337 other) |
| Zero-range bars | 25 |
| Largest gap | 274.17 hours |

### 4.3 M5 Partial Capture

`USTECH100M_M5.partial.csv` (1,795 rows) is an interrupted export and is **explicitly excluded from research**.

### 4.4 Immutability

All six original SmartHub CSVs have been verified byte-for-byte against their recorded SHA-256 hashes. No CSV was shifted, renamed, overwritten, or rehashed. The AI Lab's quarantined M5 data SHA-256 (`aecb75f4...`) is independently confirmed.

---

## 5. Instrument Specifications (Current Snapshot)

| Specification | USTECH100M | USTEC |
|---|---|---|
| Description | USTECH100mini | US Tech 100 Index |
| Contract size | 1 | 1 |
| Point / tick size | 0.1 / 0.1 | 0.01 / 0.01 |
| Tick value (USD/lot) | 0.1 / 0.1 | 0.01 / 0.01 |
| Profit / margin currency | USD / USD | USD / USD |
| Volume min / max / step | 1 / 220 / 1 | 0.1 / 250 / 0.1 |
| Calculation mode | 2 (CFD) | 2 (CFD) |
| Chart mode | 0 (Bid) | 0 (Bid) |
| Trade mode | 0: DISABLED | 0: DISABLED |

**Important:** These are current snapshots. Historical contract/cost changes are NOT documented. Current tick values do not establish historical economics.

---

## 6. Session Timing Investigation

### London Session (UTC, standard time)
- Open: ~08:00 UTC
- Close: ~16:30 UTC

### New York Session (UTC, standard time)
- Open: ~13:30 UTC
- Close: ~20:00 UTC

### Overlap
- ~13:30–16:30 UTC (standard time)

### Broker Server Time (Observed)
- Appears to be EET (UTC+2 winter / UTC+3 summer)
- This means London open appears as ~10:00/11:00 server time
- New York open appears as ~15:30/16:30 server time

**WARNING:** These session boundaries are heuristic. The NAS100 CFD may not follow standard forex session hours. Broker-specific session calendars and holidays are NOT VERIFIED.

---

## 7. DST Transition Concerns

### US vs EU DST Divergence
- US DST: 2nd Sunday of March → 1st Sunday of November
- EU DST: Last Sunday of March → Last Sunday of October
- There is a 1-2 week period in autumn (US still on DST, EU off) and spring (US already on DST, EU not yet) where the offset between US market hours and EU broker server time changes by 1 hour.

### Impact on Session Classification
If the broker server follows EU DST (as the heuristic suggests), then during the divergence periods:
- US market session open/close times shift by 1 hour relative to broker server time
- Session classification based on broker server time would be incorrect during these periods
- Any features derived from session timing would have a 1-hour error for ~2-4 weeks per year

### Required Resolution
Obtain the broker's official server-time/DST policy documentation. Until then, session-based features are unreliable across DST transitions.

---

## 8. Conclusions and Blockers

### Data Eligibility: BLOCKED

No dataset is eligible for model training or performance evaluation. All data carries `TIMEBASE_UNVERIFIED` status with explicit blockers:

1. **INDEPENDENT_TIMEBASE_AND_SESSION_EVIDENCE_REQUIRED** — No independent UTC clock comparison was performed at capture time. No broker server-time/DST policy documentation obtained.
2. **EXECUTION_COST_AND_CONTRACT_HISTORY_UNVERIFIED** — Current contract specs don't establish historical economics. No historical spread/commission/swap data.
3. **CONTRACT_NOT_CERTIFIED** — No broker certification of contract specifications.
4. **RAW_BROKER_TIMESTAMPS_NOT_UTC** — Timestamps are broker server time, not UTC.

### What Can Proceed (Safe Offline Tasks)

- Historical dataset auditing (complete)
- Missing-bar analysis (complete)
- Code correctness tests (passing)
- Backtesting engine validation (passing with synthetic data)
- Leakage detection (implemented in AI Lab)
- Risk calculation tests (passing)
- Model target and feature specifications (designed in ML_DESIGN.md)
- Reproducibility infrastructure (walk-forward, safety gate, provenance)
- Synthetic testing explicitly labeled as synthetic (passing)

### What Requires Operator Action

1. **Configure investor-only DEMO terminal**: Disable expert trading and terminal trading in the MT5 terminal settings.
2. **Obtain broker server-time/DST policy**: Request official documentation from the broker or MetaQuotes-Demo.
3. **Perform simultaneous UTC-vs-broker comparison**: Once gates pass, capture fresh quotes with NTP-bracketed observation.
4. **Complete M1/M5 historical export**: Once gates pass, export complete non-partial datasets with verified timebase.
