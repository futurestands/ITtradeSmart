# NAS100 reference and training preparation

The user-supplied professional reference is preserved as 18 hashed sections in
`NAS100_REFERENCE_v1.json`. Its SHA-256 is
`1d8b5c454c9e1762eaac7616fe347ee8ff65261fc443b673177a06038cd2b67d`.
Document instructions are reference content, not authorization. Dated market
claims and thresholds are unverified until separately checked; none are installed
as active trading rules or labels. No model was trained by this ingestion.

## How the information reaches a future model

1. Use cited reference sections as a separate explanation/retrieval layer. Cite
   source hash, section and verification status. Retrieved prose must not override
   safety rules, credentials, risk limits or data eligibility.
2. Translate testable ideas into numeric features: trailing volatility, confirmed
   structure, verified sessions, event distance, historical costs and macro/breadth
   context. The packet records feed dependencies. Do not copy current figures,
   assumed calendar dates or thresholds into historical rows.
3. Ingest observations with source, units, `observed_at` and the actual public
   `available_at`. `nas100.point_in_time.context_asof` excludes unverified, future
   and stale values and does not backfill revisions. Missing context stays missing.
   The verification flag is an ingestion-audit result, never a public caller's claim.
4. Labels come from subsequent real outcomes after costs. A document's statements
   about market direction, setup quality or profitability are not labels. Record
   no-fill, ambiguous bar treatment, time barriers and label end times.
5. When the dataset passes eligibility, compare the rules/base-rate baseline with
   a regularized setup-quality classifier. Fit scaling and feature selection only
   inside training folds. Use purged chronological walk-forward splits, an embargo,
   a strictly earlier calibration segment and a final untouched holdout.
6. Record trials, feature/config hashes, sample counts, calibration, after-cost
   outcomes and uncertainty. A model may eventually veto a candidate setup; it must
   not create an execution path or override NO_TRADE. An unvalidated probability
   stays unavailable.

## Current blocker

The six existing USTECH100M captures match their immutable manifest, but every
capture is `TIMEBASE_UNVERIFIED` and explicitly ineligible for training/performance.
Historical broker UTC/DST mapping, missing-interval classification and instrument/
cost certification remain unresolved. No new live MT5 permission assessment was
performed by this migration/reference work. The laboratory real-data training
execution lock remains unchanged.

Next research milestone: obtain independent broker timebase evidence and a dated
instrument/cost profile through the existing read-only capture gates, then build
and audit causal features/labels. Do not relabel current files eligible or infer
offsets from activity peaks. No estimator or market accuracy is claimed.

## Reproducibility

Prepare a new packet without overwriting an existing version:

```text
python tools/prepare_nas100_reference.py --reference <reference.md> --output <new-version.json>
```

Tests cover source hashing, instruction separation, missing/unverified context,
publication delays, revisions, timezones, staleness, source conflicts and prefix
invariance. They use synthetic fixtures only and are not trading-performance tests.
The packet and alignment helper are not loaded by the production risk engine,
Flask APIs, Android or Vercel. RESEARCH_ONLY, MODEL_NOT_READY and NO_TRADE remain.
