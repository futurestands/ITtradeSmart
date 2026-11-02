# Phase 1: advisory-only AI Lab connection

## Scope and starting state

Repository: `futurestands/ITtradeSmart`, branch `fix/v5-trustworthy-backtest-phase1`.
The clean, synchronized starting commit was `539b5482507072580c0110c92b776be9005b13e0`,
which already included the API/PAPER safety milestone after the requested older
`d9cedaa`. That work was preserved. Issue #1 and the prior handover/time-integrity
report were reviewed. Baseline Gateway regression: **178 passed**.
Only one editing agent was active; no project-referencing concurrent writer was found.

The existing Lab at `C:\Users\MJ\Documents\NAS100-AI-Lab-Phase1B` has no Git metadata.
Its integration contract, original v1 schemas, packaged schemas and installed validator
were inspected. No Lab source, dependencies, data or reports were changed. Its 41
original files retain their hashes. The companion service lives in this SmartHub
repository and runs using the Lab's existing **Python 3.12.10** environment. The
Gateway runs in its own **Python 3.14.6** environment; dependencies are isolated.

## Connection and safety boundary

```text
Android (existing enrolled device token)
  -> existing HTTPS Gateway deployment
     GET /api/v5/ai/status
     POST /api/v5/ai/advisory (read-only protocol query)
       -> authenticated http://127.0.0.1:8765 companion, separate server-side secret
          existing Lab validator + pinned contracts; NO model
```

The companion always returns `UNAVAILABLE`, `probability: null`, `model: null`
and `MODEL_NOT_READY`. A successful connection means the transport and contract
work, not that an AI model exists. `UNAVAILABLE_NO_REGISTERED_TARGET` is an explicit
sentinel because there is no registered prediction target. No target, price,
feature certification, trained model, trading edge or readiness is invented.

The Lab's **actual** request and response v1 schemas are byte-exact snapshots in
`backend/ai_contracts/`, pinned by SHA-256 in `source_manifest.json`. Startup verifies
both original and installed packaged Lab schemas, validator location and Lab version
0.1.1. `health_response.v1.schema.json` is a new, additive transport contract;
the existing prediction schemas were not changed. The companion uses the real
Lab validator as well as Gateway-side validation.

The service binds only literal `127.0.0.1`, checks peer and Host, rejects browser
Origin headers, requires a separate random bearer secret, suppresses request logging,
limits JSON bodies to 16 KiB and concurrent handlers to eight, and times out idle
sockets. It has no public-host option. Gateway requests use direct loopback sockets,
no proxies or redirects, a maximum response size, and a two-second total exchange
deadline. Invalid schema/version, hashes, nonfinite numbers, duplicate keys,
calendar timestamps, future feature timestamps, unknown fields or mismatched
request identity fail closed. Phase 1 also rejects otherwise-schema-valid `OK`
predictions: there is no approved model. Upstream explanatory text is never relayed;
the Gateway constructs fixed refusal messages.

Gateway routes reuse existing monitoring-device/master authorization and leave admin
controls intact. Missing credentials return 401. Invalid requests return 400 (oversize
413). Valid advisory requests receive a contract-compliant unavailable result even
when the service is offline; HTTP 200 alone does not imply a usable model. Status
separately reports connection availability, model readiness and research locks.
The Android section requests only Gateway status, never Lab credentials or its port.
The Gateway URL validator now parses host names exactly, closing the prior
`http://localhost.evil` prefix exception. Existing modules, branding and package remain.

No AI component imports or calls strategies, RiskGuardian, sizing or execution.
No AI route changes bot mode. Existing PAPER refusal and unconditional MT5 DEMO/live
execution locks are unchanged. Source inspection finds **zero `order_send` call sites**.
All 35 prior evidence files retain their hashes. NAS100 datasets remain
`TIMEBASE_UNVERIFIED`; no CSV was normalized, no model trained and no broker call made.

## Local setup and start (PowerShell)

These commands run the companion and Gateway on Windows loopback only. They do not
publish a service or configure Android TLS/network routing. Keep the existing secure
Gateway deployment and pairing workflow for phone access; never forward port 8765.
The Flask development runner below is for local verification.

```powershell
$taskRoot = 'C:\Users\MJ\Downloads\ITTraderSmartHub_v4_reviewed_patch'
$backend = Join-Path $taskRoot 'ITTraderSmartHub_v4\backend'
$labRoot = 'C:\Users\MJ\Documents\NAS100-AI-Lab-Phase1B'
Set-Location $backend

# Create only the Gateway environment if it does not exist. Do not replace the Lab venv.
if (-not (Test-Path '.venv-gateway\Scripts\python.exe')) {
    py -3.14 -m venv .venv-gateway
}
& .\.venv-gateway\Scripts\python.exe -m pip install -r requirements-gateway.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Gateway dependency setup failed' }

# Assign secrets to the environment without printing them or putting them in Android.
# Keep an already configured master token; the Lab token must always be independent.
if (-not $env:SMARTHUB_API_TOKEN) {
    $env:SMARTHUB_API_TOKEN = & .\.venv-gateway\Scripts\python.exe -c 'import secrets; print(secrets.token_urlsafe(48))'
}
$env:SMARTHUB_AI_LAB_TOKEN = & .\.venv-gateway\Scripts\python.exe -c 'import secrets; print(secrets.token_urlsafe(48))'
$env:SMARTHUB_AI_LAB_URL = 'http://127.0.0.1:8765'
$env:PYTHONDONTWRITEBYTECODE = '1'
New-Item -ItemType Directory -Force .integration-tmp | Out-Null

# This process inherits the same independent secret; only its owned handle is stopped.
$labProcess = Start-Process -FilePath "$labRoot\.venv\Scripts\python.exe" `
    -ArgumentList @('-u', "`"$backend\ai_lab_service.py`"", '--lab-root', "`"$labRoot`"", '--port', '8765') `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput "$backend\.integration-tmp\lab.out.txt" `
    -RedirectStandardError "$backend\.integration-tmp\lab.err.txt"
try {
    & .\.venv-gateway\Scripts\python.exe app.py
} finally {
    if (-not $labProcess.HasExited) { Stop-Process -InputObject $labProcess }
}
```

Gateway listens at `127.0.0.1:5000`; companion at `127.0.0.1:8765`. Existing occupants
are not stopped or replaced; choose another Lab port and matching URL if necessary.
The Lab environment must already contain its editable `nas100lab` package and
`jsonschema`; no installation into that environment is needed here. The Gateway
lock file captures this tested Windows environment, including test dependencies.
MT5 is optional in that fresh Gateway environment; broker functionality is not
established by this AI integration.

For an automated, ephemeral, actual two-process connection check (from backend):

```powershell
& .\.venv-gateway\Scripts\python.exe verify_ai_connection.py --lab-root $labRoot
```

It starts only owned processes on free loopback ports, generates ephemeral secrets,
enrolls a device using existing pairing, exercises both services and stops both.
It writes sanitized evidence under `evidence/ai_lab_integration/`. Synthetic
`EXAMPLE_NOT_MARKET_DATA` protocol input contains no price/features; it is not an
eligible research candidate. No credentials or account identifiers are recorded.

## Verification evidence

| Check | Actual result | Evidence |
|---|---|---|
| Full Gateway Python regression | **219 passed** (178 existing + 41 new cases) | `backend/evidence/ai_lab_integration/gateway_pytest.txt` |
| Existing Lab regression, Python 3.12.10 | **165 passed**, 28 pre-existing pandas warnings | `lab_pytest.txt` |
| Actual Gateway 3.14.6 -> companion 3.12.10 -> installed Lab validator | **VERIFIED** connected; MODEL_NOT_READY, probability null | `real_connection.json`, `lab_service.txt`, `gateway_service.txt` |
| Unauthenticated/malicious request | 401 / 400; bot status unchanged | `real_connection.json` |
| Companion stopped | Safe unavailable response, null probability; observed Windows connection timeout | `real_connection.json` |
| Android JVM regression | **14 passed**, 0 failures/errors/skips (8 previous + 6 new tests) | `android_verification.json` |
| Android debug APK | **BUILD SUCCESSFUL**, AI layout packaged; SHA-256 recorded | `android_build.txt`, `android_verification.json` |
| Original data and controls | 35 SmartHub evidence + 41 Lab files unchanged; protected modules unchanged | `baseline_hashes.json`, `final_checks.json` |

The 41 new Gateway cases cover successful mocked health/contract handling,
MODEL_NOT_READY, unavailable/time-limited transport, malicious fields, malformed
JSON, request/response binding, incompatible versions, redirects, invalid URLs,
wrong hashes, unauthenticated access and unchanged trading state. Their runtime
Lab dependency is mocked; the separate smoke check uses the actual installed Lab.
Android tests cover strict status presentation and URL validation. Physical phone
installation, rendered UI and mobile-to-Gateway network **NOT RUN**.

Relevant rerun commands:

```powershell
# backend working directory
& .\.venv-gateway\Scripts\python.exe -m pytest -v -p no:cacheprovider tests
New-Item -ItemType Directory -Force .integration-tmp | Out-Null
$env:PYTHONDONTWRITEBYTECODE = '1'
& "$labRoot\.venv\Scripts\python.exe" -m pytest -q -p no:cacheprovider `
    "$labRoot\tests" --basetemp "$backend\.integration-tmp\lab-tests-rerun"

# android_project working directory; installed Gradle 8.7 and JDK 21
$env:JAVA_HOME = 'C:/Program Files/Eclipse Adoptium/jdk-21.0.12.101-hotspot'
& 'C:/Users/MJ/.gradle/wrapper/dists/gradle-8.7-all/aan3ydargesu18aqyqjwhr3pc/gradle-8.7/bin/gradle.bat' `
    --offline --no-daemon '-Dorg.gradle.java.home=C:/Program Files/Eclipse Adoptium/jdk-21.0.12.101-hotspot' `
    '-Pkotlin.compiler.execution.strategy=in-process' '-Pkotlin.incremental=false' testDebugUnitTest assembleDebug
```

Use a fresh, disposable `--basetemp` child for Lab reruns: pytest clears that directory.
Recorded commands and return codes are in `test_commands.json`. No permanent services
were left running by the verification harness.

## Changed files

- Root: `.gitattributes`, `.gitignore`.
- Report: `ITTraderSmartHub_v4/AI_LAB_INTEGRATION.md`.
- Backend: `.env.example`, `app.py`, `requirements.txt`, `requirements-test.txt`,
  `requirements-gateway.lock.txt`, `ai_contract.py`, `ai_lab_adapter.py`,
  `ai_lab_service.py`, `verify_ai_connection.py`, `tests/test_ai_lab_integration.py`.
- Contracts: `ai_contracts/source_manifest.json`, `prediction_request.v1.schema.json`,
  `prediction_response.v1.schema.json`, `health_response.v1.schema.json`.
- Evidence: all new files in `backend/evidence/ai_lab_integration/` only; see the
  commit for the exact captured log/JSON list. Prior milestone evidence is untouched.
- Android: `GatewayRepository.kt`, `MainActivity.kt`, new `AIIntelligencePresenter.kt`,
  `activity_main.xml`, new `section_ai_intelligence.xml`, `ai_strings.xml`,
  `AIIntelligenceTest.kt` within the existing package/source tree.

## Limits and next milestone

This completes an advisory-only transport connection. It does not complete PAPER
integration, broker data certification, prediction, profitability or funded-account
readiness. No model lifecycle or training endpoint was added. A schema-compatible
future model still needs a separately reviewed approval mechanism; Phase 1 rejects it.

Next safest bounded work: verify the AI section on an authorized Android device
through the existing authenticated TLS Gateway, including service outage/recovery,
without enabling trading. Independently resolving the NAS100 timebase and obtaining
a suitable authorized demo contract remain prerequisites for market research.
