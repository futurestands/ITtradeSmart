# Next development plan — ordered acceptance gates

1. **Independent review and controlled integration.** Have Claude/WorkBuddy review
   both focused M2 patches, especially native process-query handle lifecycle,
   same-snapshot variant verification and the device-authenticated synthetic API.
   Preserve current source branches. Integrate only after review; push/merge/
   deployment need separate owner authorization. Do not use the unsafe demo-order
   branch. Make Lab unit tests hermetic while retaining a separately labeled
   real-local-provenance integration test.

2. **Eligible historical dataset.** Owner/provider must supply an authorized
   already-open demo session satisfying every disabled-trading gate, authoritative
   timebase evidence and contract/cost/licensing records. Collect timestamp
   witnesses using UTC/monotonic brackets and synchronized clock evidence.
   Cross-check dated winter/summer and US/EU mismatch boundaries. Freeze raw
   manifests; retain gaps and source revisions; never fill missing bars or label
   closures without market-calendar evidence. Any derived UTC dataset gets its
   own version and mapping digest. Current status remains ineligible.

3. **Causal feature and label contract.** Reuse existing swings/BOS/CHoCH, liquidity
   sweeps, FVG, displacement, session and HTF primitives. Freeze feature
   availability-at-close and confirmation delay; document order-block and
   premium/discount definitions before adding them. Specify signal, entry,
   horizon, invalidation, ambiguous-path and unresolved-label treatment. Include
   cost/contract version IDs and missingness flags. Do not add indicators merely
   to manufacture BUY/SELL signals.

4. **Reproducible chronological preparation.** Freeze feature/config/dataset
   hashes, code revision, dependency versions, seeds and event/split manifests.
   Persist absolute intervals, embargo/purge decisions, row identities and label
   end-times. Pre-register acceptance metrics/uncertainty and final holdout policy.
   Complete model cards and independently anchor variant-log head/count. Current
   helper modules are preparation, not a completed training pipeline; its hard
   lock stays in place until a separately reviewed authorization change.

5. **Training and walk-forward research only after eligibility.** Compare an
   empirical-prior/no-trade benchmark, logistic baseline and a bounded boosting
   comparison. Fit preprocessing on training only, calibration on calibration
   only, evaluate frozen test folds and untouched holdout. Include overlap-aware
   uncertainty, session/regime stability, realistic spread/slippage/commission/
   contract-currency sensitivity and independent simulator checks. Do not retune
   on the final holdout or treat synthetic results as genuine evidence.

6. **Calibrated decision contract.** Accept BUY/SELL only after pre-registered,
   independently reviewed out-of-sample gates pass. Define uncertainty,
   distribution-shift and stale-data abstention. Otherwise `NO_TRADE`. Responses
   need model/version, calibrated-probability provenance, freshness, explanation,
   invalidation and risk context. Keep unconditional broker execution disabled.

7. **Android display and runtime verification.** Review the prototype contract
   before adding any client display. Label synthetic previews clearly; real
   analysis requires eligibility gates. Preserve enrollment, secure token storage,
   branding and signing identity. Rebuild/test/lint and verify on a separately
   authorized phone update. ADB currently sees zero devices: for a later session,
   enable phone Developer options/Wireless debugging on the same network, pair
   using the phone's current pairing address/code locally, connect to its separate
   debugging address, then check `adb devices` and port-forwarding. Do not send
   codes/tokens in chat or uninstall on signing conflict. Prior phone success
   does not establish present connectivity.

8. **Supabase, only if required.** First identify the real target project and
   current schema through authorized access; design parity with hashed device
   tokens, expiry/revocation/roles, pairing and audit semantics. Review RLS and
   per-user isolation, migration/backup/rollback and quotas. Obtain explicit
   approval before any cloud migration or publishing path. Current local M2
   changes do not require Supabase.

Owner-only blockers: broker permissions/session policy, authoritative timezone
and historical data rights/economics, later app/service deployment, any cloud
migration, publication/merge. No decision is needed to run further offline
regressions; none of those owner actions was performed here.
