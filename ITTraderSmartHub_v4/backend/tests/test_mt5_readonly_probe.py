"""Deterministic fake-MT5 tests: no MetaTrader5 dependency or actual broker I/O."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timezone
from decimal import Decimal as D
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from mt5_readonly_probe import inspect_attached_terminal, ReadOnlyProbeError

NOW = datetime(2026, 11, 4, 14, 0, tzinfo=timezone.utc)


def fake_session():
    terminal = SimpleNamespace(connected=True, trade_allowed=False)
    account = SimpleNamespace(
        login=12345678, server="Example-Demo", trade_allowed=False,
        currency="USD", balance=100000.0, equity=99950.5, profit=-49.5,
    )
    spec = SimpleNamespace(
        name="US100", trade_tick_size=0.1, trade_tick_value_loss=0.25,
        trade_contract_size=1.0, volume_min=0.01, volume_max=100.0, volume_step=0.01,
    )
    api = SimpleNamespace(
        terminal_info=Mock(return_value=terminal),
        account_info=Mock(return_value=account),
        symbol_info=Mock(return_value=spec),
    )
    return api, terminal, account, spec


def inspect(api, **kwargs):
    fields = dict(expected_login=12345678, expected_server="Example-Demo",
                  alias="ftmo_trial", symbol="US100", observed_at_utc=NOW)
    fields.update(kwargs)
    return inspect_attached_terminal(api, **fields)


def test_valid_readonly_snapshot_is_explicitly_unverified():
    api, terminal, account, spec = fake_session()
    got = inspect(api)
    assert got.balance == D("100000.0") and got.equity == D("99950.5")
    assert got.tick_value_loss == D("0.25") and got.volume_step == D("0.01")
    assert got.live_verified is False and got.history_complete is False
    assert got.broker_rules_verified is False and got.clock_verified is False
    assert got.execution_authorized is False
    assert not hasattr(got, "login") and not hasattr(got, "server")
    assert api.account_info.call_count == 2 and api.terminal_info.call_count == 2
    api.symbol_info.assert_called_once_with("US100")


@pytest.mark.parametrize("property,value,reason", [
    ("connected", False, "TERMINAL_DISCONNECTED"),
    ("connected", None, "TERMINAL_DISCONNECTED"),
    ("trade_allowed", True, "TERMINAL_TRADING_MUST_BE_DISABLED"),
    ("trade_allowed", None, "TERMINAL_TRADING_MUST_BE_DISABLED"),
])
def test_terminal_state_blocked(property, value, reason):
    api, terminal, _, _ = fake_session()
    setattr(terminal, property, value)
    with pytest.raises(ReadOnlyProbeError, match=reason):
        inspect(api)
    api.symbol_info.assert_not_called()


@pytest.mark.parametrize("property,value,reason", [
    ("trade_allowed", True, "ACCOUNT_TRADING_MUST_BE_DISABLED"),
    ("trade_allowed", None, "ACCOUNT_TRADING_MUST_BE_DISABLED"),
    ("login", 87654321, "ACCOUNT_IDENTITY_MISMATCH"),
    ("server", "Wrong-Server", "ACCOUNT_IDENTITY_MISMATCH"),
    ("currency", "EUR", "NON_USD_ACCOUNT_UNSUPPORTED"),
])
def test_account_state_blocked(property, value, reason):
    api, _, account, _ = fake_session()
    setattr(account, property, value)
    with pytest.raises(ReadOnlyProbeError, match=reason):
        inspect(api)
    api.symbol_info.assert_not_called()


@pytest.mark.parametrize("property,value,reason", [
    ("name", "NAS100", "SYMBOL_NOT_VERIFIED"),
    ("trade_tick_size", 0, "INVALID_SYMBOL_SPECIFICATION"),
    ("trade_tick_value_loss", 0, "INVALID_SYMBOL_SPECIFICATION"),
    ("volume_min", -0.01, "INVALID_SYMBOL_SPECIFICATION"),
    ("volume_max", float('nan'), "INVALID_MONETARY_VALUE"),
    ("volume_step", None, "INVALID_MONETARY_VALUE"),
    ("trade_contract_size", float('inf'), "INVALID_MONETARY_VALUE"),
])
def test_symbol_specs_blocked(property, value, reason):
    api, _, _, spec = fake_session()
    setattr(spec, property, value)
    with pytest.raises(ReadOnlyProbeError, match=reason):
        inspect(api)


@pytest.mark.parametrize("property,value", [
    ("balance", float('nan')),
    ("equity", float('inf')),
    ("profit", "100"),
])
def test_invalid_account_money_fails_closed(property, value):
    api, _, account, _ = fake_session()
    setattr(account, property, value)
    with pytest.raises(ReadOnlyProbeError, match="INVALID_MONETARY_VALUE"):
        inspect(api)


def test_no_mt5_autoinitialize_login_orders_or_shutdown():
    api, _, _, _ = fake_session()
    api.initialize = Mock(side_effect=AssertionError("MUST NOT INITIALIZE"))
    api.login = Mock(side_effect=AssertionError("MUST NOT SWITCH ACCOUNT"))
    api.order_send = Mock(side_effect=AssertionError("MUST NOT TRADE"))
    api.shutdown = Mock(side_effect=AssertionError("MUST NOT SHUTDOWN EXISTING SESSION"))
    inspect(api)
    api.initialize.assert_not_called()
    api.login.assert_not_called()
    api.order_send.assert_not_called()
    api.shutdown.assert_not_called()


def test_mid_read_account_change_fails_closed():
    api, _, account, _ = fake_session()
    other = SimpleNamespace(**vars(account))
    other.login = 98765432
    api.account_info.side_effect = [account, other]
    with pytest.raises(ReadOnlyProbeError, match="SESSION_CHANGED_DURING_READ"):
        inspect(api)


def test_mid_read_trade_permission_change_fails_closed():
    api, terminal, _, _ = fake_session()
    trading = SimpleNamespace(connected=True, trade_allowed=True)
    api.terminal_info.side_effect = [terminal, trading]
    with pytest.raises(ReadOnlyProbeError, match="SESSION_CHANGED_DURING_READ"):
        inspect(api)


@pytest.mark.parametrize("kwargs,reason", [
    ({"expected_login": 0}, "INVALID_EXPECTED_ACCOUNT_ID"),
    ({"expected_login": "12345678"}, "INVALID_EXPECTED_ACCOUNT_ID"),
    ({"alias": "../private"}, "INVALID_ACCOUNT_ALIAS"),
    ({"symbol": "US100;order_send"}, "INVALID_SYMBOL"),
    ({"expected_server": ""}, "INVALID_EXPECTED_SERVER"),
    ({"observed_at_utc": datetime(2026, 11, 4)}, "INVALID_UTC_TIME"),
])
def test_local_operator_arguments_rejected(kwargs, reason):
    api, _, _, _ = fake_session()
    with pytest.raises(ReadOnlyProbeError, match=reason):
        inspect(api, **kwargs)


def test_missing_sdk_methods_is_unavailable():
    with pytest.raises(ReadOnlyProbeError, match="MT5_API_UNAVAILABLE"):
        inspect(SimpleNamespace())


def test_disconnected_terminal_does_not_read_account():
    api, terminal, _, _ = fake_session()
    terminal.connected = False
    with pytest.raises(ReadOnlyProbeError):
        inspect(api)
    api.account_info.assert_not_called()
