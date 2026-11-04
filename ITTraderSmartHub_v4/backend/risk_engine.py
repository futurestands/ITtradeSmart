"""Pipnex-style smart risk engine with exact broker lot sizing, pip value calculation, and prop firm drawdown rules."""
from dataclasses import dataclass
from math import isfinite
from decimal import Decimal, ROUND_FLOOR
import re

@dataclass(frozen=True)
class RiskDecision:
    stress_index: int
    baseline_percent: float
    effective_percent: float
    cash_limit: float


def calculate_risk(balance: float, baseline_percent: float, stress_index: int) -> RiskDecision:
    if not all(isfinite(v) for v in (balance, baseline_percent)):
        raise ValueError('Balance and risk must be finite')
    if balance <= 0 or not 0 < baseline_percent <= 100:
        raise ValueError('Balance must be positive and base risk between 0 and 100 percent')
    if not isinstance(stress_index, int) or not 0 <= stress_index <= 100:
        raise ValueError('Stress index must be an integer from 0 to 100')
    effective = baseline_percent * (1 - 0.5 * stress_index / 100)
    return RiskDecision(stress_index, baseline_perce@dataclass(frozen=True)
class BrokerContractSpec:
    """Trusted *server-side* symbol_info snapshot used for sizing only.

    No values in this class should be read from Android/client JSON. The
    loss-side tick value must already be in USD (the account currency); an MT5
    integration must establish that by reading the actual terminal/symbol.
    The pip_size convention must also be verified for that exact symbol.
    Unit tests use synthetic fixture values, not real broker specifications.
    """
    symbol: str
    tick_size: float
    tick_value_loss_usd: float
    pip_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    contract_size: float
    account_currency: str
    source: str


def _valid_broker_spec(symbol: str, spec: BrokerContractSpec | None) -> BrokerContractSpec:
    if not isinstance(spec, BrokerContractSpec) or spec.source != "TRUSTED_SERVER_SIDE_MT5":
        raise ValueError(
            "BROKER_SPEC_UNVERIFIED: A read-only, server-verified MT5 symbol "
            "specification is required; no lot size is available"
        )
    if (
        not isinstance(spec.symbol, str) or spec.symbol.upper() != symbol
        or spec.account_currency != "USD"
    ):
        raise ValueError("BROKER_SPEC_UNVERIFIED: Instrument or account currency does not match")
    numbers = (
        spec.tick_size, spec.tick_value_loss_usd, spec.pip_size,
        spec.volume_min, spec.volume_max, spec.volume_step, spec.contract_size,
    )
    if (
        any(type(v) not in (int, float) or not isfinite(v) or v <= 0 for v in numbers)
        or spec.volume_min > spec.volume_max
    ):
        raise ValueError("INVALID_BROKER_SPEC: Tick and lot limits must be finite and positive")
    return spec


def calculate_pipnex_lot_size(
    balance: float,
    risk_pct: float,
    stop_loss_pips: float,
    symbol: str = "EURUSD",
    leverage: float = 100.0,
    *,
    broker_spec: BrokerContractSpec | None = None,
) -> dict:
    """Size conservatively using *verified broker* contract values only.

    `stop_loss_pips` is the distance in the broker-verified `pip_size` unit.
    This function NEVER guesses an instrument class from its alias and NEVER
    rounds up to the broker minimum if doing so would exceed the cash budget.

    `leverage` is retained for legacy call compatibility, but margin is not
    calculated and no leverage-based trading permission is implied. This is
    nominal stop risk (not guaranteed maximum loss under slippage/gaps).
    """
    for field in (balance, risk_pct, stop_loss_pips):
        if type(field) not in (int, float) or not isfinite(field) or field <= 0:
            raise ValueError("Balance, risk percentage, and stop loss must be positive finite numbers")
    if risk_pct > 100:
        raise ValueError("Risk percentage must be at most 100")
    if not isinstance(symbol, str):
        raise ValueError("Invalid symbol")
    normalized = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9._-]{2,32}", normalized):
        raise ValueError("Invalid symbol")

    spec = _valid_broker_spec(normalized, broker_spec)

    # Decimal avoids floating-point volume-step drift (e.g. 0.1 + 3*0.2).
    dec = lambda x: Decimal(str(x))
    budget = dec(balance) * dec(risk_pct) / Decimal("100")
    pip_value_per_lot = (
        dec(spec.pip_size) / dec(spec.tick_size) * dec(spec.tick_value_loss_usd)
    )
    stop_cash_per_lot = dec(stop_loss_pips) * pip_value_per_lot
    if stop_cash_per_lot <= 0:
        raise ValueError("INVALID_BROKER_SPEC: Nonpositive stop-loss cash value")

    minimum = dec(spec.volume_min)
    maximum = dec(spec.volume_max)
    step = dec(spec.volume_step)
    raw_max_lots = budget / stop_cash_per_lot

    # Deliberately refuse rather than enforcing the minimum lot.
    if raw_max_lots < minimum:
        raise ValueError(
            "MIN_LOT_EXCEEDS_RISK_LIMIT: Even the broker's minimum volume "
            "would exceed the selected risk budget"
        )

    capped_lots = min(raw_max_lots, maximum)
    steps = ((capped_lots - minimum) / step).to_integral_value(rounding=ROUND_FLOOR)
    lots = minimum + steps * step
    actual_cash = lots * stop_cash_per_lot

    if lots < minimum or lots > maximum or actual_cash > budget:
        raise ValueError("INVALID_BROKER_SPEC: Risk-safe volume could not be established")

    return {
        "symbol": normalized,
        "status": "SIZED_FROM_VERIFIED_SPEC",
        "execution_authorized": False,
        "balance": balance,
        "risk_percentage": risk_pct,
        "risk_budget_usd": round(float(budget), 2),
        "cash_at_risk": round(float(actual_cash), 2),
        "stop_loss_pips": stop_loss_pips,
        "recommended_lots": float(lots),
        "pip_value_usd": round(float(lots * pip_value_per_lot), 2),
        "min_lot_step": spec.volume_step,
        "volume_min": spec.volume_min,
        "volume_max": spec.volume_max,
        "contract_size": spec.contract_size,
        "broker_spec_source": spec.source,
        "risk_estimate_note": "Nominal stop loss only; excludes spreads, slippage and gaps",
    }

      "contract_size": contract_size
    }


def calculate_prop_firm_rules(account_equity: float, initial_balance: float, daily_starting_equity: float,
                               max_daily_loss_pct: float = 5.0, max_total_loss_pct: float = 10.0,
                               profit_target_pct: float = 10.0) -> dict:
    """
    Pipnex Prop Firm Rules & Drawdown Shield Engine.
    Tracks Daily Drawdown, Max Trailing Drawdown, and Profit Target progress.
    """
    if initial_balance <= 0 or account_equity <= 0 or daily_starting_equity <= 0:
        raise ValueError("Balances and equities must be positive")

    daily_loss = max(0.0, daily_starting_equity - account_equity)
    daily_drawdown_pct = (daily_loss / daily_starting_equity) * 100.0

    total_loss = max(0.0, initial_balance - account_equity)
    total_drawdown_pct = (total_loss / initial_balance) * 100.0

    current_profit = account_equity - initial_balance
    profit_pct = (current_profit / initial_balance) * 100.0
    target_progress_pct = min(100.0, max(0.0, (profit_pct / profit_target_pct) * 100.0)) if profit_target_pct > 0 else 0.0

    daily_buffer_remaining = max(0.0, (initial_balance * (max_daily_loss_pct / 100.0)) - daily_loss)
    max_buffer_remaining = max(0.0, (initial_balance * (max_total_loss_pct / 100.0)) - total_loss)

    violation = False
    warning = False
    status_msg = "HEALTHY"

    if daily_drawdown_pct >= max_daily_loss_pct or total_drawdown_pct >= max_total_loss_pct:
        violation = True
        status_msg = "PROP FIRM RULE VIOLATED"
    elif daily_drawdown_pct >= (max_daily_loss_pct * 0.8) or total_drawdown_pct >= (max_total_loss_pct * 0.8):
        warning = True
        status_msg = "APPROACHING DRAWDOWN LIMIT"

    return {
        "initial_balance": initial_balance,
        "current_equity": account_equity,
        "daily_drawdown_pct": round(daily_drawdown_pct, 2),
        "total_drawdown_pct": round(total_drawdown_pct, 2),
        "max_daily_loss_pct": max_daily_loss_pct,
        "max_total_loss_pct": max_total_loss_pct,
        "profit_target_pct": profit_target_pct,
        "profit_progress_pct": round(target_progress_pct, 1),
        "daily_cash_buffer_remaining": round(daily_buffer_remaining, 2),
        "total_cash_buffer_remaining": round(max_buffer_remaining, 2),
        "status": status_msg,
        "is_violation": violation,
        "is_warning": warning
    }
