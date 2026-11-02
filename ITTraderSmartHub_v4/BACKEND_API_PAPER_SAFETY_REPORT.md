# V5 backend API and PAPER safety milestone

Research branch: `fix/v5-trustworthy-backtest-phase1`. Starting commit: `d9cedaad2ff8608e378e8d03bc1f38e0f0c5360f`. No live or demo execution enabled. PAPER is **BLOCKED**, not an implemented simulator.

## Backcheck and independent reproduction

Confirmed a clean worktree/index at the expected commit and a matching live remote branch using read-only `git ls-remote`. Read Issue #1, its latest time-integrity handover and `NAS100_TIME_INTEGRITY_REPORT.md`. Baseline full Python regression: **99 passed**. No owner changes were overwritten.

Before implementation, isolated MOCK reproductions saved in `backend/evidence/api_paper_safety/baseline_reproduction.json` established:

| Defect | Observed evidence |
|---|---|
| `/analyze` undefined variable | Authenticated Flask request with `{}` raises `NameError: name 'key' is not defined`, before broker configuration access. |
| Missing price interface | PAPER tick raises missing `MarketDataManager.last_price` AttributeError. |
| Missing freshness interface | Injecting a synthetic legacy price exposes missing `is_data_fresh` AttributeError. |
| Wrong RiskGuardian positional binding | Daily baseline is bound to free margin; open-position count 0 becomes daily starting equity; SymbolSpec becomes position count; stress 0 becomes symbol spec; freshness True becomes infrastructure stress. Real free margin is not passed. |
| Hardcoded defaults | Controller defaults to BTCUSD and a synthetic $10,000 paper balance; daily baseline also hardcoded to $10,000. These are not verified broker inputs. |
| Inaccurate monetary P&L | MOCK 10-point move at 0.5 lots returns $5 in the legacy paper engine, while explicit contract2/tick0.25/value0.50 economics give $10. This is a numerical fixture, not a strategy result. |
| Double-counted closed-position equity | MOCK target close leaves balance10,010 and equity10,020 with zero open positions. |
| Incomplete restart persistence | One virtual position written to temporary SQLite restores as zero in a new legacy engine. The temporary reproduction database was removed; existing state databases were not used. |

No installed MT5 APIs were invoked for these reproductions. `paper_trading.py`, `market_data.py` and `risk_guardian.py` were inspected. The legacy paper engine's fixed-point accounting, missing costs/Bid-Ask model and restart behavior remain unvalidated. The researched accounting, backtesting and time-integrity modules are preserved.

## Task A — `/analyze`

The endpoint now:

- Requires a valid JSON **object**, handles malformed/non-object/deeply nested JSON with400 and oversized bodies with413. No `or {}` coercion can turn invalid input into a valid request.
- Accepts only `{}`, which is what Android synchronization sends. Explicit password/login/server fields are rejected, and all other nonempty bodies are rejected. This also rejects nested/case-varied/aliased credentials and client-supplied account options without interpreting or logging them.
- Reads only host `MT5_LOGIN`, `MT5_INVESTOR_PASSWORD`, `MT5_SERVER`. Missing, invalid/nonpositive login, empty password or blank server returns503 before importing/initializing MT5. No DEMO password fallback is introduced.
- Handles unavailable MT5/import/native-library failures with503. Provider exceptions never appear in response bodies, tracebacks or logs; warnings contain fixed messages only.
- Requires exact configured account login/server identity and **explicit False booleans** for both `trade_allowed` and `trade_expert`. Missing/unknown permissions fail closed. These checks run before and after history retrieval; changed identity/permissions prevent results from being returned.
- Retrieves a seven-day UTC-aware history window only after the checks. `None` history is an outage503; a genuine empty result remains valid. Successful initialization is followed by shutdown even when analysis is rejected or fails. Cleanup failure returns503 with a fixed message.
- Returns existing deal-heuristic fields with `analysis_type=DEAL_HEURISTICS`, `timebase_status=TIMEBASE_UNVERIFIED`, and `execution_policy=RESEARCH_ONLY_LOCKED`. It does not certify broker timestamps, approve trading or assert profitable performance.

Authentication and role rules are unchanged: unauthenticated requests are rejected before body/broker handling; an enrolled monitoring device retains read-only analysis access; V5 control endpoints remain admin-only.

**Limit:** these are MOCK-tested permission/identity checks using broker-reported flags and the configured investor-password field. No genuine investor terminal session was logged into or validated in this milestone, and the API cannot cryptographically prove the password class. Existing `_mt5_lock` serializes this endpoint, not every other MT5 consumer; a centralized broker-session owner remains future work.

## Task B — explicit PAPER quarantine

The unsafe controller cycle was removed, not wired to invented account data:

- PAPER mode requests raise a controlled `PaperSafetyError`, return503 at the API, disable the demo adapter and leave mode OFF. This also avoids the Android formatter's green PAPER mode label.
- Every non-OFF `tick`, including a forced PAPER/DEMO mode or BACKTEST tick, resets to OFF and blocks before broker reads, strategy calls, risk decisions, journals, paper valuation or order routes. Offline research stays in the existing BacktestEngine; mode selection does not execute a backtest.
- There is **no PAPER unlock switch** in this milestone. Adding mock objects, setting mutable approval flags, or even providing verified-looking fields cannot unlock the legacy engine. Input adapters and accurate accounting must be reviewed together before that can change.
- The controller no longer instantiates `PaperTradingEngine`, calls its fixed `$1 per point` P&L, accesses nonexistent `last_price`/`is_data_fresh`, or passes misbound risk arguments. Risk integration itself is still **INCOMPLETE**, rather than pretending a correct call can be made without authoritative inputs.
- No active instrument is presumed: `active_symbol=null`. PAPER status is `BLOCKED_INTEGRATION_UNVERIFIED`, eligible=false, with explicit prerequisites for exact symbol/economics, account identity/equity/free margin/daily state, authoritative quote/closed-candle timebase, risk adapter, valuation and persistence. Monetary values and position/history counts are null, not invented balances or claims of empty persisted state.
- Existing paper tables/records are not interpreted, valued, overwritten, rehydrated or liquidated by the controller. A test verifies existing SQLite sentinel records survive construction and rejected PAPER requests. OFF/emergency stop remain available; emergency-stop state is not reset by a blocked request.

The legacy `paper_trading.py` remains in source for forensic comparison and direct isolated research, but is unreachable from the controller's cycle. Its defects have **not** been repaired or certified. No working end-to-end PAPER simulator, account guardian integration or restart-safe portfolio is claimed.

Android source and branding are unchanged. Response field names remain present, but unavailable numeric values are null. The legacy Android status formatter has its own $10,000 fallback for unavailable equity; that display default is not broker/account evidence. A later Android reporting milestone must render unknown state explicitly. PAPER enable requests currently return an error, not successful PAPER status.

## Validation and preservation

All new broker interactions in tests use simulated MT5 dependencies/configuration; no real initialize/login/history/order request was made during this milestone.

- Baseline: `python -m pytest -q -p no:cacheprovider tests` — **99 passed**.
- Targeted new suites: `tests/test_analyze_api.py tests/test_paper_controller_safety.py` — **79 passed**, zero failures.
- Full final Python suite — **178 passed**, zero failures. Exact interpreter/commands and UTF-8 logs are in the new evidence directory.
- API cases cover invalid JSON/body sizes/nesting, forbidden fields/aliases/nesting, configuration/library/initialization/account/history failures, read-only flag enforcement, initial and mid-request identity mismatch, sanitized errors/cleanup, successful MOCK monitoring and role/auth preservation.
- Controller cases cover unavailable required-input categories, wrong exact instrument identity, approved-looking injected risk state, forced unsafe modes, OFF/emergency stop, unknown account values, unchanged persisted records, controlled HTTP errors and admin/device boundaries. They verify quarantine, **not individual input certification or PAPER accuracy**.
- Existing financial examples, time-integrity protections and forced-enabled demo-adapter rejection remain covered by the full suite. The execution adapter remains unconditional and unchanged; no `order_send` call is introduced or invoked.
- Previous evidence/reports/datasets and NAS100 eligibility files are preserved. A pre-change hash manifest and final comparison distinguish original byte preservation from Git's existing text-line-ending normalization. Accounting/backtesting/time modules, the legacy paper engine, risk guardian and Android have no source diff against the starting commit.

## Remaining blockers and next safe milestone

NAS100 datasets remain **TIMEBASE_UNVERIFIED**. Historical broker DST/timezone/session rules, complete synchronized lower-timeframe data and a suitable comparable authorized DEMO contract remain unverified. No historical CSV was normalized or promoted.

PAPER still needs a serialized read-only broker/account snapshot provider with exact instrument identity and authoritative time/equity/free margin/persistent daily state; correctly named RiskGuardian inputs; a persistent, restart-reconciled ledger using explicit instrument/cost accounting; unrealized equity, margin and risk audit verification. Metadata fallbacks, quote authentication, journal restart identifiers and funded-rule state remain separate blockers.

Next: establish broker/timebase/session evidence and design/test that snapshot-and-ledger boundary under mocks while retaining the PAPER and MT5 execution blocks. Only assess a PAPER unlock after full accounting, persistence and risk integration are independently validated. Profitability, funded-account readiness and live/demo execution remain outside this milestone.
