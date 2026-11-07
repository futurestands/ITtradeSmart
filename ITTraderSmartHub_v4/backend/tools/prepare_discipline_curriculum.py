"""Create rule-labelled synthetic coaching examples, never fit an estimator."""
from dataclasses import asdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
import argparse
import json
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from nas100.discipline import CHECKS,review_entry_intent


def build_curriculum():
    now=datetime(2025,1,2,12,tzinfo=timezone.utc)
    base={key:True for key in CHECKS}
    cases=[('wait_with_complete_plan','WAIT',base,now,'synthetic-plan'),
           ('wait_for_missing_evidence','WAIT',{},None,None),
           ('complete_buy_checklist','BUY',base,now,'synthetic-plan'),
           ('complete_sell_checklist','SELL',base,now,'synthetic-plan')]
    for key in CHECKS:
        checks=dict(base); checks[key]=False
        cases.append(('breach_'+key,'BUY',checks,now,'synthetic-plan'))
    missing=dict(base); missing.pop('risk_engine_passed')
    cases.extend([
        ('missing_risk_evidence','BUY',missing,now,'synthetic-plan'),
        ('missing_plan','BUY',base,now,None),
        ('future_evidence','SELL',base,now+timedelta(seconds=1),'synthetic-plan'),
        ('stale_evidence','BUY',base,now-timedelta(minutes=6),'synthetic-plan'),
        ('revenge_entry_after_limit','BUY',dict(base,cooldown_clear=False,loss_limit_clear=False),now,'synthetic-plan'),
    ])
    result=[]
    for name,action,checks,evidence_at,plan in cases:
        review=review_entry_intent(action,checks,decision_at=now,evidence_at=evidence_at,
            max_evidence_age=timedelta(minutes=5),plan_id=plan)
        result.append({'scenario_id':name,'synthetic':True,'human_reviewed':False,
            'label_source':'DETERMINISTIC_POLICY_DRAFT_NOT_MARKET_OUTCOME',
            'intended_use':'BEHAVIOR_COACH_CURRICULUM_ONLY',
            'market_performance_evidence':False,'estimator_fitted':False,
            'input':{'action':action,'checks':checks,'decision_at':now.isoformat(),
                'evidence_at':evidence_at.isoformat() if evidence_at else None,
                'plan_id':plan,'max_evidence_age_seconds':300},
            'expected_review':asdict(review)})
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); records=build_curriculum()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        for record in records: stream.write(json.dumps(record,sort_keys=True)+'\n')
    print(json.dumps({'status':'SYNTHETIC_CURRICULUM_PREPARED_NOT_TRAINED',
        'examples':len(records),'estimator_fitted':False,'trade_permission':'NO_TRADE'}))

if __name__=='__main__': main()
