# Phase 3 cloud authentication candidate — not deployed

The owner authorized only provisioning of the dedicated Neon `free_v3` database
`smarthub-phase3-preview`, resource `store_3WehZ5haplK9AUbU`, exclusively connected
to SmartHub project `prj_WCV9dRjSufSvTeoYLJVhSf6yyKkC` in team
`team_QYSxGQ6tdhAh4OMvaf7wTcX8`, environments Preview and Development.
Provisioning is complete. **No SQL was executed. Stop before schema application.**

`schema.sql` is the complete proposed v1 DDL for separate owner review. It adds
one isolated schema, five tables and a non-login least-privilege runtime role.
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
