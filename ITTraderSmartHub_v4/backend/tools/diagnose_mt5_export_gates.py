r"""Inspect MT5 export permission gates without printing account identifiers or secrets.

From backend, with the intended investor-only demo terminal already open:
    .\.venv-gateway\Scripts\python.exe tools\diagnose_mt5_export_gates.py

No logins, order requests, permission changes or market-data exports are made.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

REQUIRED = (
    "terminal_connected",
    "demo_account",
    "account_trading_disabled",
    "account_expert_disabled",
    "terminal_trading_disabled",
)

def inspect_flags(mt5) -> dict:
    """Inspect only non-sensitive permission values from an already attached SDK."""
    try:
        account, terminal = mt5.account_info(), mt5.terminal_info()
    except Exception:
        return {
            "status": "BLOCKED",
            "reason": "MT5_INFO_UNAVAILABLE",
            "checks": {key: None for key in REQUIRED},
        }

    checks = {
        "terminal_connected": (
            getattr(terminal, "connected", None) is True if terminal is not None else False
        ),
        "demo_account": (
            type(getattr(account, "trade_mode", None)) is int
            and account.trade_mode == getattr(mt5, "ACCOUNT_TRADE_MODE_DEMO", 0)
        ) if account is not None else False,
        "account_trading_disabled": (
            getattr(account, "trade_allowed", None) is False if account is not None else False
        ),
        "account_expert_disabled": (
            getattr(account, "trade_expert", None) is False if account is not None else False
        ),
        "terminal_trading_disabled": (
            getattr(terminal, "trade_allowed", None) is False if terminal is not None else False
        ),
    }
    failed = [key for key in REQUIRED if checks[key] is not True]
    return {
        "status": "PASS_READ_ONLY_DEMO_GATES" if not failed else "BLOCKED",
        "reason": "ALL_REQUIRED_GATES_PASS" if not failed else "REQUIRED_FLAG_NOT_DISABLED",
        "checks": checks,
        "failed_checks": failed,
        "note": "Never relax export checks or switch to trading-enabled credentials.",
    }

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--terminal", default=r"C:\Program Files\MetaTrader 5\terminal64.exe")
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        print(json.dumps({"status": "BLOCKED", "reason": "WINDOWS_REQUIRED"}))
        return 2

    from export_mt5_nas100 import terminal_already_running
    if not Path(args.terminal).is_file() or not terminal_already_running(args.terminal):
        print(json.dumps({"status": "BLOCKED", "reason": "TERMINAL_NOT_ALREADY_RUNNING"}))
        return 2

    try:
        import MetaTrader5 as mt5
    except ImportError:
        print(json.dumps({"status": "BLOCKED", "reason": "MT5_PACKAGE_UNAVAILABLE"}))
        return 2

    initialized = False
    try:
        initialized = bool(mt5.initialize(args.terminal, timeout=10000))
        if not initialized:
            print(json.dumps({"status": "BLOCKED", "reason": "MT5_ATTACHMENT_FAILED"}))
            return 2
        result = inspect_flags(mt5)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "PASS_READ_ONLY_DEMO_GATES" else 2
    except Exception:
        print(json.dumps({"status": "BLOCKED", "reason": "MT5_DIAGNOSTIC_FAILED"}))
        return 2
    finally:
        if initialized:
            try:
                mt5.shutdown()
            except Exception:
                pass

if __name__ == "__main__":
    raise SystemExit(main())
