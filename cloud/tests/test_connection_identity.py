"""Mock connector only. No PostgreSQL or Neon SQL is executed."""
from contextlib import contextmanager
from types import SimpleNamespace
import sys
import pytest
from auth_store import postgres_connection, PRIVATE_LOGIN, RUNTIME_ROLE, IDENTITY_SQL


@pytest.fixture
def connector(monkeypatch):
    monkeypatch.setenv('VERCEL_ENV', 'preview')
    monkeypatch.setenv('SMARTHUB_CLOUD_DATABASE_URL',
                       'postgresql://'+PRIVATE_LOGIN+'@db.example.invalid/test?sslmode=verify-full')
    identity = [PRIVATE_LOGIN, PRIVATE_LOGIN] + [False]*10
    calls = []
    class DB:
        def execute(self, sql):
            calls.append(sql)
            return SimpleNamespace(fetchone=lambda: tuple(identity) if sql == IDENTITY_SQL else (RUNTIME_ROLE,))
    @contextmanager
    def connect(*args, **kwargs):
        calls.append(kwargs)
        yield DB()
    monkeypatch.setitem(sys.modules, 'psycopg', SimpleNamespace(connect=connect))
    return identity, calls


def test_private_login_sets_only_transaction_local_runtime_role(connector):
    _, calls = connector
    with postgres_connection():
        assert 'SET LOCAL ROLE smarthub_cloud_runtime' in calls
    assert 'idle_in_transaction_session_timeout=10000' in calls[0]['options']


@pytest.mark.parametrize('index', range(2, 12))
def test_privileged_inheriting_or_operator_membership_identity_is_rejected(connector, index):
    identity, calls = connector
    identity[index] = True
    with pytest.raises(RuntimeError):
        with postgres_connection():
            pytest.fail('Privileged web identity accepted')
    assert 'SET LOCAL ROLE smarthub_cloud_runtime' not in calls


@pytest.mark.parametrize('username', ['neondb_owner', 'smarthub_cloud_operator'])
def test_owner_or_operator_database_url_is_rejected(connector, monkeypatch, username):
    monkeypatch.setenv('SMARTHUB_CLOUD_DATABASE_URL', f'postgresql://{username}@db.example.invalid/test?sslmode=verify-full')
    with pytest.raises(RuntimeError):
        with postgres_connection():
            pytest.fail('Owner/operator URL accepted')
    assert connector[1] == []


@pytest.mark.parametrize('environment', ['production', 'unknown'])
def test_production_or_unknown_environment_is_rejected(connector, monkeypatch, environment):
    monkeypatch.setenv('VERCEL_ENV', environment)
    monkeypatch.setenv('SMARTHUB_CLOUD_ENVIRONMENT', 'development')
    with pytest.raises(RuntimeError):
        with postgres_connection():
            pytest.fail('Production override accepted')
    assert connector[1] == []


@pytest.mark.parametrize('index', [0, 1])
def test_dsn_identity_must_match_actual_database_session(connector, index):
    connector[0][index] = 'unexpected_identity'
    with pytest.raises(RuntimeError):
        with postgres_connection():
            pytest.fail('Database session identity mismatch accepted')
