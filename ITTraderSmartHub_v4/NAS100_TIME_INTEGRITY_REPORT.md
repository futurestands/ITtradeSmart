# NAS100 time integrity — bounded milestone

Date: 2026-11-02. **TIMEBASE_UNVERIFIED. Research eligibility remains blocked.**

## Backcheck and scope

Started from clean `fix/v5-trustworthy-backtest-phase1` at `2b9823ed3832e475ae76a49d81b893421beb4116`. Fetched origin without merging; no incoming branch commits. Read Issue #1 and independent audit comment [6574439198](https://github.com/futurestands/ITtradeSmart/issues/1#issuecomment-6574439198) before implementation. Baseline regression: **71 passed**. No Android source, broker settings, Windows clock/timezone, trading credentials or execution policy changed.

All 16 original evidence files, including six original index CSV captures and the original reports/hashes, are preserved byte-for-byte. New captures/analysis/eligibility records are under `backend/evidence/time_integrity/`. Original evidence's `time_utc` heading is historical, **not a validated timebase**; the new eligibility sidecar supersedes any inference of research eligibility from its structural-check results.

## Findings: what is established and what is not

| Question | Evidence / verdict |
|---|---|
| Is Windows two hours wrong? | **No such error observed.** Two independent NTP providers agree Windows is about 0.72–0.73 seconds slow, corroborated by HTTPS Date. A current clock comparison cannot prove the host's historical clock state at the old capture. |
| Does local timezone explain Python conversion? | Windows reports E. Africa Standard Time, UTC+03:00. Explicit `datetime.fromtimestamp(raw, timezone.utc)` preserves the input epoch; it does not apply Nairobi time or automatically discover broker DST. |
| What do fresh broker timestamps show? | Subsequent live USTECH100M/USTEC/EURUSD ticks have raw epoch labels about +7,200 seconds versus Windows. The current data path behaves like a UTC+02:00 wall-clock representation. This is empirical current-date behavior, not a verified multi-year timezone rule. |
| Are bars and ticks on unrelated clocks? | Fresh closed M15 OHLC reconciles exactly with 3,752 historical Bid ticks in the same raw interval. Complete overlapping M15/M30/H1/H4 price windows match at zero relative offset. |
| Why did the first fresh bar tail look only one hour ahead? | The first capture had an older tail, advancing by about one hour in the subsequent capture. Overlapping completed bars retained identical OHLC and raw labels. This is evidence of an older history snapshot, consistent with stale/cache synchronization, **not proof of a separate +1-hour bar timezone**. Exact terminal cache lifecycle was not observed. |
| Is a universal subtraction of 7,200 seconds justified? | **No.** Historical broker timezone/DST rules and the exact server/terminal/API component responsible are not independently established. A shared raw-time offset is invisible to cross-timeframe price matching. No normalized research dataset was released. |

**Confirmed pipeline defect:** raw broker timestamps were promoted to fields named UTC without checking the live timebase against independent UTC, without per-call observation brackets, and without asserting closed-bar availability. The original probe's observation field was its start time, not the instant every quote or dataset was retrieved. The old ~2h01m26s difference therefore includes unknown capture latency; its extra 86 seconds must not be called clock drift.

**Upstream root cause limit:** current observations strongly support a broker/feed-path UTC+2 representation. They do not distinguish broker-server convention from terminal/library/feed transformation or establish a historical DST schedule. The appropriate outcome is quarantine and fail-closed eligibility, rather than an invented timezone correction.

## Independent UTC clock evidence

`capture_clock_reference.py` performs read-only requests. It validates NTP mode, leap state, stratum, response length, request-origin echo, server receive/transmit order, network round trip and host wall-clock versus monotonic progression. Raw request transmit bytes, full NTP response hex and four observation timestamps are saved. It never synchronizes Windows.

| Capture | Provider | Server minus Windows | NTP round trip |
|---|---|---:|---:|
| 10:16:58 UTC | time.cloudflare.com | +0.717462 s | 0.025071 s |
| 10:16:58 UTC | time.google.com | +0.719489 s | 0.147022 s |
| 10:32:14 UTC | time.cloudflare.com | +0.732571 s | 0.024662 s |
| 10:32:14 UTC | time.google.com | +0.733447 s | 0.148093 s |

HTTPS Date from both providers corroborated the first measurement at seconds resolution. Google's second HTTPS request succeeded; Cloudflare's second HTTPS TLS handshake timed out, retained as FAILED rather than discarded. UDP NTP here is unauthenticated, not NTS; independent providers and HTTPS support the seconds-scale conclusion, not sub-millisecond accuracy or historical broker DST. Google smears leap seconds and Cloudflare does not; no system NTP configuration was changed or mixed.

`w32tm /query /status` and `/query /source` reported service-not-started (`0x80070426`). Windows timezone was queried read-only; no clock/service repair was attempted. The separate tool clock also agreed at seconds scale, but network measurements are the independent comparison used above.

## Fresh MT5 captures and timestamp hypotheses

Three bounded captures started at 10:15:49, 10:20:17 and 10:25:14 UTC. All MT5 calls have Windows UTC before/after and monotonic duration. Account DEMO status and identity consistency were checked in memory without recording login/server identity. No login, symbol selection, orders, account mutation or terminal setting change occurred.

The later captures show terminal connected=true, trade_allowed=false, build=6296; Python package=5.0.6231. Quotes progressed across later observations, unlike the first capture's repeated cached quote. USTECH100M, USTEC and EURUSD all exhibit the approximate +2-hour raw quote labeling, so this is not isolated to a single NAS100 candle conversion.

| Sample | Raw integer / displayed epoch label | Observation | Hypothetical minus 7,200 s |
|---|---|---|---|
| Original quote | 1793616499 / 10:48:19Z | Probe **started** 08:46:53Z; exact quote read time unavailable | 08:48:19Z |
| Original M15 last bar | Old CSV label 10:30Z | Per-call bracket unavailable | 08:30Z open |
| Original M30 last bar | Old CSV label 10:00Z | Per-call bracket unavailable | 08:00Z open |
| Fresh USTECH100M quote | 1793622316128 ms / 12:25:16.128Z | 10:25:16.108375–10:25:16.108530Z | 10:25:16.128Z |
| Fresh closed M15 | 1793620800 / 12:00Z open | Retrieved during third capture around 10:25Z | 10:00Z open, 10:15Z close |
| Fresh terminal position-zero M15 | Raw label 12:15Z open | Same capture | 10:15Z open, 10:30Z close: **still forming** |

These are **diagnostic hypotheses**, not original-versus-approved normalized data. `analysis.json` tests subtraction of 0, 3,600, 7,200 and 10,800 seconds for quote age and bar-open/close scenarios. At 10:25:16.108Z, the USTECH100M raw quote is 7,200.0195 seconds ahead of Windows. Subtraction of 7,200 leaves a quote roughly 0.02 seconds ahead of the slow local clock, compatible with the independently measured ~0.72-second local lag and normal quote age. The other tested offsets leave roughly one-hour errors.

At the first capture, M15 position zero was labeled 11:15Z; later it was 12:15Z. The first/second capture share **251 M15, 125 M30, 62 H1 and 14 H4 completed bars**, all with unchanged OHLC at identical raw timestamps. The second/third share 255/127/63/15, also unchanged. No timezone relabeling between these captures was observed. This highlights that terminal position alone is insufficient evidence of current, synchronized history.

For the third capture's closed M15 `[1793620800, 1793621700)`:

- 3,752 historical ticks in the same raw interval give Bid OHLC **28664.7 / 28675.3 / 28647.3 / 28666.5**, exactly matching the bar.
- The interval shifted +3,600 seconds returned zero ticks. That empty response is not by itself proof of an offset, but the unshifted exact OHLC match establishes raw tick/bar interval consistency for this sample.
- The interval uses bar **open**, not close, timestamps. Historical range filtering is half-open to avoid including the next bar's first tick.

## Timeframe alignment results

The analyzer reconstructs OHLC from exact lower-timeframe slots and compares identical price movements with higher bars. It tests relative lower-frame offsets −7,200, −3,600, 0, +3,600, +7,200 seconds. Windows outside joint acquisition coverage are counted separately; interior missing slots are **not filled or silently excluded**. Fresh terminal position zero is excluded in every timeframe. Results do not establish absolute UTC or session-gap validity.

| Original capture comparison, zero relative offset | Complete windows / exact OHLC matches | Windows missing lower slots |
|---|---:|---:|
| M15 → M30 | 2,496 / 2,496 | 7 |
| M15 → H1 | 1,245 / 1,245 | 9 |
| M15 → H4 | 267 / 267 | 60 |
| M30 → H1 | 2,493 / 2,493 | 13 |
| H1 → H4 | 1,090 / 1,090 | 218 |

For **each** fresh capture after position-zero exclusion: 124 M15→M30, 60 M15→H1, 10 M15→H4, 60 M30→H1 and 11 H1→H4 complete windows match exactly at zero relative offset. Missing-window counts are 3/3/5/3/4 respectively. Most tested nonzero offsets yield zero matches; one original shifted H1→H4 window matches by coincidence. No offset is selected by optimization, and a shared offset cannot be resolved this way.

**Verdict:** relative price alignment VERIFIED for complete windows. Full synchronized coverage is INCOMPLETE; missing slots need broker session/calendar evidence. Absolute UTC and historical DST remain TIMEBASE_UNVERIFIED. A strict research alignment check rejects incomplete coverage, even when every available complete window matches.

## Minimal code corrections

- `bot/time_integrity.py`: explicit UTC timebase evidence, reference-clock uncertainty, timeframe and grid origin; rejects future or not-yet-closed bars, naive/non-UTC/ambiguous labels, off-grid opens, duplicate/unordered bars and unexplained missing intervals. Verified gaps require exact intervals. H4 may need a non-midnight UTC grid after a future verified normalization; zero UTC phase is not universally presumed.
- `BacktestEngine` now requires explicit verified timebase context before replay. `MarketDataManager` requires it before returning/caching broker or SQLite candles and checks timeframe identity. A time failure propagates; it cannot be masked by fallback to older cache. No live broker timebase context is issued by this milestone.
- Numerical tests supply clearly labeled MOCK contexts for synthetic data; those are not broker time certification. The context is a trusted caller assertion, not a cryptographic broker attestation or a completed dataset approval service.
- Quote freshness recheck rejects both stale and future timestamps, closing the old negative-age bypass. Structural-only quote authentication remains an outstanding architecture issue.
- Discovery now writes to unique directories, preserves raw integer times and labels epoch rendering UNVERIFIED; never exports those renderings as confirmed `time_utc`. Per-call observation brackets and explicit TIMEBASE_UNVERIFIED/research_eligible=false are included. It no longer overwrites original captures.
- The evidence verifier still verifies bytes/structure, but explicitly returns research_eligible=false and TIMEBASE_UNVERIFIED and writes its new report under the new milestone directory. Sidecar `dataset_eligibility.json` quarantines every original index CSV by its unchanged SHA-256, including the already excluded partial M5.
- No historical CSV was shifted, renamed, overwritten or rehashed to hide a change. Diagnostic offsets produce no normalized trading dataset.

## Instrument suitability and other outstanding failures

Fresh `symbol_info` confirms **USTECH100M and USTEC remain trade_mode=0/DISABLED**. USTEC now has a quote, unlike the earlier no-quote snapshot; that does not change its disabled trade mode.

| Specification | USTECH100M | USTEC |
|---|---|---|
| Description | USTECH100mini | US Tech 100 Index |
| Contract size | 1 | 1 |
| Point / tick size | 0.1 / 0.1 | 0.01 / 0.01 |
| Profit/loss tick value, USD per lot | 0.1 / 0.1 | 0.01 / 0.01 |
| Volume min / max / step | 1 / 220 / 1 | 0.1 / 250 / 0.1 |
| Calculation / chart mode | CFD (2) / Bid (0) | CFD (2) / Bid (0) |
| Profit / margin currency | USD / USD | USD / USD |

A comparable authorized DEMO connection must identify the exact Nasdaq-100 exposure (cash/mini CFD versus futures, no ETF substitution), allow the intended BUY/SELL operations on a DEMO account, and provide authoritative point/tick/contract economics, account-currency calculation, volume/stops/margin rules, spread/commission/financing, sessions/holidays, and dated server timezone/DST conventions. Capture current ticks and complete historical bars under a verified timebase before research. Current disabled symbols are not a suitable execution eligibility demonstration. No broker account was changed or trading enabled to test this.

Isolated diagnostics again reproduce:

- PAPER: `AttributeError: 'MarketDataManager' object has no attribute 'last_price'`. Source still references absent `is_data_fresh`, hardcodes BTCUSD/equity baselines and misbinds RiskGuardian positional parameters. Real broker free margin is not supplied; later parameter bindings are also wrong. No full PAPER cycle is claimed.
- `/analyze`: authenticated local Flask test request raises `NameError: name 'key' is not defined` in `any(key in body for k in (...))`. It fails before broker credential handling/MT5 calls. Preserved and documented, not expanded into an unrelated integration refactor.

## Validation and safety

- Full final Python regression: **99 passed**, including 28 new time-integrity cases beyond the 71-test baseline. Actual command/output: `backend/evidence/time_integrity/pytest_time_integrity.txt`.
- Tests cover future/partial M15/M30/H1/H4 bars, clock uncertainty at close, naive DST-ambiguous labels, explicit H4 phase, unexplained gaps, duplicate/noninteger timestamps, relative price mismatch, incomplete aggregation, common-offset ambiguity, engine/loader default blocks, cache-bypass prevention and future stored quotes. Existing accounting and forced-enabled execution-lock tests remain passing.
- Real network/MT5 observations are VERIFIED execution evidence; timebase-context unit tests are MOCK-TESTED. Structural verification is not market-time approval.
- Original evidence byte hashes verified before/after; all 16 prior evidence files remain unchanged. Git shows zero Android project or execution-adapter diffs against the starting commit. No Android JVM/device/release suite rerun was needed for unchanged Android sources; the prior milestone's eight JVM tests are historical evidence only.
- `final_checks.json` distinguishes local bytes from Git's pre-existing LF/CRLF handling of text artifacts. All six index CSVs match starting-commit blobs byte-for-byte; other evidence is unchanged locally and canonically identical to Git after line-ending comparison. Neither original content nor original hash records were rewritten.
- No Python `order_send` call sites. Unconditional execution adapter interlock unchanged; valid admin/forced-enabled rejection remains tested. No order submission, no DEMO enablement, no paid dependency, no main merge.

## Next safest milestone

Obtain an owner-authorized comparable DEMO broker's **dated server-time/DST policy** or independent timestamped quote/tick evidence across both seasonal regimes, confirm symbol permissions and session calendars, and reconcile absolute UTC before releasing derived data. Any eventual normalization must preserve raw epochs, produce separate versioned derived datasets with date-dependent mappings and lineage, and validate closed bars and H4 grid phases. Then complete synchronized data capture and repair serialized broker/PAPER/controller integration. Strategy optimization, profitability evaluation and funded readiness remain blocked. Stop this milestone here.

Primary references: [MT5 Python bar UTC contract](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrom_py), [MT5 tick-range API](https://www.mql5.com/en/docs/python_metatrader5/mt5copyticksrange_py), [server-origin TimeCurrent](https://www.mql5.com/en/docs/dateandtime/timecurrent), [local-computed TimeGMT](https://www.mql5.com/en/docs/dateandtime/timegmt), [Cloudflare NTP](https://developers.cloudflare.com/time-services/ntp/), [Google Public NTP](https://developers.google.com/time). These docs describe expected interfaces; actual broker time behavior above is established only by the saved observations.
