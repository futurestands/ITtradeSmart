"""Research-stage, read-only prop-firm loss-threshold calculations.

This module is deliberately NOT connected to Flask, Android or MT5. A typed
snapshot is not a broker connection; the upstream server must independently
attest account identity, fresh equity, session clock and historical maxima.

Policy references were reviewed 2026-11-04. Re-verify against current firm
objectives and exact purchased account terms before production deployment.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional


class AccountModel(str, Enum):
    FTMO_2_STEP = "FTMO_2_STEP"
    FTMO_1_STEP = "FTMO_1_STEP"
    FTMO_INSTANT = "FTMO_INSTANT"
    FUNDEDNEXT_STELLAR_2_STEP = "FUNDEDNEXT_STELLAR_2_STEP"


class DataOrigin(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"
    BROKER_READ_ONLY = "BROKER_READ_ONLY"


class ComplianceStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    WITHIN_LOSS_LIMITS = "WITHIN_LOSS_LIMITS"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    BREACHED = "BREACHED"


class MaxLossMethod(str, Enum):
    STATIC = "STATIC"
    EOD_TRAILING_BALANCE = "EOD_TRAILING_BALANCE"
    INTRADAY_TRAILING_CLOSED_BALANCE = "INTRADAY_TRAILING_CLOSED_BALANCE"


@dataclass(frozen=True)
class RulePolicy:
    model: AccountModel
    daily_allowance_fraction: Decimal
    total_allowance_fraction: Decimal
    total_method: MaxLossMethod
    reset_zone: str
    reset_offsets_minutes: frozenset[int]
    source_url: str
    reviewed_on: str = "2026-11-04"


# These are specific account models, NOT interchangeable provider defaults.
# FTMO: https://ftmo.com/en/trading-objectives/
# FundedNext: https://help.fundednext.com/en/articles/9941519-daily-loss-limit-vs-maximum-loss-limit
POLICIES = {
    AccountModel.FTMO_2_STEP: RulePolicy(
        AccountModel.FTMO_2_STEP, Decimal("0.05"), Decimal("0.10"),
        MaxLossMethod.STATIC, "CE(S)T", frozenset({60, 120}),
        "https://ftmo.com/en/trading-objectives/",
    ),
    AccountModel.FTMO_1_STEP: RulePolicy(
        AccountModel.FTMO_1_STEP, Decimal("0.03"), Decimal("0.10"),
        MaxLossMethod.EOD_TRAILING_BALANCE, "CE(S)T", frozenset({60, 120}),
        "https://ftmo.com/en/trading-objectives/",
    ),
    AccountModel.FTMO_INSTANT: RulePolicy(
        AccountModel.FTMO_INSTANT, Decimal("0.03"), Decimal("0.10"),
        MaxLossMethod.INTRADAY_TRAILING_CLOSED_BALANCE,
        "CE(S)T", frozenset({60, 120}),
        "https://ftmo.com/en/trading-objectives/",
    ),
    AccountModel.FUNDEDNEXT_STELLAR_2_STEP: RulePolicy(
        AccountModel.FUNDEDNEXT_STELLAR_2_STEP, Decimal("0.05"), Decimal("0.10"),
        MaxLossMethod.STATIC, "BROKER_SERVER", frozenset({120, 180}),
        "https://help.fundednext.com/en/articles/9941519-daily-loss-limit-vs-maximum-loss-limit",
    ),
}


@dataclass(frozen=True)
class AccountObservation:
    """Attested, same-account values, with an explicitly observed reset window.

    Equity must INCLUDE floating P/L, swap and commission effects. High-water
    balances must be tracked independently by the trusted server-side ledger;
    an arbitrary Android JSON field cannot constitute trusted history.

    For DST, both offsets are REQUIRED from a verified server clock. They may
    differ on a transition day. No automatic assumption about FundedNext's
    GMT+2/GMT+3 seasonal transition date is made here.
    """
    model: AccountModel
    initial_capital: Decimal
    balance: Decimal
    equity: Decimal
    day_start_balance: Decimal
    observed_at_utc: datetime
    session_start_at_utc: datetime
    reset_utc_offset_minutes: int
    observation_utc_offset_minutes: int
    origin: DataOrigin = DataOrigin.UNVERIFIED
    account_currency: str = "USD"
    clock_verified: bool = False
    rules_verified_for_account: bool = False
    history_verified: bool = False
    highest_eod_balance: Optional[Decimal] = None
    highest_closed_balance: Optional[Decimal] = None


@dataclass(frozen=True)
class ComplianceReport:
    status: ComplianceStatus
    source: DataOrigin
    live_verified: bool
    policy_model: Optional[str]
    policy_reviewed_on: Optional[str]
    daily_floor: Optional[Decimal]
    total_floor: Optional[Decimal]
    daily_remaining: Optional[Decimal]
    total_remaining: Optional[Decimal]
    daily_consumed_pct: Optional[Decimal]
    total_consumed_pct: Optional[Decimal]
    reason_codes: tuple[str, ...]
    execution_authorized: bool = False
    assessment_scope: str = "LOSS_LIMITS_ONLY"


def _unknown(reason: str, model: Optional[AccountModel] = None) -> ComplianceReport:
    return ComplianceReport(
        ComplianceStatus.UNKNOWN, DataOrigin.UNVERIFIED, False,
        model.value if isinstance(model, AccountModel) else None,
        None, None, None, None, None, None, None, (reason,), False,
    )


def _money(value: object) -> bool:
    # Reject nonfinite, absurdly large or extreme-exponent input. This also
    # prevents Decimal overflow during subsequent risk arithmetic.
    return (
        type(value) is Decimal and value.is_finite()
        and (value.is_zero() or -12 <= value.adjusted() <= 11)
    )


def _aware_utc(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() == timedelta(0)
    )


def _checked_snapshot(o: AccountObservation, *, now_utc: datetime, max_age_seconds: int) -> Optional[str]:
    if not isinstance(o.model, AccountModel) or o.model not in POLICIES:
        return "UNKNOWN_ACCOUNT_MODEL"
    if not isinstance(o.origin, DataOrigin) or o.origin is DataOrigin.UNVERIFIED:
        return "UNVERIFIED_SOURCE"
    if o.origin is DataOrigin.BROKER_READ_ONLY:
        # Future read-only adapter must provide non-forgeable provenance. Until
        # that integration exists, a caller-supplied label is NOT verification.
        return "BROKER_ADAPTER_NOT_IMPLEMENTED"
    if o.account_currency != "USD":
        return "UNSUPPORTED_ACCOUNT_CURRENCY"
    if (type(o.clock_verified) is not bool or type(o.rules_verified_for_account) is not bool
            or type(o.history_verified) is not bool):
        return "INVALID_VERIFICATION_FLAGS"
    if not o.clock_verified or not o.rules_verified_for_account:
        return "UNVERIFIED_RULE_OR_CLOCK"
    monetary = (o.initial_capital, o.balance, o.equity, o.day_start_balance)
    if any(not _money(v) for v in monetary) or o.initial_capital <= 0:
        return "INVALID_MONEY_DATA"
    if not _aware_utc(now_utc) or not _aware_utc(o.observed_at_utc) or not _aware_utc(o.session_start_at_utc):
        return "INVALID_UTC_TIMESTAMPS"
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 3600:
        return "INVALID_FRESHNESS_POLICY"
    age = (now_utc - o.observed_at_utc).total_seconds()
    if not 0 <= age <= max_age_seconds:
        return "STALE_OR_FUTURE_OBSERVATION"
    session_age = (o.observed_at_utc - o.session_start_at_utc).total_seconds()
    if not 0 <= session_age < 25 * 3600:
        return "SESSION_RESET_UNVERIFIED"
    policy = POLICIES[o.model]
    if (
        type(o.reset_utc_offset_minutes) is not int
        or type(o.observation_utc_offset_minutes) is not int
        or o.reset_utc_offset_minutes not in policy.reset_offsets_minutes
        or o.observation_utc_offset_minutes not in policy.reset_offsets_minutes
    ):
        return "INVALID_SERVER_OFFSET"
    # Local session start must be midnight on broker's attested offset.
    start_local = o.session_start_at_utc + timedelta(minutes=o.reset_utc_offset_minutes)
    observed_local = o.observed_at_utc + timedelta(minutes=o.observation_utc_offset_minutes)
    if (
        (start_local.hour, start_local.minute, start_local.second, start_local.microsecond) != (0, 0, 0, 0)
        or start_local.date() != observed_local.date()
    ):
        return "SESSION_RESET_UNVERIFIED"
    if policy.total_method is MaxLossMethod.EOD_TRAILING_BALANCE:
        if not o.history_verified or not _money(o.highest_eod_balance):
            return "EOD_HISTORY_UNVERIFIED"
        if o.highest_eod_balance < max(o.initial_capital, o.day_start_balance):
            return "INCONSISTENT_EOD_HISTORY"
    if policy.total_method is MaxLossMethod.INTRADAY_TRAILING_CLOSED_BALANCE:
        if not o.history_verified or not _money(o.highest_closed_balance):
            return "CLOSED_BALANCE_HISTORY_UNVERIFIED"
        if o.highest_closed_balance < max(o.initial_capital, o.balance):
            return "INCONSISTENT_CLOSED_HISTORY"
    return None


def evaluate_compliance(
    snapshot: AccountObservation,
    *,
    now_utc: datetime,
    max_age_seconds: int = 120,
) -> ComplianceReport:
    """Evaluate broker thresholds; NEVER return an order permission.

    - Only synthetic fixtures can receive numerical statuses at this phase.
      Reports are always marked live_verified=False and SYNTHETIC_TEST.
    - Broker-labelled snapshots return UNKNOWN until an authenticated, trusted
      backend provider attests account identity, live equity and full history.
    - This does NOT account for undetected intratick breaches or broker-specific
      rule versions not explicitly listed in POLICIES.
    """
    if not isinstance(snapshot, AccountObservation):
        return _unknown("INVALID_OBSERVATION")
    error = _checked_snapshot(snapshot, now_utc=now_utc, max_age_seconds=max_age_seconds)
    if error:
        return _unknown(error, snapshot.model)

    policy = POLICIES[snapshot.model]
    allowance_daily = snapshot.initial_capital * policy.daily_allowance_fraction
    allowance_total = snapshot.initial_capital * policy.total_allowance_fraction
    daily_floor = snapshot.day_start_balance - allowance_daily
    if policy.total_method is MaxLossMethod.STATIC:
        reference_high = snapshot.initial_capital
    elif policy.total_method is MaxLossMethod.EOD_TRAILING_BALANCE:
        reference_high = max(snapshot.initial_capital, snapshot.highest_eod_balance)
    else:
        reference_high = max(snapshot.initial_capital, snapshot.highest_closed_balance)
    total_floor = reference_high - allowance_total

    remaining_daily_raw = snapshot.equity - daily_floor
    remaining_total_raw = snapshot.equity - total_floor
    consumed_daily = max(Decimal("0"),
                         (snapshot.day_start_balance - snapshot.equity) * Decimal("100") / allowance_daily)
    consumed_total = max(Decimal("0"),
                         (reference_high - snapshot.equity) * Decimal("100") / allowance_total)
    percent = max(consumed_daily, consumed_total)

    # Conservative equality handling: a floor touch is always reported as a
    # breach, even for wording that defines a technical breach as "below".
    if remaining_daily_raw <= 0 or remaining_total_raw <= 0:
        status = ComplianceStatus.BREACHED
    elif percent >= Decimal("95"):
        status = ComplianceStatus.CRITICAL
    elif percent >= Decimal("80"):
        status = ComplianceStatus.WARNING
    else:
        status = ComplianceStatus.WITHIN_LOSS_LIMITS

    return ComplianceReport(
        status=status,
        source=snapshot.origin,
        live_verified=False,
        policy_model=policy.model.value,
        policy_reviewed_on=policy.reviewed_on,
        daily_floor=daily_floor,
        total_floor=total_floor,
        daily_remaining=max(Decimal("0"), remaining_daily_raw),
        total_remaining=max(Decimal("0"), remaining_total_raw),
        daily_consumed_pct=consumed_daily,
        total_consumed_pct=consumed_total,
        reason_codes=("SYNTHETIC_TEST_ONLY",) if snapshot.origin is DataOrigin.SYNTHETIC_TEST else (),
        execution_authorized=False,
    )
