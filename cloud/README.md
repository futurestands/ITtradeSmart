# Phase 3 cloud authentication and phone preview

Current status (7 November 2026): the approved schema migration completed on
`winter-hat-40889380 / br-autumn-scene-bcqp4rjv / ep-winter-cake-bcffwgio / neondb`.
The two privilege roles remain NOLOGIN. The owner subsequently approved the
private runtime login activation; it is active only on the child with restricted
runtime membership. No phone enrollment code has yet been issued. See
`docs/PREVIEW_RUNTIME_ACTIVATION.md` and `docs/PHONE_CONNECTION_GUIDE.md`.
Preview/Development provider aliases
were retargeted to the child. Production is unchanged. See
`docs/SCHEMA_MIGRATION_COMPLETION.md` for the authoritative migration record and
`docs/PRIVATE_RUNTIME_BOOTSTRAP_PLAN.md` for the earlier activation review plan.

The owner has now requested GitHub publishing and an online phone preview.
Publishing/deployment alone does not activate authentication storage, provide
live MT5 data or train a market model. Android cloud pairing needs the private
runtime bootstrap and a one-time device code. RESEARCH_ONLY / MODEL_NOT_READY /
NO_TRADE remain mandatory. The older notes below describe earlier review gates
and must not be interpreted as the current migration outcome.

## Historical proposal and review notes

The final migration gate is documented in `docs/FINAL_MIGRATION_GATE.md` and
supersedes earlier connection/default-membership assumptions. No migration is authorized.
The earlier read-only preflight confirmed `neondb` and verify-full direct/pooled
TLS on main. Authenticated metadata now identifies the intended child branch
`phase3-auth-development` / `br-autumn-scene-bcqp4rjv` / `ep-winter-cake-bcffwgio`.
Preview/Development DSNs still target main; migration and child connectivity
remain NO-GO. No bindings were changed. Do not claim a full gate PASS.
See `docs/NEON_PREFLIGHT.md`. The SQL retains its fail-closed physical-name guard.

The owner authorized provisioning of the dedicated Neon `free_v3` resource
`smarthub-phase3-preview`, resource `store_3WehZ5haplK9AUbU`, exclusively connected
to SmartHub project `prj_WCV9dRjSufSvTeoYLJVhSf6yyKkC` in team
`team_QYSxGQ6tdhAh4OMvaf7wTcX8`, environments Preview and Development.
Provisioning and approved read-only SELECTs are complete. **No DDL or data changes
were executed against Neon. Stop before schema application.**

`schema.sql` is now the proposed v1.1 fresh-install DDL; `schema.v1.review.sql`
preserves the unapplied v1 proposal. The v1.1 permission, login, rate-window and
operator controls in `docs/AUTH_V1_1_REVIEW.md` supersede the older v1 notes below.
Runtime/operator privilege roles must always remain NOLOGIN. A separate private
web login starts NOLOGIN/NOINHERIT and maps only to runtime; its activation is a
separately approved bootstrap, not a conversion of a privilege role into a login.
No runtime import, request or deployment applies migrations. PostgreSQL TLS must
use `sslmode=verify-full`; configure the post-review runtime URL only as
`SMARTHUB_CLOUD_DATABASE_URL`, never use an owner connection as the HTTP identity.
The provider's generated variables are not automatically treated as approved
application credentials. No production configuration was changed.

Tokens and enrollment codes are high entropy; only their SHA-256 hashes are
stored. Access expires after one hour, refresh after thirty days, and enrollment
codes after ten minutes. Refresh and enrollment are consumed transactionally.
Device revocation blocks access and renewal. Client IDs cannot select an existing
principal; enrollment creates a new server-assigned principal. Admins must be
bootstrapped privately after approval; no admin secret exists in Android.

Routes: public `/health`; one-time `/api/v5/device/enroll` and rotating
`/api/v5/device/renew`; authenticated `/api/v5/device/revoke`, AI status,
research-progress and advisory; admin-only code issuance and device revocation.
Unknown/broken authentication storage fails closed; there is no memory/SQLite
production fallback. The SQLite test double tests transaction logic, not live
PostgreSQL DDL, certificate trust, cloud durability or final permissions.

Research remains unavailable, model not ready and advisory always NO_TRADE.
The existing backend research-unavailable contract is reused byte-for-byte as
`research_contract.py`; no local report file loader is invoked by HTTP routes.
No MT5, broker credentials, market acquisition or training is deployed.

Android work preserves legacy encrypted local preference keys and separates
origin-bound cloud sessions. The local device token is not sent to a public
cloud host. Redirects are disabled. The signing key and app ID are unchanged.
No app was installed in this phase before owner review; no mobile-data test has
been accepted. Vercel protection must be addressed without placing a bypass or
administrator credential in the APK.

Remaining review items include direct PostgreSQL integration/role tests, separate
private bootstrap tooling, rate/audit retention, distributed edge abuse controls,
device-storage instrumentation, real HTTPS/mobile acceptance and external review.
No production-readiness claim is made from offline tests.

v1.1 uses database-clock 60-second windows and explicit expiry columns. Operator
cleanup is bounded, has a five-minute grace and appends an audit event. Runtime
cannot delete buckets, change their windows, read/rewrite audit or create/rotate/
revoke admin sessions. Existing admin HTTP tokens remain read-valid for code
issuance/device revocation; admin rotation/revocation and audit reads are offline
operator tasks. There is no HTTP audit reader or scheduled cleanup job.

The connector rejects Production/unknown environments and privileged/owner/
operator URLs or sessions, then SET LOCAL ROLEs to runtime. No dedicated runtime
URL, private login or database role mapping has actually been installed. SQL
and maintenance artifacts are excluded from Vercel uploads and never auto-run.
