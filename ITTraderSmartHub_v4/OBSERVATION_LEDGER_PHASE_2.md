# ITTrader SmartHub — Phase 2 research observation ledger

Date: 2026-11-04
Branch: `feature/mt5-observation-ledger-research-20261104`
Base: `feature/prop-compliance-loss-limits-20261104`

## Objective

Prepare a persistent, locally testable event history for future read-only MT5
account monitoring, **without claiming that an MT5 account is connected**.
This phase is deliberately independent of the running Gateway, Android, and
the five-field broker-profile registry.

## Delivered

- `backend/observation_ledger.py`: isolated SQLite event store for explicitly
  synthetic balance/equity observations.
- `backend/tests/test_observation_ledger.py`: 31 new parameterized local tests
  covering persistence across restart, atomic writes, ordering, data validation,
  session baselines, synthetic-only provenance, historical peak separation,
  append-only SQL triggers, and FTMO DST transitions.
- `backend/COMPLIANCE_ENGINE_PHASE_1.md` from the parent branch remains the
  authoritative documented scope for the compliance calculations.

## Trust and data correctness boundaries

1. `ObservationLedger` **requires an explicit local SQLite path**. It must
   never be constructed with `SMARTHUB_STATE_DB`, which belongs to the
   authentication/telemetry Gateway store. It does not read that environment
   variable and makes no changes to existing databases.
2. Its `append()` method **accepts only `DataOrigin.SYNTHETIC_TEST`**.
   Broker-labelled, unverified or other inputs are rejected with
   `BROKER_ADAPTER_NOT_IMPLEMENTED`. No HTTP endpoint calls this class.
3. No MT5 terminal is initialized. There are no trade-execution APIs.
4. The account key is a restricted local **alias**, not a stored login number,
   broker secret or a claim of authenticated account identity.
5. Financial values use `Decimal`, UTC observations and separate server offset
   fields. A transaction rejects duplicate or backwards observation times,
   mid-session starting balance changes and account-model changes.
6. `END_OF_DAY_BALANCE` and `CLOSED_BALANCE` are separate event types.
   Their observed maxima are not interchangeable, do not prove a complete
   history and do not yet assert a broker-defined certified high-water mark.
7. The SQLite table has UPDATE/DELETE rejection triggers, but this is a logical
   append-only mechanism and **not tamper-proof**: a process with direct file
   access could change or replace the database. Full security/audit attestation
   remains future work.
8. All summaries set `live_verified=False`, `history_complete=False` and
   `execution_authorized=False`. This phase does **not** call
   `evaluate_compliance()` to report a real connected account as compliant.

## Validation performed

The new module and 31 tests passed Python 3.13 compilation and local isolated
pytest runs using a **test-only compatibility stub for the compliance-engine
enums and rule offsets**, not the actual Windows Gateway environment.
The source was committed to the feature branch; the **full 354+ Windows Gateway
suite and Android build remain to be run** on the user's checkout.

No live MT5 trading, broker connection, user-account observation or phone data
was accessed during those isolated tests.

## Future work (must be separately reviewed)

1. Read-only broker identity binding and actual MT5 `account_info`,
   `symbol_info`, deals and live equity collection.
2. Robust broker date/time reset attestation; classify gaps and restarts,
   detect missed peaks and derive trustworthy EOD and closed-balance maxima.
3. Add a **separate authenticated internal ingestion adapter**, not an Android
   JSON endpoint that accepts account peaks or fake origin flags.
4. Secure local storage, OS permissions, trusted-history integrity checks,
   retention and privacy safeguards.
5. Only after verification, expose read-only compliance summaries. Unknown
   status is mandatory on missing data. No order placement.
6. Revalidate exact provider/account-model terms, including any product changes,
   before using a risk result for real-money decisions.

## Windows verification

From `ITTraderSmartHub_v4/backend`, after checking out this branch:

```powershell
$python = ".\.venv-gateway\Scripts\python.exe"
& $python -m py_compile observation_ledger.py compliance_engine.py risk_engine.py
if ($LASTEXITCODE -ne 0) { throw "Compilation failed" }
& $python -m pytest -q tests/test_observation_ledger.py
if ($LASTEXITCODE -ne 0) { throw "Observation ledger tests failed" }
& $python -m pytest -q tests
if ($LASTEXITCODE -ne 0) { throw "Gateway tests failed" }
```

Do not restart the existing Gateway or install a new APK for a research-only
Python module. The running application remains on its previous release.
