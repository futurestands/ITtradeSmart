from datetime import datetime,timedelta,timezone
import pytest
from nas100.discipline import CHECKS,review_entry_intent

NOW=datetime(2025,1,2,12,tzinfo=timezone.utc)
def review(action='BUY',checks=None,**extra):
    options=dict(decision_at=NOW,evidence_at=NOW,max_evidence_age=timedelta(minutes=5),plan_id='synthetic-plan')
    options.update(extra)
    return review_entry_intent(action,{k:True for k in CHECKS} if checks is None else checks,**options)

@pytest.mark.parametrize('action',['BUY','SELL','WAIT'])
def test_even_complete_checklist_never_authorizes_trading(action):
    result=review(action)
    assert result.decision=='NO_TRADE' and result.trade_authorized is False
    assert result.model_trained is False and result.probability is None
    assert result.execution_mode=='RESEARCH_ONLY' and result.model_status=='MODEL_NOT_READY'

@pytest.mark.parametrize('check',tuple(CHECKS))
def test_each_failed_gate_blocks_entry_with_explanation(check):
    checks={k:True for k in CHECKS}; checks[check]=False
    result=review(checks=checks)
    assert result.status=='ENTRY_INTENT_VIOLATES_RULES'
    assert CHECKS[check][0] in result.blockers and CHECKS[check][1] in result.feedback

def test_waiting_with_missing_data_is_not_punished():
    result=review('WAIT',{},evidence_at=None,plan_id=None)
    assert result.status=='DISCIPLINED_WAIT'
    assert 'EVIDENCE_TIME_MISSING' in result.blockers and len(result.missing_checks)==len(CHECKS)

def test_missing_gate_is_not_a_pass():
    checks={k:True for k in CHECKS}; del checks['risk_engine_passed']
    result=review(checks=checks)
    assert result.status=='INCOMPLETE_CHECKLIST'
    assert 'MISSING_EVIDENCE:risk_engine_passed' in result.blockers

@pytest.mark.parametrize('value',[1,0,'true','false',[],{}])
def test_truthy_and_falsey_non_boolean_evidence_is_rejected(value):
    with pytest.raises(ValueError): review(checks={'risk_engine_passed':value})

def test_unknown_check_cannot_override_safety():
    with pytest.raises(ValueError): review(checks={'approve_trade':True})

@pytest.mark.parametrize('at,blocker',[(None,'EVIDENCE_TIME_MISSING'),
    (NOW+timedelta(seconds=1),'FUTURE_EVIDENCE'),(NOW-timedelta(minutes=6),'STALE_EVIDENCE')])
def test_current_point_in_time_evidence_is_required(at,blocker):
    result=review(evidence_at=at)
    assert result.status=='INCOMPLETE_CHECKLIST' and blocker in result.blockers

def test_missing_plan_blocks_entry():
    assert 'PLAN_MISSING' in review(plan_id=None).blockers

def test_naive_clock_rejected():
    with pytest.raises(ValueError): review(decision_at=NOW.replace(tzinfo=None))

def test_input_hash_covers_action_evidence_and_plan():
    original=review()
    assert original.input_hash==review().input_hash
    assert original.input_hash!=review(action='WAIT').input_hash
    assert original.input_hash!=review(plan_id='different-synthetic-plan').input_hash
    assert original.input_hash!=review(evidence_at=NOW-timedelta(seconds=1)).input_hash

def test_caller_input_not_modified():
    checks={'cooldown_clear':False}; before=checks.copy()
    review(checks=checks)
    assert checks==before

def test_curriculum_is_explicitly_synthetic_not_performance_or_fitted_model():
    import importlib.util
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'tools/prepare_discipline_curriculum.py'
    spec=importlib.util.spec_from_file_location('discipline_curriculum_test',path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    examples=module.build_curriculum()
    assert len(examples)==21 and len({r['scenario_id'] for r in examples})==21
    assert all(r['synthetic'] and not r['human_reviewed'] and not r['estimator_fitted'] for r in examples)
    assert all(not r['market_performance_evidence'] and not r['expected_review']['trade_authorized'] for r in examples)
    assert any(r['expected_review']['status']=='DISCIPLINED_WAIT' for r in examples)
