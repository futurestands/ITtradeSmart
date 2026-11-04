# SmartHub — prop-firm loss-limit engine, isolated Phase 1

**Date:** 2026-11-04  
**Scope:** Calculations and synthetic regression tests only. No new Flask endpoint, Android screen, registry migration, broker connection, account-history ledger, cloud service or order execution.

## Official model-specific rules reviewed 2026-11-04

| Account model | Daily floor | Maximum-loss floor | Reset reference |
|---|---|---|---|
| FTMO 2-Step | Account balance at day start minus 5% of initial capital | Initial capital minus 10% | 00:00 Central European local time, accounting for seasonal offset |
| FTMO 1-Step | Account balance at day start minus 3% of initial capital | Highest **end-of-day balance** (or initial capital if higher) minus 10% initial | 00:00 Central European local time |
| FTMO Instant | Account balance at day start minus 3% of initial capital | Highest recorded **closed-trade balance** (or initial if higher) minus 10% initial | CET/CEST day start for daily-loss floor; total floor may increase intraday |
| FundedNext Stellar 2-Step | Account balance at day start minus 5% of initial capital | Initial capital minus 10% | 00:00 broker server time; documented +02:00/+03:00 seasonal offset |

Authoritative policy references:
- FTMO trading objectives: <https://ftmo.com/en/trading-objectives/>
- FTMO model comparison: <https://ftmo.com/en/comparison-table/>
- FundedNext daily-vs-total limits: <https://help.fundednext.com/en/articles/9941519-daily-loss-limit-vs-maximum-loss-limit>
- FundedNext daily calculation: <https://help.fundednext.com/en/articles/8019811-how-can-i-calculate-the-daily-loss-limit>

**Equity** must represent the broker-reported figure including open P/L, commissions and swaps. Do not estimate it from trade history. A touch of a threshold is classified as a breach conservatively. This engine evaluates **loss limits only**; it does not evaluate consistency, news-trading rules, profit targets, account eligibility, maximum per-position risk, or all firm terms.

## Safety boundaries

- The existing `mt5_accounts.local.json` **five-field schema remains untouched**.
- A single exact account model must be supplied. An unspecified/unsupported model returns `UNKNOWN`; no broker-name inference.
- Decimal-only financial values; invalid, nonfinite and extreme-value inputs return `UNKNOWN`.
- Both reset-time UTC offset and observation-time UTC offset must be supplied by verified upstream clock observations. The two may differ on DST transition days. The engine does not guess the GMT+2/GMT+3 FundedNext transition date.
- Explicit session-start and observation timestamps must be UTC; stale/future data and missing resets return `UNKNOWN`.
- EOD and closed-balance high-water histories are mandatory for trailing models and must be independently tracked/attested on the server. They must **never** be taken from mobile JSON.
- The current implementation has **no broker adapter**. Any snapshot marked `BROKER_READ_ONLY` returns `UNKNOWN: BROKER_ADAPTER_NOT_IMPLEMENTED` even if it claims to be authenticated. Therefore the only status-producing inputs are explicitly labeled **`SYNTHETIC_TEST`** research cases.
- Reports are always `live_verified=False`, `assessment_scope=LOSS_LIMITS_ONLY` and `execution_authorized=False`. A green `WITHIN_LOSS_LIMITS` result in a unit test is NOT an approval for any trade or a claim of comprehensive prop-firm compliance.
- The module imports no other project modules and has no access to the network, filesystem, MT5 or order placement.

## Numerical report semantics

1. Daily floor: `day_start_balance - initial_capital * daily_allowance_fraction`.
2. Total floor: `(initial_capital | maximum EOD balance | maximum closed balance) - initial_capital * total_allowance_fraction`, based on selected model.
3. **Remaining buffer** is `max(0, current_equity - floor)`.
4. **Limit consumed** is `max(0, (reference_balance - current_equity) / allowance * 100)`; it may exceed 100% during a breach.
5. Status: `BREACHED` at or below either floor; `CRITICAL` at >=95% of either allowance consumed; `WARNING` at >=80%; otherwise `WITHIN_LOSS_LIMITS` (synthetic only). Invalid input: `UNKNOWN` without computed floors or buffers.

## Verification executed in the assistant's isolated Python 3.13 environment

```
python -m py_compile compliance_engine.py
python -m pytest -q tests/test_compliance_engine.py
46 passed
```

**Not verified yet:** The full Windows Gateway test suite, Android Gradle build, actual installed APK behavior, current merchant account conditions, or any live broker account. These must be checked separately.

## Next safe sequence

1. Run the complete Windows Gateway test suite on the new isolated feature branch. Existing PR for NAS100 should not be merged or overwritten as part of this step.
2. Independently verify the **specific actual FTMO Free Trial / FundedNext Trial models** and published rules, including timestamps and reset clocks; neither is automatically classified as a purchasable challenge model.
3. Implement a separate, append-only, authenticated local observation store with atomic commits / crash recovery / audit trail, recording broker-account identity, equity, balance, reset events and observed closed/EOD maxima. Do not overwrite the alias registry or store secrets in it.
4. Implement real **read-only** MT5 terminal acquisition and authoritative account binding; only then add a trusted provenance mechanism and allow verified results. Do not let Android supply rule percentages, peaks or clock attestations.
5. Consider a read-only dashboard API after end-to-end verification, with `UNKNOWN` for disconnects, stale data, historical gaps or unauthorized terminals. Keep trading execution locked.

No profitability or commercial-readiness claim is implied by a passing mathematics suite.
