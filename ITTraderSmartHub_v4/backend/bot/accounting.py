"""Explicit linear, same-currency research accounting. No inferred symbol economics."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from math import isfinite, isclose


@dataclass(frozen=True)
class ResearchInstrument:
    symbol: str
    point: float
    tick_size: float
    tick_value_profit: float
    tick_value_loss: float
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    profit_currency: str
    account_currency: str
    provenance: str

    def __post_init__(self):
        values = (self.point, self.tick_size, self.tick_value_profit, self.tick_value_loss,
                  self.contract_size, self.volume_min, self.volume_max, self.volume_step)
        if not all(isfinite(x) and x > 0 for x in values) or self.volume_min > self.volume_max:
            raise ValueError("Invalid instrument economics")
        if not self.symbol or not self.provenance:
            raise ValueError("Exact symbol and economics provenance required")
        # Existing result fields are USD. Cross-currency/futures/nonlinear instruments
        # require a separate historically valid broker calculation adapter.
        if self.account_currency != "USD" or self.profit_currency != "USD":
            raise ValueError("BLOCKED_UNSUPPORTED_CURRENCY_CONVERSION")
        for value in (self.tick_value_profit, self.tick_value_loss):
            if not isclose(value, self.contract_size * self.tick_size, rel_tol=1e-8):
                raise ValueError("BLOCKED_UNSUPPORTED_NONLINEAR_CONTRACT")

    def validate_volume(self, volume):
        if not isfinite(volume) or not self.volume_min <= volume <= self.volume_max:
            raise ValueError("Volume outside broker limits")
        steps = Decimal(str(volume)) / Decimal(str(self.volume_step))
        if steps != steps.to_integral_value():
            raise ValueError("Volume violates broker step")

    def fill(self, price, buy):
        if not isfinite(price) or price <= 0:
            raise ValueError("Invalid fill price")
        ticks = Decimal(str(price)) / Decimal(str(self.tick_size))
        nearest = ticks.to_integral_value()
        if abs(ticks - nearest) < Decimal("0.0000001"):
            ticks = nearest  # suppress binary addition noise, not real off-grid prices
        return float(ticks.to_integral_value(rounding=ROUND_CEILING if buy else ROUND_FLOOR)
                     * Decimal(str(self.tick_size)))

    def pnl(self, direction, volume, entry, exit_price):
        self.validate_volume(volume)
        if direction not in ("BUY", "SELL"):
            raise ValueError("Invalid direction")
        if not all(isfinite(x) and x > 0 for x in (entry, exit_price)):
            raise ValueError("Invalid price")
        change = (exit_price - entry) * (1 if direction == "BUY" else -1)
        value = self.tick_value_profit if change >= 0 else self.tick_value_loss
        return change / self.tick_size * value * volume


@dataclass(frozen=True)
class ResearchCosts:
    slippage_price: float
    commission_round_trip_per_lot: float
    financing_per_lot_per_bar: float  # disclosed simplification, not broker swaps

    def __post_init__(self):
        if not all(isfinite(x) and x >= 0 for x in (
                self.slippage_price, self.commission_round_trip_per_lot,
                self.financing_per_lot_per_bar)):
            raise ValueError("Costs must be finite, nonnegative explicit assumptions")
