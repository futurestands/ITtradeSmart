# ITTrader SmartHub v4 — Integration Audit (2026-10-28)

## Scope
Reviewed the submitted v4 ZIP and made focused backend reliability improvements. This is **not** a full Android repository merge, APK, live MT5 verification, or production release.

## Changes made in this reviewed copy
- `backend/v4_services.py`: optional SQLite-backed stress snapshot and append-only event records, loaded on restart. Enable with `SMARTHUB_STATE_DB` set to an absolute path on a restricted Windows-host directory. If absent, volatile mode is retained for backwards compatibility.
- `backend/v4_services.py`: reject stress measurements older than 120 seconds when producing the infrastructure risk ceiling, with `SERVER_TELEMETRY_STALE` and no effective risk approval.
- `backend/tests/test_v4_services.py`: tests for restart persistence and stale telemetry rejection.
- No Kotlin branding, UI, package name, WebSocket or MT5 order functions changed.

## Verified here
`python -m pytest -q backend/tests`: **19 passed, 1 skipped**. The Flask endpoint suite is skipped because Flask is not installed in this environment. Python risk/persistence tests are *not* live gateway/MT5 tests.

## Blockers
- Missing `AndroidManifest.xml`, `activity_main.xml`, resources/icons/themes, Gradle wrapper and complete project configuration: no Android build or branding-asset comparison possible.
- `GatewaySession.kt` is an empty placeholder: secure Android-to-gateway authentication not operational.
- TLS, device enrollment, Android Keystore, VPS deployment and live MT5 investor login not configured or tested here.
- Market/behavior risk fusion, MT5 exposure-aware routing, persistent reconstructed trade history and statistical incident-impact research remain unimplemented.
- SQLite optional mode is suitable for a single local gateway process only. Do not run multiple workers against mutable in-memory state. Add database migrations, durable authentication event audit, retention policy and concurrency strategy before production.
- Backend currently accepts static bearer secret in environment, not device-scoped credentials. The `/risk` legacy endpoint accepts user-submitted stress and must not be used for authoritative policy decisions.
- The algorithm classifies MT5 deals heuristically; full episode reconstruction and lot-based monetary loss estimates remain unverified.

## Integration next steps
1. Obtain full existing Android Studio repo and merge only source modifications after reviewing conflicts; preserve original branding.
2. Install Flask and run integration suite on the gateway host; configure isolated MT5 investor terminal and dedicated secrets store.
3. Build and test Android; implement scoped device enrollment, secure token storage and private authenticated HTTPS transport.
4. Build real telemetry collector and durable trading records; only then implement risk fusion, alert correlation and research pipeline.
5. Run end-to-end tests on a demo/read-only account and produce a Git commit in the actual repository.

No Git commit hash exists: this archive is not connected to a Git worktree.
