# Final pre-migration review — no SQL execution authorized

Baseline: `4df15275fc8a17543c7a6c2f4cbbf1d7c7cbc453`. The final review tightened
the candidate without applying it. All verification here is offline source/SQL
parsing, policy-expression evaluation, transaction tests in temporary SQLite,
mocked connection tests and read-only provider metadata. None is live PostgreSQL
ACL/RLS enforcement or a Neon TLS/pooling acceptance test.

## Corrections

1. Explicit membership options: ADMIN FALSE, INHERIT FALSE, SET TRUE on the sole
   runtime-to-private-login mapping. The connector checks the actual direct grant
   options in addition to ownership, elevated flags and unexpected memberships.
   These catalog fields/membership options require PostgreSQL 16 or newer.
2. Pin certifi 2026.10.23 as a public CA trust bundle; force verify-full, channel
   binding, TLS >=1.2 and disable alternative GSS encryption. DSN overrides of
   trust, hostaddr, services and session startup options are rejected. No custom
   CA, client key, provider secret or Vercel bypass credential is embedded.
3. Neon transaction-pool compatibility: explicit transaction scope, automatic
   preparation disabled, empty startup options, transaction-local search_path,
   statement/idle timeouts and role. Never depend on session state surviving a
   pooled transaction. Reject implicit PGOPTIONS/PGSERVICE settings. See
   [Neon pooling](https://neon.com/docs/connect/connection-pooling) and
   [PostgreSQL transaction-local settings](https://www.postgresql.org/docs/current/sql-set.html).
4. Require separately verified non-secret DATABASE_HOST/DATABASE_NAME settings
   to match the private runtime URL exactly (Neon pooled endpoint, port 5432).
   No values were configured. They cannot be guessed from a resource display name.
5. The migration checks pg_catalog.current_database() against physical database
   `neondb` before any CREATE/GRANT. The owner explicitly authorized this correction
   after direct and pooled SELECTs verified the actual name. Wrong target aborts
   the transaction. `smarthub-phase3-preview` is the resource name, not the database.
   Independently verify the approved project, branch and endpoint in authenticated
   provider metadata before execution; the database-name guard cannot prove them.

## Final gate outcome

PASS for the proposed source/schema controls, supported by offline tests:
runtime cannot write administrator roles/sessions or own/change policies; no
SECURITY DEFINER routine is introduced; token refresh/enrollment are atomic;
revocation is checked on every fresh authorization/renewal; durable rate upserts
and bounded operator cleanup are retained; runtime audit is append-only; source
and Android contain no database credential; fresh-install DDL is transactional;
RESEARCH_ONLY_LOCKED/NO_TRADE and no-execution rules remain.

Live preflight confirmed `neondb`, direct and pooled SELECT connectivity, and
client certificate/hostname validation with verify-full on both endpoints.
The PostgreSQL backend reported ssl=false; see the proxy/TLS distinction in
`NEON_PREFLIGHT.md`. Authenticated provider metadata now maps the tested endpoint
to main, not the intended child. Child `phase3-auth-development` is verified as
`br-autumn-scene-bcqp4rjv`, endpoint `ep-winter-cake-bcffwgio`. Preview/Development
DSNs still target main. No bindings were changed; migration is NO-GO.
The private runtime is not provisioned and the application's
transaction-local role/ACL/RLS sequence has not been verified live. Migration
and credential bootstrap remain forbidden. An offline PASS is not a live PASS.

The final report in outputs provides the ten-point statement/test checklist and
the exact SQL checksum. Execution remains withheld, awaiting explicit owner
approval with an identified physical database and a verified-TLS direct migration
connection. Do not execute SQL, activate logins, create credentials, deploy, push,
merge, remove resources or modify Production from this review.

## Boundaries for a later approval

Target: Neon winter-hat-40889380 / smarthub-phase3-preview, free_v3, store
store_3WehZ5haplK9AUbU, sole Vercel project prj_WCV9dRjSufSvTeoYLJVhSf6yyKkC,
Preview and Development only. Intended physical target: `neondb` on child
`phase3-auth-development` (`br-autumn-scene-bcqp4rjv`), endpoint
`ep-winter-cake-bcffwgio`, independently verified in the authenticated console.
The existing `ep-cold-hall-bcb1xvqr` belongs to main (`br-red-butterfly-bc69ov3c`)
and must never be used for this migration. Reverify metadata and actual DSN
bindings immediately before any later approved execution.
The file does NOT create/rename a database.

Any future migration approval must name the exact file hash and allow only the
fresh-install transaction after target/collision/version/backup checks. Roles are
cluster-scoped inside this Neon project, so role-name collisions are an abort,
not permission to reuse an existing role. No password or LOGIN activation is in
the schema. Runtime/operator roles always remain NOLOGIN. Direct owner/migration
credentials and offline operator credentials must never be used by the HTTP app.
Admin bootstrap/rotation/revocation and audit reading stay offline-operator tasks.

Immediate revocation means new authorization and renewal checks after revocation
commits; it does not retroactively cancel already-authorized in-flight responses.
Fixed rate windows permit boundary bursts. Cleanup scheduling, audit retention,
trusted peer identity and edge abuse controls remain separate readiness items.
Transaction ROLLBACK reverts pre-commit DDL; a committed schema has no automatic
destructive downgrade. No live rollback demonstration was performed.
