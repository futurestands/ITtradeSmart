"""Pure synthetic history tests; never connect to user MT5, Gateway or profile registry."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
import sqlite3

import pytest

from compliance_engine import AccountModel, DataOrigin
from observation_ledger import ObservationLedger, ObservationEvent, EventKind

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
START = datetime(2026, 11, 3, 23, 0, tzinfo=timezone.utc)


def example(kind=EventKind.SNAPSHOT, **changes):
    event = ObservationEvent(
        alias='ftmo_demo', model=AccountModel.FTMO_2_STEP, kind=kind,
        observed_at_utc=NOW, session_start_utc=START,
        initial_capital=D('100000'), balance=D('100500'),
        equity=D('100450.25'), day_start_balance=D('100000'),
        reset_offset_minutes=60, observation_offset_minutes=60,
    )
    return replace(event, **changes)


@pytest.fixture
def ledger(tmp_path):
    return ObservationLedger(tmp_path / 'synthetic_observations.sqlite3')


def test_local_append_and_read(ledger):
    assert ledger.append(example()) == 1
    result = ledger.summary('ftmo_demo')
    assert result.count == 1
    assert result.latest.balance == D('100500')
    assert result.latest.equity == D('100450.25')
    assert result.live_verified is False and result.history_complete is False
    assert result.execution_authorized is False
    assert result.highest_recorded_closed_balance is None


def test_restart_recovery(tmp_path):
    f = tmp_path / 'restart.sqlite3'
    ObservationLedger(f).append(example())
    assert ObservationLedger(f).summary('ftmo_demo').count == 1


def test_writes_are_atomic_and_reject_duplicates(ledger):
    ledger.append(example())
    with pytest.raises(ValueError, match='NON_MONOTONIC'):
        ledger.append(example(kind=EventKind.CLOSED_BALANCE))
    assert ledger.summary('ftmo_demo').count == 1


def test_monotonic_same_account_order(ledger):
    ledger.append(example())
    later = example(observed_at_utc=NOW + timedelta(seconds=1), balance=D('100700'))
    assert ledger.append(later) == 2
    assert ledger.summary('ftmo_demo').count == 2
    with pytest.raises(ValueError, match='NON_MONOTONIC'):
        ledger.append(example(observed_at_utc=NOW - timedelta(seconds=1)))


def test_event_highwater_separate_eod_and_closed(ledger):
    ledger.append(example(EventKind.CLOSED_BALANCE))
    ledger.append(example(EventKind.END_OF_DAY_BALANCE,
                          observed_at_utc=NOW + timedelta(seconds=1), balance=D('100750')))
    ledger.append(example(EventKind.CLOSED_BALANCE,
                          observed_at_utc=NOW + timedelta(seconds=2), balance=D('100900')))
    ledger.append(example(EventKind.END_OF_DAY_BALANCE,
                          observed_at_utc=NOW + timedelta(seconds=3), balance=D('100600')))
    result = ledger.summary('ftmo_demo')
    assert result.highest_recorded_eod_balance == D('100750')
    assert result.highest_recorded_closed_balance == D('100900')
    assert result.history_complete is False


def test_profile_isolation(ledger):
    ledger.append(example())
    ledger.append(example(alias='second_demo'))
    assert ledger.summary('ftmo_demo').count == 1
    assert ledger.summary('second_demo').count == 1
    assert ledger.summary('no_match') is None


def test_account_model_or_initial_capital_change_blocked(ledger):
    ledger.append(example())
    with pytest.raises(ValueError, match='PROFILE_MODEL_OR_INITIAL'):
        ledger.append(example(observed_at_utc=NOW+timedelta(seconds=1), model=AccountModel.FTMO_1_STEP))
    with pytest.raises(ValueError, match='PROFILE_MODEL_OR_INITIAL'):
        ledger.append(example(observed_at_utc=NOW+timedelta(seconds=1), initial_capital=D('200000')))
    assert ledger.summary('ftmo_demo').count == 1


@pytest.mark.parametrize('field,value,reason', [
    ('alias', '../../keys', 'INVALID_ALIAS'),
    ('alias', 'a', 'INVALID_ALIAS'),
    ('alias', 'FTMO', 'INVALID_ALIAS'),
    ('origin', DataOrigin.BROKER_READ_ONLY, 'BROKER_ADAPTER_NOT_IMPLEMENTED'),
    ('origin', DataOrigin.UNVERIFIED, 'BROKER_ADAPTER_NOT_IMPLEMENTED'),
    ('initial_capital', D('0'), 'INVALID_MONEY_DATA'),
    ('initial_capital', D('NaN'), 'INVALID_MONEY_DATA'),
    ('equity', float('inf'), 'INVALID_MONEY_DATA'),
    ('balance', D('1e100000'), 'INVALID_MONEY_DATA'),
    ('currency', 'EUR', 'UNSUPPORTED_CURRENCY'),
    ('model', 'FTMO_FAKE', 'INVALID_MODEL_OR_KIND'),
    ('kind', 'ORDER', 'INVALID_MODEL_OR_KIND'),
    ('observed_at_utc', NOW.replace(tzinfo=None), 'INVALID_UTC_TIME'),
    ('reset_offset_minutes', 300, 'INVALID_SERVER_TIME_OFFSET'),
    ('session_start_utc', NOW + timedelta(days=1), 'INVALID_SESSION_TIME'),
    ('session_start_utc', NOW - timedelta(days=2), 'SESSION_RESET_UNVERIFIED'),
    ('session_start_utc', NOW, 'SESSION_RESET_UNVERIFIED'),
])
def test_rejects_invalid_observations(ledger,field,value,reason):
    with pytest.raises(ValueError, match=reason):
        ledger.append(example(**{field:value}))
    assert ledger.summary('ftmo_demo') is None


def test_sqlite_read_write_protection(ledger):
    ledger.append(example())
    with sqlite3.connect(ledger.path) as db:
        with pytest.raises(sqlite3.DatabaseError, match='APPEND_ONLY'):
            db.execute("UPDATE observation_events SET equity='999' WHERE id=1")
        with pytest.raises(sqlite3.DatabaseError, match='APPEND_ONLY'):
            db.execute("DELETE FROM observation_events WHERE id=1")
    assert ledger.summary('ftmo_demo').latest.equity == D('100450.25')


def test_no_default_path_or_unexpected_credentials(tmp_path):
    with pytest.raises(ValueError,match='EXPLICIT_DB_PATH_REQUIRED'):
        ObservationLedger('')
    with pytest.raises(ValueError,match='UNSAFE_DB_LOCATION'):
        ObservationLedger(tmp_path / 'not_created' / 'database.sqlite3')
    ledger = ObservationLedger(tmp_path / 'empty.sqlite3')
    assert ledger.summary('ftmo_demo') is None


def test_ftmo_spring_dst_event_valid(ledger):
    # Same CE(S)T trading day, observed after DST jump.
    event=example(observed_at_utc=datetime(2026,3,29,12,tzinfo=timezone.utc),
                  session_start_utc=datetime(2026,3,28,23,tzinfo=timezone.utc),
                  reset_offset_minutes=60,observation_offset_minutes=120)
    ledger.append(event)
    assert ledger.summary('ftmo_demo').count == 1


def test_ftmo_fall_dst_event_valid(ledger):
    event=example(observed_at_utc=datetime(2026,10,25,12,tzinfo=timezone.utc),
                  session_start_utc=datetime(2026,10,24,22,tzinfo=timezone.utc),
                  reset_offset_minutes=120,observation_offset_minutes=60)
    ledger.append(event)
    assert ledger.summary('ftmo_demo').count == 1


def test_no_order_execution_capabilities():
    import observation_ledger
    assert not hasattr(observation_ledger,'send_order')
    assert not hasattr(observation_ledger,'execute_trade')
    assert not hasattr(observation_ledger,'connect_mt5')


def test_same_session_day_start_balance_cannot_change(ledger):
    ledger.append(example())
    with pytest.raises(ValueError, match='SESSION_BASELINE_CHANGED'):
        ledger.append(example(observed_at_utc=NOW+timedelta(seconds=2),
                              day_start_balance=D('99999')))
    assert ledger.summary('ftmo_demo').count == 1


def test_new_session_baseline_may_change_but_remains_unverified(ledger):
    first = example(observed_at_utc=datetime(2026,11,4,20,tzinfo=timezone.utc))
    ledger.append(first)
    next_session = example(observed_at_utc=datetime(2026,11,5,12,tzinfo=timezone.utc),
                           session_start_utc=datetime(2026,11,4,23,tzinfo=timezone.utc),
                           day_start_balance=D('100500'))
    ledger.append(next_session)
    result = ledger.summary('ftmo_demo')
    assert result.count == 2
    assert result.latest.day_start_balance == D('100500')
    assert result.history_complete is False and result.live_verified is False
