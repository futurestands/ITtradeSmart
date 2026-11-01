"""Risk Guardian: Mandatory risk layer enforcing strict broker-authoritative order_calc_profit() and order_calc_margin() verification with zero test-mode fallbacks."""
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
    - 2% daily loss stop relative to persistent daily starting equity baseline.
    - Max 3 concurrent open positions.
    - Infrastructure Stress Index formula: EffectiveRisk = BaselineRisk * (1 - 0.5 * Stress / 100).
    - FAILS CLOSED if telemetry stress is missing or invalid.
    - STRICT REQUIREMENT: Requires valid broker-authoritative order_calc_profit() and order_calc_margin() responses with sufficient free margin. Zero test-mode fallback.
    """

    def __init__(self, max_trade_risk_pct: float = 0.5, max_daily_loss_pct: float = 2.0, max_open_positions: int = 3):
        self.max_trade_risk_pct = max_trade_risk_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_open_positions = max_open_positions

    def validate_trade_signal(self, signal: Signal, verified_account_equity: float, verified_free_margin: float,
                              daily_starting_equity: float, open_positions_count: int, symbol_spec: SymbolSpec,
                              infrastructure_stress: int = None, data_fresh: bool = True,
                              mt5_gateway_client=None) -> RiskValidationResult:
        reasons = []

        if not data_fresh:
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["FAIL_CLOSED_STALE_MARKET_DATA"])

        if infrastructure_stress is None or not isinstance(infrastructure_stress, int) or not 0 <= infrastructure_stress <= 100:
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["FAIL_CLOSED_MISSING_OR_INVALID_TELEMETRY_STRESS"])

        if verified_account_equity <= 0 or not isfinite(verified_account_equity):
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["INVALID_VERIFIED_ACCOUNT_EQUITY"])

        if verified_free_margin < 0 or not isfinite(verified_free_margin):
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["INVALID_FREE_MARGIN"])

        if daily_starting_equity <= 0 or not isfinite(daily_starting_equity):
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["INVALID_DAILY_STARTING_EQUITY"])

        if not signal or signal.direction not in ("BUY", "SELL"):
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["INVALID_SIGNAL_DIRECTION"])

        # Stop Loss Direction Compliance
        if signal.direction == "BUY" and signal.stop_loss >= signal.entry_price:
            reasons.append("INVALID_STOP_LOSS_BUY_DIRECTION")
        if signal.direction == "SELL" and signal.stop_loss <= signal.entry_price:
            reasons.append("INVALID_STOP_LOSS_SELL_DIRECTION")

        if open_positions_count >= self.max_open_positions:
            reasons.append("MAX_OPEN_POSITIONS_REACHED")

        if signal.stop_loss <= 0 or abs(signal.entry_price - signal.stop_loss) <= 0:
            reasons.append("MISSING_PROTECTIVE_STOP")

        daily_loss = max(0.0, daily_starting_equity - verified_account_equity)
        daily_loss_pct = (daily_loss / daily_starting_equity) * 100.0 if daily_starting_equity > 0 else 0.0
        if daily_loss_pct >= self.max_daily_loss_pct:
            reasons.append("DAILY_LOSS_LIMIT_EXCEEDED")

        # Infrastructure Stress Mitigation Formula
        stress_factor = 1.0 - (0.5 * infrastructure_stress / 100.0)
        effective_risk_pct = self.max_trade_risk_pct * stress_factor

        cash_at_risk_allowed = verified_account_equity * (effective_risk_pct / 100.0)
        sl_distance = abs(signal.entry_price - signal.stop_loss)

        if sl_distance <= 0:
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["INVALID_STOP_LOSS_DISTANCE"])

        # STRICT REQUIREMENT: Obtain broker order_calc_profit() and order_calc_margin() results via serialized gateway service.
        cash_risk_per_lot = 0.0
        margin_required_per_lot = 0.0
        broker_calc_success = False

        if mt5_gateway_client is not None:
            try:
                action = "BUY" if signal.direction == "BUY" else "SELL"
                profit_res, margin_res = mt5_gateway_client.calc_order(action, symbol_spec.symbol, 1.0, signal.entry_price, signal.stop_loss)
                if profit_res is not None and profit_res < 0 and margin_res is not None and margin_res > 0:
                    cash_risk_per_lot = abs(profit_res)
                    margin_required_per_lot = float(margin_res)
                    broker_calc_success = True
            except Exception:
                pass
        else:
            try:
                import MetaTrader5 as mt5
                action = mt5.ORDER_TYPE_BUY if signal.direction == "BUY" else mt5.ORDER_TYPE_SELL
                profit_res = mt5.order_calc_profit(action, symbol_spec.symbol, 1.0, signal.entry_price, signal.stop_loss)
                margin_res = mt5.order_calc_margin(action, symbol_spec.symbol, 1.0, signal.entry_price)
                if profit_res is not None and profit_res < 0 and margin_res is not None and margin_res > 0:
                    cash_risk_per_lot = abs(profit_res)
                    margin_required_per_lot = float(margin_res)
                    broker_calc_success = True
            except Exception:
                pass

        if not broker_calc_success:
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["FAIL_CLOSED_BROKER_CALCULATION_UNAVAILABLE"])

        if cash_risk_per_lot <= 0 or margin_required_per_lot <= 0:
            return RiskValidationResult(False, 0.0, 0.0, 0.0, ["INVALID_BROKER_CALCULATION_RESPONSE"])

        raw_lots = cash_at_risk_allowed / cash_risk_per_lot

        # Round DOWN to nearest volume step (e.g. 0.01)
        step_multiplier = 1.0 / symbol_spec.lot_step
        stepped_lots = floor(raw_lots * step_multiplier) / step_multiplier

        if stepped_lots < symbol_spec.min_lot:
            min_lot_risk = symbol_spec.min_lot * cash_risk_per_lot
            reasons.append(f"MIN_LOT_EXCEEDS_RISK_LIMIT (Min lot risk ${min_lot_risk:.2f} > Max risk ${cash_at_risk_allowed:.2f})")

        allocated_lots = max(symbol_spec.min_lot, min(symbol_spec.max_lot, stepped_lots))
        actual_cash_at_risk = allocated_lots * cash_risk_per_lot
        total_margin_required = allocated_lots * margin_required_per_lot

        # Verify sufficient free margin
        if total_margin_required > verified_free_margin:
            reasons.append("INSUFFICIENT_FREE_MARGIN")

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
