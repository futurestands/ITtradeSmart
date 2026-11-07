# ICT study and model-development plan

Status: RESEARCH_ONLY / MODEL_NOT_READY / NO_TRADE. This is preparation,
not a completed mentorship course or trained market model. No endorsement by
Michael Huddleston is implied. Videos are educational sources, not orders to
the application and not profitable-trade labels.

## What is available

The author's [website](https://theinnercircletrader.com/index.html) links the
[official channel](https://www.youtube.com/innercircletrader). Public player
metadata confirmed that Episodes 2, 3 and 6 belong to channel
`UCtjxa77NqamhVC8atV85Rog`. No full lesson was reviewed. English automatic
caption responses were empty; the normal browser transcript panel remained
loading. No cookies, access-control bypass or third-party AI summaries were
used as lesson evidence. The research video was paused and its new tab closed.

`ICT_STUDY_CATALOG_v1.json` preserves these limitations. Its seven cards contain
one source-metadata card, three existing-code hypotheses, two research-protocol
cards and one user-policy card. It is deliberately not an invented ICT course.
`tools/query_ict_study.py` performs local token-overlap retrieval. It fits no
weights, calls no provider and has no runtime/API integration.

From the backend, use the isolated Python environment to run:

    python tools/query_ict_study.py "market structure liquidity"
    python tools/query_ict_study.py "ftmo risk discipline"

Source notes must remain concise original summaries with citations. Preserve
only necessary excerpts; do not copy an entire channel into the repository.

## Study queue and acceptance criteria

| Topic | Existing component | Required evidence before teaching equivalence |
|---|---|---|
| Structure and liquidity | `swings.py`, `structure.py`, `liquidity.py` | Review official lesson segments and chart context; distinguish confirmed pivot breaks from discretionary MSS; include failed sweeps. |
| Displacement and imbalance | `fvg.py` | Define displacement and zone boundaries from reviewed sources; current ATR threshold is an unoptimised code convention. |
| Higher-timeframe context | `analysis.py`, `timeframes.py` | Annotate a specified contextual rule; only fully closed higher-timeframe bars are knowable. |
| Sessions, daily bias and events | `sessions.py`, `point_in_time.py` | Verify lesson definitions, exchange/broker timezone, historical DST and point-in-time event releases; no universal session window is assumed. |
| Invalidation and management | Existing risk engine and simulator | Record stops, targets, expiry, ambiguous candle paths and hypothetical partial costs before evaluating outcomes. No broker actions. |
| Discipline and account limits | `discipline.py`, `prop_account_plan.py` | Maintain independent hard gates; FTMO 2-Step Phase 1 is selected, original size configurable, personal ceiling 0.5%, maximum three entries including zero. Live account binding remains absent. |

Order blocks, breakers, mitigation, premium/discount and other ICT terminology
remain unverified topics, not enabled features. Add a concept only after a
source segment, explicit measurable definition, counterexamples and causal
tests exist. Do not select attractive examples retrospectively.

## Annotation record to collect

Each original study/journal record should include:

- Source URL, channel ID, segment start/end, source-review method, review date,
  reviewer and unresolved transcription/chart ambiguity.
- Dataset digest, instrument and contract version, UTC decision time, timeframe,
  feature version and every feature's availability time.
- Planned direction or WAIT, setup family, entry/invalidation/target/expiry,
  cost assumptions, session/event evidence and checklist failures.
- Human annotation of setup validity made without future outcome visibility;
  preserve uncertainty and reviewer disagreements instead of forcing a label.
- Separately stored subsequent outcome, label interval/end time, fill model and
  costs. A compliant loss is not automatically poor discipline; a rule-breaking
  win is not good discipline. No-trade and failed setups must be retained.

No such human-reviewed ICT examples have yet been collected. The existing
21 synthetic discipline cases are software exercises, not expert labels.

## Feature preparation implemented

`nas100/study_features.py` produces nine diagnostic feature fields using the
existing detectors: ATR/close, structure direction, consolidation, sweep
direction/age, two unfilled-zone counts, and signed distance to the latest
confirmed high/low measured in ATR. These pivots may already be consumed;
distance does not establish resting liquidity. Partially filled zones count
as unfilled. The features are implementation hypotheses, not a certified ICT
representation. No actual order-book liquidity is observed.

Only candles closed by the UTC decision time enter the detectors. Insufficient
history, warm-up, gaps and unknown states remain explicit. A stale latest bar
is flagged. Every result remains training-ineligible regardless of values.
The module is an offline preparation surface, not wired into Android, the
gateway, cloud runtime or any predictive model.

This prefix-based reference implementation prioritises auditability over
throughput. It is not a streaming feature service. Do not run it over millions
of overlapping prefixes until a separately tested incremental implementation
exists. Any unexplained gap in the supplied history leaves the vector missing;
certify session boundaries and define dataset segmentation before changing
that conservative behaviour.

## Training and independent evaluation

1. Resolve the six captured datasets' UTC/broker DST mapping, missing intervals,
   session closures and historical instrument/cost certification. Keep their
   `TIMEBASE_UNVERIFIED` quarantine until independently supported.
2. Complete source review and blind annotation; freeze a feature/target manifest
   and variant log before performance evaluation. Describe exclusions too.
3. Use causal rule candidates and the reviewed next-bar fill simulator. The lab
   also has a legacy close-entry labeler: do not mix its target with the
   next-open candidate target or treat their metrics as interchangeable.
4. Keep outcomes strictly outside feature/scaler inputs. Purge train/calibration
   events overlapping a later interval; set an embargo for label horizons.
   Split by time and group related candidates/trades to prevent duplicate
   leakage. Fit transforms and models inside training folds only.
5. Compare a fixed rule baseline and empirical prior to regularised logistic
   and constrained tree models. Fit probability calibration on an earlier,
   disjoint segment. Any selection/threshold tuning belongs before the final
   untouched holdout. Record all variants, including failures.
6. Evaluate cost-aware outcomes, calibration/Brier/log loss, uncertainty,
   regime/session coverage, drawdown and abstention. Stress spread/slippage and
   missing data. Account rules remain independent deterministic vetoes.
7. Only after reviewed out-of-sample evidence, consider a separately approved
   model artifact for shadow analysis. BUY/SELL would be analysis labels; risk,
   permissions and execution require their own gates. Current outputs remain
   NO_TRADE, with no advertised accuracy or profitability.

The laboratory's unconditional real-data training lock is unchanged. Running a
synthetic fitting experiment checks software only; it cannot certify market
skill. Learning more prose cannot repair unverified market timestamps/costs.
Runtime bootstrap, deployments, Android changes and trading remain outside
this work's authorization.
