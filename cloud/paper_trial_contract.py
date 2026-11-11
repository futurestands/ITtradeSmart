"""Allowlisted published paper evidence. No live worker, model or broker access."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

MODELS={'empirical_prior','logistic','gradient_boosting'}
COUNTS={'directional_scored','direction_correct','paper_entries','paper_waits','paper_closed',
        'paper_profitable','paper_losing','paper_flat','paper_unknown','paper_pending'}
FLAGS={'execution_authorized':False,'model_status':'MODEL_NOT_READY','decision':'NO_TRADE',
       'scope':'PUBLISHED_PAPER_EVIDENCE_NOT_LIVE_STATUS','costs_certified':False,'clock_certified':False}


def unavailable(status='NOT_PUBLISHED'):
    return {'schema_version':1,'status':status,**FLAGS,'captured_at_utc':None,
            'run_state':None,'tracks':[]}


def _pairs(pairs):
    value={}
    for key,item in pairs:
        if key in value:raise ValueError('Duplicate key')
        value[key]=item
    return value


def validate_snapshot(value, *, now=None):
    keys={'schema_version','status',*FLAGS,'captured_at_utc','run_state','tracks'}
    if not isinstance(value,dict) or set(value)!=keys:raise ValueError('Unexpected evidence fields')
    if type(value['schema_version']) is not int or value['schema_version']!=1:
        raise ValueError('Unsupported evidence schema')
    for key,expected in FLAGS.items():
        if type(value[key]) is not type(expected) or value[key]!=expected:raise ValueError('Safety scope mismatch')
    if value['status']!='PAPER_EVIDENCE_AVAILABLE' or value['run_state'] not in ('IN_PROGRESS_AT_CAPTURE','COMPLETED','STOPPED'):
        raise ValueError('Invalid recorded state')
    captured=datetime.fromisoformat(value['captured_at_utc'])
    if captured.utcoffset()!=timedelta(0) or captured>(now or datetime.now(timezone.utc))+timedelta(minutes=5):
        raise ValueError('Future or unverified capture label')
    tracks=value['tracks']
    if not isinstance(tracks,list) or len(tracks)!=3:raise ValueError('Three frozen tracks required')
    if {r.get('model') for r in tracks if isinstance(r,dict)}!=MODELS:raise ValueError('Model set mismatch')
    for track in tracks:
        if set(track)!={'model',*COUNTS}:raise ValueError('Unexpected track fields')
        if any(type(track[k]) is not int or not 0<=track[k]<=1_000_000 for k in COUNTS):
            raise ValueError('Bounded integer observations required')
        if (track['direction_correct']>track['directional_scored']
                or track['paper_profitable']+track['paper_losing']+track['paper_flat']+track['paper_unknown']!=track['paper_closed']
                or track['paper_closed']+track['paper_pending']!=track['paper_entries']):
            raise ValueError('Inconsistent observation counts')
    return value


def read_snapshot(path, expected_sha256):
    try:
        if not isinstance(expected_sha256,str) or len(expected_sha256)!=64:return unavailable()
        target=Path(path)
        if target.is_symlink() or not target.is_file() or not 0<target.stat().st_size<=65536:
            return unavailable('INVALID_EVIDENCE')
        raw=target.read_bytes()
        if len(raw)>65536 or hashlib.sha256(raw).hexdigest()!=expected_sha256:
            return unavailable('INVALID_EVIDENCE')
        value=json.loads(raw,object_pairs_hook=_pairs,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
        return validate_snapshot(value)
    except Exception:
        return unavailable('INVALID_EVIDENCE')
