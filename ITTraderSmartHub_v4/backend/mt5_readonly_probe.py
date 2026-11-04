"""Guarded *local* MT5 inspection, not a broker-history or execution adapter.

NO module import, login, initialize, network I/O, persistence or SDK call is
performed at import time. A caller must explicitly pass a previously attached
MetaTrader5 API object; this function never logs in or changes accounts.

The account's trade_allowed == False and terminal trade-disabled flag are
necessary gates, not cryptographic proof of investor-password provenance.
Results remain UNVERIFIED and cannot approve trades or attest firm compliance.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

_ALIAS = re.compile(r"[a-z][a-z0-9_-]{2,31}\Z")
_SYMBOL = re.compile(r"[A-Za-z0-9._-]{2,32}\Z")


class ReadOnlyProbeError(ValueError):
    """Codes only; never echo account number, terminal path or credentials."""


@dataclass(frozen=True)
class UnverifiedMt5Observation:
    alias: str
    symbol: str
    observed_at_utc: datetime
    balance: Decimal
    equity: Decimal
    floating_profit: Decimal
    tick_size: Decimal
    tick_value_loss: Decimal
    contract_size: Decimal
    volume_min: Decimal
    volume_max: Decimal
    volume_step: Decimal
    account_currency: str
    origin: str = "LOCAL_MT5_READ_UNATTESTED"
    account_identity_matched: bool = True
    broker_rules_verified: bool = False
    clock_verified: bool = False
    history_complete: bool = False
    live_verified: bool = False
    execution_authorized: bool = False


def _money(value: Any) -> Decimal:
    if type(value) not in (int, float, Decimal):
        raise ReadOnlyProbeError("INVALID_MONETARY_VALUE")
    number = Decimal(str(value))
    if not number.is_finite() or (not number.is_zero() and not -12 <= number.adjusted() <= 11):
        raise ReadOnlyProbeError("INVALID_MONETARY_VALUE")
    return number


def _positive(value: Any) -> Decimal:
    number = _money(value)
    if number <= 0:
        raise ReadOnlyProbeError("INVALID_SYMBOL_SPECIFICATION")
    return number


def inspect_attached_terminal(
    api: Any,
    *,
    expected_login: int,
    expected_server: str,
    alias: str,
    symbol: str,
    observed_at_utc: datetime | None = None,
) -> UnverifiedMt5Observation:
    """Read-only snapshot from an ALREADY ATTACHED terminal; NO initialize().

    The expected login and server are supplied by a trusted *local operator*,
    not a request from Android. They are checked but never included in output.
    Supplying a test double does not attest provenance; snapshot is unverified.
    """
    if type(expected_login) is not int or expected_login <= 0 or expected_login >= 10**18:
        raise ReadOnlyProbeError("INVALID_EXPECTED_ACCOUNT_ID")
    if not isinstance(expected_server, str) or not 1 <= len(expected_server) <= 120:
        raise ReadOnlyProbeError("INVALID_EXPECTED_SERVER")
    if not isinstance(alias, str) or not _ALIAS.fullmatch(alias):
        raise ReadOnlyProbeError("INVALID_ACCOUNT_ALIAS")
    if not isinstance(symbol, str) or not _SYMBOL.fullmatch(symbol):
        raise ReadOnlyProbeError("INVALID_SYMBOL")
    now = observed_at_utc if observed_at_utc is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset().total_seconds() != 0:
        raise ReadOnlyProbeError("INVALID_UTC_TIME")
    if not all(callable(getattr(api, x, None)) for x in ("account_info", "terminal_info", "symbol_info")):
        raise ReadOnlyProbeError("MT5_API_UNAVAILABLE")

    # Read only. No retries, terminal launch, account switching, password or order methods.
    terminal = api.terminal_info()
    if terminal is None or getattr(terminal, "connected", None) is not True:
        raise ReadOnlyProbeError("TERMINAL_DISCONNECTED")
    if getattr(terminal, "trade_allowed", None) is not False:
        raise ReadOnlyProbeError("TERMINAL_TRADING_MUST_BE_DISABLED")
    account = api.account_info()
    if account is None:
        raise ReadOnlyProbeError("ACCOUNT_INFO_UNAVAILABLE")
    if getattr(account, "trade_allowed", None) is not False:
        raise ReadOnlyProbeError("ACCOUNT_TRADING_MUST_BE_DISABLED")
    if getattr(account, "login", None) != expected_login or getattr(account, "server", None) != expected_server:
        raise ReadOnlyProbeError("ACCOUNT_IDENTITY_MISMATCH")
    currency = getattr(account, "currency", None)
    if currency != "USD":
        raise ReadOnlyProbeError("NON_USD_ACCOUNT_UNSUPPORTED")

    info = api.symbol_info(symbol)
    if info is None or getattr(info, "name", None) != symbol:
        raise ReadOnlyProbeError("SYMBOL_NOT_VERIFIED")

    minimum = _positive(getattr(info, "volume_min", None))
    maximum = _positive(getattr(info, "volume_max", None))
    step = _positive(getattr(info, "volume_step", None))
    if minimum > maximum:
        raise ReadOnlyProbeError("INVALID_SYMBOL_SPECIFICATION")
    snapshot = UnverifiedMt5Observation(
        alias=alias,
        symbol=symbol,
        observed_at_utc=now,
        balance=_money(getattr(account, "balance", None)),
        equity=_money(getattr(account, "equity", None)),
        floating_profit=_money(getattr(account, "profit", None)),
        tick_size=_positive(getattr(info, "trade_tick_size", None)),
        tick_value_loss=_positive(getattr(info, "trade_tick_value_loss", None)),
        contract_size=_positive(getattr(info, "trade_contract_size", None)),
        volume_min=minimum,
        volume_max=maximum,
        volume_step=step,
        account_currency=currency,
    )
    # Re-read account and connection after symbol inspection to fail if the
    # operator switches terminals/accounts during the snapshot.
    end_account = api.account_info()
    end_terminal = api.terminal_info()
    if (end_account is None or end_terminal is None
            or getattr(end_account, "login", None) != expected_login
            or getattr(end_account, "server", None) != expected_server
            or getattr(end_account, "trade_allowed", None) is not False
            or getattr(end_terminal, "connected", None) is not True
            or getattr(end_terminal, "trade_allowed", None) is not False):
        raise ReadOnlyProbeError("SESSION_CHANGED_DURING_READ")
    return snapshot
