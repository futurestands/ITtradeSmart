# NAS100 eligibility and timebase blocker review

## Current MT5 evidence

The guarded existing diagnostic was executed from the isolated backend using the
existing gateway Python SDK. Native Windows inventory found one terminal image,
zero unreadable candidates and one exact match to the intended existing binary.
The limited-query fallback does not start/stop processes or read memory,
command-line arguments, credentials or account identifiers.

| Required diagnostic | Observed |
|---|---|
| terminal_connected | true |
| demo_account | true |
| account_trading_disabled | true |
| account_expert_disabled | false — BLOCKED |
| terminal_trading_disabled | false — BLOCKED |

Result: `BLOCKED / REQUIRED_FLAG_NOT_DISABLED`. No historical export or live UTC
witness collection was attempted after these failed gates. No account was
switched, logged into, or identified in outputs; permissions were not modified.
No new historical data, genuine research signals or performance statistics are
reported. Account read-only permission is observed; investor-login provenance is
not inferred solely from that flag.

The native path fallback uses `QueryFullProcessImageNameW` with
`PROCESS_QUERY_LIMITED_INFORMATION`, as documented by
[Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew).
Matching a path is not account identity certification, nor an atomic binding of
SDK attachment to a process. Existing identity continuity and permission checks
remain unchanged. Unknown/duplicate native candidates fail closed.

Owner/operator requirement: supply an already-open authorized demo session for
which all five existing checks pass, and rerun the diagnostic before export.
Terminal algorithmic-trading controls and account expert authorization are
different fields; a UI switch must not be assumed to change server/account
permissions. Seek provider clarification if account expert permission cannot be
disabled. Do not relax checks or substitute trading-enabled credentials.

## Immutable historical reproduction

Analyzed the existing tracked 5,000-row USTECH100M H1 capture offline. The file's
SHA-256 before and after was
`35007b45ad6e62dfde7ae8b5e91cee7351cdfb93225de64e0bb42fd876b3b71d`.
Raw labels/epochs were not changed and no corrected dataset was created.

Method: weekdays only, group high-low by raw-label hour; divide each hourly mean
by the regime-wide median candle range. Partial days remain in the sample.

| Raw-label date regime | Observed days | Bars | Peak hour | Normalized peak |
|---|---:|---:|---:|---:|
| 2025-12-02–2026-03-06 | 66 | 1497 | 16 | 3.3202 |
| 2026-03-09–2026-03-27 | 13 | 272 | 15 | 2.1476 |
| 2026-03-30–2026-10-23 | 139 | 3140 | 16 | 2.5179 |
| 2026-10-26–2026-10-30 | 4 | 82 | 15 | 2.2221 |

These reproduce the reported 16/15/16/15 pattern. It is consistent with the
EU-DST broker-clock hypothesis relative to US cash-open activity. Activity peaks
are not independent clock anchors; missing days, regime changes and the small
autumn sample prevent certification. Gaps remain unclassified rather than
automatically called market closures. Full hourly aggregates and method are in
`M2_DST_REPRODUCTION.json`; the reproduction script is included in the package.

## Documentation and contradiction

[MetaQuotes Python API documentation](https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesfrom_py)
states that returned bar data uses UTC. That general convention does not resolve
the contradictory observed labels in this dataset.

A [2015 MetaQuotes-site discussion](https://www.mql5.com/en/forum/63796)
describes winter +2/summer +3 chart/server behavior, but is not a dated 2026
historical numeric-epoch specification. Other community replies assert a
[US-style DST rule](https://www.mql5.com/en/forum/516135), which conflicts with
the EU-rule inference from this capture. These discussions are corroborating or
contradictory claims, not accepted provider certification. No sufficient current
authoritative policy mapping this exact feed's historical epochs was found.

## Software handling and observation preparation

SmartHub candle adapters produce aware UTC objects from numeric epochs. Session
classification uses IANA zones; resampling uses epoch-aligned UTC buckets, closed
bars and full fill by default. Correct conversion mechanics do not prove that
the input numeric epoch represents genuine UTC. Broker H4/D1 alignment may differ.
The Lab retains quarantine/timebase provenance, uses normalized naive broker
labels for heuristic DST investigation, and keeps promotion blocked.

Added a pure offline UTC witness assessment contract with six synthetic tests:
positive +2/+3 hour contradictions, a consistent sample, stale source labels,
clock-step rejection and naive-clock rejection. UTC wall-clock brackets must be
short and agree with monotonic elapsed time. Raw epochs and offset intervals are
preserved. Even a matching sample remains `TIMEBASE_UNVERIFIED` and ineligible.
This complements the existing evidence system; it does not replace its records
or its blocked promotion path. No real witness was collected this turn.

## Eligibility decision

**BLOCKED:** timebase unverified; export gates fail; historical contract economics
and costs not certified. There is no accepted real training dataset. No synthetic
or integrity manifest can override these conditions. No real-market estimator
was trained or independently evaluated.

Next evidence must include synchronized independent UTC observations, fresh quote
proof with raw epoch/time_msc and UTC/monotonic brackets, exact provider/build/date
scope, DST-boundary coverage, market closure records, licensing and historical
contract/spread/commission/currency economics. Freeze raw hashes; create separately
versioned derived data only after external review of a documented mapping.
