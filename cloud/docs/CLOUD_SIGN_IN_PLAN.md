# Cloud sign-in replacing copied device codes

Status: prepared design; provider configuration and live phone acceptance are
not complete. No public sign-up or administrator bootstrap is authorized by
this design. Preserve existing device sessions during rollout.

## Intended experience

Open the research app, choose Sign in, complete identity-provider authentication
on the phone, then return to the app connected directly to the existing Vercel
Preview hostname. Store and rotate the existing device access/refresh tokens in
Android Keystore-backed encrypted preferences. The laptop is not a runtime or
network dependency. Expiration, revocation and device-storage loss still require
reauthentication; never promise an irrevocable permanent connection.

## Identity and device authorization

Provider preference is pending: Google sign-in or an email sign-in link. Do not
create an email service, enable billing or send mail until that route is selected
and its exact service is approved. For Google, use the supported Android identity
SDK and Google's maintained server token verifier, not a custom JWT verifier.
Register the research package and the verified existing signing certificate.

The server must verify token signature, issuer, expected audience, expiry and a
fresh server-issued nonce. Authorize only an explicitly configured owner subject;
a successful identity-provider sign-in by an arbitrary person must not grant hub
access. Use the stable verified subject, not an unverified email supplied by the
client. A subject allowlist is server-only configuration, never an APK secret.

Use a short-lived durable single-use enrollment challenge bound to the nonce,
with separate domain-prefixed hash material so a Google challenge cannot be
redeemed at the existing code route. Consume the challenge and create only a
device principal, session and success audit in one transaction. Failed audit or
issuance must roll back consumption. Require concurrent replay tests. Any
required schema or privilege change must be separately reviewed and approved;
do not expand the runtime role silently. Never grant administrator roles.

The existing rate limits, hashed database credentials, RLS and private runtime
role restrictions remain mandatory. No plaintext identity or refresh tokens in
logs, source, URLs or client error responses. Native sign-in requests must use
the supported provider UI; browser OAuth, if used, requires an external browser,
PKCE, state, exact redirect validation and an app-bound callback.

## Rollout and acceptance

1. Finish and validate independent encrypted Cloud storage, including readable
   legacy migration, unreadable legacy preservation, failed writes and restart.
2. Identify the actual owner and OAuth application without collecting secrets
   in chat; configure only this project's Preview/Development environments.
3. Implement provider authentication, owner authorization and atomic challenge
   redemption; preserve the existing pairing route for controlled recovery.
4. Reject wrong owner, issuer, audience, nonce, expiry, signature and replay;
   test concurrent redemption, audit failure and immediate revocation.
5. Build with the same signer/package, verify live phone sign-in on mobile data,
   reopen and refresh without a laptop, then verify the denied/revoked cases.
6. Release only to the isolated Preview. Production, Neon main, local SQLite,
   broker credentials and existing Android records remain outside this change.

Cloud authentication does not supply market data or train a model. Continue
RESEARCH_ONLY, MODEL_NOT_READY and NO_TRADE throughout this rollout.

Primary references:
- https://developers.google.com/identity/sign-in/android/backend-auth
- https://developers.google.com/identity/openid-connect/openid-connect
- https://www.rfc-editor.org/rfc/rfc8252
