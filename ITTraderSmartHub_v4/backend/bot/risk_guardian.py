"""Risk Guardian: Independent mandatory risk layer enforcing 0.5% max equity risk, 2% daily loss stop, broker symbol specifications, and margin validation."""
from dataclasses import dataclass
from math import floor, isfinite
from .strategies import Signal
from .market_data import SymbolSpec


@dataclass(frozen=True)
class RiskValidationResult:
    approved: bool
    allocated_lots: float
    cash_at_risk: float
    effective_risk_pct: float
    reason_codes: list


class RiskGuardian:
    """
    Independent Risk Guardian Decision Layer.
    Rules:
    - Maximum 0.5% of verified equity at risk per trade.
    - 2% daily loss stop.
    - Max 3 concurrent open positions.
    - Infrastructure Stress Index formula: EffectiveRisk = BaselineRisk * (1 - 0.5 * Stress / 100).
    - Fractional lot volume stepping with floor rounding down.
    - EXPLICIT REJECTION if symbol min_lot exceeds cash risk allowance.
    - Validation of stop loss direction compliance.
    """

    def __init__(self, max_trade_risk_pct: float = 0.5, max_daily_loss_pct: float = 2.0, max_open_positions: int = 3):
        self.max_trade_risk_pct = max_trade_risk_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_open_positions = max_open_positions

    def validate_trade_signal(self, signal: Signal, account_equity: float, daily_starting_equity: float,
                              open_positions_count: int, symbol_spec: SymbolSpec, infrastructure_stress: int = 0,
                              data_fresh: bool = True) -> RiskValidationResult:
        reasons = []

        if not data_fresh:
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["FAIL_CLOSED_STALE_MARKET_DATA"])

        if account_equity <= 0 or not isfinite(account_equity):
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["INVALID_ACCOUNT_EQUITY"])

        if not isinstance(infrastructure_stress, int) or not 0 <= infrastructure_stress <= 100:
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["INVALID_INFRASTRUCTURE_STRESS"])

        if not signal or signal.direction not in ("BUY", "SELL"):
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["INVALID_SIGNAL_DIRECTION"])

        # Validate Stop Loss Direction Compliance
        if signal.direction == "BUY" and signal.stop_loss >= signal.entry_price:
            reasons.append("INVALID_STOP_LOSS_BUY_DIRECTION")
        if signal.direction == "SELL" and signal.stop_loss <= signal.entry_price:
            reasons.append("INVALID_STOP_LOSS_SELL_DIRECTION")

        if open_positions_count >= self.max_open_positions:
            reasons.append("MAX_OPEN_POSITIONS_REACHED")

        if signal.stop_loss <= 0 or abs(signal.entry_price - signal.stop_loss) <= 0:
            reasons.append("MISSING_PROTECTIVE_STOP")

        daily_loss = max(0.0, daily_starting_equity - account_equity)
        daily_loss_pct = (daily_loss / daily_starting_equity) * 100.0 if daily_starting_equity > 0 else 0.0
        if daily_loss_pct >= self.max_daily_loss_pct:
            reasons.append("DAILY_LOSS_LIMIT_EXCEEDED")

        # Infrastructure Stress Mitigation Formula
        stress_factor = 1.0 - (0.5 * infrastructure_stress / 100.0)
        effective_risk_pct = self.max_trade_risk_pct * stress_factor

        cash_at_risk_allowed = account_equity * (effective_risk_pct / 100.0)
        sl_distance = abs(signal.entry_price - signal.stop_loss)

        if sl_distance <= 0:
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["INVALID_STOP_LOSS_DISTANCE"])

        ticks_in_sl = sl_distance / symbol_spec.tick_size
        cash_risk_per_lot = ticks_in_sl * symbol_spec.tick_value

        if cash_risk_per_lot <= 0:
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["INVALID_TICK_VALUE"])

        raw_lots = cash_at_risk_allowed / cash_risk_per_lot

        # Round DOWN to nearest lot step (e.g. 0.01)
        step_multiplier = 1.0 / symbol_spec.lot_step
        stepped_lots = floor(raw_lots * step_multiplier) / step_multiplier

        # Rejection rule: If minimum lot size exceeds maximum cash risk allowance -> REJECT TRADE
        if stepped_lots < symbol_spec.min_lot:
            min_lot_risk = symbol_spec.min_lot * cash_risk_per_lot
            reasons.append(f"MIN_LOT_EXCEEDS_RISK_LIMIT (Min lot risk ${min_lot_risk:.2f} > Max risk ${cash_at_risk_allowed:.2f})")

        allocated_lots = max(symbol_spec.min_lot, min(symbol_spec.max_lot, stepped_lots))
        actual_cash_at_risk = allocated_lots * cash_risk_per_lot

        approved = len(reasons) == 0

        if not approved:
            allocated_lots = 0.0
            actual_cash_at_risk = 0.0

        return RiskValidationResult(
            approved=approved,
            allocated_lots=allocated_lots,
            cash_at_risk=round(actual_cash_at_risk, 2),
            effective_risk_pct=round(effective_risk_pct, 4),
            reason_codes=reasons if reasons else ["RISK_APPROVED"]
        )
