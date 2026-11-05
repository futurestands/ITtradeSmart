"""Synthetic-only tests of non-sensitive MT5 export-gate inspection."""
from types import SimpleNamespace

from tools.diagnose_mt5_export_gates import inspect_flags

class StubMT5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    def __init__(self, *, mode=0, connected=True, account_trade=False, expert=False, terminal_trade=False):
        self.account = SimpleNamespace(trade_mode=mode, trade_allowed=account_trade, trade_expert=expert)
        self.terminal = SimpleNamespace(connected=connected, trade_allowed=terminal_trade)
    def account_info(self):
        return self.account
    def terminal_info(self):
        return self.terminal

def test_fully_disabled_demo_gates_pass():
    result = inspect_flags(StubMT5())
    assert result["status"] == "PASS_READ_ONLY_DEMO_GATES"
    assert result["failed_checks"] == []

def test_account_trade_allowed_blocks():
    assert inspect_flags(StubMT5(account_trade=True))["failed_checks"] == ["account_trading_disabled"]

def test_expert_trade_allowed_blocks():
    assert inspect_flags(StubMT5(expert=True))["failed_checks"] == ["account_expert_disabled"]

def test_terminal_trade_allowed_blocks():
    assert inspect_flags(StubMT5(terminal_trade=True))["failed_checks"] == ["terminal_trading_disabled"]

def test_live_account_blocks():
    assert "demo_account" in inspect_flags(StubMT5(mode=2))["failed_checks"]

def test_not_connected_blocks():
    assert "terminal_connected" in inspect_flags(StubMT5(connected=False))["failed_checks"]

def test_missing_flags_block():
    sdk = StubMT5()
    sdk.account.trade_allowed = None
    result = inspect_flags(sdk)
    assert result["status"] == "BLOCKED"
    assert "account_trading_disabled" in result["failed_checks"]

def test_no_broker_identity_in_report():
    sdk = StubMT5()
    sdk.account.login = 12345678
    sdk.account.server = "secret-broker"
    result = inspect_flags(sdk)
    assert "12345678" not in str(result)
    assert "secret-broker" not in str(result)

def test_sdk_failure_fails_closed():
    class Broken:
        def account_info(self):
            raise RuntimeError("broker credentials should not be echoed")
    result = inspect_flags(Broken())
    assert result["status"] == "BLOCKED"
    assert "credentials" not in str(result)
