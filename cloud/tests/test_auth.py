"""Offline transaction tests. SQLite is ONLY a test double, never cloud storage.

Live PostgreSQL/TLS/permissions must be separately verified after target approval.
"""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from auth_store import Store, digest, postgres_connection


@pytest.fixture
def fixture(tmp_path):
    path = tmp_path/'TEST_ONLY.sqlite3'
    schema = (Path(__file__).parents[1]/'schema.sql').read_text()
    schema = schema.replace('CREATE SCHEMA IF NOT EXISTS smarthub_cloud_auth;', '')
    schema = schema.replace('smarthub_cloud_auth.', '').replace('BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY', 'INTEGER PRIMARY KEY')
    schema = '\n'.join(line for line in schema.splitlines() if not line.startswith(('REVOKE ', 'GRANT ', 'CREATE ROLE ')))
    with sqlite3.connect(path) as connection:
        connection.executescript(schema)

    class Connection:
        def __init__(self, db):
            self.db = db
        def execute(self, sql, params=()):
            return self.db.execute(sql.replace('smarthub_cloud_auth.', '').replace('%s', '?'), params)

    @contextmanager
    def connect():
        with sqlite3.connect(path, timeout=10) as db:
            db.execute('PRAGMA foreign_keys=ON')
            yield Connection(db)
    clock = [1800000000]
    store = Store(connect=connect, clock=lambda: clock[0])
    app = create_app(store)
    app.config['TESTING'] = True
    return store, app.test_client(), clock, path


def enrollment(store, client, device='phone1'):
    code = store.enrollment_code()
    response = client.post('/api/v5/device/enroll', json=dict(device_id=device, device_name='SYNTHETIC_PHONE', pairing_code=code))
    assert response.status_code == 201
    return response.json, code


def auth(session):
    return {'Authorization': 'Bearer '+session['device_token']}


@pytest.mark.parametrize('route', ['/api/v5/ai/status', '/api/v5/ai/research-progress', '/api/v5/ai/advisory', '/api/v5/admin/enrollment-codes'])
def test_protected_routes_reject_missing_or_local_admin_credential(fixture, route):
    _, client, _, _ = fixture
    for headers in ({}, {'Authorization': 'Bearer '+'c'*48}):
        assert client.get(route, headers=headers).status_code == 401


def test_enrollment_code_single_use_and_never_plaintext_in_database(fixture):
    store, client, _, path = fixture
    session, code = enrollment(store, client)
    assert client.post('/api/v5/device/enroll', json=dict(device_id='phone2', device_name='TEST', pairing_code=code)).status_code == 401
    payload = path.read_bytes()
    assert code.encode() not in payload
    assert session['device_token'].encode() not in payload
    assert session['refresh_token'].encode() not in payload


def test_code_consumption_is_atomic_across_instances(fixture):
    store, _, _, _ = fixture
    code = store.enrollment_code()
    def consume(i):
        return Store(store.connect, store.clock).enroll('phone'+str(i), 'TEST', code)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(consume, (10, 11)))
    assert sum(result is not None for result in results) == 1


def test_expired_code_is_rejected(fixture):
    store, client, clock, _ = fixture
    code = store.enrollment_code()
    clock[0] += 601
    assert client.post('/api/v5/device/enroll', json=dict(device_id='phone1', device_name='TEST', pairing_code=code)).status_code == 401


def test_expiry_rotation_and_refresh_replay(fixture):
    store, client, clock, _ = fixture
    session, _ = enrollment(store, client)
    clock[0] += 3601
    assert client.get('/api/v5/ai/status', headers=auth(session)).status_code == 401
    rotated = client.post('/api/v5/device/renew', json={'refresh_token': session['refresh_token']})
    assert rotated.status_code == 200
    assert rotated.json['device_token'] != session['device_token']
    assert client.post('/api/v5/device/renew', json={'refresh_token': session['refresh_token']}).status_code == 401
    assert client.get('/api/v5/ai/status', headers=auth(rotated.json)).status_code == 200


def test_refresh_expiry_and_revocation(fixture):
    store, client, clock, _ = fixture
    session, _ = enrollment(store, client)
    assert client.post('/api/v5/device/revoke', headers=auth(session)).status_code == 200
    assert client.get('/api/v5/ai/status', headers=auth(session)).status_code == 401
    assert client.post('/api/v5/device/renew', json={'refresh_token': session['refresh_token']}).status_code == 401
    other, _ = enrollment(store, client, 'phone2')
    clock[0] += 2592001
    assert client.post('/api/v5/device/renew', json={'refresh_token': other['refresh_token']}).status_code == 401


def test_device_cannot_issue_codes_or_revoke_another_device(fixture):
    store, client, _, _ = fixture
    session, _ = enrollment(store, client)
    assert client.post('/api/v5/admin/enrollment-codes', headers=auth(session)).status_code == 403
    assert client.post('/api/v5/admin/devices/other/revoke', headers=auth(session)).status_code == 403
    assert client.post('/api/v5/device/revoke', headers=auth(session), json={'device_id': 'other'}).status_code == 400


def test_admin_is_a_separate_database_role(fixture):
    store, client, _, _ = fixture
    with store.connect() as db:
        db.execute('INSERT INTO smarthub_cloud_auth.devices VALUES (%s,%s,%s,FALSE,%s)', ('admin1', 'OPERATOR', 'admin', 1))
        session = store._session(db, 'admin1')
    assert client.post('/api/v5/admin/enrollment-codes', headers=auth(session)).status_code == 201


def test_state_survives_a_new_store_and_application_instance(fixture):
    store, client, _, _ = fixture
    session, _ = enrollment(store, client)
    cold = create_app(Store(store.connect, store.clock)).test_client()
    assert cold.get('/api/v5/ai/status', headers=auth(session)).status_code == 200
    assert cold.post('/api/v5/device/revoke', headers=auth(session)).status_code == 200
    assert client.get('/api/v5/ai/status', headers=auth(session)).status_code == 401


def test_rate_limit_is_durable_and_audited(fixture):
    store, client, _, path = fixture
    for _ in range(10):
        assert client.post('/api/v5/device/enroll', json={}).status_code == 400
    cold = create_app(Store(store.connect, store.clock)).test_client()
    assert cold.post('/api/v5/device/enroll', json={}).status_code == 429
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM audit WHERE event='ENROLLMENT_RATE_LIMIT'").fetchone()[0] == 1


@pytest.mark.parametrize('data', [{}, {'device_id':'bad;DROP','device_name':'x','pairing_code':'x'}, {'role':'admin'}, []])
def test_untrusted_enrollment_inputs_fail_closed(fixture, data):
    _, client, _, _ = fixture
    assert client.post('/api/v5/device/enroll', json=data).status_code == 400


def test_database_loss_is_safe_and_never_leaks_exception(fixture):
    store, _, _, _ = fixture
    def denied():
        raise RuntimeError('SYNTHETIC_SECRET_MUST_NOT_LEAK')
    store.connect = denied
    client = create_app(store).test_client()
    response = client.post('/api/v5/device/enroll', json={})
    assert response.status_code == 503 and response.json['action'] == 'NO_TRADE'
    assert 'SYNTHETIC_SECRET' not in response.get_data(as_text=True)
    assert client.get('/health').status_code == 200


def test_contracts_no_trade_headers_and_no_execution_routes(fixture):
    store, client, _, _ = fixture
    session, _ = enrollment(store, client)
    response = client.get('/api/v5/ai/status', headers=auth(session))
    assert response.json['model_trained'] is False and response.json['probability'] is None
    research = client.get('/api/v5/ai/research-progress', headers=auth(session))
    assert research.json['schema_version'] == 1 and research.json['source'] == 'NONE'
    assert research.json['real_market_training_authorized'] is False
    advisory = client.post('/api/v5/ai/advisory', headers=auth(session), json={'password':'SYNTHETIC_SENTINEL','force_trade':True})
    assert advisory.json['action'] == 'NO_TRADE' and advisory.json['probability'] is None
    assert 'SYNTHETIC_SENTINEL' not in advisory.get_data(as_text=True)
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['X-Smarthub-Generated-At']
    for route in ('/api/v5/bot/trade', '/order_send', '/api/v5/mt5/order'):
        assert client.post(route, headers=auth(session)).status_code == 404


def test_missing_store_does_not_fall_back_to_local_state(monkeypatch):
    monkeypatch.delenv('SMARTHUB_CLOUD_DATABASE_URL', raising=False)
    with pytest.raises(RuntimeError):
        with postgres_connection():
            pytest.fail('No database may be opened')


@pytest.mark.parametrize('dsn', ['sqlite:///state.db', 'postgresql://test.invalid/db?sslmode=disable', 'postgresql://test.invalid/db?sslmode=require'])
def test_database_transport_requires_verified_tls(monkeypatch, dsn):
    monkeypatch.setenv('SMARTHUB_CLOUD_DATABASE_URL', dsn)
    with pytest.raises(RuntimeError):
        with postgres_connection():
            pytest.fail('Unverified database transport')
