"""Research-only context alignment; no model fit, signal, account or order API.

Text references explain candidate features. They are not market observations or
training labels. A private ingestion audit must certify a numerical observation;
the verified flag must never be copied from an untrusted HTTP request.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from typing import Iterable, Optional


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('An aware timestamp is required')
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ContextSample:
    feature: str
    value: float
    units: str
    observed_at: datetime
    available_at: datetime
    source_id: str
    verified: bool = False

    def __post_init__(self):
        if not all(isinstance(v,str) and v.strip() for v in (self.feature,self.units,self.source_id)):
            raise ValueError('Feature, units and provenance are required')
        if type(self.value) not in (int,float) or not math.isfinite(self.value):
            raise ValueError('A finite numeric observation is required')
        if type(self.verified) is not bool:
            raise ValueError('Verification must be an explicit boolean')
        if _utc(self.available_at) < _utc(self.observed_at):
            raise ValueError('An observed value cannot be available before observation')


@dataclass(frozen=True)
class ContextResult:
    value: Optional[float]
    units: Optional[str]
    observed_at: Optional[datetime]
    available_at: Optional[datetime]
    source_id: Optional[str]
    reason: str
    label: str = 'RESEARCH_CONTEXT_NOT_A_TRADE_DECISION'


def context_asof(feature: str, decision_at: datetime, samples: Iterable[ContextSample],
                 *, max_age: timedelta) -> ContextResult:
    """Use only certified data published by decision time; never forward-fill
    beyond an explicit age limit, backfill a revision, or use an old revision as
    a fresh observation. Newer observation periods take priority over revisions
    of older periods. No availability date is inferred from a daily date label.
    """
    decision=_utc(decision_at)
    if not isinstance(feature,str) or not feature.strip():
        raise ValueError('Feature is required')
    if not isinstance(max_age,timedelta) or max_age < timedelta(0):
        raise ValueError('An explicit nonnegative age limit is required')
    matching=[s for s in samples if s.feature==feature]
    verified=[s for s in matching if s.verified]
    usable=[s for s in verified if _utc(s.available_at)<=decision]
    if not usable:
        reason='NOT_YET_AVAILABLE' if verified else ('UNVERIFIED_CONTEXT' if matching else 'MISSING_CONTEXT')
        return ContextResult(None,None,None,None,None,reason)
    latest=max((_utc(s.observed_at),_utc(s.available_at)) for s in usable)
    selected=[s for s in usable if (_utc(s.observed_at),_utc(s.available_at))==latest]
    if len({(s.value,s.units) for s in selected})!=1:
        raise ValueError('Conflicting simultaneous source observations')
    sample=sorted(selected,key=lambda s:s.source_id)[0]
    if decision-_utc(sample.observed_at)>max_age:
        return ContextResult(None,None,None,None,None,'STALE_CONTEXT')
    return ContextResult(float(sample.value),sample.units,_utc(sample.observed_at),
                         _utc(sample.available_at),sample.source_id,'AVAILABLE')
