"""Tests use synthetic account values, NEVER actual trading or broker connections."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compliance_engine import (
    AccountModel, AccountObservation, ComplianceStatus, DataOrigin, POLICIES,
    evaluate_compliance, MaxLossMethod,
)

D = Decimal
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def sample(model=AccountModel.FTMO_2_STEP, **changes):
    offset = 120 if model is AccountModel.FUNDEDNEXT_STELLAR_2_STEP else 60
    start = datetime(2026, 11, 4, 0, 0, tzinfo=timezone.utc) - timedelta(minutes=offset)
    base = AccountObservation(
        model=model, initial_capital=D('100000'), balance=D('100000'),
        equity=D('100000'), day_start_balance=D('100000'),
        observed_at_utc=NOW, session_start_at_utc=start,
        reset_utc_offset_minutes=offset, observation_utc_offset_minutes=offset,
        origin=DataOrigin.SYNTHETIC_TEST, account_currency='USD',
        rules_verified_for_account=True, clock_verified=True, history_verified=True,
        highest_eod_balance=D('100000'), highest_closed_balance=D('100000'),
    )
    return replace(base, **changes)


def check(model=AccountModel.FTMO_2_STEP, **changes):
    return evaluate_compliance(sample(model, **changes), now_utc=NOW)


def test_no_trade_capability_in_report():
    x = check()
    assert x.status is ComplianceStatus.WITHIN_LOSS_LIMITS
    assert x.source is DataOrigin.SYNTHETIC_TEST
    assert x.live_verified is False and x.execution_authorized is False
    assert x.reason_codes == ('SYNTHETIC_TEST_ONLY',)


@pytest.mark.parametrize('model,daily_fund,total_fund,method', [
    (AccountModel.FTMO_2_STEP, '5000', '10000', MaxLossMethod.STATIC),
    (AccountModel.FTMO_1_STEP, '3000', '10000', MaxLossMethod.EOD_TRAILING_BALANCE),
    (AccountModel.FTMO_INSTANT, '3000', '10000', MaxLossMethod.INTRADAY_TRAILING_CLOSED_BALANCE),
    (AccountModel.FUNDEDNEXT_STELLAR_2_STEP, '5000', '10000', MaxLossMethod.STATIC),
])
def test_official_policy_fractions_and_starting_floors(model,daily_fund,total_fund,method):
    p = POLICIES[model]
    assert D('100000') * p.daily_allowance_fraction == D(daily_fund)
    assert D('100000') * p.total_allowance_fraction == D(total_fund)
    assert p.total_method is method
    result = check(model)
    assert result.daily_floor == D('100000') - D(daily_fund)
    assert result.total_floor == D('100000') - D(total_fund)


@pytest.mark.parametrize('equity,status,consumed', [
    ('96000', ComplianceStatus.WARNING, '80'),
    ('95250', ComplianceStatus.CRITICAL, '95'),
    ('95000', ComplianceStatus.BREACHED, '100'),
    ('94000', ComplianceStatus.BREACHED, '120'),
])
def test_ftmo_2_step_daily_warning_critical_and_breach(equity,status,consumed):
    r = check(equity=D(equity))
    assert r.status is status
    assert r.daily_consumed_pct == D(consumed)
    assert r.daily_remaining == max(D('0'), D(equity) - D('95000'))


def test_ftmo_2_step_uses_start_day_balance_not_daily_initial_floor():
    r = check(balance=D('104000'), day_start_balance=D('104000'), equity=D('99000'))
    assert r.daily_floor == D('99000')
    assert r.total_floor == D('90000')
    assert r.status is ComplianceStatus.BREACHED


def test_fundednext_stellar_2_step_uses_initial_allowance_plus_day_profit():
    r = check(AccountModel.FUNDEDNEXT_STELLAR_2_STEP,
              balance=D('102000'), day_start_balance=D('100000'), equity=D('102000'))
    assert r.daily_floor == D('95000')
    assert r.daily_remaining == D('7000')
    assert r.total_floor == D('90000')


def test_fundednext_new_day_does_not_rebase_daily_allowance_from_current_balance():
    r = check(AccountModel.FUNDEDNEXT_STELLAR_2_STEP,
              balance=D('110000'), day_start_balance=D('110000'), equity=D('105000'))
    assert r.daily_floor == D('105000')
    assert r.status is ComplianceStatus.BREACHED


def test_ftmo_1_step_day_floor_uses_three_percent_of_initial_not_current_balance():
    r = check(AccountModel.FTMO_1_STEP,
              balance=D('102000'), day_start_balance=D('102000'),
              highest_eod_balance=D('102000'), equity=D('101500'))
    assert r.daily_floor == D('99000')
    assert r.total_floor == D('92000')
    assert r.daily_remaining == D('2500')  # Google's draft wrongly asserted $3000.
    assert r.status is ComplianceStatus.WITHIN_LOSS_LIMITS


def test_ftmo_1_step_no_unsupported_cap_at_initial_capital():
    r = check(AccountModel.FTMO_1_STEP,
              balance=D('115000'), day_start_balance=D('115000'),
              highest_eod_balance=D('115000'), equity=D('114000'))
    assert r.total_floor == D('105000')  # NOT capped at initial $100,000.
    assert r.total_remaining == D('9000')


def test_ftmo_1_step_highest_eod_does_not_fall_on_later_bad_day():
    r = check(AccountModel.FTMO_1_STEP,
              balance=D('106000'), day_start_balance=D('106000'),
              highest_eod_balance=D('112000'), equity=D('105000'))
    assert r.total_floor == D('102000')
    assert r.total_remaining == D('3000')


def test_ftmo_instant_trails_closed_balance_not_floating_equity_high():
    r = check(AccountModel.FTMO_INSTANT,
              balance=D('101000'), day_start_balance=D('101000'),
              highest_closed_balance=D('105000'), equity=D('100500'))
    assert r.total_floor == D('95000')
    assert r.daily_floor == D('98000')
    assert r.status is ComplianceStatus.WITHIN_LOSS_LIMITS


def test_ftmo_instant_sticky_highwater_after_closed_loss():
    r = check(AccountModel.FTMO_INSTANT,
              balance=D('99000'), day_start_balance=D('99000'),
              highest_closed_balance=D('110000'), equity=D('99000'))
    assert r.total_floor == D('100000')
    assert r.status is ComplianceStatus.BREACHED


def test_ftmo_instant_critical_threshold_from_trailing_balance():
    r = check(AccountModel.FTMO_INSTANT,
              balance=D('96000'), day_start_balance=D('97000'),
              highest_closed_balance=D('105000'), equity=D('95500'))
    assert r.total_floor == D('95000')
    assert r.total_consumed_pct == D('95')
    assert r.status is ComplianceStatus.CRITICAL


@pytest.mark.parametrize('field,value,code', [
    ('origin', DataOrigin.UNVERIFIED, 'UNVERIFIED_SOURCE'),
    ('account_currency', 'EUR', 'UNSUPPORTED_ACCOUNT_CURRENCY'),
    ('clock_verified', False, 'UNVERIFIED_RULE_OR_CLOCK'),
    ('rules_verified_for_account', False, 'UNVERIFIED_RULE_OR_CLOCK'),
    ('initial_capital', D('0'), 'INVALID_MONEY_DATA'),
    ('balance', float('nan'), 'INVALID_MONEY_DATA'),
    ('equity', D('Infinity'), 'INVALID_MONEY_DATA'),
    ('equity', D('1e1000000'), 'INVALID_MONEY_DATA'),
    ('equity', D('1e-1000000'), 'INVALID_MONEY_DATA'),
    ('equity', '100000', 'INVALID_MONEY_DATA'),
    ('observed_at_utc', datetime(2026, 11, 4, 12), 'INVALID_UTC_TIMESTAMPS'),
    ('session_start_at_utc', datetime(2026, 11, 3, 23), 'INVALID_UTC_TIMESTAMPS'),
    ('observation_utc_offset_minutes', 900, 'INVALID_SERVER_OFFSET'),
    ('reset_utc_offset_minutes', True, 'INVALID_SERVER_OFFSET'),
    ('session_start_at_utc', datetime(2026, 11, 4, 0, tzinfo=timezone.utc), 'SESSION_RESET_UNVERIFIED'),
])
def test_broker_data_validation_fails_unknown(field,value,code):
    r=check(**{field: value})
    assert r.status is ComplianceStatus.UNKNOWN
    assert r.reason_codes == (code,)
    assert r.daily_floor is None and r.total_floor is None
    assert r.execution_authorized is False


def test_stale_data_or_future_data_is_unknown():
    assert check(observed_at_utc=NOW - timedelta(seconds=121)).reason_codes == ('STALE_OR_FUTURE_OBSERVATION',)
    assert check(observed_at_utc=NOW + timedelta(seconds=1)).status is ComplianceStatus.UNKNOWN


def test_late_reset_is_unknown_even_if_balance_data_recent():
    r = check(session_start_at_utc=NOW - timedelta(hours=40))
    assert r.reason_codes == ('SESSION_RESET_UNVERIFIED',)


def test_unverified_eod_or_closed_history_is_unknown():
    for model in (AccountModel.FTMO_1_STEP, AccountModel.FTMO_INSTANT):
        r = check(model, history_verified=False)
        assert r.status is ComplianceStatus.UNKNOWN
        assert 'HISTORY_UNVERIFIED' in r.reason_codes[0]


def test_eod_and_closed_history_cannot_be_lower_than_known_balances():
    assert check(AccountModel.FTMO_1_STEP,
                 highest_eod_balance=D('101000'), day_start_balance=D('102000')).reason_codes == ('INCONSISTENT_EOD_HISTORY',)
    assert check(AccountModel.FTMO_INSTANT,
                 highest_closed_balance=D('101000'), balance=D('102000')).reason_codes == ('INCONSISTENT_CLOSED_HISTORY',)


def test_dst_spring_ftmo_with_changed_attested_offset():
    # Prague/CET reset 2026-03-29 00:00 UTC+1 is 2026-03-28 23:00Z.
    # Afternoon after DST switch the observed offset is UTC+2, same trade day.
    now = datetime(2026, 3, 29, 12, tzinfo=timezone.utc)
    s = sample(observed_at_utc=now,
               session_start_at_utc=datetime(2026,3,28,23,tzinfo=timezone.utc),
               reset_utc_offset_minutes=60, observation_utc_offset_minutes=120)
    r = evaluate_compliance(s, now_utc=now)
    assert r.status is ComplianceStatus.WITHIN_LOSS_LIMITS


def test_dst_autumn_ftmo_with_changed_attested_offset():
    # Prague/CEST reset 2026-10-25 00:00 UTC+2 is 2026-10-24 22:00Z.
    now = datetime(2026,10,25,12,tzinfo=timezone.utc)
    s = sample(observed_at_utc=now,
               session_start_at_utc=datetime(2026,10,24,22,tzinfo=timezone.utc),
               reset_utc_offset_minutes=120, observation_utc_offset_minutes=60)
    assert evaluate_compliance(s, now_utc=now).status is ComplianceStatus.WITHIN_LOSS_LIMITS


@pytest.mark.parametrize('offset,utc_start',[(120,22),(180,21)])
def test_fundednext_explicit_attested_server_offsets(offset,utc_start):
    start=datetime(2026,11,3,utc_start,tzinfo=timezone.utc)
    r = check(AccountModel.FUNDEDNEXT_STELLAR_2_STEP,
              session_start_at_utc=start,
              reset_utc_offset_minutes=offset, observation_utc_offset_minutes=offset)
    assert r.status is ComplianceStatus.WITHIN_LOSS_LIMITS


def test_unverified_account_model_and_snapshot_are_unknown():
    r=evaluate_compliance('untrusted data',now_utc=NOW)
    assert r.status is ComplianceStatus.UNKNOWN
    assert r.reason_codes==('INVALID_OBSERVATION',)
    r=evaluate_compliance(replace(sample(), model='FTMO_GENERIC'), now_utc=NOW)
    assert r.status is ComplianceStatus.UNKNOWN
    assert r.reason_codes==('UNKNOWN_ACCOUNT_MODEL',)


def test_broker_named_observation_is_unknown_without_real_readonly_adapter():
    # Merely labelling a snapshot as broker-connected must never prove its origin.
    r = check(origin=DataOrigin.BROKER_READ_ONLY)
    assert r.status is ComplianceStatus.UNKNOWN
    assert r.reason_codes == ("BROKER_ADAPTER_NOT_IMPLEMENTED",)
    assert r.execution_authorized is False
    assert r.live_verified is False


def test_ftmo_1step_missing_required_highwater_never_looks_compliant():
    r=check(AccountModel.FTMO_1_STEP, highest_eod_balance=None)
    assert r.status is ComplianceStatus.UNKNOWN


def test_exact_loss_floor_is_breached_conservatively():
    r=check(AccountModel.FTMO_2_STEP, equity=D('90000'), day_start_balance=D('94000'))
    assert r.total_floor == D('90000')
    assert r.status is ComplianceStatus.BREACHED


def test_no_margin_trade_lot_position_size_or_orders_in_engine():
    import compliance_engine as mod
    assert not hasattr(mod, 'send_order')
    assert not hasattr(mod, 'calculate_lots')
    assert not hasattr(mod, 'place_trade')
