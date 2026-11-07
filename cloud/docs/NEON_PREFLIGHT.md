<!-- controlled-child-recovery-complete -->
# Recovery update — 6 November 2026

Child identity, direct/pooled verify-full connections and all 17 Preview/Development aliases now pass. Automatic main variable injection was disconnected only for this project. Production has zero database variables and its deployment is unchanged. The child owner was privately reset by the owner; the old main owner credential was subsequently retired after known consumers moved. No migration or runtime credential bootstrap has run. 154 offline checks pass. The SQL checksum is `50ea100e8334ab0923edcb5634bd8af3bbe0127cebd255cabfa292c2ba456db7`.

Target: winter-hat-40889380 / br-autumn-scene-bcqp4rjv / ep-winter-cake-bcffwgio / neondb. Separate migration approval, backup/object preflight and live least-privilege validation remain required. RESEARCH_ONLY, MODEL_NOT_READY and NO_TRADE remain.

## Historical notes before credential recovery

# Neon physical-target preflight and migration boundary

Updated 2026-11-06. **NO-GO: intended child identity is verified, but current
Preview/Development DSNs still target main.** No schema, credential or environment
binding was changed. Migration execution has not been authorized.

## Distinct identities

| Identity | Expected / observed | Evidence status |
|---|---|---|
| Neon project | winter-hat-40889380 | Authenticated Vercel integration metadata and NEON_PROJECT_ID agree |
| Resource display name | smarthub-phase3-preview | Authenticated integration resource store_3WehZ5haplK9AUbU |
| Plan | free_v3 | Provider metadata; one connected Vercel project |
| PostgreSQL database | neondb | Independent direct and pooled identity SELECTs; confirmed by owner |
| Intended endpoint | ep-winter-cake-bcffwgio | Authenticated child branch Computes page |
| Intended branch | phase3-auth-development / br-autumn-scene-bcqp4rjv | Authenticated overview, project ID and child-creation dialog |
| Parent / forbidden migration target | main / br-red-butterfly-bc69ov3c / ep-cold-hall-bcb1xvqr | Authenticated main overview labels Production; main Computes page confirms old endpoint |
| Vercel project | prj_WCV9dRjSufSvTeoYLJVhSf6yyKkC | Linked project and authenticated API agree |
| Environment targets | Preview, Development only | 16 encrypted variables; zero Production variables; both environments' six DSN aliases still resolve to main |

The SQL database guard now requires `pg_catalog.current_database() = 'neondb'`.
On mismatch it raises before CREATE/GRANT. A generic database name does not prove
the Neon project, branch or endpoint; it must not replace external identity checks.
The authenticated console now confirms main is the default/Production branch.
Only phase3-auth-development is the intended migration target. Preview/Development
variable targeting alone does not isolate database-branch access.

## Mandatory independent identity gate

Before any migration, read the endpoint details in the authenticated Neon provider
console/API and verify all of the following together:

1. Project ID is exactly winter-hat-40889380; resource belongs to the approved
   isolated Free project, with no other Vercel project connected.
2. Endpoint ID is exactly ep-winter-cake-bcffwgio. Branch must be exactly
   br-autumn-scene-bcqp4rjv / phase3-auth-development. Record the source
   and verification time; do not use connection-string naming as sole evidence.
3. That branch's database is neondb. Verify direct and pooler endpoints refer to
   that same branch. Then run the separately authorized identity/TLS SELECTs on
   the selected direct migration connection.
4. Recheck Vercel environment targets, exact reviewed file checksum and explicit
   owner migration approval. Abort on any missing field or mismatch.

An existing authenticated console tab established both branches and endpoint
ownership even though a new SSO flow still requested account linking verification.
Sources: /app/projects/winter-hat-40889380/branches/br-autumn-scene-bcqp4rjv and
the corresponding /computes pages for child and main. Child creation was performed
by the owner, not this review. No account/security settings were changed.

Fresh in-memory inspection of Preview and Development found all six DSN aliases
still point to ep-cold-hall-bcb1xvqr/neondb (main). There are no Git-branch env
overrides. The local read-only probe now pins the child endpoint before any TLS
or database connection and therefore rejects these current bindings. No SQL was
sent in this branch review. Child connectivity/TLS is not yet tested.

Before any separately approved configuration correction, review a plan to retarget
only Preview/Development consistently to the child; do not edit main/Production,
invent child credentials, create a runtime login or rely on hostname substitution.
After correction, rerun both bindings and child verify-full connection checks.

Credential incident: an existing child connection dialog had an unmasked owner
credential and it entered a tool response. Its value was not copied into project
files/reports or used for a connection. The owner was notified; private rotation
and any necessary credential propagation require separate approval. No rotation
was performed. Credentials must not be reproduced in chat or evidence artifacts.

## Why pg_stat_ssl can disagree with client TLS

PostgreSQL documents pg_stat_ssl as the TLS state of each PostgreSQL backend
connection. It is not a certificate test of an upstream client-to-proxy connection.
Neon places an authentication/protocol proxy before compute, including for the
unpooled/direct endpoint. Removing the pooler does not remove the Neon proxy.
Neon's public proxy code terminates incoming TLS and creates a separate compute
connection with its own TLS mode.

Our earlier direct and pooled main libpq connections both succeeded with verify-full, a certifi
CA bundle, channel_binding=require, TLS >=1.2 and GSS encryption disabled. libpq
reported ssl_in_use=true while pg_stat_ssl returned false/NULL/NULL. These facts
measure different connections. Proxy TLS termination is the architecture-consistent
explanation; the SQL result does not mean the external client used plaintext.

The diagnostic additionally performs a credential-free PostgreSQL SSLRequest and
standard-library TLS handshake with mandatory CA/hostname validation. The separate
evidence records actual TLS protocol/cipher and certificate fingerprint, alongside
any timeout. No authentication packets or SQL are sent on that diagnostic socket.

Limits: public source establishes architecture, not this managed deployment's
exact build or internal transport. These main results do not establish child TLS.
pg_stat_ssl=false means that PostgreSQL backend
did not use PostgreSQL-level TLS. It does not establish whether another provider
network encryption layer protects the internal hop. Do not claim end-to-end
compute TLS or change client TLS settings to make the observation disappear.
If internal-hop TLS is a mandatory policy, obtain provider confirmation before GO.

Primary references:

- [PostgreSQL pg_stat_ssl](https://www.postgresql.org/docs/current/monitoring-stats.html#MONITORING-PG-STAT-SSL-VIEW)
- [Neon security overview](https://neon.com/docs/security/security-overview)
- [Neon proxy TLS termination source](https://github.com/neondatabase/neon/blob/main/proxy/src/stream.rs)
- [Separate compute connection configuration](https://github.com/neondatabase/neon/blob/main/proxy/src/compute/mod.rs)
- [Separate compute TLS negotiation](https://github.com/neondatabase/neon/blob/main/proxy/src/compute/tls.rs)
- [libpq certificate/hostname validation](https://www.postgresql.org/docs/current/libpq-ssl.html)

## Next approval and validation stages

Migration is a fresh-install transaction only. Prior to a later approved execution,
obtain approval for read-only version/authority/collision and backup/snapshot checks,
identify their exact target, and abort on existing schema/role names. Roles are
cluster-scoped in this Neon project. Preserve other schemas, databases and projects.
Use a verify-full direct connection. Never reuse an owner URL in the HTTP runtime.
ROLLBACK before COMMIT reverses the transactional DDL; no destructive post-commit
downgrade is authorized. No password or LOGIN activation is in the proposed SQL.

Offline tests parse PostgreSQL/PLpgSQL, evaluate actual policy/guard expressions,
mock connector security and exercise transaction logic in disposable SQLite test
doubles. They do not verify live PostgreSQL ACL/RLS enforcement. After a separately
approved isolated migration, live permission/transaction tests must precede any
separately approved runtime credential/bootstrap, deployment or Android mobile-data
acceptance. SET LOCAL role/timeouts and application writes were not executed by
this read-only preflight. No mobile-data readiness claim follows from SELECT 1.

RESEARCH_ONLY, MODEL_NOT_READY and NO_TRADE remain in effect. No model activation,
MT5 connection, broker credential, order API, local gateway/SQLite or Android
enrollment change is part of this preparation.
