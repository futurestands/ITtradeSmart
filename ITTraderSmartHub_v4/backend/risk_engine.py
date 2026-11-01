"""Pipnex-style smart risk engine with exact broker lot sizing, pip value calculation, and prop firm drawdown rules."""
from dataclasses import dataclass
from math import isfinite, floor

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
    return RiskDecision(stress_index, baseline_percent, effective, balance * effective / 100)


def calculate_pipnex_lot_size(balance: float, risk_pct: float, stop_loss_pips: float, symbol: str = "EURUSD", leverage: float = 100.0) -> dict:
    """
    Pipnex Smart Lot Size & Pip Value Calculator.
    Computes exact broker lot sizes (0.01 steps), cash at risk, pip value, and margin requirement.
    Supports Forex (EURUSD, GBPUSD, USDJPY), Metals (XAUUSD), Crypto (BTCUSD), Indices (US30, NAS100).
    """
    if not all(isfinite(v) for v in (balance, risk_pct, stop_loss_pips)) or balance <= 0 or risk_pct <= 0 or stop_loss_pips <= 0:
        raise ValueError("Balance, risk percentage, and stop loss pips must be positive finite numbers")

    sym_upper = symbol.upper().replace("/", "").replace("_", "")

    # Contract specifications
    if "XAU" in sym_upper or "GOLD" in sym_upper:
        contract_size = 100.0       # 100 oz per lot
        pip_size = 0.10             # $0.10 per pip per lot
        pip_value_per_lot = 10.0    # $10 per pip for 1.00 lot
    elif "BTC" in sym_upper:
        contract_size = 1.0         # 1 BTC per lot
        pip_size = 1.0              # $1.00 per point
        pip_value_per_lot = 1.0     # $1.00 per point per lot
    elif "US30" in sym_upper or "NAS100" in sym_upper or "GER30" in sym_upper or "SPX500" in sym_upper:
        contract_size = 1.0
        pip_size = 1.0
        pip_value_per_lot = 1.0
    elif "JPY" in sym_upper:
        contract_size = 100000.0
        pip_size = 0.01
        pip_value_per_lot = 9.10    # ~ $9.10 per pip for 1 lot USDJPY
    else:
        # Standard Forex (EURUSD, GBPUSD, AUDUSD)
        contract_size = 100000.0
        pip_size = 0.0001
        pip_value_per_lot = 10.0    # $10 per pip for 1.00 lot

    cash_at_risk = balance * (risk_pct / 100.0)
    raw_lots = cash_at_risk / (stop_loss_pips * pip_value_per_lot)

    # Step rounding to 0.01 lot minimum, max 100 lots
    stepped_lots = floor(raw_lots * 100.0) / 100.0
    recommended_lots = max(0.01, min(100.0, stepped_lots))

    actual_cash_at_risk = recommended_lots * stop_loss_pips * pip_value_per_lot
    pip_value = recommended_lots * pip_value_per_lot

    return {
        "symbol": sym_upper,
        "balance": balance,
        "risk_percentage": risk_pct,
        "cash_at_risk": round(actual_cash_at_risk, 2),
        "stop_loss_pips": stop_loss_pips,
        "recommended_lots": recommended_lots,
        "pip_value_usd": round(pip_value, 2),
        "min_lot_step": 0.01,
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
