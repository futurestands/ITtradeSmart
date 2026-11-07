# Account-aware prop-firm planning — research milestone

7 November 2026. User-selected first profile: FTMO 2-Step Challenge Phase 1.
Personal ceiling: 0.5% of original account size, at most three entries per firm
trading day, no minimum trade quota. No real account, currency or terminal was
bound. Examples below are USD synthetic fixtures, not account-size availability.

| Original capital | Personal per-entry ceiling before tighter limits |
|---|---|
| 5,000 | 25 |
| 10,000 | 50 |
| 100,000 | 500 |

This is planned nominal/stressed stop risk, not a guaranteed maximum loss. Gaps,
slippage, outages and broker behavior can exceed it. Never enlarge risk to catch
up with a target or reach a daily trade quota.

## Official source review, not an active account certification

| Firm/programme | Reviewed differences and blockers |
|---|---|
| FTMO 2-Step Phase 1 | 10% profit target, 5% daily allowance, 10% static total loss limit, four trading days. Daily equity floor uses the midnight CE(S)T balance minus allowance based on original capital. Exact purchased terms still required. |
| GOAT 2 Step GOAT | Page describes 4% daily loss using higher reset balance/equity, 10% static maximum loss, and a separate 1% floating-loss variant. Purchase date changes a funded-stage payout condition. Reset wording says 5 PM EST; do not infer its seasonal UTC mapping. |
| FundingPips 2 Step Standard | Purchased configuration chooses 3%/5% daily loss; 10% static maximum. Daily baseline uses higher opening balance/equity. Phase, add-ons and reward cycle affect news, holding and other restrictions. Partial closes can trigger news-related consequences. |
| FundedNext | Models have different loss allowances. The current EA policy restricts automation by platform and size and includes SL/TP-modifying tools; account-specific permission must be checked independently. |

Sources, checked 7 November 2026:

- FTMO: https://ftmo.com/en/trading-objectives/
- GOAT: https://help.goatfundedtrader.com/2-step-goat.html
- FundingPips: https://help.fundingpips.com/hc/en-us/articles/34501809112081-2-Step-Standard
- FundedNext losses: https://help.fundednext.com/en/articles/9941519-daily-loss-limit-vs-maximum-loss-limit
- FundedNext automation: https://help.fundednext.com/en/articles/8020763-is-ea-allowed-in-fundednext

These are selected research notes, not complete firm rules or a recommendation
to buy a challenge. Other programmes are not executable profiles. Fees and market
prices are distinct from original account capital. Account size must come from
the purchased account and trusted registration, not be inferred from current
balance, a server name, a screenshot estimate or client-supplied JSON.

## Implemented offline behavior

`prop_account_plan.plan_ftmo_phase1` composes the existing compliance evaluator
with the personal cap and a separate existing-risk-engine cash cap. It reserves
additional current-equity-to-stop downside on all open positions and pending
entries, plus unincurred costs and an explicit buffer. Floating P/L already in
equity is not subtracted twice. It respects free margin, rounds volume down and
rejects minimum-volume oversizing, bad stop/target direction and tick misalignment.

Rule/account/ledger references must match. Current snapshot and reset-window
metadata must agree, and unknown exposure or incomplete history blocks a plan.
The entry counter must include durable pending-entry reservations. A partial
close must not create another daily entry slot. Multiple terminals and concurrent
requests require a single durable, atomic reservation service; that service is
NOT implemented or connected by this milestone.

Target progress uses closed balance. Reaching the target stops new simulated
entries for review; it does not certify passing the challenge or close positions.
No new position is forced to satisfy minimum trading days. Other account rules
remain a separate required gate, not a claim that the loss calculator covers all
conditions.

`simulated_partial_volumes` checks a user-specified allocation against minimum/
step limits, including the remainder. It requires separately reviewed permission.
It neither selects profit-taking levels nor assumes an SL/TP/partial was executed.
Recompute exposure only from a fresh confirmed post-fill observation. Execution,
trigger prices and partial-fill handling remain unimplemented.

## Rule changes and freshness

`tools/check_ftmo_rule_source.py` performs an on-demand, TLS-verified GET of one
fixed official URL with redirects disabled and bounded document size. It outputs
only source metadata/fingerprint, not a rule approval. Unknown baseline, changed
content, fetch failure, stale check or account mismatch prevents a new plan.
The planner rejects changed hashes and stale/future rule checks. The review and
purchased terms must remain tied to the exact account/programme/phase/version.

An unchanged HTML fingerprint does not establish complete policy correctness.
Navigation/marketing changes can cause conservative false positives. A changed
page requires review; no model may silently rewrite or weaken a profile. Legacy
purchase terms and direct notices can supersede a current generic marketing page.
No periodic watcher, background job, continuous live monitoring or phone alert
delivery is deployed. A production monitor would need decision-time freshness
checks, durable snapshots, rule-change alerts and a reviewed polling schedule.

## Current boundary

Numerical plans accept synthetic observations only. Existing BROKER_READ_ONLY
labels still return UNKNOWN/BROKER_ADAPTER_NOT_IMPLEMENTED; no adapter gate was
bypassed. Every result has NO_TRADE, execution_authorized=false, live_verified=false,
RESEARCH_ONLY and MODEL_NOT_READY. Simulated lot sizes are not live recommendations.
The original risk engine, gateway, database, Android and Production remain unchanged.

Next: review the account's purchased agreement, currency, original size, creation/
reset dates, variant and platform; implement authenticated read-only binding and
durable entry/exposure tracking; verify reset/DST and cost/contract feeds; then
validate snapshots/replay and alerts. Runtime credentials, deployment and any
execution functionality remain separate approval gates. No model weights were
trained: mandatory financial limits belong in deterministic, versioned controls.
