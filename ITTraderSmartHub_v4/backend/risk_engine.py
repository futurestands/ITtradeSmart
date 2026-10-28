"""Auditable, deterministic advisory risk calculations (no order execution)."""
from dataclasses import dataclass
from math import isfinite

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
