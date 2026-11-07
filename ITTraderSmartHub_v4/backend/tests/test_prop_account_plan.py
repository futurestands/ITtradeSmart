from dataclasses import replace
from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
import pytest
from compliance_engine import AccountModel,AccountObservation,DataOrigin
from prop_account_plan import (PlanningEvidence,SimulationContract,PROFILE,
    plan_ftmo_phase1,simulated_partial_volumes)

NOW=datetime(2026,11,7,12,tzinfo=timezone.utc)
START=datetime(2026,11,6,23,tzinfo=timezone.utc)
def fixtures(size='10000'):
    s=AccountObservation(AccountModel.FTMO_2_STEP,D(size),D(size),D(size),D(size),
        NOW,START,60,60,DataOrigin.SYNTHETIC_TEST,'USD',True,True,True)
    e=PlanningEvidence('synthetic-account','synthetic-account','synthetic-account',PROFILE,
        NOW,START,0,True,NOW,NOW,'a'*64,'a'*64,True,True,D('0'),D('10000'),
        D('10000'),D('5'),D('10000'))
    c=SimulationContract('SYNTHETIC_US100','USD',NOW,True,D('20000'),D('19900'),D('20200'),
        'BUY',D('1'),D('100'),D('10'),D('100'),D('.01'),D('100'),D('.01'))
    return s,e,c
def plan(s=None,e=None,c=None,**kwargs):
    base=fixtures(); return plan_ftmo_phase1(s or base[0],e or base[1],c or base[2],now_utc=NOW,**kwargs)

@pytest.mark.parametrize('size,ceiling',[('5000','25'),('10000','50'),('100000','500')])
def test_account_size_controls_ceiling_not_lot_guess(size,ceiling):
    s,e,c=fixtures(size); result=plan(s,e,c)
    assert result.status=='SIMULATION_ONLY' and result.configured_cash_ceiling==D(ceiling)
    assert result.simulated_cash_risk<=D(ceiling)
    assert result.execution_authorized is False and result.live_verified is False
    assert result.decision=='NO_TRADE' and result.model_status=='MODEL_NOT_READY'

def test_profits_do_not_raise_original_capital_ceiling():
    s,e,c=fixtures(); s=replace(s,balance=D('10500'),equity=D('10500'))
    assert plan(s,e,c).configured_cash_ceiling==D('50')

def test_existing_risk_engine_cap_is_stricter_than_personal_ceiling():
    s,e,c=fixtures(); result=plan(s,replace(e,risk_engine_cash_cap=D('12')),c)
    assert result.simulated_cash_budget==D('12') and result.simulated_cash_risk<=D('12')

def test_floating_loss_existing_exposure_and_buffer_reduce_headroom():
    s,e,c=fixtures(); s=replace(s,equity=D('9700'))
    # Daily floor=9500; current equity already includes the floating loss.
    result=plan(s,replace(e,additional_open_and_pending_risk=D('180')),c)
    assert result.simulated_cash_budget==D('15')

def test_personal_daily_budget_reserves_existing_risk():
    s,e,c=fixtures(); result=plan(s,replace(e,personal_daily_remaining=D('40'),additional_open_and_pending_risk=D('20')),c)
    assert result.simulated_cash_budget==D('15')

def test_costs_are_inside_budget_and_volume_rounds_down():
    result=plan(); assert result.simulated_lots==D('.45')
    assert result.simulated_cash_risk==D('49.50')

def test_insufficient_margin_reduces_volume():
    s,e,c=fixtures(); result=plan(s,replace(e,free_margin=D('10')),c)
    assert result.simulated_lots==D('.10')

def test_minimum_lot_never_rounds_up_over_budget():
    s,e,c=fixtures(); result=plan(s,replace(e,risk_engine_cash_cap=D('.5')),c)
    assert result.status=='BLOCKED' and result.simulated_lots is None

@pytest.mark.parametrize('count',[3,4,30])
def test_three_entries_is_a_cap_even_after_partial_closes(count):
    s,e,c=fixtures(); assert plan(s,replace(e,entries_and_entry_reservations_today=count),c).reasons==('DAILY_ENTRY_CAP_REACHED',)

def test_zero_entries_valid_and_third_entry_can_be_simulated():
    s,e,c=fixtures()
    assert plan(s,replace(e,entries_and_entry_reservations_today=2),c).status=='SIMULATION_ONLY'

@pytest.mark.parametrize('field,value,reason',[
    ('rule_account_ref','different','ACCOUNT_BINDING_MISMATCH'),
    ('ledger_account_ref','different','ACCOUNT_BINDING_MISMATCH'),
    ('ledger_complete',False,'INCOMPLETE_ENTRY_AND_POSITION_LEDGER'),
    ('current_source_hash','b'*64,'RULE_SOURCE_CHANGED_REVIEW_REQUIRED'),
    ('current_source_hash','','RULE_SOURCE_FINGERPRINT_MISSING'),
    ('purchased_terms_match',False,'ACCOUNT_TERMS_OR_OTHER_RULES_UNVERIFIED'),
    ('other_rule_gates_clear',False,'ACCOUNT_TERMS_OR_OTHER_RULES_UNVERIFIED'),
    ('additional_open_and_pending_risk',None,'MISSING_RISK_RESERVATION_OR_BUDGET'),
    ('rules_checked_at',NOW-timedelta(days=2),'STALE_OR_FUTURE_RULE_CHECK'),
    ('rules_checked_at',NOW+timedelta(seconds=1),'STALE_OR_FUTURE_RULE_CHECK'),
    ('ledger_observed_at',NOW-timedelta(seconds=1),'LEDGER_WINDOW_MISMATCH'),
])
def test_missing_conflicting_or_changed_evidence_blocks(field,value,reason):
    s,e,c=fixtures(); assert plan(s,replace(e,**{field:value}),c).reasons==(reason,)

def test_broker_label_cannot_fake_an_authenticated_adapter():
    s,e,c=fixtures(); result=plan(replace(s,origin=DataOrigin.BROKER_READ_ONLY),e,c)
    assert result.reasons==('BROKER_ADAPTER_NOT_IMPLEMENTED',)

def test_no_guessing_another_ftmo_model():
    s,e,c=fixtures(); assert plan(replace(s,model=AccountModel.FTMO_1_STEP),e,c).status=='BLOCKED'

@pytest.mark.parametrize('change',[{'risk_fraction':D('.01')},{'max_daily_entries':4}])
def test_personal_caps_cannot_be_silently_raised(change):
    assert plan(**change).reasons==('PERSONAL_CEILING_CANNOT_BE_RAISED',)

def test_target_uses_closed_balance_and_is_not_an_auto_pass():
    s,e,c=fixtures(); result=plan(s,replace(e,free_margin=D('1000')),c)
    assert result.phase1_target_balance==D('11000') and result.closed_profit_remaining==D('1000')
    assert plan(replace(s,balance=D('11000'),equity=D('11000')),e,c).reasons==('PROFIT_TARGET_REACHED_STOP_FOR_PHASE_REVIEW',)

@pytest.mark.parametrize('changes',[{'stop':D('20100')},{'target':D('19950')},
    {'entry':D('20000.1')},{'currency':'EUR'},{'symbol':''}, {'profile_complete':False},
    {'observed_at':NOW-timedelta(minutes=3)}])
def test_invalid_or_stale_instrument_data_has_no_lots(changes):
    s,e,c=fixtures(); result=plan(s,e,replace(c,**changes))
    assert result.status=='BLOCKED' and result.simulated_lots is None

def test_partial_close_sizes_and_remainder_are_tradable():
    assert simulated_partial_volumes(D('.10'),(D('.5'),D('.5')),minimum=D('.01'),step=D('.01'),permission=True)==(D('.05'),D('.05'))

@pytest.mark.parametrize('total,fractions',[
    (D('.01'),(D('.5'),D('.5'))),(D('.03'),(D('.9'),D('.1'))),
    (D('.10'),(D('.6'),D('.6'))),
])
def test_too_small_or_overallocated_partial_schedule_rejected(total,fractions):
    with pytest.raises(ValueError): simulated_partial_volumes(total,fractions,minimum=D('.01'),step=D('.01'),permission=True)

def test_unknown_partial_rule_permission_is_not_allowed():
    with pytest.raises(ValueError): simulated_partial_volumes(D('.1'),(D('.5'),D('.5')),minimum=D('.01'),step=D('.01'),permission=False)
