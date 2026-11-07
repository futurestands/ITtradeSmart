"""FTMO phase-1 account-aware SIMULATION only. No broker or execution API.

Uses the existing synthetic-only compliance evaluator. No caller-provided
BROKER_READ_ONLY label is promoted into trusted live account verification.
Open-risk reservations mean ADDITIONAL loss from present equity to all existing
position/pending stops plus costs, not floating loss already included in equity.
"""
from dataclasses import dataclass
from datetime import datetime,timedelta,timezone
from decimal import Decimal,ROUND_FLOOR
from typing import Optional,Tuple
import re
from compliance_engine import (AccountModel,AccountObservation,ComplianceStatus,
                               DataOrigin,evaluate_compliance)

D=Decimal
PROFILE='FTMO_2_STEP_CHALLENGE_PHASE1'

def money(value,positive=False):
    return (type(value) is D and value.is_finite()
        and (value.is_zero() or -12<=value.adjusted()<=11)
        and (value>0 if positive else value>=0))

def utc(value):
    return isinstance(value,datetime) and value.tzinfo is not None and value.utcoffset()==timedelta(0)

@dataclass(frozen=True)
class PlanningEvidence:
    account_ref: str
    rule_account_ref: str
    ledger_account_ref: str
    profile: str
    ledger_observed_at: datetime
    ledger_session_start: datetime
    entries_and_entry_reservations_today: int
    ledger_complete: bool
    rules_reviewed_at: datetime
    rules_checked_at: datetime
    approved_source_hash: str
    current_source_hash: str
    purchased_terms_match: bool
    other_rule_gates_clear: bool
    additional_open_and_pending_risk: Optional[Decimal]
    risk_engine_cash_cap: Decimal
    personal_daily_remaining: Decimal
    safety_buffer: Decimal
    free_margin: Decimal

@dataclass(frozen=True)
class SimulationContract:
    symbol: str
    currency: str
    observed_at: datetime
    profile_complete: bool
    entry: Decimal
    stop: Decimal
    target: Decimal
    side: str
    tick_size: Decimal
    # Nominal stop loss from executable entry; currency must match the account.
    stop_loss_per_lot: Decimal
    # Only costs NOT already included above: avoids double-counting bid/ask spread.
    additional_cost_per_lot: Decimal
    margin_per_lot: Decimal
    volume_min: Decimal
    volume_max: Decimal
    volume_step: Decimal

@dataclass(frozen=True)
class AccountPlan:
    status: str
    reasons: Tuple[str,...]
    configured_cash_ceiling: Optional[Decimal]=None
    simulated_cash_budget: Optional[Decimal]=None
    simulated_lots: Optional[Decimal]=None
    simulated_cash_risk: Optional[Decimal]=None
    phase1_target_balance: Optional[Decimal]=None
    closed_profit_remaining: Optional[Decimal]=None
    execution_authorized: bool=False
    live_verified: bool=False
    decision: str='NO_TRADE'
    mode: str='RESEARCH_ONLY'
    model_status: str='MODEL_NOT_READY'
    scope: str='SYNTHETIC_PLANNING_NOT_FULL_FIRM_COMPLIANCE'

def _blocked(code): return AccountPlan('BLOCKED',(code,))

def _hash(value):
    return isinstance(value,str) and len(value)==64 and all(c in '0123456789abcdef' for c in value)

def _on_grid(volume,minimum,step):
    return volume>=minimum and (volume-minimum)%step==0

def plan_ftmo_phase1(snapshot:AccountObservation,evidence:PlanningEvidence,
                     contract:SimulationContract,*,now_utc:datetime,
                     max_snapshot_age_seconds:int=120,max_rule_age_seconds:int=86400,
                     risk_fraction:Decimal=D('0.005'),max_daily_entries:int=3)->AccountPlan:
    """User policy: <=0.5% of original size, <=3 daily entry reservations.
    Stricter settings are allowed; raising either ceiling is not supported.
    A completed plan is a simulation, never a suggestion to execute it.
    """
    if not isinstance(snapshot,AccountObservation) or not isinstance(evidence,PlanningEvidence) or not isinstance(contract,SimulationContract):
        return _blocked('INVALID_TYPED_EVIDENCE')
    if snapshot.model is not AccountModel.FTMO_2_STEP or evidence.profile!=PROFILE:
        return _blocked('WRONG_PROGRAMME_OR_PHASE')
    if (not money(risk_fraction,True) or risk_fraction>D('0.005')
        or type(max_daily_entries) is not int or not 1<=max_daily_entries<=3):
        return _blocked('PERSONAL_CEILING_CANNOT_BE_RAISED')
    if type(max_snapshot_age_seconds) is not int or not 1<=max_snapshot_age_seconds<=3600:
        return _blocked('INVALID_FRESHNESS_POLICY')
    if type(max_rule_age_seconds) is not int or not 1<=max_rule_age_seconds<=86400:
        return _blocked('INVALID_RULE_FRESHNESS_POLICY')
    compliance=evaluate_compliance(snapshot,now_utc=now_utc,max_age_seconds=max_snapshot_age_seconds)
    if compliance.status is ComplianceStatus.UNKNOWN:
        return _blocked(compliance.reason_codes[0])
    if snapshot.origin is not DataOrigin.SYNTHETIC_TEST:
        return _blocked('LIVE_ADAPTER_NOT_IMPLEMENTED')
    if compliance.status is not ComplianceStatus.WITHIN_LOSS_LIMITS:
        return _blocked('LOSS_LIMIT_WARNING_OR_BREACH')
    if not isinstance(evidence.account_ref,str) or not evidence.account_ref.strip() or not (
        evidence.account_ref==evidence.rule_account_ref==evidence.ledger_account_ref):
        return _blocked('ACCOUNT_BINDING_MISMATCH')
    if evidence.ledger_observed_at!=snapshot.observed_at_utc or evidence.ledger_session_start!=snapshot.session_start_at_utc:
        return _blocked('LEDGER_WINDOW_MISMATCH')
    if evidence.ledger_complete is not True:
        return _blocked('INCOMPLETE_ENTRY_AND_POSITION_LEDGER')
    if type(evidence.entries_and_entry_reservations_today) is not int or evidence.entries_and_entry_reservations_today<0:
        return _blocked('INVALID_ENTRY_COUNTER')
    if evidence.entries_and_entry_reservations_today>=max_daily_entries:
        return _blocked('DAILY_ENTRY_CAP_REACHED')
    if not all(utc(t) for t in (now_utc,evidence.rules_checked_at,evidence.rules_reviewed_at)):
        return _blocked('RULE_TIME_UNVERIFIED')
    if not evidence.rules_reviewed_at<=evidence.rules_checked_at<=now_utc or (
        now_utc-evidence.rules_checked_at).total_seconds()>max_rule_age_seconds:
        return _blocked('STALE_OR_FUTURE_RULE_CHECK')
    if not _hash(evidence.approved_source_hash) or not _hash(evidence.current_source_hash):
        return _blocked('RULE_SOURCE_FINGERPRINT_MISSING')
    if evidence.approved_source_hash!=evidence.current_source_hash:
        return _blocked('RULE_SOURCE_CHANGED_REVIEW_REQUIRED')
    if evidence.purchased_terms_match is not True or evidence.other_rule_gates_clear is not True:
        return _blocked('ACCOUNT_TERMS_OR_OTHER_RULES_UNVERIFIED')
    values=(evidence.additional_open_and_pending_risk,evidence.risk_engine_cash_cap,
            evidence.personal_daily_remaining,evidence.safety_buffer,evidence.free_margin)
    if any(not money(v) for v in values) or evidence.safety_buffer<=0:
        return _blocked('MISSING_RISK_RESERVATION_OR_BUDGET')
    if contract.profile_complete is not True or contract.currency!=snapshot.account_currency:
        return _blocked('INSTRUMENT_PROFILE_OR_CURRENCY_UNVERIFIED')
    if not isinstance(contract.symbol,str) or not re.fullmatch(r'[A-Za-z0-9._-]{2,32}',contract.symbol):
        return _blocked('INSTRUMENT_SYMBOL_MISSING_OR_INVALID')
    if not utc(contract.observed_at) or not 0<=(now_utc-contract.observed_at).total_seconds()<=max_snapshot_age_seconds:
        return _blocked('STALE_OR_FUTURE_INSTRUMENT_PROFILE')
    positive=(contract.entry,contract.stop,contract.target,contract.tick_size,
              contract.stop_loss_per_lot,contract.margin_per_lot,contract.volume_min,
              contract.volume_max,contract.volume_step)
    if any(not money(v,True) for v in positive) or not money(contract.additional_cost_per_lot):
        return _blocked('INVALID_CONTRACT_ECONOMICS')
    if contract.volume_min>contract.volume_max or contract.side not in ('BUY','SELL'):
        return _blocked('INVALID_CONTRACT_OR_DIRECTION')
    if any(price%contract.tick_size!=0 for price in (contract.entry,contract.stop,contract.target)):
        return _blocked('PRICE_NOT_ON_TICK_GRID')
    if not ((contract.side=='BUY' and contract.stop<contract.entry<contract.target)
            or (contract.side=='SELL' and contract.target<contract.entry<contract.stop)):
        return _blocked('STOP_OR_TARGET_WRONG_DIRECTION')
    target=snapshot.initial_capital*D('1.10')
    remaining=max(D('0'),target-snapshot.balance)
    if remaining==0:
        return _blocked('PROFIT_TARGET_REACHED_STOP_FOR_PHASE_REVIEW')
    ceiling=snapshot.initial_capital*risk_fraction
    # Equity already reflects present floating P/L and incurred costs. Reserve
    # only additional future downside from that same equity snapshot.
    reserve=evidence.additional_open_and_pending_risk
    headroom=min(compliance.daily_remaining,compliance.total_remaining)-reserve-evidence.safety_buffer
    personal=evidence.personal_daily_remaining-reserve-evidence.safety_buffer
    budget=min(ceiling,evidence.risk_engine_cash_cap,headroom,personal)
    if budget<=0:
        return _blocked('NO_BUFFERED_RISK_HEADROOM')
    unit_risk=contract.stop_loss_per_lot+contract.additional_cost_per_lot
    raw=min(budget/unit_risk,contract.volume_max,evidence.free_margin/contract.margin_per_lot)
    if raw<contract.volume_min:
        return _blocked('MINIMUM_VOLUME_EXCEEDS_BUDGET_OR_MARGIN')
    steps=((raw-contract.volume_min)/contract.volume_step).to_integral_value(rounding=ROUND_FLOOR)
    lots=contract.volume_min+steps*contract.volume_step
    cash=lots*unit_risk
    if cash>budget or lots*contract.margin_per_lot>evidence.free_margin:
        return _blocked('CONSERVATIVE_ROUNDING_FAILED')
    return AccountPlan('SIMULATION_ONLY',('NO_EXECUTION_PERMISSION','STOPS_DO_NOT_GUARANTEE_MAXIMUM_LOSS'),
        ceiling,budget,lots,cash,target,remaining)

def simulated_partial_volumes(total:Decimal,fractions:Tuple[Decimal,...],*,
                              minimum:Decimal,step:Decimal,permission:bool)->Tuple[Decimal,...]:
    """Volume feasibility only; no trigger prices, fills, profit or stop changes.
    Partial permission must be separately reviewed for firm/platform/news rules.
    """
    if permission is not True:
        raise ValueError('PARTIAL_RULE_PERMISSION_UNVERIFIED')
    if not all(money(v,True) for v in (total,minimum,step)) or not _on_grid(total,minimum,step):
        raise ValueError('INVALID_INITIAL_VOLUME')
    if not isinstance(fractions,tuple) or len(fractions)<2 or any(not money(v,True) for v in fractions) or sum(fractions)!=D('1'):
        raise ValueError('COMPLETE_PARTIAL_SCHEDULE_REQUIRED')
    if any(total*fraction<minimum for fraction in fractions):
        raise ValueError('REQUESTED_PARTIAL_BELOW_MINIMUM')
    result=[]; remaining=total
    for fraction in fractions[:-1]:
        intended=total*fraction
        if intended<minimum: raise ValueError('PARTIAL_BELOW_MINIMUM')
        close=minimum+((intended-minimum)/step).to_integral_value(rounding=ROUND_FLOOR)*step
        remaining-=close
        if not _on_grid(close,minimum,step) or not _on_grid(remaining,minimum,step):
            raise ValueError('PARTIAL_OR_REMAINDER_NOT_TRADABLE')
        result.append(close)
    result.append(remaining)
    return tuple(result)
