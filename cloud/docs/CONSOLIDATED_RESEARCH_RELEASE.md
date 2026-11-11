# Consolidated research test release — 11 November 2026

This is one consolidated test candidate, not a trading-ready product. The owner
requested no more intermediate APK installations. Keep the earlier candidate
private; hand over only one verified consolidated APK after Preview validation.

## Included

- Android switchable local research profiles for FTMO, FundedNext, GOAT and
  FundingPips. They contain programme, stage, original size, currency and terms
  metadata; they do not log in to MT5 or approve a policy. Fixed official links
  send no account data. Cloud/local enrollment stores remain separate/unchanged.
- Authenticated, GET-only `/api/v5/ai/paper-trial` serving one integrity-pinned,
  sanitized deployment-local artifact. No upload, filesystem path input, model
  inference, SDK call or trade-control route is added. Existing device auth,
  token renewal, rate limits and audit permissions remain authoritative.
- Android paper-evidence panel shows recorded capture time, state at capture,
  correct/wrong directional classifications, virtual entry/wait counts,
  hypothetical positive/negative/flat outcomes and unknown/pending outcomes.
  Historical snapshots are labelled and never claim the local worker is live.
- Private prospective paper test records mistakes and abstentions without
  broker orders. The Windows status replacement failure was corrected with
  immutable numbered snapshots and tested with an open reader.

## Actual evidence and limits

The corrected source stopped on a RuntimeError at 08:59:30 UTC. The follower
stopped on its source failure at 08:59:33 UTC. Both wrote completion receipts;
this is not a successful full two-hour trial. Three source forecasts were
recorded, two directional outcomes observed, one left unresolved. The paper
tracks recorded nine WAIT decisions and zero virtual entries; there is no
paper-trade profitability evidence. The data-bridge interruption requires
separate diagnosis; no broker or clock permission is relaxed to keep it running.

Published evidence SHA-256:
`a19ba4d1c70afbd6bc66710e813e12e1942d3db85a65efc15674924a2e003d50`.
It contains only allowlisted counts, capture time and safety flags. Private
account references, credentials, prices, model files and raw candles are absent.
The compiler verified both hash-linked journals and final completion digests.
The compiled state is STOPPED, not RUNNING or READY.

## Checks

- Android feature build: 59 unit tests passed, no failures/errors/skips; lint
  passed with zero errors and 205 warnings. Final version metadata bump requires
  another build before handover. Existing research signing certificate preserved.
- Selected cloud auth/publication/paper tests: 52 passed. One unchanged SQL-parser
  test was deselected because pglast is unavailable in this local interpreter.
  The unchanged connection-identity suite also requires unavailable psycopg.
  Attempts to install pinned dependencies did not succeed. No claim is made that
  those tests were rerun. Schema, auth store, privileges and migrations unchanged.
- Earlier local paper regressions: 382 passed before the status-writer fix;
  55 targeted checks passed afterward. These are overlapping suites.
- Published artifact tampering, unsafe fields, fake readiness, count mismatches,
  duplicate keys, missing credentials and forbidden route inputs are rejected.

## Release gates

1. Confirm exact Vercel Preview project/team through authenticated metadata.
   The connected Vercel plugin returned 404; the existing authenticated CLI
   successfully resolved the saved SmartHub project and owner. Do not create
   a replacement project or switch teams silently.
2. Capture Production deployment ID and database-variable target metadata;
   abort if database aliases reach Production. Do not print variable values.
3. Audit deployment inputs, then publish only the existing Preview project.
   Preserve Production, Neon schema/credentials, main branch and phone records.
4. Verify health, protected paper endpoint, artifact contract and existing
   Preview hostname. Confirm Production and environment metadata unchanged.
5. Build the final APK, verify package/version/signing certificate/digest and
   retain exactly one candidate for handover. No uninstall or re-pair is part
   of this release. Actual phone UI testing happens after that single update;
   it cannot be claimed in advance.

Remaining product work beyond this test release: automatic programme-specific
rule discovery with source coverage, persisted reviewed-policy bindings and
change alerts, account-aware portfolio simulation, stable continuous feed
hosting, labeled ICT training and independent validation. No trained/validated
trading AI, firm compliance or order execution is claimed. Preserve RESEARCH_ONLY,
MODEL_NOT_READY and NO_TRADE throughout.
