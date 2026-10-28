# ITTrader SmartHub v4 — Implementation handover

## Source and scope
Based on the existing v3 Security Foundation ZIP. This is an incremental **v4 API scaffold**, not a finished Android APK or a fully implemented trading-risk intelligence platform. All original brand assets, app name, namespace and market WebSocket source are unchanged. The archive still lacks AndroidManifest.xml, layouts, resources, settings.gradle and the Gradle wrapper, so no Android build was possible.

## Implemented
- Added `backend/v4_services.py`: strict validation, server-only ephemeral telemetry state, alert cursoring, infrastructure risk ceiling, fail-closed incomplete risk fusion, and no-data research response.
- Updated `backend/app.py`: `POST /api/v4/telemetry/stress` (separate agent token), `POST /api/v4/risk/context`, `POST /api/v4/alerts/query`, and `POST /api/v4/research/incident-impact` (existing general token).
- Added `SMARTHUB_TELEMETRY_TOKEN` to `.env.example`; requires independent random secret on Windows host.
- Added `V4ApiContracts.kt`: lightweight Android JSON request builders and safe unavailable response text. `MainActivity.kt` only has integration comments; no UI changes or enabled calls because `GatewaySession.kt` remains an unauthenticated placeholder.
- Added `tests/test_v4.py` for Flask HTTP endpoints and `tests/test_v4_services.py` for dependency-free services.

## Unimplemented / next tasks
1. Reconstitute full original Android Studio project before merging. Preserve original branding, manifest, icons, layouts and package ID.
2. Implement secure device enrollment, short-lived scoped credentials, Android Keystore storage, VPN/TLS reverse proxy, and strict TLS validation; never hardcode token.
3. Add real authorized Windows telemetry collector with service authentication; current stress ingest accepts a trusted-source identifier and token but does not cryptographically prove the source device identity beyond the token. Add freshness timeout and persistent storage.
4. Implement server-verified market volatility, broker account exposure and behavior metrics; `risk/context` currently deliberately returns `UNAVAILABLE`, never a fabricated risk approval.
5. Implement MT5 position snapshots and service dependency mapping; alert routing is currently an in-memory event list, not full exposure-aware alerting. No push notifications yet.
6. Add persistent incident/trade time series and statistically validated comparison methodology; research currently returns `UNAVAILABLE` instead of synthetic analytics.
7. Verify Python 3.13 + Flask + MetaTrader5 on Windows, authenticated endpoint tests, MT5 investor-only login, and Android APK/instrumentation tests. No trade execution must be enabled.
8. Replace global shared device token strategy with scope-aware per-device issuance/revocation, separate telemetry agent scopes, durable audit, rate limits, and secure process boundaries.

## Deployment warning
The Flask process binds localhost only; these endpoints are NOT ready for public deployment. In-memory state is lost on restart and shared across neither workers nor hosts. Existing risk calculations are advisory only; they cannot constrain independently placed MT5 trades.

## Test commands (on Windows gateway)
`py -m pip install -r backend/requirements.txt pytest` then `cd backend` and `py -m pytest -q`. MT5 installation is a separate Windows-only step with a test investor account.
