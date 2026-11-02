# V5 first milestone: baseline, broker discovery and accounting repair

Date: 2026-11-02. Research only. No strategy profitability or funded-account readiness is established.

## Repository backcheck

- Correct workspace: `C:\Users\MJ\Downloads\ITTraderSmartHub_v4_reviewed_patch`.
- Origin: `https://github.com/futurestands/ITtradeSmart.git`.
- Starting checkout: `fix/v5-broker-verified-research`, clean working tree, commit `63972b14d713302a51e439df78a5f8f783e3b2d7`.
- Safely fetched origin without merging. Remote research branch pointed to the same commit, with no additional commits. Switched to tracking `fix/v5-trustworthy-backtest-phase1` before changes.
- Read master Issue #1 through the GitHub connector. No local AGENTS.md was found in the workspace search/tracked inventory.
- Recent source history: real EURUSD report at `63972b1`; broker-calculation fail-closed changes at `b92b24d` and `3334b79`; metadata/authentication changes at `398eed4`; synthetic fallback removal at `5048aae`.
- No owner work was overwritten; no main-branch changes or merge. Final delivery commit is recorded in the Issue #1 handover, avoiding a self-referential SHA in this file.

Status vocabulary: VERIFIED = direct source or execution evidence, with the evidence type stated; MOCK-TESTED = simulated dependencies; INCOMPLETE = partial implementation; BLOCKED = prerequisite unavailable; FAILED = observed incorrect behavior; NOT RUN = no execution evidence.

## Baseline architecture and feature inventory

| Component | Evidence and current status |
|---|---|
| Flask gateway `backend/app.py` | VERIFIED source: local loopback binding; health, analysis, risk, enrollment, telemetry, alerts, research and V5 bot endpoints. Auth/request regression tests are MOCK-TESTED with Flask test client. No production server deployment performed. |
| `v4_services.py` | MOCK-TESTED pairing, hashed tokens, device roles/revocation, rate limits, telemetry freshness and SQLite restart behavior. Exposure connection is absent; effective risk deliberately unavailable. Incident research returns UNAVAILABLE, not calculated statistics. |
| `risk_engine.py` | INCOMPLETE financial advisory calculators: hardcoded pip values/contracts and generic 5%/10% rules. Minimum-lot clamping can exceed requested risk. A claimed trailing limit is actually static. These are not broker sizing or verified firm compliance. Existing arithmetic tests passing do not validate the assumptions. |
| `trade_analysis.py` | MOCK-TESTED deal heuristics aggregate observed costs and separate position IDs. Partial histories/reversals remain provisional; volume anomaly is not monetary risk. Live history route is FAILED: isolated authenticated `/analyze` request raises `NameError: name 'key' is not defined`. |
| `bot/market_data.py` | VERIFIED actual MT5 connectivity/data through separate discovery probe. Loader now excludes position 0, supports D1/H4/H1/M30/M15/M5/M1, rejects unknown timeframes, preserves exact fetch symbol, rejects nonfinite fields and non-UTC timestamps. Remaining metadata fallbacks, normalization elsewhere, cache provenance/closure/freshness and structural-only quote authentication remain INCOMPLETE. |
| `bot/strategies.py` | VERIFIED source: MA+ATR, Donchian, RSI+SMA regime and a passive benchmark. Preserved unchanged. No validated edge. MA/RSI inputs contain extra lag; Donchian TR predecessor indexing needs repair; fixed five-decimal protective levels may violate index tick grids. The benchmark repeatedly emits BUY and is not a true buy-and-hold portfolio benchmark. Confidence constants are not calibrated probabilities. |
| `bot/risk_guardian.py` | MOCK-TESTED missing calculation/margin rejection. Partial equity risk, daily loss, position count and stress sizing exist, requiring broker profit/margin calculations. Missing independent persistent daily/high-water state, account identity ownership, weekly/total/trailing limits, correlated exposure, duplicate protection and session/news policy. Finite-value/type validation needs adversarial review. Direct global MT5 access remains. |
| `bot/bot_controller.py` | FAILED in isolated PAPER instance: `AttributeError: 'MarketDataManager' object has no attribute 'last_price'`. Also references absent `is_data_fresh`, misbinds RiskGuardian positional arguments and uses hardcoded account baselines/default BTCUSD. No end-to-end PAPER readiness. Instance was emergency-stopped after diagnostic. |
| `bot/paper_trading.py` | INCOMPLETE: assumes $1 per price point per lot; lacks proper Bid/Ask/cost model; unrealized aggregation can double-count just-closed P&L; restart does not rehydrate positions/history. Tables existing is not persistent portfolio correctness. |
| `bot/trading_journal.py` | INCOMPLETE: SQLite signal/decision records exist, but counters reset on restart and INSERT OR REPLACE can overwrite prior audit rows. Full immutable execution/outcome audit not established. |
| `bot/analytics.py` | INCOMPLETE: no-loss profit factor is not a ratio and no genuine equity drawdown series is produced. Not used as validation for this repaired replay. |
| `bot/demo_execution.py` | Starting state FAILED safety requirement: admin-enabled path reached `mt5.order_send`, allowlists defaulted to the configured account. Replaced by unconditional research interlock; both enablement and forced-enabled submission tested. No MT5 import or submission call remains in this adapter. |
| `bot/mql5/SmartHub_MA_Crossover.mq5` | VERIFIED source: indicator handles and printed signals only, no orders/deal ledger. ATR/signal timing differ from Python. Compilation, tester configuration, report and trade reconciliation NOT RUN. |
| Historical/report utilities | `run_real_mt5_research.py` retrieved at position 1, unlike old manager. `generate_report.py` and that script used defective backtesting and hardcoded readiness claims. Both now abort at main entry. Legacy report marked superseded and exposed account-login text removed. |

### Existing Android application

Source reviewed: MainActivity, GatewayRepository, GatewaySession, MarketWebSocketManager, V4ApiContracts, manifest/layouts/build configuration and V4ContractsTest. Branding, package `com.ittrader.smarthub`, Kotlin sources and UI were preserved.

- Implemented in source: pairing and logout/revocation, Keystore-backed encrypted preferences, HTTP repository callbacks, telemetry/risk/alerts/research queries, Pipnex advisory inputs, bot OFF/PAPER/backtest/emergency-stop buttons, contract JSON formatting, Binance BTC/USDT WebSocket with reconnect/staleness handling.
- INCOMPLETE integration: ordinary device tokens cannot even query V5 status because all V5 routes require admin. UI controls therefore do not establish authorized working bot control. HTTP sync `/analyze` currently fails as above. Phone-entered equity remains advisory, never authoritative broker equity.
- Security follow-up: URL loopback exception uses string prefixes (`http://localhost...` / `http://127.0.0.1...`) rather than parsed-host equality. Whether Android blocks a particular cleartext request is not proof that validation is correct. WebSocket lifecycle/reconnect overflow also needs review.
- Missing: NAS100 broker overview, synchronized multi-timeframe summaries, reliable floating equity/drawdown, firm-specific compliance state, validated strategy performance and full journal dashboard. The displayed BTC feed is a separate market, not NAS100 data.
- Android contract tests passed: 8 tests, 0 failures/errors/skips. This is JVM validation, not physical-device UI/network/broker verification. APK signing, release build and physical workflow were NOT RUN for this milestone.

## REA investigation

VERIFIED installed package: `rea-agents` 6.7.0, npm launcher at `%APPDATA%/npm/rea.ps1`. Read installed README/package/launcher and actual help for `providers`, `observe-native-ui`, `list-adb-devices`, `resolve-adb-packages`, `inspect-adb-package`; no invented command was treated as evidence.

- `rea providers --format json` reports `observe_native_ui` through native-macos as unavailable, `unsupported_host`: native macOS utilities require macOS. No REA observation of MT5 screens/Strategy Tester is claimed.
- First sandbox provider check also hit Windows native self-test access restrictions; repeated read-only provider check outside sandbox. No provider installation or binary injection was performed.
- ADB initially absent from PATH. Set REA_ADB_PATH to the existing SDK platform-tools/adb.exe for this process only. REA reported ADB 37.0.1 and one connected device in evidence `ev_01e787b0f75007fe0b36cffa2f58c28392021b9b4b4bed165241a593140445bb`; later inventories reported zero devices. Device identifier intentionally omitted here.
- Package inspection attempts returned argument-validation errors after the target disappeared. SmartHub installation, risk screens, Android-to-gateway traffic and mobile UI behavior remain NOT RUN/BLOCKED, not observed facts. No screen capture, private logcat, authentication bypass or proprietary-source retrieval.
- REA evidence is capability reconnaissance only. The architecture findings above come from source and isolated diagnostics; market history/specifications come from official MT5 APIs.

Optional public reference reviewed: [EarnForex Account Protector README](https://raw.githubusercontent.com/EarnForex/Account-Protector/master/README.md). It describes configurable conditions/actions, position filters, timed actions and emergency controls. Useful design inference: separate detection conditions from actions and provide an explicit emergency-entry stop. No code copied, advisor installed or emergency closing enabled. Its existence is not proof of funded-firm compliance.

## Broker discovery and data evidence

Python 3.14.6, MetaTrader5 5.0.6231. Official symbols_get enumerated **12,212 symbols** on a DEMO USD connection. Account identity was compared in memory during each probe; no passwords/login IDs were saved. Initialization used the already configured terminal; no login, symbol selection or order request was made. This is probe-local identity checking, not a completed persistent gateway identity control.

`backend/evidence/nas100_discovery_timeout.json` records a probe that completed seven USTECH100M histories and timed out on USTEC D1. `nas100_discovery.json` records a later complete candidate-metadata inventory and partial CSV acquisition. Each file is a separate timestamped snapshot; do not combine their hashes as if they were one synchronized dataset.

| Specification | USTECH100M | USTEC |
|---|---|---|
| Broker description | USTECH100mini | US Tech 100 Index |
| Contract size | 1 | 1 |
| Point / tick size | 0.1 / 0.1 | 0.01 / 0.01 |
| Tick value profit/loss (USD per lot) | 0.1 / 0.1 | 0.01 / 0.01 |
| Profit / margin currency | USD / USD | USD / USD |
| Volume min / max / step | 1 / 220 / 1 | 0.1 / 250 / 0.1 |
| Calculation mode | 2 (CFD constant observed from installed MT5) | 2 |
| Chart mode | 0 (Bid constant observed from installed MT5) | 0 |
| Trade mode | 0: DISABLED | 0: DISABLED |
| Spread snapshot | 27 points = 2.7 price units (earlier snapshot) | 0 metadata, no quote; not proof of zero costs |
| Margin evidence | Current minimum-volume BUY estimate 286.34 USD in earlier snapshot; varies with quote | Unavailable without quote |
| Sessions / holidays | NOT VERIFIED | NOT VERIFIED |

The later USTECH100M broker profit check returned **$1** for BUY 1 lot from 28653.1 to 28654.1, matching 10 ticks × $0.1. It excludes fees and validates only the current environment, not historical currency conversion, strategy execution or tester reconciliation. See exact values in JSON.

Many name/description matches are ETFs/shares; excluded as substitutes. The later broad inventory also includes NCIQ, whose classification requires description-based ETF exclusion; the final probe code applies that exclusion. Stored snapshots retain what was actually observed, rather than being rewritten to simulate a rerun.

Both identified index candidates currently have trading disabled. USTEC has no current quote and its historical query timed out. Suitable broker/execution comparability is therefore **BLOCKED**, despite available USTECH100M research history. A compatible connection must be an owner-authorized DEMO broker exposing the intended Nasdaq-100 contract with full trading permissions, current quotes, authoritative contract/margin/cost specifications and relevant sessions/history. No automatic broker switching or credentials in chat are required. Do not substitute ETFs, EURUSD, or assume the mini contract matches a future funded-account contract.

### Available closed-bar history (first completed USTECH100M responses)

| Timeframe | Returned bars | First UTC bar | Last UTC bar |
|---|---:|---|---|
| D1 | 1,631 | 2020-06-01 00:00 | 2026-10-29 00:00 |
| H4 | 5,000 | 2023-05-05 20:00 | 2026-11-02 04:00 |
| H1 | 5,000 | 2025-12-02 06:00 | 2026-11-02 09:00 |
| M30 | 5,000 | 2026-05-25 04:00 | 2026-11-02 10:00 |
| M15 | 5,000 | 2026-08-11 21:15 | 2026-11-02 10:15 |
| M5 | 5,000 | 2026-10-01 09:45 | 2026-11-02 10:35 |
| M1 | 5,000 | 2026-10-26 05:17 | 2026-11-02 10:43 |

The requests started at position 1, excluding the terminal's forming bar. All seven first responses had ordered timestamps and zero invalid OHLC rows. This is limited structural validation: D1's old end timestamp, market gaps, session timestamps/DST, completeness, historical spread semantics, last-quote freshness, tick availability and terminal chart limits require investigation. Do not infer a continuous aligned period from separate 5,000-row requests.

The later export saved complete D1/H4/H1/M30/M15 CSV files with hashes. M5 export was interrupted after 1,795 rows: retained explicitly as `USTECH100M_M5.partial.csv`, **not eligible for research**. M1 CSV was not exported. Future CSV/checkpoint publication now uses temporary files and atomic replacement; parent process imposes a 90-second total probe limit, including native calls that can hold the Python GIL.

`backend/evidence/data_quality.json` records file hashes, counts, UTC/OHLC/order checks and interval distributions. The legacy EURUSD H1 CSV contains 5,000 structurally valid, UTC-aware rows; its terminal provenance has NOT been independently reconciled. Discovery/export gaps and timeouts are reported rather than patched with invented candles.

## Backtesting defect assessment and bounded repair

Starting defects independently confirmed in source: spread/slippage treated as whole price units, arbitrary P&L factor 0.1, no volume/contract/currency model, entry at next candle close while protective levels are older, exit checks begin a further candle late, replay credits future exits while allowing overlapping new entries, fabricated dataset version, no ledger, invalid no-loss profit factor, annualized per-trade Sharpe and randomized multiplication of old drawdown mislabeled Monte Carlo. No chronological untouched holdout was implemented.

Implemented smallest self-contained replacement of that unsafe accounting path, preserving strategy implementations:

- Explicit ResearchInstrument economics/provenance and ResearchCosts, no inferred symbol constants or pip-to-index guesses. USD same-currency linear contracts only; other currencies/nonlinear economics fail closed. Tick values must agree with the supported contract formula. This is not a generic broker accounting adapter.
- Broker volume bounds/step and protective tick grid validated; adverse fill rounding handles binary addition noise. Invalid/nonfinite prices, costs and timestamps are rejected.
- Bid OHLC plus historical spread-points × broker point; BUY opens Ask/closes Bid, SELL opens Bid/closes Ask. Explicit adverse slippage on entry and market exits; target treated conservatively as a limit. Explicit round-trip commission and simplified per-bar financing assumption.
- Signal sees only prior closed bars; entry at following open. Single position, at most five holding bars, no exit-bar re-entry; duplicate signal identities rejected. Entry candle participates in stops/targets. Stop wins ambiguous collisions; gapped stops fill at worse open; targets receive no favorable gap improvement. Signals already beyond their bracket at entry are skipped.
- Full precision per-trade ledger, realized-balance curve, content hash, average win/loss, net return, expectancy, win rate, profit factor and drawdown. Undefined no-loss profit factor is null; no regular-time Sharpe is invented. JSON/CSV export and separate UUID-keyed SQLite research result table.
- Monte Carlo explicitly NOT_IMPLEMENTED; no random drawdown PASS label. Strategy Sharpe/out-of-sample/tester validation explicitly absent.
- Unconfigured HTTP backtest route returns 503 BLOCKED_RESEARCH_ACCOUNTING instead of fabricated performance. Deprecated report utilities abort, and legacy report is marked invalid.

Limitations: closed-trade balance drawdown excludes floating/intrabar losses; no margin liquidation or funded compliance simulation; fixed within-bar spreads and per-bar financing are assumptions, not broker historical tick/swap reconstruction. Tick ordering, latency, historical commission/swap tables, dynamic conversion, historical spec changes, full tick fills and strategy-ledger reconciliation are NOT implemented. No NAS100 strategy comparison or profitability metric was run in this milestone.

### Numerical and regression evidence

- Baseline command: `python.exe -m pytest -q -p no:cacheprovider tests`: **34 passed, 1 failed**. The old unavailable-MT5 test incorrectly relied on host absence. Both dependency-unavailable tests now explicitly isolate MT5 using monkeypatch; they do not disable the installed terminal.
- Final backend: **71 passed**. Full command/output retained in `backend/evidence/pytest_phase1.txt`; explicit interpreter is `C:/Users/MJ/AppData/Local/Python/pythoncore-3.14-64/python.exe` because WindowsApps `python` alias could not execute.
- NAS100-style MOCK fixture: tick 0.25, tick value $0.50/lot, contract 2, volume 0.5. A favorable 10-point move = 10/0.25 × 0.50 × 0.5 = **$10**, BUY and SELL; adverse move = **-$10**. These are labeled fixtures, not the discovered broker spec.
- Secondary EURUSD MOCK: 10 pips × $10/pip/lot × 0.1 lot = **$10**.
- Flat Bid round trip with fixture spread 1 point of price, slippage 0.25 each side: gross **-$1.50**, commission **-$1**, five-bar financing **-$0.50**, net **-$3**. Entry-bar collision and worse stop-gap examples produce **-$12.50** and **-$22.50**, respectively. These are numerical assertions, not strategy returns.
- Tests also cover SELL Ask stop, target gap limit, no overlap/duplicates, future signal rejection, invalid economics/volume/timestamps/costs, tick-grid/binary-noise rounding, result persistence/export and HTTP/admin submission interlock.
- Baseline diagnostics in `backend/evidence/baseline_diagnostics.json` reproduce both controller and `/analyze` failures and record Python syntax parsing and zero remaining Python order_send call sites.
- Android: installed Gradle 8.7, `testDebugUnitTest`, 8 JVM contract tests passed. Initial isolated cache/JDK 25 attempt failed with class major version 69; another build succeeded using compiler fallback. The final JDK 21 in-process, nonincremental run completed BUILD SUCCESSFUL in 2m 34s; output is in `backend/evidence/android_phase1.txt`, with XML counts in `android_test_summary.json`. No production Kotlin/branding changes.

## Safety and next milestone

Execution is **DISABLED BY CODE**, independent of bot mode, token, environment or the mutable enabled flag. A future unlock requires a separately approved code change. No demo-mode endpoint was enabled and no order was submitted. No paid service/dependency introduced. Main remains untouched.

Recommended order:

1. Complete broker suitability/provenance: confirm disabled USTECH100M/USTEC status with broker, select an appropriate authorized DEMO contract, obtain verified sessions/holidays/costs and freeze atomic synchronized datasets. Reacquire M5/M1; do not use partial captures. Preserve this research-only lock.
2. Centralize serialized MT5 ownership/account identity and fix controller/market-data/RiskGuardian interfaces, broker equity/free margin, persistent daily baseline, journal IDs and paper cash accounting. Add a genuine PAPER full-cycle integration test before any forward evaluation. Fix `/analyze` NameError and parsed-host URL validation separately.
3. Preregister strategy hypotheses/parameters and chronological train/validation/untouched-test boundaries, with warm-up/purge rules excluding crossing trades. Reconcile a small deterministic ledger with native MT5 before ranking candidates. Keep confidence as explanation, not probability.
4. Proposed multi-timeframe framework (INCOMPLETE, not implemented): UTC close-time availability joins for D1/H4 bias, H1/M30 context and M15/M5 triggers; only bars whose close time is at/before decision time. Start with single-timeframe controls and a small frozen set such as H4+M15, not unrestricted optimization. M1 deferred pending tick/cost evidence. Freeze untouched holdout before research and log every attempted configuration.
5. Proposed independent guardian (INCOMPLETE): configurable rule profiles with reset timezone, static/trailing equity floor, daily/weekly loss, high-water mark, unrealized P&L/costs, total/correlated exposure, streak/duplicate/session/news/overnight limits, margin and infrastructure breakers. Persist decisions and account state transactionally in SQLite; entry stop latches across restart and strategy cannot override it. Obtain current official rules only after firm selection; no generic firm guarantee. Emergency liquidation remains outside this research milestone.

Overall milestone decision: **accounting fixtures and execution interlock MOCK-TESTED; actual broker discovery VERIFIED; data capture and integrated research engine INCOMPLETE; suitable broker/PAPER/strategy-validation readiness BLOCKED.**

Primary references used for interpretation: [MT5 closed/current bar indexing](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrompos_py), [profit calculation in account currency/current environment](https://www.mql5.com/en/docs/python_metatrader5/mt5ordercalcprofit_py), [symbol properties and point-based spread](https://www.mql5.com/en/docs/constants/environment_state/marketinfoconstants). Broker facts and strategy evidence are the local probe outputs, not these documentation examples.
