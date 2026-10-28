# ITTrader SmartHub v3 — security-first prototype update

## What is actually in this archive
Source-level update to the four-file v2 prototype. It is **not a complete buildable Android Studio project**: the uploaded source lacks a Gradle wrapper, settings.gradle, AndroidManifest.xml, resources/layout and other required application scaffolding. The Python backend is independently testable. Do not claim an APK is built or tested.

## Changes
- Backend refuses broker credentials in API body; they are read from Windows host environment variables.
- Backend requires a long bearer token and binds its development listener only to 127.0.0.1.
- Requires investor-mode MT5 session according to account trade permission flags; does not send orders.
- Adds 50%-maximum infrastructure stress risk reduction and parameter validation.
- Adds a conservative history deal/position classifier for potential post-loss re-entry and historical volume anomalies. It does not claim a medical/psychological diagnosis, and is not a complete reversal/partial-history P&L engine.
- Android removes broker credential submission, demands an HTTPS URL and refuses sync until a secure session token mechanism exists.
- Android prevents default/fabricated position sizes and labels the basic units formula as illustrative, not broker-approved lots.

## Backend local setup (Windows with MT5 installed)
1. Install Python and MT5 terminal and obtain a read-only investor login. Install `pip install -r backend/requirements.txt MetaTrader5` on Windows.
2. Set `MT5_LOGIN`, `MT5_INVESTOR_PASSWORD`, `MT5_SERVER` and a strong random `SMARTHUB_API_TOKEN` as protected environment variables. `.env.example` is only a template; the app does not auto-load it.
3. `cd backend && python app.py` binds localhost:5000 only. Validate locally with an authenticated client.
4. For phone access, put a properly configured TLS reverse proxy behind a private VPN. Do not open TCP 5000 to the internet. Authenticate devices independently for production; do not embed the long-lived token in the APK.
5. Install secure device login/token storage (Android Keystore), then implement `GatewaySession` before attempting phone sync. Sync intentionally FAILS CLOSED until this is provided.

## Validation
`cd backend && python -m pytest -q tests/` (pytest required). The risk engine is advisory and never places trades.

## Remaining blockers
- The Android source cannot be built from this archive alone; restore the missing original Android Studio project or generate missing project infrastructure before compiling.
- The phone's gateway authentication needs secure enrollment/session handling; `GatewaySession` is deliberately unconfigured.
- Add symbol-aware server-side lot sizing via MT5 `order_calc_profit`, spread/slippage reserve, stop validation and volume stepping.
- MT5 behavior classification is conservative but incomplete for history window boundaries, partial exits and reversals; further reconstruct using positions/orders and longer history before relying on flags.
- Add authenticated device tests, market feed reconnection and stale-feed handling.
- A read-only investor gateway cannot prevent trades placed directly in MT5.
- Ensure legal approval and secret redaction before using workplace production logs.
