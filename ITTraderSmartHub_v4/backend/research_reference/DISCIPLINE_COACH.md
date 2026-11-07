# Discipline coach: first research milestone

This is an offline deterministic coach and a draft training curriculum. It is not
a fitted model, a market predictor, an execution permission or a replacement for
the existing risk engine. No Flask/Android/database wiring or deployment occurs.

The coach reviews new-entry intentions and WAIT. It does not manage open positions
or infer emotions from a loss. Labels describe observable checklist compliance,
not whether someone is psychologically disciplined or whether a trade will win.

## Curriculum

- Follow a recorded plan; require confirmed setup and known costs/data.
- Respect the existing risk, loss, exposure, session and event gates.
- Stand aside during cooldown; flag an entry attempted after a blocked limit.
- Flag chasing, missing stops and widening the planned stop.
- Treat unknown, future and stale evidence as unavailable.
- Accept WAIT even when an entry checklist is complete. Never reward activity
  simply because it creates more trades.

Numerical financial limits come from the existing reviewed policy/risk engine.
This module invents no risk percentages, trade counts, loss budgets or event
windows. The five-minute age in the synthetic examples is a software fixture,
not a validated market threshold. Inputs are caller-supplied evidence and must
be bound to trusted records before future integration; a boolean is not proof.

`nas100.discipline.review_entry_intent` returns reason codes, explanations, an
input hash and a policy version. Even a complete checklist returns NO_TRADE,
trade_authorized=false, model_trained=false and probability=null. Safety checks
remain external hard rules; a learned coach must never override them.

Prepare a new version of the draft examples without overwriting earlier work:

```text
python tools/prepare_discipline_curriculum.py --output research_reference/discipline_curriculum_v1.jsonl
```

All 21 examples are rule-generated synthetic scenarios, explicitly NOT human-
reviewed or market-performance evidence. They are useful for testing the coaching
interface and drafting annotation guidance, not for claiming learned skill.

## How actual discipline training follows

1. Collect redacted journal episodes: the plan before entry, evidence available
   then, intended action, rule checks and the actual behavior afterward. Do not
   upload account credentials, personal identifiers or private journals to a model
   provider without separate authorization.
2. Have a human review labels and feedback. Include patient no-trade decisions,
   rule-compliant losses and rule-breaking wins. Profit must not erase a breach,
   and a loss must not automatically mean poor discipline.
3. Keep scenario families and later journal periods in separate evaluation sets;
   do not put paraphrases of the same episode in both training and testing.
4. Train a separate explanation/classification coach only after a model, reviewed
   dataset, privacy boundary and evaluation plan are chosen. Measure missed
   breaches, false accusations and unsafe advice, not just overall accuracy.
5. Require zero risk-override recommendations on the fixed safety challenge set.
   That test is a release requirement, not proof of universal safety. Hard gates
   remain enforced outside the learned model. Check unfamiliar/missing evidence
   and instructions attempting to override NO_TRADE.

Behavior coaching can be developed before a predictive market model. Historical
market-outcome training still requires certified timestamps, sessions and costs;
this work does not change dataset eligibility or the existing training lock.

Synthetic behavior tests also cannot establish how a person or system will react
under real financial pressure. NFA discusses that limitation for hypothetical
trading results:
https://www.nfa.futures.org/rulebooksql/rules.aspx?RuleID=9025&Section=9.

No model weights were fitted, no broker API was added, and RESEARCH_ONLY,
MODEL_NOT_READY and NO_TRADE remain unchanged. Journal persistence and phone UI
integration remain future work requiring their own review.
