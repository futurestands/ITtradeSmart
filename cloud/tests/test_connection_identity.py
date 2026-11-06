"""Mock connector only. No PostgreSQL or Neon SQL is executed."""
from contextlib import contextmanager
from types import SimpleNamespace
import sys
import pytest
import certifi
from psycopg.conninfo import make_conninfo, conninfo_to_dict
from auth_store import postgres_connection, PRIVATE_LOGIN, RUNTIME_ROLE, IDENTITY_SQL


@pytest.fixture
def connector(monkeypatch):
    monkeypatch.setenv('VERCEL_ENV', 'preview')
    monkeypatch.setenv('SMARTHUB_CLOUD_DATABASE_URL',
                       'postgresql://'+PRIVATE_LOGIN+'@ep-synthetic-pooler.us-east-2.aws.neon.tech/test?sslmode=verify-full')
    monkeypatch.setenv('SMARTHUB_CLOUD_DATABASE_HOST', 'ep-synthetic-pooler.us-east-2.aws.neon.tech')
    monkeypatch.setenv('SMARTHUB_CLOUD_DATABASE_NAME', 'test')
    identity = [PRIVATE_LOGIN, PRIVATE_LOGIN] + [False]*11
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
    assert "SET LOCAL idle_in_transaction_session_timeout = '10s'" in calls


@pytest.mark.parametrize('index', range(2, 13))
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


def test_final_gate_tls_and_pooling_settings_are_explicit(connector):
    with postgres_connection():
        pass
    settings = connector[1][0]
    assert settings['sslrootcert'] == certifi.where()
    assert settings['sslmode'] == 'verify-full'
    assert settings['channel_binding'] == 'require'
    assert settings['options'] == ''
    assert settings['prepare_threshold'] is None
    assert settings['autocommit'] is False
    assert "SET LOCAL statement_timeout = '5s'" in connector[1]
    assert "SET LOCAL idle_in_transaction_session_timeout = '10s'" in connector[1]


@pytest.mark.parametrize('extra', ['options=role%3Dadmin', 'hostaddr=127.0.0.1',
                                  'service=untrusted', 'sslrootcert=untrusted.pem',
                                  'channel_binding=disable', 'sslmode=require'])
def test_final_gate_dsn_cannot_override_trust_target_or_startup(connector, monkeypatch, extra):
    import os
    monkeypatch.setenv('SMARTHUB_CLOUD_DATABASE_URL', os.environ['SMARTHUB_CLOUD_DATABASE_URL']+'&'+extra)
    with pytest.raises(RuntimeError):
        with postgres_connection():
            pytest.fail('Unsafe DSN override accepted')
    assert connector[1] == []


@pytest.mark.parametrize('key,value', [('SMARTHUB_CLOUD_DATABASE_HOST','ep-other-pooler.us-east-2.aws.neon.tech'),
                                      ('SMARTHUB_CLOUD_DATABASE_NAME','other_database'),
                                      ('SMARTHUB_CLOUD_DATABASE_HOST',''),
                                      ('SMARTHUB_CLOUD_DATABASE_NAME','')])
def test_final_gate_approved_target_is_required(connector, monkeypatch, key, value):
    monkeypatch.setenv(key,value)
    with pytest.raises(RuntimeError):
        with postgres_connection():
            pytest.fail('Unapproved database target accepted')
    assert connector[1] == []


@pytest.mark.parametrize('key', ['PGOPTIONS','PGSERVICE'])
def test_final_gate_implicit_connection_configuration_is_rejected(connector, monkeypatch, key):
    monkeypatch.setenv(key,'untrusted')
    with pytest.raises(RuntimeError):
        with postgres_connection():
            pytest.fail('Implicit PostgreSQL options admitted')
    assert connector[1] == []


def test_final_gate_libpq_accepts_the_tls_parameters_offline(connector):
    from pathlib import Path
    with postgres_connection():
        pass
    settings = dict(connector[1][0])
    settings.pop('prepare_threshold')
    settings.pop('autocommit')
    parsed = conninfo_to_dict(make_conninfo(**settings))
    assert parsed['sslmode'] == 'verify-full' and parsed['channel_binding'] == 'require'
    assert Path(parsed['sslrootcert']).is_file()
