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
from auth_store import Store, digest, new_token, postgres_connection, DB_NOW


@pytest.fixture
def fixture(tmp_path):
    path = tmp_path/'TEST_ONLY.sqlite3'
    # Deliberately separate test-double DDL. PostgreSQL roles/RLS/grants are
    # parsed in test_v11_security.py, NOT simulated as verified PostgreSQL here.
    schema = '''
    CREATE TABLE devices(id TEXT PRIMARY KEY, name TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'device' CHECK(role IN ('device','admin')),
      revoked BOOLEAN NOT NULL DEFAULT FALSE, created_at BIGINT NOT NULL DEFAULT 1800000000);
    CREATE TABLE sessions(access_hash TEXT PRIMARY KEY, refresh_hash TEXT UNIQUE NOT NULL,
      device_id TEXT NOT NULL REFERENCES devices(id), access_until BIGINT NOT NULL, refresh_until BIGINT NOT NULL);
    CREATE TABLE enrollment(code_hash TEXT PRIMARY KEY, expires_at BIGINT NOT NULL, used BOOLEAN NOT NULL DEFAULT FALSE);
    CREATE TABLE rate_limits(scope TEXT NOT NULL, identity_hash TEXT NOT NULL,
      window_start BIGINT NOT NULL, expires_at BIGINT NOT NULL, count INTEGER NOT NULL,
      PRIMARY KEY(scope,identity_hash,window_start));
    CREATE TABLE audit(id INTEGER PRIMARY KEY,occurred_at BIGINT NOT NULL,event TEXT NOT NULL,principal_hash TEXT NOT NULL);
    '''
    with sqlite3.connect(path) as connection:
        connection.executescript(schema)
    observed_sql = []

    class Connection:
        def __init__(self, db):
            self.db = db
        def execute(self, sql, params=()):
            observed_sql.append(sql)  # SQL text only; never record token parameters.
            if sql == DB_NOW:
                return self.db.execute('SELECT ?', (clock[0],))
            return self.db.execute(sql.replace('smarthub_cloud_auth.', '').replace('%s', '?'), params)

    @contextmanager
    def connect():
        with sqlite3.connect(path, timeout=10) as db:
            db.execute('PRAGMA foreign_keys=ON')
            yield Connection(db)
    clock = [1800000000]
    store = Store(connect=connect)
    store._test_sql = observed_sql
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


def operator_bootstrap(store, clock):
    """Privileged fixture setup only; production web Store cannot issue this."""
    access, refresh = new_token('access'), new_token('refresh')
    with store.connect() as db:
        db.execute('INSERT INTO smarthub_cloud_auth.devices VALUES (%s,%s,%s,FALSE,%s)',
                   ('admin1', 'OPERATOR', 'admin', clock[0]))
        db.execute('INSERT INTO smarthub_cloud_auth.sessions VALUES (%s,%s,%s,%s,%s)',
                   (digest(access), digest(refresh), 'admin1', clock[0]+3600, clock[0]+2592000))
    return dict(device_token=access, refresh_token=refresh)


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
        return Store(store.connect).enroll('phone'+str(i), 'TEST', code)
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
    store, client, clock, _ = fixture
    session = operator_bootstrap(store, clock)
    assert client.post('/api/v5/admin/enrollment-codes', headers=auth(session)).status_code == 201


def test_state_survives_a_new_store_and_application_instance(fixture):
    store, client, _, _ = fixture
    session, _ = enrollment(store, client)
    cold = create_app(Store(store.connect)).test_client()
    assert cold.get('/api/v5/ai/status', headers=auth(session)).status_code == 200
    assert cold.post('/api/v5/device/revoke', headers=auth(session)).status_code == 200
    assert client.get('/api/v5/ai/status', headers=auth(session)).status_code == 401


@pytest.mark.parametrize('operation,event', [('enroll', 'DEVICE_ENROLLED'),
    ('renew', 'SESSION_RENEWED'), ('revoke', 'DEVICE_SELF_REVOKED')])
def test_success_audit_failure_rolls_back_authentication_mutation(fixture, operation, event):
    store, client, _, path = fixture
    if operation == 'enroll':
        code = store.enrollment_code()
    else:
        session, _ = enrollment(store, client)
    with sqlite3.connect(path) as db:
        # Simulate an audit write failing after the token mutation, not a
        # connection failure before the transaction begins.
        db.execute("CREATE TRIGGER fail_success_audit BEFORE INSERT ON audit "
                   "WHEN NEW.event='"+event+"' BEGIN SELECT RAISE(ABORT,'TEST_AUDIT_FAILURE'); END")
    with pytest.raises(sqlite3.IntegrityError, match='TEST_AUDIT_FAILURE'):
        if operation == 'enroll':
            store.enroll('test-phone', 'TEST', code)
        elif operation == 'renew':
            store.renew(session['refresh_token'])
        else:
            store.revoke(session['device_id'])
    with sqlite3.connect(path) as db:
        if operation == 'enroll':
            assert db.execute('SELECT used FROM enrollment WHERE code_hash=?', (digest(code),)).fetchone() == (0,)
            assert db.execute('SELECT count(*) FROM devices').fetchone() == (0,)
            assert db.execute('SELECT count(*) FROM sessions').fetchone() == (0,)
        else:
            assert db.execute('SELECT refresh_hash FROM sessions').fetchone() == (digest(session['refresh_token']),)
            assert db.execute('SELECT revoked FROM devices').fetchone() == (0,)
        db.execute('DROP TRIGGER fail_success_audit')
    if operation == 'enroll':
        assert store.enroll('test-phone', 'TEST', code)
    elif operation == 'renew':
        assert store.renew(session['refresh_token'])
    else:
        assert store.revoke(session['device_id'])
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM audit WHERE event=?', (event,)).fetchone() == (1,)


def test_rate_limit_is_durable_and_audited(fixture):
    store, client, _, path = fixture
    for _ in range(10):
        assert client.post('/api/v5/device/enroll', json={}).status_code == 400
    cold = create_app(Store(store.connect)).test_client()
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
    monkeypatch.setenv('VERCEL_ENV', 'development')
    monkeypatch.delenv('SMARTHUB_CLOUD_DATABASE_URL', raising=False)
    with pytest.raises(RuntimeError):
        with postgres_connection():
            pytest.fail('No database may be opened')


@pytest.mark.parametrize('dsn', ['sqlite:///state.db', 'postgresql://test.invalid/db?sslmode=disable', 'postgresql://test.invalid/db?sslmode=require'])
def test_database_transport_requires_verified_tls(monkeypatch, dsn):
    monkeypatch.setenv('VERCEL_ENV', 'development')
    monkeypatch.setenv('SMARTHUB_CLOUD_DATABASE_URL', dsn)
    with pytest.raises(RuntimeError):
        with postgres_connection():
            pytest.fail('Unverified database transport')


def test_database_default_creates_device_without_selecting_client_identity(fixture):
    store, client, _, path = fixture
    first, _ = enrollment(store, client, 'admin1')
    second, _ = enrollment(store, client, 'admin1')
    assert first['device_id'] != second['device_id'] != 'admin1'
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT DISTINCT role FROM devices').fetchall() == [('device',)]


def test_runtime_cannot_mint_rotate_or_self_revoke_operator_admin_session(fixture):
    store, client, clock, _ = fixture
    admin = operator_bootstrap(store, clock)
    with store.connect() as db, pytest.raises(PermissionError):
        store._session(db, 'admin1')
    assert client.post('/api/v5/device/renew', json={'refresh_token': admin['refresh_token']}).status_code == 401
    assert client.post('/api/v5/device/revoke', headers=auth(admin)).status_code == 403
    assert store.principal(admin['device_token']) == ('admin1', 'admin')
    assert client.post('/api/v5/admin/devices/admin1/revoke', headers=auth(admin)).status_code == 404
    assert client.get('/api/v5/admin/audit', headers=auth(admin)).status_code == 404


def test_admin_can_revoke_device_and_device_cannot_read_admin_audit(fixture):
    store, client, clock, _ = fixture
    admin = operator_bootstrap(store, clock)
    device, _ = enrollment(store, client)
    assert client.get('/api/v5/admin/audit', headers=auth(device)).status_code == 403
    assert client.post('/api/v5/admin/devices/'+device['device_id']+'/revoke', headers=auth(admin)).status_code == 200
    assert store.principal(device['device_token']) is None
    assert store.renew(device['refresh_token']) is None


def test_rotation_issuance_failure_rolls_back_consumption(fixture, monkeypatch):
    store, client, _, _ = fixture
    session, _ = enrollment(store, client)
    def fail(*args):
        raise RuntimeError('SYNTHETIC_PRIVATE_FAILURE')
    monkeypatch.setattr(store, '_session', fail)
    response = client.post('/api/v5/device/renew', json={'refresh_token': session['refresh_token']})
    assert response.status_code == 503 and 'SYNTHETIC_PRIVATE_FAILURE' not in response.get_data(as_text=True)
    assert store.principal(session['device_token'])


def test_concurrent_refresh_consumption_has_one_winner(fixture):
    store, client, _, _ = fixture
    session, _ = enrollment(store, client)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: Store(store.connect).renew(session['refresh_token']), (1, 2)))
    assert sum(value is not None for value in results) == 1
    assert store.principal(session['device_token']) is None


def test_rate_windows_roll_over_without_reusing_expired_counters(fixture):
    store, _, clock, path = fixture
    assert all(store.rate('enrollment', 'TEST_IDENTITY', 10) for _ in range(10))
    assert not store.rate('enrollment', 'TEST_IDENTITY', 10)
    clock[0] += 59
    assert not Store(store.connect).rate('enrollment', 'TEST_IDENTITY', 10)
    clock[0] += 1
    assert Store(store.connect).rate('enrollment', 'TEST_IDENTITY', 10)
    with sqlite3.connect(path) as db:
        rows = db.execute('SELECT window_start,expires_at,count FROM rate_limits ORDER BY window_start').fetchall()
    assert rows == [(1800000000, 1800000060, 11), (1800000060, 1800000120, 1)]


def test_concurrent_rate_counters_do_not_overgrant_and_saturate(fixture):
    store, _, _, path = fixture
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: Store(store.connect).rate('enrollment', 'SHARED', 10), range(30)))
    assert sum(results) == 10
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count FROM rate_limits').fetchone() == (11,)


@pytest.mark.parametrize('scope,limit', [('arbitrary', 10), ('enrollment', 1000), ('access', True)])
def test_unregistered_rate_policies_are_rejected(fixture, scope, limit):
    with pytest.raises(ValueError):
        fixture[0].rate(scope, 'TEST', limit)


def test_final_gate_runtime_dml_is_valid_postgresql(fixture):
    import re
    from pglast import parse_sql
    store, client, _, _ = fixture
    session, _ = enrollment(store, client)
    assert client.get('/api/v5/ai/status', headers=auth(session)).status_code == 200
    renewed = store.renew(session['refresh_token'])
    assert renewed and store.revoke(renewed['device_id'])
    for sql in set(store._test_sql):
        indexes = iter(range(1, sql.count('%s')+1))
        assert parse_sql(re.sub(r'%s', lambda _: '$'+str(next(indexes)), sql))
