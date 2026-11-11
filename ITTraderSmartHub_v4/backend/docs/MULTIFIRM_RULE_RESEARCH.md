# Changeable accounts and official-source rule research

An account does not need to be permanently selected during development.
`prop_rule_research.py` adds a local research foundation for FTMO, FundedNext,
GOAT and FundingPips. Existing compliance, account planning, risk engine,
authentication, Android and cloud deployment behavior remain unchanged.

## Intended account workflow

1. Add/select an account with an opaque private local reference. Confirm firm,
   exact programme, current stage, currency, original advertised size and
   applicable purchase/creation/legacy-terms version. MT5 metadata alone cannot
   attest all these fields. Do not infer original size from current balance.
2. Research the firm's official sources without sending account identifiers,
   credentials, balance or other private account data to the search/fetch service.
   The current CLI fetches fixed server-controlled official HTTPS entry points;
   it is not a general web-search service or complete programme-rule extractor.
3. Match candidate rules against the account's actual terms. Store a reviewed,
   versioned rule set and source evidence separately from the research candidate.
   The current module does not implement policy approval or persistence.
4. Recheck before accepting a fresh plan. The research gate rejects checks older
   than its explicit freshness limit (at most 24 hours), future timestamps,
   missing fingerprints, changed sources or mismatched firms. Page changes can
   be cosmetic; a hash difference requires review, not an automatic rule update.
5. Account/programme/stage/currency/size/terms changes invalidate the earlier
   binding. Switching back requires a fresh source check; no cached account's
   permission or risk reservation should transfer to a different account.

An unchanged page still does not approve a policy. Source pages can be indexes,
partial documents, stale public summaries or bot-challenge HTML. Fetching one
cannot certify complete programme coverage. Actual news rules, reset clocks,
drawdown method, consistency, automated-trading/hosting permission, partial exits
and applicable historical terms must be explicitly reviewed. Web text is inert
research evidence, not an instruction to the software or an executable policy.

## Implemented boundary and checks

`AccountRuleContext` holds an explicit typed research context. Every field is
included in equality checks against the reviewed context. `review_source_binding`
never returns execution authorization or verified rules, including on success.
All results retain RESEARCH_ONLY, MODEL_NOT_READY and NO_TRADE.

`tools/check_prop_rule_sources.py --source <source-id>` performs an on-demand
read-only fetch. Source IDs come from a fixed immutable registry; arbitrary URLs
and redirects are refused. Requests use TLS hostname/certificate verification
against the OS trust store, a timeout and a 2 MB response limit. Failures withhold
raw diagnostic details and do not invent source hashes or fall back to permissive
rules. No external account credentials are accepted.

Official entry points checked on 11 November 2026:

- FTMO: https://ftmo.com/en/trading-objectives/
- FundedNext: https://help.fundednext.com/en/
- GOAT: https://help.goatfundedtrader.com/en/collections/11969353-rules
- FundingPips: https://help.fundingpips.com/hc/en-us/articles/47328410434065-Responsible-Trading-Policy

The live CLI retrieved HTML fingerprints for the first three; FundingPips
returned an HTTP error and remained unavailable. None were marked approved or
complete. In-agent official-source research separately reached FundingPips's
public policy through the web research tool; that does not imply the app's
standalone fetch succeeded or can bypass provider access restrictions.

GOAT's official minimum-holding-time page demonstrates why an effective terms
cohort is necessary: its funded-account rule distinguishes purchase dates.
https://help.goatfundedtrader.com/en/articles/12849041-what-is-the-minimum-holding-time-for-trades

## Verification and remaining implementation

110 selected tests passed: new multi-firm research, existing account planning
and existing compliance. No trades, database migrations, deployments, Git pushes
or phone changes occurred. Initial test collection using an ML environment
failed because the legacy FTMO checker requires certifi. The new module uses
standard-library verified TLS and adds no dependency. The final selected suite
excluded the unchanged legacy checker; it was not claimed as rerun/passing.

Still needed: authenticated account-management UI/API, private persistence of
versioned policy reviews, programme-specific source coverage/extraction with
citations, a reviewed-policy approval path, scheduling and safe change alerts,
and routing reviewed supported policies into the existing risk engine. No new
endpoint, background scheduler, rule auto-approval or APK feature is implemented
by this research-layer change. Do not expose a public arbitrary-URL fetch API.
The user ceilings remain at most 0.5% original-size planned risk and three daily
entries, subject to stricter account rules and existing risk-engine decisions.
