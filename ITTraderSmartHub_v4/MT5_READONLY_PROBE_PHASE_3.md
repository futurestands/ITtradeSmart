# SmartHub Phase 3A — guarded MT5 read-only account inspection

Date: 2026-11-04. Branch: `feature/mt5-readonly-inspection-20261104`. Base: `feature/mt5-observation-ledger-research-20261104`.

## Objective

Prepare an isolated, *read-only account inspector* for the existing Windows
MetaTrader 5 terminal, while preserving the already verified SQLite research
ledger and loss-limit engine. This is an inspection library, **not** an
automatic terminal connector or a live data pipeline.

Files: `backend/mt5_readonly_probe.py` and
`backend/tests/test_mt5_readonly_probe.py`.

## Safety boundaries

- **No `MetaTrader5` import at module import time**, no `initialize()`,
  `login()`, `shutdown()`, `order_send()`, filesystem writes, network
  access, Flask routes, Android/API changes, trading-mode changes, credentials,
  SQLite writes or edits to the existing five-field broker profiles.
- `inspect_attached_terminal(api, ...)` accepts a separately prepared local
  API object that is already connected by the **operator**, not an Android
  request. Tests use fully mocked API objects.
- A trade-enabled account (`account_info().trade_allowed != False`) or
  trade-enabled terminal (`terminal_info().trade_allowed != False`) is
  rejected. It also requires `connected == True`, exact expected account
  number and server match, and USD account currency.
- These flags are **necessary safety conditions**, not cryptographic proof
  of the investor password. Actual MT5 access must be established by the
  operator with investor-only credentials in the MetaTrader terminal; do not
  use a master-login terminal for this inspection. The library **does not
  attempt to log in or switch accounts**.
- Financial data are read with `account_info` and the exact broker instrument
  from `symbol_info`. The result reports balance, equity, floating P/L,
  tick size, **loss-side tick value**, contract size, broker min/max/lot step.
  It does not guess US100 alias mappings or pip/point definitions.
- Account identity and trading-disabled conditions are checked once before
  and again after symbol inspection. Account numbers and server details
  are not included in the result.
- The result **always** remains `origin=LOCAL_MT5_READ_UNATTESTED`,
  `live_verified=False`, `history_complete=False`,
  `clock_verified=False`, `broker_rules_verified=False`,
  `execution_authorized=False`. Even a real locally observed session does
  not prove correct historical peaks, UTC reset times or complete brokerage
  terms.
- This module is deliberately **not integrated** into
  `observation_ledger`, `compliance_engine`, `risk_engine`, `app.py` or
  Android. In particular, it cannot by itself override those modules' strict
  `BROKER_ADAPTER_NOT_IMPLEMENTED` gating.

## Upstream official API references

- Investor vs master terminal accounts: https://www.metatrader5.com/en/terminal/help/startworking/authorization
- MT5 `account_info` and `trade_allowed`: https://www.mql5.com/en/docs/python_metatrader5/mt5accountinfo_py
- MT5 terminal flags: https://www.mql5.com/en/docs/python_metatrader5/mt5terminalinfo_py
- Loss-side tick value, tick size and lots: https://www.mql5.com/en/docs/python_metatrader5/mt5symbolinfo_py

**Important:** Official `initialize()` may start a terminal using saved login
details, including a trading-capable master account. The inspector does not
invoke `initialize()`; that operator-controlled setup is out of scope and
requires a separate security review.

## Verification

Local sandbox Python 3.13:

```
python -m py_compile mt5_readonly_probe.py tests/test_mt5_readonly_probe.py
python -m pytest -q tests/test_mt5_readonly_probe.py
31 passed
```

Mocked tests covered missing/invalid account and server, connected/trading
flags, exact symbol, unsafe tick values and lot volumes, invalid balances,
non-UTC timestamps, session switching mid-read, and explicit proof that
`initialize`, `login`, `order_send`, `shutdown` are not called.

**Pending:** Complete Windows Gateway tests on this branch; actual logged-in
investor-only terminal observation; Android build (no Android files changed).
No actual broker account was accessed or credentials collected.

## Safe Windows test commands

```powershell
Set-Location "C:\Users\MJ\Documents\ITtradeSmart-NAS100-Integration\ITTraderSmartHub_v4\backend"
$python = ".\.venv-gateway\Scripts\python.exe"
& $python -m py_compile mt5_readonly_probe.py
if ($LASTEXITCODE -ne 0) { throw "Syntax check failed" }
& $python -m pytest -q tests/test_mt5_readonly_probe.py
if ($LASTEXITCODE -ne 0) { throw "MT5 inspection tests failed" }
& $python -m pytest -q tests
if ($LASTEXITCODE -ne 0) { throw "Gateway tests failed" }
```

Never run a live MT5 probe until the intended investor-only account and exact
terminal symbol have been independently confirmed on the Windows host. The
safe default is no live inspection and no new permissions.
