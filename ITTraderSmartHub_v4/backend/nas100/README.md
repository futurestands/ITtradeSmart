# nas100 — market-structure engine (Phase 1)

Standalone, read-only analysis package. **No broker I/O, no MetaTrader5 import, no order
functions, no credentials, no network, no file access.** A static test
(`test_package_has_no_execution_network_or_credential_code`) enforces this.

Status of the decision layer: **rule-based, UNVALIDATED, not backtested on real NAS100 data.**
It outputs no probability (`model_confidence` is always `None`). All tests use synthetic
fixtures (`tests/nas100_fixtures.py`); they prove the code matches the definitions below and
say nothing about profitability.

## Install / run

```
cd backend
py -m pip install pytest tzdata        # tzdata is required on Windows (no system tz database)
py -m pytest -q tests                  # existing gateway + NAS100 tests
```

## Usage

```python
from nas100 import candles_from_rates, analyze_multitimeframe, decide

candles = candles_from_rates(rates, server_tz="UTC")   # official MT5 Python API convention
mtf = analyze_multitimeframe(candles, base_minutes=5, htf_minutes=[60])
decision = decide(mtf.ltf, mtf.htf[60], now=datetime.now(timezone.utc))
```

Data acquisition is deliberately separate: the gateway fetches rates; this package only
converts and analyses them.

## Conventions (whole package)

* `Candle.time` = OPEN time, tz-aware UTC. A candle's information exists at its CLOSE.
* Every output carries the index at which it became knowable (`confirmed_index`,
  `detected_index`, event `index`). Nothing is stamped earlier than the data supports.
* `analyze` is pure: identical input gives an `==` identical result.
* Structurally invalid data raises `DataValidationError`; sparse data is *reported*
  (`DataQuality.gaps`, `Analysis.status`), never repaired or guessed.
* All defaults in `config.py` are unoptimised conventions. Tuning them against a backtest is
  parameter mining; do that only inside walk-forward validation (see `docs/ML_DESIGN.md`).

## Definitions

| Concept | Definition (module) |
|---|---|
| Swing high / low | Fractal: strictly higher (lower) than the `L` bars before and `R` bars after; equal prices are not pivots. Confirmed at `i+R`. (`swings.py`) |
| HH / HL / LH / LL | Label vs the previous confirmed swing of the same kind; `trend_from_swings`: bull = latest HH+HL, bear = LH+LL, else range. (`swings.py`) |
| BOS | Close beyond the most recent unbroken confirmed swing, in the direction of the current trend (first break from "no trend" is an initial BOS). (`structure.py`) |
| CHoCH | Close beyond the reference swing *against* the current trend; flips the trend. Close-based: a wick alone is not a break. (`structure.py`) |
| FVG | Bullish `low[i] > high[i-2]`, bearish `high[i] < low[i-2]`, size >= `fvg_min_atr`*ATR; fill status computed up to an explicit `as_of`. (`fvg.py`) |
| Liquidity sweep | Active confirmed swing level traded through by wick with the close back on the original side; a close beyond it is a break, not a sweep; one event per level. (`liquidity.py`) |
| ATR | Wilder, period 14, true range includes the previous close (price gaps counted). (`volatility.py`) |
| Volatility regime | Trailing-window percentile rank of ATR: LOW / NORMAL / HIGH; FLAT if ATR/close ~ 0; UNKNOWN without history. (`volatility.py`) |
| Consolidation | Window range <= 3.5 ATR **and** Kaufman efficiency ratio <= 0.30. (`volatility.py`) |
| Sessions | Local wall-clock windows via IANA zones (Tokyo, London, New York, NY cash, first hour of cash, London/NY overlap); never a fixed UTC offset. (`sessions.py`) |
| Multi-timeframe | Epoch-aligned resample emitting only closed buckets (>= `min_fill` of expected bars). (`timeframes.py`) |
| Decision | Checklist in `decision.py` docstring: data quality -> regime -> session -> HTF bias -> sweep -> shift -> open FVG -> geometry (stop, untouched-liquidity target, RR). NO TRADE is the default. |

Not implemented in Phase 1: order blocks, displacement scoring, session high/low ranges,
equal-highs/lows clustering, economic-calendar filter, premium/discount zones.

## Known limitations

1. **No real-data validation.** Nothing here has run on real USTECH100M history yet.
2. **Broker time.** Official API epochs are UTC and must not be shifted by an assumed
   server offset. Non-API wall-clock datasets require explicit `time_encoding="verified_wall_clock"`
   and the independently verified IANA zone. Conversion cannot attest broker clock accuracy.
3. **HTF alignment.** Resampled H4/D1 buckets align to UTC epoch multiples, not necessarily to
   the broker's own bars; verify before using H4+.
4. **Gap classification:** all missing spans remain unverified faults. Duration alone never
   establishes a session closure. Recent LTF and HTF gaps block decisions.
5. **Session windows are conventions**, and cash-index holidays/early closes are not modelled.
6. **O(n^2)-ish loops** (swing scans, sweeps) are fine for thousands of bars; vectorise
   before processing multi-year M1 history.
7. Stop/target/entry are *analytic suggestions on closed candles*, not executable orders:
   spread, slippage, broker stop-level and volume rules are not modelled here (that is the
   job of the risk layer, which this package does not replace or modify).

## Still to connect (not done in this change)

* **MT5:** a read-only collector in the gateway that calls `copy_rates_range` for
  USTECH100M and passes rows to `candles_from_rates`; plus `symbol_info` capture (digits,
  point, tick value, volume step/min/max, stops level).
* **Flask:** a new read-only endpoint (e.g. `/api/v4/nas100/analysis`) behind the existing
  bearer auth. Not added, to leave existing API contracts untouched.
* **Android:** a result schema/summary builder alongside `V4ApiContracts`, and UI that labels
  output "rule-based, unvalidated".
* **Supabase:** persistence of decisions/journal (the integration is not in the audited commit,
  so nothing was designed against it).
* **Risk engine:** feed `Decision.entry/stop` into the existing advisory risk calculation.
  The infrastructure formula is untouched.

## Integration corrections and next milestone (2026-11-05)

This archive was Phase 1 (82 original tests), not the corrected Phase 2 package
described in the handoff. Local integration adds 19 synthetic regression cases,
bringing these three original suites plus integration guards to 101 cases.
Future data, stale/non-higher HTF context, unknown configured spreads and recent
unverified gaps now fail closed. FVG formation must follow the structure shift.
Resampling validates source order/grid and requires full buckets by default.
Explicit wall-clock conversion rejects nonexistent DST times.

The new separate `../nas100_data_audit.py` CLI inspects existing raw CSV exports:

```powershell
python nas100_data_audit.py --input evidence/USTECH100M_M15.csv --timeframe M15
```

Its JSON reports hashes, intervals, malformed OHLC, duplicates and future/unclosed
bars against an observation time. It never normalizes timestamps, emits signals,
simulates trades or approves a dataset for research. A successful diagnostic exit
code is not research approval. Phase 2 simulator/exporter/research tests remain
pending receipt of the actual review archive.

Timestamp convention reference: https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrom_py
