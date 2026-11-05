# NAS100_ICT_PropEA — zero-trade diagnosis: evidence required

Status: **NOT DIAGNOSED.** Neither `NAS100_ICT_PropEA.mq5` nor `.ex5` nor any Strategy Tester
Journal exists in the GitHub commit or in this session. No cause is claimed.

## Files needed (exact)

1. `NAS100_ICT_PropEA.mq5` and every `#include` it uses (an `.ex5` alone cannot be audited).
2. The Strategy Tester **Journal** (`Journal` tab, or `<MT5 data folder>\Tester\logs\<date>.log`)
   for a zero-trade run, unedited, from the first line (it states symbol, period, model, deposit,
   leverage, history-sync messages and any `OrderSend`/`CTrade` retcodes).
3. The tester **Settings/Inputs** screenshot or the `.set` file: Symbol, Timeframe, Date range,
   "Every tick" / "1 minute OHLC" / "Open prices only", Deposit, Leverage, Spread (current /
   fixed), Optimization = disabled, and all EA inputs.
4. The **Report**'s Results tab (bars, ticks, symbols, "history quality") and Graph.
5. `symbol_info` for `USTECH100M` from the gateway's MT5: `digits`, `point`, `trade_tick_size`,
   `trade_tick_value`, `trade_contract_size`, `volume_min/max/step`, `trade_stops_level`,
   `trade_freeze_level`, `trade_mode`, `filling_mode`, `session_trade` times, `margin_initial`.
6. Broker server time zone and DST behaviour (server clock vs UTC at two dates, one in each
   US/UK DST regime) so session filters can be checked.

## What the review will check, in order (hypotheses, not findings)

| # | Check | How it is confirmed |
|---|---|---|
| 1 | Symbol string/suffix hard-coded (`NAS100`, `US100`, `USTEC`) vs `USTECH100M` | grep source; Journal "symbol not found" |
| 2 | Tester history: bars synchronised for the whole range? | Journal sync lines, Report "history quality" |
| 3 | Time/session filter using fixed GMT offsets or server time vs UTC; DST weeks | source of the time function; compare to Journal timestamps |
| 4 | Entry logic reachable at all (conditions that cannot co-occur, uninitialised indicator handles returning EMPTY_VALUE, `CopyBuffer` failures) | source + added debug counters per filter |
| 5 | Volatility / ATR / spread thresholds scaled for a different instrument (points vs price units, digits) | compare thresholds to `point`/`digits` |
| 6 | SL/TP distance below `trade_stops_level` or normalised with wrong digits | Journal retcode 10016 (invalid stops) |
| 7 | Lot size below `volume_min`, off `volume_step`, or margin-limited (retcode 10014 / 10019) | Journal; deposit/leverage |
| 8 | Filling mode unsupported by the symbol (retcode 10030) | Journal; `filling_mode` |
| 9 | EA gates on `AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)` / `TerminalInfoInteger(TERMINAL_TRADE_ALLOWED)` | source. NOTE: the tester simulates its own account, so a live investor-only login normally does not explain zero tester trades; this is only a cause if the EA code itself reads those flags on the live terminal context. |
| 10 | New-bar / once-per-day / max-trades / prop-firm daily-loss gate latched | source + counters |

## Method once evidence exists

Add per-filter rejection counters (a diagnostic build only, with **no** loosening of any
filter), rerun the same range, and report how many bars were rejected by each condition. Any
fix is proposed separately, with a reproducible before/after run. No filter is to be relaxed
merely to create trades.
