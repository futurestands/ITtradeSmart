"""Offline research-document ingestion. Never trains or activates a model."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def build_reference(path: Path) -> dict:
    payload=path.read_bytes()
    text=payload.decode('utf-8-sig')
    digest=hashlib.sha256(payload).hexdigest()
    sections=[]; heading='Preamble'; lines=[]
    def flush():
        content='\n'.join(lines).strip()
        if content:
            sections.append({'section':heading,'text':content,
                'content_sha256':hashlib.sha256(content.encode()).hexdigest(),
                'verification':'USER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED',
                'usable_as_numeric_feature':False,'usable_as_training_label':False})
    for line in text.splitlines():
        if re.match(r'^#{1,3} ',line):
            flush(); heading=line.lstrip('# ').strip(); lines=[]
        else: lines.append(line)
    flush()
    return {'format_version':'1.0','source_name':path.name,'source_sha256':digest,
        'source_is_instruction':False,'purpose':'CITED_RESEARCH_REFERENCE_AND_HYPOTHESES',
        'model_trained':False,'model_status':'MODEL_NOT_READY',
        'execution_mode':'RESEARCH_ONLY','trade_permission':'NO_TRADE',
        'dated_market_claims':'QUARANTINED_UNTIL_PRIMARY_SOURCE_AND_ASOF_VERIFICATION',
        'threshold_policy':'Hypotheses only; preregister and validate before operational use',
        'sections':sections,
        'candidate_feature_groups':[
            {'group':'sessions_events','features':['minutes_since_cash_open','minutes_to_next_event','dst_mismatch_week'],
             'needs':['verified UTC timebase','dated exchange calendar','calendar publication and revision times']},
            {'group':'volatility_structure','features':['trailing_atr_percentile','efficiency_ratio','confirmed_sweep','fvg_distance_atr'],
             'needs':['closed bars','confirmation timestamps','trailing windows without centered lookahead']},
            {'group':'costs','features':['spread_atr_ratio','stop_spread_ratio','contract_profile_age'],
             'needs':['dated broker contract','historical bid/ask spread','commission and financing assumptions']},
            {'group':'macro_breadth','features':['ten_year_yield_change','volatility_index_close','top10_weight','breadth_above_50d'],
             'needs':['licensed point-in-time observations','available_at and observed_at','historical constituent membership']},
        ],
        'training_prerequisites':['eligible immutable dataset','verified historical UTC and DST',
            'certified instrument costs','causal features and labels','purged chronological splits',
            'training-only preprocessing','prior calibration split','untouched final holdout',
            'experiment registry and acceptance criteria'],
        'runtime_integration':'NONE; packet is not loaded by Flask, Android, risk engine or cloud runtime'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    packet=build_reference(args.reference)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(packet,stream,indent=2,ensure_ascii=False); stream.write('\n')
    print(json.dumps({'status':'PREPARED_NOT_TRAINED','source_sha256':packet['source_sha256'],
        'sections':len(packet['sections']),'model_trained':False,'trade_permission':'NO_TRADE'}))

if __name__=='__main__': main()
