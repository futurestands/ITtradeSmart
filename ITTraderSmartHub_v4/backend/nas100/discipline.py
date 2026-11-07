"""Offline entry-discipline coaching; no prediction, training or execution.

Checklist inputs are caller-supplied evidence, not independent certification.
The existing risk engine remains authoritative. Passing this review can never
authorize a trade or change RESEARCH_ONLY / MODEL_NOT_READY / NO_TRADE.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

POLICY_VERSION='discipline-entry-v1'
CHECKS=MappingProxyType({
    'risk_engine_passed':('RISK_ENGINE_REJECTED','Respect the existing risk-engine rejection.'),
    'loss_limit_clear':('LOSS_LIMIT_REACHED','Stand aside when the configured loss limit is reached.'),
    'cooldown_clear':('COOLDOWN_ACTIVE','Wait for the configured cooldown; do not chase a recovery.'),
    'exposure_clear':('EXPOSURE_LIMIT','Respect the existing exposure limit.'),
    'stop_present':('STOP_MISSING','Record the planned invalidation and stop before reviewing an entry.'),
    'stop_not_widened':('STOP_WIDENED','Do not enlarge the planned loss to avoid accepting invalidation.'),
    'not_chasing':('CHASING_ENTRY','Wait for the predefined setup rather than chasing a move.'),
    'setup_confirmed':('SETUP_UNCONFIRMED','Wait for the predefined setup to be confirmed.'),
    'session_allowed':('SESSION_BLOCKED','Respect the verified session restriction.'),
    'event_clear':('EVENT_BLOCKED','Respect the event-risk gate.'),
    'data_verified':('DATA_UNVERIFIED','Missing or unverified data cannot justify entry.'),
    'costs_verified':('COSTS_UNVERIFIED','Missing cost evidence cannot justify entry.'),
})

def _utc(value):
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('An aware timestamp is required')
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class DisciplineReview:
    status: str
    proposed_action: str
    blockers: Tuple[str,...]
    failed_checks: Tuple[str,...]
    missing_checks: Tuple[str,...]
    feedback: Tuple[str,...]
    input_hash: str
    policy_version: str = POLICY_VERSION
    decision: str = 'NO_TRADE'
    trade_authorized: bool = False
    model_trained: bool = False
    probability: Optional[float] = None
    execution_mode: str = 'RESEARCH_ONLY'
    model_status: str = 'MODEL_NOT_READY'
    evidence_scope: str = 'CALLER_SUPPLIED_CHECKLIST_NOT_INDEPENDENT_CERTIFICATION'


def review_entry_intent(action: str, checks: Mapping[str,Optional[bool]], *,
                        decision_at: datetime, evidence_at: Optional[datetime],
                        max_evidence_age: timedelta, plan_id: Optional[str]=None) -> DisciplineReview:
    """Assess a new-entry intention or WAIT, not management of an open position.
    No numeric financial limits are invented: callers must use the existing
    engine/policy for loss, exposure, session, costs and cooldown checks.
    """
    if action not in ('BUY','SELL','WAIT'):
        raise ValueError('Action must be BUY, SELL or WAIT')
    if not isinstance(checks,Mapping) or set(checks)-set(CHECKS):
        raise ValueError('Unknown checklist field')
    if any(value is not None and type(value) is not bool for value in checks.values()):
        raise ValueError('Evidence must be true, false or unknown; no truthy coercion')
    if plan_id is not None and (not isinstance(plan_id,str) or not plan_id.strip()):
        raise ValueError('Plan ID must be a nonempty string or unknown')
    if not isinstance(max_evidence_age,timedelta) or max_evidence_age < timedelta(0):
        raise ValueError('An explicit nonnegative evidence-age limit is required')
    decision=_utc(decision_at)
    observed=_utc(evidence_at) if evidence_at is not None else None
    snapshot={key:checks.get(key) for key in CHECKS}
    failed=tuple(key for key,value in snapshot.items() if value is False)
    missing=tuple(key for key,value in snapshot.items() if value is None)
    blockers=[]; feedback=[]
    if plan_id is None:
        blockers.append('PLAN_MISSING'); feedback.append('Write the entry plan before considering an entry.')
    if observed is None:
        blockers.append('EVIDENCE_TIME_MISSING')
    elif observed>decision:
        blockers.append('FUTURE_EVIDENCE')
    elif decision-observed>max_evidence_age:
        blockers.append('STALE_EVIDENCE')
    for key in failed:
        code,message=CHECKS[key]; blockers.append(code); feedback.append(message)
    for key in missing:
        blockers.append('MISSING_EVIDENCE:'+key)
    if missing or any(code in blockers for code in ('EVIDENCE_TIME_MISSING','FUTURE_EVIDENCE','STALE_EVIDENCE')):
        feedback.append('Obtain current verified checklist evidence; do not infer a pass.')
    if action=='WAIT':
        status='DISCIPLINED_WAIT'
        feedback.insert(0,'Waiting is a valid entry decision; there is no requirement to trade.')
    elif failed:
        status='ENTRY_INTENT_VIOLATES_RULES'
    elif blockers:
        status='INCOMPLETE_CHECKLIST'
    else:
        status='CHECKLIST_COMPLETE_RESEARCH_ONLY'
        feedback.append('The checklist is complete for research review; it does not authorize a trade.')
    payload={'policy_version':POLICY_VERSION,'action':action,'checks':snapshot,'plan_id':plan_id,
             'decision_at':decision.isoformat(),'evidence_at':observed.isoformat() if observed else None,
             'max_evidence_age_microseconds':max_evidence_age//timedelta(microseconds=1)}
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return DisciplineReview(status,action,tuple(blockers),failed,missing,tuple(feedback),digest)
