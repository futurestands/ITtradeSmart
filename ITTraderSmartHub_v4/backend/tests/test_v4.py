import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
pytest.importorskip("flask", reason="Flask must be installed on gateway host")
from v4_services import ContextStore, risk_context, research_request

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('SMARTHUB_API_TOKEN', 'a'*48)
    monkeypatch.setenv('SMARTHUB_TELEMETRY_TOKEN', 'b'*48)
    from app import app, _v4_store
    _v4_store.stress = None
    _v4_store.alerts.clear()
    _v4_store.devices.clear()
    _v4_store.audit_logs.clear()
    _v4_store.request_counts.clear()
    _v4_store.seq = 0
    app.config['TESTING'] = True
    return app.test_client()

H = {'Authorization': 'Bearer ' + 'a'*48}
T = {'X-Telemetry-Token': 'b'*48}

def test_unauthorized(client):
    assert client.post('/api/v4/risk/context', json={}).status_code == 401

def test_device_enrollment_and_revocation(client):
    # Enroll device using master enrollment secret
    res = client.post('/api/v4/device/enroll', json={
        'device_id': 'device-12345678',
        'device_name': 'Test Pixel',
        'enrollment_secret': 'a'*48
    })
    assert res.status_code == 200
    token = res.json['device_token']
    assert token and len(token) == 64

    # Use enrolled device token
    dev_header = {'Authorization': f'Bearer {token}'}
    res_risk = client.post('/api/v4/risk/context', json={'schema_version': 1, 'baseline_risk_pct': 1, 'symbol': 'EURUSD'}, headers=dev_header)
    assert res_risk.status_code == 200

    # Revoke device
    res_revoke = client.post('/api/v4/device/revoke', json={'device_id': 'device-12345678'}, headers=H)
    assert res_revoke.status_code == 200

    # Now token should be rejected
    res_rejected = client.post('/api/v4/risk/context', json={'schema_version': 1, 'baseline_risk_pct': 1, 'symbol': 'EURUSD'}, headers=dev_header)
    assert res_rejected.status_code == 401

def test_agent_ingest_and_alerts(client):
    r = client.post('/api/v4/telemetry/stress', json={'stress_index': 60, 'source': 'authorized_telemetry_agent'}, headers=T)
    assert r.status_code == 200
    a = client.post('/api/v4/alerts/query', json={'schema_version': 1, 'console': 'combined', 'limit': 10}, headers=H)
    assert a.status_code == 200 and len(a.json['alerts']) == 1

def test_reject_client_stress(client):
    r = client.post('/api/v4/risk/context', json={'schema_version': 1, 'baseline_risk_pct': 1, 'symbol': 'EURUSD', 'stress_index': 0}, headers=H)
    assert r.status_code == 400

def test_fusion_fails_closed(client):
    client.post('/api/v4/telemetry/stress', json={'stress_index': 80, 'source': 'authorized_telemetry_agent'}, headers=T)
    r = client.post('/api/v4/risk/context', json={'schema_version': 1, 'baseline_risk_pct': 1, 'symbol': 'EURUSD'}, headers=H)
    assert r.status_code == 200 and r.json['effective_risk_pct'] is None
    assert r.json['infrastructure_risk_ceiling_pct'] == pytest.approx(.6)

def test_research_unavailable_without_fake_results(client):
    r = client.post('/api/v4/research/incident-impact', json={'schema_version': 1, 'start_utc': '2026-09-01T00:00:00Z', 'end_utc': '2026-10-01T00:00:00Z', 'outcome': 'rule_violation'}, headers=H)
    assert r.status_code == 200 and r.json['status'] == 'UNAVAILABLE' and r.json['result'] is None

def test_auth_audit_endpoint(client):
    client.post('/api/v4/device/enroll', json={'device_id': 'dev-99999999', 'enrollment_secret': 'wrong_secret'})
    res = client.get('/api/v4/auth/audit', headers=H)
    assert res.status_code == 200
    logs = res.json['audit_logs']
    assert any(log['event_type'] == 'ENROLLMENT_FAILED' for log in logs)
