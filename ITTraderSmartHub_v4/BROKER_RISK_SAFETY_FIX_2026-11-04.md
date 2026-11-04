# ITTrader SmartHub — broker sizing and Donchian ATR remediation

Date: 2026-11-04
Branch: `feature/nas100-apk-research-dashboard`
Status: **Source changes committed; Windows full-suite run and on-device confirmation still required**.

## Why this change

An independent audit identified three serious financial-calculation defects:

1. `calculate_pipnex_lot_size` silently treated unknown index symbols such as FTMO `US100`, `USTEC` and `USTECH100M` as Forex and assumed a $10 pip value and 100,000 contract.
2. The calculator forced a `0.01` lot minimum even when doing so would exceed the chosen cash risk.
3. The Donchian strategy computed ATR with a shifted previous-bar index, including a wrapped reference to the final candle in the first iteration.

These affected sizing validity and historical backtest conclusions; the previous results must not be marketed as real investment performance.

## Implemented safety changes

- Introduced internal, immutable `BrokerContractSpec`, requiring exact symbol, tick size, loss-side USD tick value, broker-defined pip unit, minimum/maximum/step volumes, contract size, USD account currency, and server-side MT5 origin.
- No hard-coded EURUSD, GOLD, crypto, NAS100, `US100` or other contract assumptions remain in the calculator.
- **No live MT5 adapter is wired in yet.** Until a *verified server-side* MT5 symbol specification is available, calculator requests deliberately return HTTP 400 with `BROKER_SPEC_UNVERIFIED` and **no `recommended_lots` field**. This disables potentially unsafe sizing in the existing Android app without requiring the app to display a misleading fallback.
- Untrusted client JSON cannot provide a broker spec. Any optional `broker_spec` field in an Android HTTP request is ignored and cannot authorize a calculation.
- Volume is rounded down on the broker's min-plus-step grid; if the broker's minimum lot exceeds risk, `MIN_LOT_EXCEEDS_RISK_LIMIT` is returned, never a forced minimum volume.
- A requested stop is rounded **up** to a tradable number of ticks when evaluating cash risk. Decimal arithmetic avoids fractional lot-step drift.
- The nominal calculation explicitly disclaims spreads, slippage, gaps and fees and returns `execution_authorized: false`. It cannot place an order.
- Donchian ATR now uses `enumerate(candles[1:], start=1)`, ensuring that the immediate previous close is used, without wrapped/future index.
- Added regression tests for US100 and other aliases, unverified/invalid broker specs, minimum lot, volume cap, lot steps, non-integral stop ticks, protected HTTP endpoint and historical Donchian ATR.

**Only Python backend sizing, Donchian strategy, their tests and this documentation were changed.** Android UI layout, account profiles, authentication, broker connection policy, trading locks, and any live order execution were untouched.

## Required verification on Windows

~~~powershell
$hub = "C:\Users\MJ\Documents\ITtradeSmart-NAS100-Integration\ITTraderSmartHub_v4"
Set-Location "$hub\android_project"
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "Git update failed" }

Set-Location "$hub\backend"
.\.venv-gateway\Scripts\python.exe -m pytest -q tests
if ($LASTEXITCODE -ne 0) { throw "Gateway regression tests failed" }

Set-Location "$hub\android_project"
.\gradlew.bat --no-daemon testDebugUnitTest assembleDebug
if ($LASTEXITCODE -ne 0) { throw "Android build failed" }
~~~

No APK installation or pairing change is required simply to update these server-side calculations. **Do not restart the running Windows Gateway before all regression tests pass and a suitable maintenance point is chosen.** Existing running process remains on the old, unsafe calculation code until explicitly restarted.

## Next blockers before commercial use

1. Establish actual **read-only** MT5 symbol-info retrieval for each selected broker account, including market watch symbol, trade tick size, trade tick value **loss side**, account currency and volume grid. Verify the broker-specific pip/point convention, otherwise size must remain unavailable.
2. Use authoritative broker account rule limits; the older prop-firm drawdown helper is a static initial-balance model, **not** a proven trailing-drawdown rule engine. Android's legacy 'Total Trailing Drawdown' label is currently misleading and must be corrected before relying on it.
3. Validate spread, commission, overnight funding, slip, hard stop and equity drawdowns; strategy profitability and trade execution remain unproven.
4. Regenerate historical Donchian strategy results after the ATR fix. Prior Donchian backtests are invalidated and must not be cited as performance.
5. Do not change or enable `PAPER`, `DEMO` or live execution until separate, explicit approval, verified data and policy checks.

This remediation is a **safety foundation**, not a profitable algorithm or fully operating MT5 sizing service.
