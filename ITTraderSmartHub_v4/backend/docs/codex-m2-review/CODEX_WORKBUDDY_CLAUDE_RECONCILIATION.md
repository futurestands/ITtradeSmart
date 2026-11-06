# WorkBuddy / Claude / Codex reconciliation

All nine requested documents were available: the three Claude discovery,
architecture and research-roadmap documents in Downloads, and the six WorkBuddy
reports in the SmartHub application directory. None is treated as proof of code
or runtime behavior by itself. The supplied master handover is the current user
instruction; older document instructions do not authorize publishing or deployment.

| Claim | Independent result | Action |
|---|---|---|
| SmartHub M1: 660 passed, 2 skipped | Reproduced | Preserve tests; document skip limits |
| Lab M1: 497 passed | Clean clone 496/1 because ignored provenance JSON is absent; final suite passes when unchanged metadata is supplied | Report external dependency; do not claim hermetic CI |
| `/analyze` uses undefined `key` | Current generator expression is valid; reconciliation regression passes | No production repair |
| BotController lacks `last_price` | PAPER/DEMO cycles deliberately raise; no execution unlock | Preserve unconditional interlock |
| `analyse_dst_transitions` has wrong signature | Expects normalized DataFrame; CLI supplies it; path string is caller misuse | Preserve source/API |
| Phone previously paired and app enrolled | Owner-reported prior evidence; currently ADB lists zero devices | Do not call the phone broken or updated |
| Gateway and Lab connected, MODEL_NOT_READY | Prior owner report; current gateway health is 200 and port 8765 health is unreachable | Authenticated runtime link not reproduced; no service restart |
| No ML infrastructure | Separate Lab has features, labels, folds, synthetic logistic/boosting and calibration code | Distinguish existing research software from a validated real model |
| Export blocked by account/terminal flags | Reproduced same two failing flags after trustworthy exact-image query | Keep export blocked |
| UTC+2/+3 broker clock | H1 activity pattern reproduced; official API UTC convention conflicts with indirect observations | Hypothesis; no dataset promotion |
| Supabase integration ready | Local SQL proposal exists; inspected Android/backend source has no active client | No cloud-readiness claim |
| Master-agent architecture complete | Claude document is a proposed role/workflow design | No implemented orchestration claimed |

WorkBuddy documents have stale intermediate test counts/checklists (for example,
642/492 in part of the ledger) and an older resume-branch instruction. Current
Git objects and the actual fresh runs take precedence. The M1 report chain also
contains the additional SmartHub documentation commit 8998f0f beyond the three
originally listed commits.

M1 review and M2 authorship are separate assurances: Codex independently tested
WorkBuddy's additions, then authored corrections. Codex has not independently
approved its own M2 changes. Claude or another independent reviewer must assess
the two local patches before WorkBuddy integrates them. No agent message was sent
and no integration or publication was performed.
