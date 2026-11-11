from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
import pytest
from test_auth import fixture,enrollment,auth
import published_paper as published
from paper_trial_contract import FLAGS,COUNTS,MODELS,validate_snapshot,read_snapshot


def snapshot():
    tracks=[]
    for name in sorted(MODELS):
        track={'model':name,**{k:0 for k in COUNTS}}
        track.update(directional_scored=2,direction_correct=1,paper_waits=3)
        tracks.append(track)
    return {'schema_version':1,'status':'PAPER_EVIDENCE_AVAILABLE',**FLAGS,
            'captured_at_utc':'2026-11-11T07:00:00+00:00','run_state':'IN_PROGRESS_AT_CAPTURE','tracks':tracks}


def test_snapshot_does_not_claim_liveness_or_profitability():
    value=validate_snapshot(snapshot(),now=datetime(2026,11,11,8,tzinfo=timezone.utc))
    assert value['scope']=='PUBLISHED_PAPER_EVIDENCE_NOT_LIVE_STATUS'
    assert not value['execution_authorized'] and value['decision']=='NO_TRADE'


@pytest.mark.parametrize('mutation',['extra','approved','bool_count','bad_totals','duplicate_model','future','readiness'])
def test_invalid_snapshot_rejected(mutation):
    value=snapshot()
    if mutation=='extra':value['account_password']='MUST_NOT_BE_ACCEPTED'
    if mutation=='approved':value['execution_authorized']=True
    if mutation=='bool_count':value['tracks'][0]['paper_entries']=True
    if mutation=='bad_totals':value['tracks'][0]['paper_losing']=1
    if mutation=='duplicate_model':value['tracks'][0]['model']=value['tracks'][1]['model']
    if mutation=='future':value['captured_at_utc']='2099-01-01T00:00:00+00:00'
    if mutation=='readiness':value['model_status']='READY'
    with pytest.raises(ValueError):validate_snapshot(value)


def test_pinned_reader_refuses_changed_bytes_and_duplicate_keys(tmp_path):
    path=tmp_path/'report.json';raw=json.dumps(snapshot()).encode();path.write_bytes(raw)
    pin=hashlib.sha256(raw).hexdigest()
    assert read_snapshot(path,pin)['status']=='PAPER_EVIDENCE_AVAILABLE'
    path.write_bytes(raw+b' ')
    assert read_snapshot(path,pin)['status']=='INVALID_EVIDENCE'
    path.write_bytes(b'{"schema_version":1,"schema_version":1}')
    assert read_snapshot(path,hashlib.sha256(path.read_bytes()).hexdigest())['status']=='INVALID_EVIDENCE'


def test_authenticated_read_only_route_and_no_inputs(fixture,tmp_path,monkeypatch):
    store,client,_,_=fixture
    route='/api/v5/ai/paper-trial'
    assert client.get(route).status_code==401
    session,_=enrollment(store,client)
    path=tmp_path/'snapshot.json';raw=json.dumps(snapshot()).encode();path.write_bytes(raw)
    monkeypatch.setattr(published,'BUNDLE_FILE',path)
    monkeypatch.setattr(published,'EXPECTED_SHA256',hashlib.sha256(raw).hexdigest())
    response=client.get(route,headers=auth(session))
    assert response.status_code==200 and response.json==snapshot()
    assert response.headers['Cache-Control']=='no-store'
    assert client.get(route+'?path=private',headers=auth(session)).status_code==400
    assert client.post(route,headers=auth(session),json={}).status_code==405


def test_missing_artifact_is_not_a_zero_loss_report(fixture,monkeypatch):
    store,client,_,_=fixture;session,_=enrollment(store,client)
    monkeypatch.setattr(published,'EXPECTED_SHA256',None)
    value=client.get('/api/v5/ai/paper-trial',headers=auth(session)).json
    assert value['status']=='NOT_PUBLISHED' and value['tracks']==[]
