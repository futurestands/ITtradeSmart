# Codex M2 implementation report

## Local result awaiting independent review

Both isolated clones use `feature/codex-m2-independent-review-20261106`. SmartHub commit `74f266ce9a7619a8f33f72ea4329688fc2d7a2eb`, parent
`8998f0f30abc7f814fb935e458e9c04c2a6a56a0`. Lab commit `10517541f48424dfe970f04ce7ac15bdd2d5e896`, parent `4b2561634b9a5c8f4978e6f7ea6978790be6fd40`.
Both are clean; patches are included. No original WorkBuddy files or branches
were replaced and nothing was pushed or merged.

## Verified corrections and new preparation

1. Reject non-string JSON object keys at every depth before hashing, preventing
   numeric/string nested-key collisions. Preserve valid existing config digests.
   Handle cyclic/deep inputs as controlled validation errors.
2. Keep strict manifest-directory scans in manifest-root coordinates and reject
   unrelated scan roots. Preserve existing `.manifest.json` scan convention.
3. Require literal Boolean false for manifest eligibility/training fields;
   recomputing a digest around numeric zero no longer evades type checks.
4. Validate model-card schema, nonempty identity fields and restricted evaluation
   status, rejecting contradictory real-market-validation claims.
5. Verify the loaded variant-log history before appending; corrupt history leaves
   the original bytes untouched. Shared validation avoids different append/verify
   rules. This remains a single-writer integrity log, not authenticated storage.
6. Add limited-query exact-image fallback when Windows PowerShell path metadata
   is absent or inaccessible. Same basename elsewhere, unknown paths and duplicate
   native matches do not authorize attachment. Permission gates are unchanged.
7. Add offline UTC witness assessment and six synthetic regression cases without
   certifying a timebase or correcting labels.
8. Prototype `GET /api/v5/nas100/research-preview`: existing device authentication,
   default disabled (503), explicit local opt-in only, no client inputs, fixed
   synthetic fixture, existing pure NAS100 rule analysis, provenance/as-of/hash,
   reasons/invalidation, always `NO_TRADE`, null probability, `MODEL_NOT_READY`.
   Device enrollment and privileged bot access remain separate. Not enabled on
   the running gateway and not displayed by the Android application.

## File inventory

SmartHub:

- `ITTraderSmartHub_v4/backend/app.py` (M)
- `ITTraderSmartHub_v4/backend/docs/CODEX_M2_REVIEW.md` (A)
- `ITTraderSmartHub_v4/backend/nas100_research_preview.py` (A)
- `ITTraderSmartHub_v4/backend/tests/test_codex_m2_research_preview.py` (A)
- `ITTraderSmartHub_v4/backend/tests/test_codex_m2_terminal_identity.py` (A)
- `ITTraderSmartHub_v4/backend/tools/export_mt5_nas100.py` (M)
- `ITTraderSmartHub_v4/backend/tools/terminal_identity.py` (A)

Lab:

- `docs/CODEX_M2_REVIEW.md` (A)
- `src/nas100lab/reproducibility.py` (M)
- `src/nas100lab/timebase_observation.py` (A)
- `tests/test_codex_m2_reproducibility_review.py` (A)
- `tests/test_codex_m2_timebase_observation.py` (A)

The five requested engineering reports and evidence package are external
deliverables. They are not silently committed into the owner's active checkouts.

## Validation evidence

Before M1 fixes: Lab adversarial tests **12 failed, 1 passed**; terminal fallback
tests **2 failed, 2 passed**. Before prototype implementation: API **6 failed,
1 passed**. A later cyclic-input test caught an issue introduced by my recursive
validator before finalization; it was corrected. These red runs are included.

Final SmartHub **675 passed, 2 skipped, 0 failed**; Lab **517 passed, 0 skipped,
0 failed**. Lab requires the unchanged ignored provenance fixture described in
the M1 report. Existing suites include backend, Phase 1/2 NAS100, simulator,
calibration isolation, purging/embargo, HTF boundaries and execution locks.

AST parse/review found zero `order_send`/`order_check` calls in **53 SmartHub** and
**27 Lab** tracked production Python files. Test traps are excluded from that
production count. Staged private-key/GitHub-token/JWT/artifact pattern checks and
Git whitespace checks passed. Manual diff review found no added broker passwords,
signing material, database credentials, raw market CSVs or trained model artifacts.
This is a bounded change review, not a forensic secret audit of old history.

Confirmed no changes to risk formulas, Android, existing signing keys/package
configuration, Supabase SQL, execution interlock or the real-training lock.
No new dependencies, services, orders, migrations or account permission changes.

## Android, gateway, database and Supabase assessment

- Current port 5000 `/health`: HTTP 200. This alone does not verify authenticated
  phone enrollment, running commit, AI link or active DB path.
- Current port 8765 `/health`: connection unavailable. Prior CONNECTED /
  MODEL_NOT_READY and installed phone claims remain owner-reported, not reproduced.
- ADB returned zero devices. No install, launch, pairing change or uninstall.
  No Android build/unit/lint run was performed in this M2 review: Android source
  was unchanged. Earlier 32-test/lint/APK evidence is historical, not a new result.
- Android source calls `/api/v5/ai/status` and `/api/v5/ai/research-progress`; it
  does not call the new preview route. Release package remains
  `com.ittrader.smarthub`; existing debug suffix `.research` is unchanged.
- Backend persistence is SQLite or in-memory according to configuration.
  Owner-provided `.integration-tmp/smarthub_state.sqlite3` exists and passes
  read-only `PRAGMA quick_check`; user_version is 0, which is not proof of missing
  migrations. Runtime process configuration was not independently read or inferred
  from unrelated shell variables. No migration was necessary for these changes.
- Inspected backend/Android have no active Supabase client. Existing SQL proposes
  telemetry, alerts, devices, auth_audit, indexes and service-role RLS policies.
  Its plaintext token design and alert shape do not match current SQLite
  token_hash/role/pairing-code semantics. Treat as an unvalidated cloud proposal,
  not a compatible applied schema. Live cloud application status is unverified.
  No cloud access or migration occurred.

## Remaining limitations

Export remains blocked by two permission flags. UTC semantics, missing-candle
classification, historical costs and contract certification remain unresolved.
Hash manifests do not enforce filesystem immutability; log truncation/replacement
requires an independent head/count anchor. Model-card validation is not complete
performance certification. The native Windows API needs independent code review;
precheck/attachment is not atomic. New API is synthetic and local only.
No genuine trained model, calibrated real probability or profitable strategy is
claimed. Codex-authored corrections await an independent reviewer and owner-led
integration; tests are not that approval.
