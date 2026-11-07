# Isolated schema migration completed

Report prepared 7 November 2026.

Approved SQL SHA-256: `50ea100e8334ab0923edcb5634bd8af3bbe0127cebd255cabfa292c2ba456db7`. Committed `2026-11-06T20:28:44.335931+00:00`.

Target: winter-hat-40889380 / br-autumn-scene-bcqp4rjv / ep-winter-cake-bcffwgio / neondb. Five auth tables, three dormant NOLOGIN roles, eight indexes, one identity sequence, eight RLS policies and 41 PostgreSQL 18 constraints were verified. The two public cloud_admin defaults, other existing child objects, main catalog, Vercel configuration and SQLite bytes were preserved.

An encrypted pre-migration pg_dump and catalog were locally recovery-tested. 59 live checks passed before commit and again from a fresh connection. Post-migration backend: 693 passed / 3 skipped; cloud/executor: 118 passed.

No runtime LOGIN/password, admin bootstrap, deployment, Android change or Git publishing was performed. NO_TRADE, RESEARCH_ONLY and MODEL_NOT_READY remain. Actual private-login connection and full deployed authentication flow await separate bootstrap/deployment approval. Training remains blocked by ineligible data; see backend/research_reference/README.md for preparation and boundaries.

Local evidence: PHASE3_SCHEMA_MIGRATION_RESULT.json, PHASE3_SCHEMA_BACKUP_RESTORE_RESUME.json, PHASE3_SCHEMA_COMPLETION_SUMMARY.json and PHASE3_SCHEMA_MIGRATION_COMPLETION_REPORT.md. Older preflight/review documents describe historical gates and are superseded by this completion record.
