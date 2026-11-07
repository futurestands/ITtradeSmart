# Cloud auth v1.1 — local approval candidate

Current preflight status supersedes the historical unqueried-target notes below:
physical database `neondb` and client verify-full direct/pooled connections were
verified with approved read-only SELECTs. The owner authorized changing the guard
to `neondb`. Provider metadata now verifies child `phase3-auth-development`
(`br-autumn-scene-bcqp4rjv`, `ep-winter-cake-bcffwgio`). Existing Preview/Development
DSNs still target main; earlier connection tests were on main, not the child.
Live child connectivity, ACL/RLS and application transactions remain unverified.
No migration is authorized. See `NEON_PREFLIGHT.md`.

No Neon SQL, login bootstrap, secret configuration, migration, deployment, push
or merge was performed. The owner requested corrections and a second review.

## Exact proposed target

Neon Free `free_v3`, resource `smarthub-phase3-preview`, Vercel store
`store_3WehZ5haplK9AUbU`, Neon project `winter-hat-40889380`; sole connected
project `ittrader_smarthub_vercel_cloud_preview_ready`, Vercel project
`prj_WCV9dRjSufSvTeoYLJVhSf6yyKkC`, team `team_QYSxGQ6tdhAh4OMvaf7wTcX8`.
Read-only provider metadata still reports one connected project and Free plan.
All 16 encrypted provider variables target Preview/Development; none targets
Production. Values were not printed or exported. Actual branch/database name,
host, current schemas, role grants and TLS have NOT been queried over PostgreSQL;
those must be checked in the approved migration preflight.

## Permission and operation matrix

| Operation | Web runtime | Offline operator |
|---|---|---|
| Device creation | INSERT id/name only; role=device default; active device RLS check | Explicit privileged bootstrap |
| Role/identity promotion | No INSERT/UPDATE role, id update or timestamp write | Controlled operator role |
| Revocation | UPDATE revoked only on device rows, WITH CHECK revoked=true | Device/admin management |
| Device session create/rotate/delete | Allowed for device principals; atomic refresh consume/insert | Allowed |
| Administrator session create/rotate/revoke | Denied by Store and RLS | Offline only |
| Validate an existing admin HTTP token | Read-only allowed | Allowed |
| Enrollment-code issue / admin device-revoke HTTP | Requires valid existing admin HTTP token | Bootstrap controls that token |
| Audit append | Explicit columns + identity sequence USAGE | Explicit columns + sequence USAGE |
| Audit read | Denied; no HTTP audit reader | SELECT only (no UPDATE/DELETE) |
| Rate bucket modification | INSERT, UPDATE count only; no window/identity update/delete | Bounded reviewed expired cleanup |
| SQL ownership, schema/role administration | Not granted | Not granted; migration owner is separate |

PostgreSQL combines table and column permissions, so v1's table-wide device
INSERT/UPDATE grants were removed rather than left alongside column grants.
See [GRANT semantics](https://www.postgresql.org/docs/current/sql-grant.html).
Both devices and sessions enable and force row security; runtime policies also
prevent minting a new session for a privately bootstrapped admin ID. See
[row-security rules](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).
The migration owner remains a trusted DDL authority, not a web login.

## Login mapping

Runtime and operator roles are NOLOGIN/NOINHERIT. The sole web membership is
runtime -> private `smarthub_cloud_preview_login` (NOLOGIN/NOINHERIT until approved
bootstrap). No operator/owner membership is granted to it. The connector requires
this username in the verified-TLS DSN, checks actual session/current identity,
rejects superuser/CREATEROLE/CREATEDB/BYPASSRLS/replication/inheriting/operator
membership flags, then SET LOCAL ROLEs to runtime and verifies it.
Unexpected direct/indirect role membership, privileged runtime-role attributes,
and web ownership of authentication schema/tables are also rejected.
Transaction pooling must be tested with this exact sequence. Identity failures are generic
503 responses, without driver/secret details. Credentials do not exist yet and
must later be configured only as Preview/Development SMARTHUB_CLOUD_DATABASE_URL.

Admin bootstrap credentials stay offline. An admin HTTP token cannot be renewed
or self-revoked by the shared web identity: use controlled offline rotation/
revocation. This restriction is intentional and tested; do not add an operator
database URL to the application as a shortcut. Audit viewing is likewise an
operator SQL task; HTTP admin-audit access has not been implemented.

## Durable windows and cleanup

Database-clock 60-second fixed windows; primary key scope + identity hash + start;
expiry=start+60, explicit checks, indexed expiry, atomic upsert and count saturation
at policy limit+1. Allowed policies: enrollment/renewal 10 per minute per peer,
access 120 per minute per access-token hash. No client/app clock supplies windows.
Fixed windows permit a boundary burst; they are not a sliding-window algorithm.

The runtime has no DELETE or expiry/window UPDATE privilege. Operator cleanup
is an explicit, unscheduled SQL review file with a maximum 1000 rows per run,
expiry predicate repeated on DELETE, and 300-second in-flight grace. The web
connector's 10-second idle transaction and 5-second statement limits are shorter
than this grace. Cleanup appends one hashed-operator audit event when rows are
removed and returns counts only; no audit rows are changed/deleted. Runtime
cannot invoke it with its grants, and no HTTP endpoint/import calls it.
The operator must bound run frequency/total work and monitor storage. Audit
retention remains append-only pending a separate retention policy. No scheduler
or maintenance credential was installed. No active-window reset is proposed.

## Validation and limits

Original v1 failed 12 of 15 new schema/security contract cases. The final cloud
suite includes original auth regression tests plus PostgreSQL parser/grant checks,
an independent interpreter of the actual row-policy expressions, connector mocks,
concurrent code/refresh/rate checks, expiry/rollover/saturation and rollback checks.
Temporary SQLite tests exercise Store transaction logic; they do not pretend to
enforce PostgreSQL ACL/RLS. No PostgreSQL connection or DDL was executed.

Remaining approval risks: live PostgreSQL version/CREATEROLE privileges and grant/
RLS behavior, actual login memberships/least privilege and TLS trust, transaction
pooling, private admin bootstrap tooling, cleanup scheduling, edge abuse limits,
audit retention and independent code review. Missing runtime setup fails closed.
Research stays RESEARCH_ONLY_LOCKED, MODEL_NOT_READY and NO_TRADE. Android, the
local gateway/SQLite records and risk/execution modules were not changed here.

## Migration boundary

This is fresh-install v1.1, not an executable upgrade against a deployed v1.
Archive v1 is retained for the unified review diff. After approval only, confirm
exact provider target and database identity, snapshot existing schema/metadata,
abort on pre-existing proposed schema/roles, then apply the reviewed schema in
one transaction. Validate real permissions before any separate private LOGIN/
password/admin bootstrap. Never make the runtime privilege role a LOGIN, grant
operator to the web login, use an owner URL, connect Production or run startup DDL.
No destructive rollback or provider-project deletion is authorized.
