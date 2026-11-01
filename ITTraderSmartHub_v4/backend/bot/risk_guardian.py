"""Risk Guardian: Independent mandatory risk layer with trade limits and Infrastructure Stress Index integration."""
from dataclasses import dataclass
from math import floor
from .strategies import Signal


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
    - Max trade risk: 0.5% of account equity
    - Daily loss limit: 2.0% of daily starting equity
    - Infrastructure Stress Index formula: EffectiveRisk = BaselineRisk * (1 - 0.5 * Stress / 100)
    - Max positions: 3
    - Mandatory protective stop loss check
    """
    def __init__(self, max_trade_risk_pct: float = 0.5, max_daily_loss_pct: float = 2.0, max_open_positions: int = 3):
        self.max_trade_risk_pct = max_trade_risk_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_open_positions = max_open_positions

    def validate_trade_signal(self, signal: Signal, account_equity: float, daily_starting_equity: float,
                              open_positions_count: int, infrastructure_stress: int = 0,
                              pip_value_usd: float = 10.0) -> RiskValidationResult:
        reasons = []

        if not signal or signal.direction not in ("BUY", "SELL"):
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["INVALID_SIGNAL_DIRECTION"])

        if open_positions_count >= self.max_open_positions:
            reasons.append("MAX_OPEN_POSITIONS_REACHED")

        if signal.stop_loss <= 0 or abs(signal.entry_price - signal.stop_loss) <= 0:
            reasons.append("MISSING_PROTECTIVE_STOP")

        daily_loss = max(0.0, daily_starting_equity - account_equity)
        daily_loss_pct = (daily_loss / daily_starting_equity) * 100.0 if daily_starting_equity > 0 else 0.0
        if daily_loss_pct >= self.max_daily_loss_pct:
            reasons.append("DAILY_LOSS_LIMIT_EXCEEDED")

        # Infrastructure Stress Mitigation Factor
        stress_factor = 1.0 - (0.5 * infrastructure_stress / 100.0)
        effective_risk_pct = self.max_trade_risk_pct * stress_factor

        cash_at_risk = account_equity * (effective_risk_pct / 100.0)
        sl_distance = abs(signal.entry_price - signal.stop_loss)

        if sl_distance > 0:
            raw_lots = cash_at_risk / (sl_distance * pip_value_usd)
            stepped_lots = floor(raw_lots * 100.0) / 100.0
            allocated_lots = max(0.01, min(10.0, stepped_lots))
        else:
            allocated_lots = 0.01

        approved = len(reasons) == 0

        if not approved:
            allocated_lots = 0.0
            cash_at_risk = 0.0

        return RiskValidationResult(
            approved=approved,
            allocated_lots=allocated_lots,
            cash_at_risk=round(cash_at_risk, 2),
            effective_risk_pct=round(effective_risk_pct, 4),
            reason_codes=reasons if reasons else ["RISK_APPROVED"]
        )
