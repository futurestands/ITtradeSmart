"""Causal, conservative *research-only* execution simulator for rule-based signals.

This module does not connect to a broker, calculate lot sizes, or place orders.
It models prices as a single OHLC reference stream (not level-2 bid/ask); a
configured round-trip spread/slippage/commission allowance is deducted once
from gross R. It cannot substantiate live execution quality or trading profits.

A signal is knowable only when its decision candle CLOSES; the next bar is the
first possible fill. For ambiguous intra-bar paths, the stop is taken first.
"""
from dataclasses import dataclass
from datetime import timedelta
from math import isfinite
from typing import Optional, Sequence, Tuple

from .candles import Candle, validate_candles
from .decision import BUY, SELL, NO_TRADE, Decision


def _nonnegative(name: str, x: float) -> None:
    if isinstance(x, bool) or not isinstance(x, (float, int)) or not isfinite(x) or x < 0:
        raise ValueError(f'{name} must be finite and nonnegative')


@dataclass(frozen=True)
class FillAssumptions:
    """All price costs expressed in broker *points*, not USD.

    `spread_points` is a mandatory round-trip scenario floor. Known entry/exit
    bar spreads can widen that floor, never reduce it. Slippage is charged on
    both sides and commission once per round trip. No USD return is inferred.
    """
    point_size: float
    spread_points: float
    slippage_points_per_side: float = 0.0
    commission_points_round_trip: float = 0.0
    max_wait_bars: int = 3
    max_hold_bars: int = 48

    def __post_init__(self):
        for name in ('point_size', 'spread_points', 'slippage_points_per_side',
                     'commission_points_round_trip'):
            _nonnegative(name, getattr(self, name))
        if self.point_size <= 0:
            raise ValueError('point_size must be positive')
        if not isfinite(self.total_cost_price):
            raise ValueError('combined execution costs must be finite')
        for name in ('max_wait_bars', 'max_hold_bars'):
            val = getattr(self, name)
            if type(val) is not int or val <= 0:
                raise ValueError(f'{name} must be a positive integer')

    @property
    def total_cost_price(self) -> float:
        return self.point_size * (self.spread_points + 2 * self.slippage_points_per_side +
                                  self.commission_points_round_trip)


@dataclass(frozen=True)
class Outcome:
    signal_index: int
    action: str
    status: str                   # NO_FILL | TARGET | STOP | TIMEOUT | INCOMPLETE
    entry_index: Optional[int]
    exit_index: Optional[int]
    entry_price: Optional[float]
    exit_price: Optional[float]
    gross_r: Optional[float]
    net_r: Optional[float]
    costs_r: Optional[float]
    assumption: str = 'OHLC_PROXY_STOP_FIRST_NOT_LIVE_EXECUTION'
    spread_points_applied: Optional[float] = None


def simulate_signal(decision: Decision, candles: Sequence[Candle], signal_index: int,
                    cfg: FillAssumptions) -> Outcome:
    """Evaluate one already-produced signal using only bars AFTER its close.

    The caller must generate each decision causally from the prefix ending at
    `signal_index`. This function verifies the signal timestamp matches that
    prefix exactly and does not generate its own trade signal.

    The entry is a *limit* reference price. If it trades in a following candle,
    fill at the specified price (never grant favourable price improvement).
    After entry, if both barriers appear inside a bar, treat stop as first.
    At a stop gap against the position, fill at the worse of open and stop.
    A position still open at the last supplied bar is INCOMPLETE, not TIMEOUT.
    """
    if type(signal_index) is not int or not 0 <= signal_index < len(candles):
        raise ValueError('signal_index out of range')
    if decision.action not in (BUY, SELL):
        raise ValueError('only actionable decisions can be simulated')
    if decision.timeframe_minutes <= 0:
        raise ValueError('invalid signal timeframe')
    validate_candles(candles, decision.timeframe_minutes)
    expected = candles[signal_index].time + timedelta(minutes=decision.timeframe_minutes)
    if decision.as_of != expected:
        raise ValueError('decision timestamp does not match the signal candle close')
    if any(x is None or isinstance(x, bool) or not isinstance(x, (float, int)) or not isfinite(x)
           for x in (decision.entry, decision.stop, decision.target)):
        raise ValueError('decision requires finite entry, stop, and target prices')
    buy = decision.action == BUY
    entry, stop, target = decision.entry, decision.stop, decision.target
    if not ((stop < entry < target) if buy else (target < entry < stop)):
        raise ValueError('invalid signal stop/entry/target geometry')
    risk = abs(entry - stop)
    if min(entry, stop, target) <= 0 or not isfinite(risk):
        raise ValueError('signal prices and risk must be positive and finite')
    last = len(candles) - 1
    fill_idx = None
    for i in range(signal_index + 1, min(last, signal_index + cfg.max_wait_bars) + 1):
        c = candles[i]
        # A limit order is marketable when price passes through the entry level.
        if (c.low <= entry) if buy else (c.high >= entry):
            fill_idx = i
            break
    if fill_idx is None:
        still_waiting = last < signal_index + cfg.max_wait_bars
        return Outcome(signal_index, decision.action,
                       'INCOMPLETE' if still_waiting else 'NO_FILL', None, None,
                       None, None, None, None, None)

    exit_deadline = fill_idx + cfg.max_hold_bars - 1
    entry_spread = candles[fill_idx].spread
    spread_floor = max(cfg.spread_points, entry_spread if entry_spread is not None else 0)

    def costs_at(spread):
        cost = cfg.point_size * (spread + 2 * cfg.slippage_points_per_side + cfg.commission_points_round_trip) / risk
        if not isfinite(cost):
            raise ValueError('execution costs in R must be finite')
        return cost

    cost_r = costs_at(spread_floor)
    for i in range(fill_idx, min(last, exit_deadline) + 1):
        c = candles[i]
        stopped = (c.low <= stop) if buy else (c.high >= stop)
        targeted = (c.high >= target) if buy else (c.low <= target)
        # On an intrabar limit fill the earlier high/low may precede entry.
        # Credit a same-bar target only if entry was marketable at the open,
        # or the close proves price reached the target after passing entry.
        at_open = (c.open <= entry) if buy else (c.open >= entry)
        close_proves_target = (c.close >= target) if buy else (c.close <= target)
        if i == fill_idx and not at_open and not close_proves_target:
            targeted = False
        if stopped:  # Conservative outcome when BOTH barriers touched.
            ex = min(stop, c.open) if buy else max(stop, c.open)
            state = 'STOP'
        elif targeted:
            ex = target  # no favourable price improvement granted
            state = 'TARGET'
        elif i == exit_deadline:
            ex = c.close
            state = 'TIMEOUT'
        else:
            continue
        gross = ((ex - entry) if buy else (entry - ex)) / risk
        applied_spread = max(spread_floor, c.spread if c.spread is not None else 0)
        cost_r = costs_at(applied_spread)
        if not isfinite(gross) or not isfinite(gross - cost_r):
            raise ValueError('outcome in R must be finite')
        return Outcome(signal_index, decision.action, state, fill_idx, i,
                       entry, ex, gross, gross - cost_r, cost_r,
                       spread_points_applied=applied_spread)
    return Outcome(signal_index, decision.action, 'INCOMPLETE', fill_idx, None,
                   entry, None, None, None, cost_r, spread_points_applied=spread_floor)


@dataclass(frozen=True)
class ResearchSummary:
    signals: int
    completed: int
    no_fill: int
    incomplete: int
    wins: int
    losses: int
    expectancy_r: Optional[float]
    max_drawdown_r: Optional[float]
    gross_r: Optional[float]
    net_r: Optional[float]
    validation: str = 'UNVALIDATED_RESEARCH_ONLY'


def summarize(outcomes: Sequence[Outcome]) -> ResearchSummary:
    """Summarize completed (TARGET/STOP/TIMEOUT) trades in additive R units.

    Ignoring unfilled signals for per-fill expectancy must not hide their count.
    This is NOT a compounding equity curve or an actual brokerage P&L report.
    """
    done = [o for o in outcomes if o.status in ('TARGET', 'STOP', 'TIMEOUT') and o.net_r is not None]
    results = [o.net_r for o in done]
    equity, peak, worst = 0.0, 0.0, 0.0
    for r in results:
        equity += r
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return ResearchSummary(len(outcomes), len(done),
                           sum(o.status == 'NO_FILL' for o in outcomes),
                           sum(o.status == 'INCOMPLETE' for o in outcomes),
                           sum(r > 0 for r in results), sum(r <= 0 for r in results),
                           sum(results) / len(results) if results else None,
                           worst if results else None,
                           sum(o.gross_r for o in done) if done else None,
                           sum(results) if results else None)
