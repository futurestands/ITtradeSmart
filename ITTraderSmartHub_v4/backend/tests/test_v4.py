import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
pytest.importorskip("flask", reason="Flask must be installed on gateway host")

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('SMARTHUB_API_TOKEN', 'a'*48)
    monkeypatch.setenv('SMARTHUB_TELEMETRY_TOKEN', 'b'*48)
    from app import app, _v4_store
    _v4_store.stress = None
    _v4_store.alerts.clear()
    _v4_store.devices.clear()
    _v4_store.pairing_codes.clear()
    _v4_store.audit_logs.clear()
    _v4_store.request_counts.clear()
    _v4_store.enrollment_failures.clear()
    _v4_store.seq = 0
    app.config['TESTING'] = True
    return app.test_client()

ADMIN_H = {'Authorization': 'Bearer ' + 'a'*48}
TELEMETRY_H = {'X-Telemetry-Token': 'b'*48}

def test_unauthorized(client):
    assert client.post('/api/v4/risk/context', json={}).status_code == 401

def test_pairing_code_enrollment_and_renewal(client):
    # 1. Admin generates one-time pairing code
    res_code = client.post('/api/v4/admin/pairing-code', json={'ttl_minutes': 10}, headers=ADMIN_H)
    assert res_code.status_code == 200
    pcode = res_code.json['pairing_code']

    # 2. Mobile enrolls with pairing code
    res_enroll = client.post('/api/v4/device/enroll', json={
        'device_id': 'device-pixel8-1234',
        'device_name': 'Pixel 8',
        'pairing_code': pcode
    })
    assert res_enroll.status_code == 200
    token = res_enroll.json['device_token']
    dev_H = {'Authorization': f'Bearer {token}'}

    # 3. Cannot re-use the same one-time pairing code
    res_reuse = client.post('/api/v4/device/enroll', json={
        'device_id': 'device-pixel8-5678',
        'device_name': 'Pixel 8 Copy',
        'pairing_code': pcode
    })
    assert res_reuse.status_code == 400

    # 4. Token renewal
    res_renew = client.post('/api/v4/device/renew', headers=dev_H)
    assert res_renew.status_code == 200
    new_token = res_renew.json['device_token']
    new_dev_H = {'Authorization': f'Bearer {new_token}'}

    # Old token is invalidated
    assert client.post('/api/v4/risk/context', json={'schema_version': 1, 'baseline_risk_pct': 1, 'symbol': 'EURUSD'}, headers=dev_H).status_code == 401
    # New token works
    assert client.post('/api/v4/risk/context', json={'schema_version': 1, 'baseline_risk_pct': 1, 'symbol': 'EURUSD'}, headers=new_dev_H).status_code == 200

def test_ordinary_device_cannot_read_audit_logs(client):
    # Admin generates code & device enrolls
    pcode = client.post('/api/v4/admin/pairing-code', json={}, headers=ADMIN_H).json['pairing_code']
    token = client.post('/api/v4/device/enroll', json={'device_id': 'dev-user1-1234', 'pairing_code': pcode}).json['device_token']
    dev_H = {'Authorization': f'Bearer {token}'}

    # Device attempts to read admin audit logs -> 403 Forbidden
    res = client.get('/api/v4/auth/audit', headers=dev_H)
    assert res.status_code == 403
    assert 'Forbidden' in res.json['error']

def test_ordinary_device_cannot_revoke_other_devices(client):
    # Enroll Device A and Device B
    pcodeA = client.post('/api/v4/admin/pairing-code', json={}, headers=ADMIN_H).json['pairing_code']
    tokenA = client.post('/api/v4/device/enroll', json={'device_id': 'dev-userA-1234', 'pairing_code': pcodeA}).json['device_token']

    pcodeB = client.post('/api/v4/admin/pairing-code', json={}, headers=ADMIN_H).json['pairing_code']
    tokenB = client.post('/api/v4/device/enroll', json={'device_id': 'dev-userB-5678', 'pairing_code': pcodeB}).json['device_token']

    devA_H = {'Authorization': f'Bearer {tokenA}'}
    devB_H = {'Authorization': f'Bearer {tokenB}'}

    # Device A attempts to revoke Device B -> 403 Forbidden
    res_revoke_other = client.post('/api/v4/device/revoke', json={'device_id': 'dev-userB-5678'}, headers=devA_H)
    assert res_revoke_other.status_code == 403

    # Device A revokes its own session -> 200 OK
    res_revoke_self = client.post('/api/v4/device/revoke', json={'device_id': 'dev-userA-1234'}, headers=devA_H)
    assert res_revoke_self.status_code == 200

def test_cannot_enroll_with_leaked_master_secret(client):
    res = client.post('/api/v4/device/enroll', json={
        'device_id': 'dev-attacker-123',
        'enrollment_secret': 'a'*48,
        'pairing_code': 'PAIR-000000'
    })
    assert res.status_code == 400
    assert 'Master secrets' in res.json['error']

def test_enrollment_rate_limiting(client):
    for i in range(5):
        client.post('/api/v4/device/enroll', json={'device_id': 'dev-attacker-999', 'pairing_code': 'INVALID-CODE'})

    res_blocked = client.post('/api/v4/device/enroll', json={'device_id': 'dev-attacker-999', 'pairing_code': 'INVALID-CODE'})
    assert res_blocked.status_code == 400
    assert 'Too many failed enrollment attempts' in res_blocked.json['error']

def test_agent_ingest_and_alerts(client):
    r = client.post('/api/v4/telemetry/stress', json={'stress_index': 60, 'source': 'authorized_telemetry_agent'}, headers=TELEMETRY_H)
    assert r.status_code == 200
    a = client.post('/api/v4/alerts/query', json={'schema_version': 1, 'console': 'combined', 'limit': 10}, headers=ADMIN_H)
    assert a.status_code == 200 and len(a.json['alerts']) == 1

def test_reject_client_stress(client):
    r = client.post('/api/v4/risk/context', json={'schema_version': 1, 'baseline_risk_pct': 1, 'symbol': 'EURUSD', 'stress_index': 0}, headers=ADMIN_H)
    assert r.status_code == 400

def test_fusion_fails_closed(client):
    client.post('/api/v4/telemetry/stress', json={'stress_index': 80, 'source': 'authorized_telemetry_agent'}, headers=TELEMETRY_H)
    r = client.post('/api/v4/risk/context', json={'schema_version': 1, 'baseline_risk_pct': 1, 'symbol': 'EURUSD'}, headers=ADMIN_H)
    assert r.status_code == 200 and r.json['effective_risk_pct'] is None
    assert r.json['infrastructure_risk_ceiling_pct'] == pytest.approx(.6)
