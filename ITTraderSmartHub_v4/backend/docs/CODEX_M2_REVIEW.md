# Codex M2 local review candidate

Based on WorkBuddy SmartHub `8998f0f30abc7f814fb935e458e9c04c2a6a56a0`.
Not pushed, merged, deployed or independently approved.

## Terminal identity

The existing exact resolved executable path check remains. If PowerShell image
metadata is empty/unavailable, Windows Toolhelp inventory plus
`QueryFullProcessImageNameW` with `PROCESS_QUERY_LIMITED_INFORMATION` can supply
the full executable path. Unknown or duplicate native candidates fail closed.
No command lines, process memory or credentials are read. This identifies an
image, not a verified account or data timebase; all existing SDK identity and
permission gates remain mandatory. The existing precheck/SDK-attachment race is
not an atomic process binding and remains a limitation.

## Synthetic research API prototype

`GET /api/v5/nas100/research-preview` uses existing device-scope authentication.
It returns 503 unless `SMARTHUB_SYNTHETIC_PREVIEW_ENABLED=1` is explicitly set in
a local test gateway. Do not enable it in the running gateway without deployment
review. Query parameters and request bodies are rejected. It consumes only a
fixed 96-bar integer synthetic fixture and invokes the existing pure NAS100 rule
engine. It returns rule counts/trend/session state, fixture hash/as-of, reasons,
invalidation, `NO_TRADE`, null probability and `MODEL_NOT_READY`.

This is an API contract demonstration, not a real symbol quote or prediction.
No exporter, broker SDK, file loader, estimator or AI Lab call is reachable from
the handler. Existing Android screens do not call this route. There are no
Android, signing, database, Supabase, risk-engine or execution-interlock changes.

## Validation

Windows gateway Python 3.14.6, pytest 9.2.0: **675 passed, 2 skipped**.
Skipped tests require filesystem symlink privileges. New regressions cover exact
native identity, other-path rejection, missing/ambiguous metadata, authentication,
default-off behavior, deterministic synthetic output and input rejection.

Independent reviewer must assess the native API/handle lifecycle and route
contract before integrating these local changes. No market-edge claim follows
from passing software tests.
