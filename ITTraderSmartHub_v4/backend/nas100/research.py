"""Causal rule-engine evaluation on historical candles — research only.

For each scanned candle i, the analyst sees candles[:i+1] ONLY. HTF bars
are regenerated from that prefix and must have closed by the decision time.
This intentionally slow reference implementation prioritizes auditability;
large datasets will require a separately tested streaming implementation.
"""
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, Optional, Sequence, Tuple

from .analysis import analyze_multitimeframe
from .backtest import FillAssumptions, Outcome, ResearchSummary, simulate_signal, summarize
from .candles import Candle, validate_candles
from .config import EngineConfig
from .decision import BUY, SELL, Decision, decide


@dataclass(frozen=True)
class SignalObservation:
    signal_index: int
    decision: Decision


@dataclass(frozen=True)
class ResearchRun:
    inspected: int
    actionable: Tuple[SignalObservation, ...]
    executed_proxy: Tuple[Outcome, ...]
    summary: ResearchSummary
    caveat: str = 'RESEARCH_ONLY_NOT_TRAINED_OR_VALIDATED'
    decision_counts: Tuple[Tuple[str, int], ...] = ()


def scan_signals(candles: Sequence[Candle], base_minutes: int, htf_minutes: int,
                 *, cfg: EngineConfig = EngineConfig(), start: int = 0,
                 stop: Optional[int] = None, stride: int = 1,
                 max_inspections: int = 2000,
                 observer: Optional[Callable[[int, Decision], None]] = None) -> Tuple[SignalObservation, ...]:
    """Produce deduplicated BUY/SELL *observations*, never trade orders.

    Include `now=last_closed_time` to force no-future and freshness guards.
    Signal de-duplication requires a NO TRADE between repeated actions with
    identical entry/stop/target; this is a conservative approximation of an
    event-driven scanner, NOT a fully fledged trading rules engine.
    """
    if (type(base_minutes) is not int or base_minutes <= 0 or type(htf_minutes) is not int
            or htf_minutes <= base_minutes or htf_minutes % base_minutes):
        raise ValueError('htf_minutes must be a multiple of base_minutes and larger')
    if type(start) is not int or start < 0:
        raise ValueError('start must be a nonnegative integer')
    if stop is None:
        stop = len(candles)
    if type(stop) is not int or not 0 <= stop <= len(candles) or stop < start:
        raise ValueError('stop must be between start and candle count')
    if type(stride) is not int or stride <= 0:
        raise ValueError('stride must be a positive integer')
    if type(max_inspections) is not int or max_inspections <= 0:
        raise ValueError('max_inspections must be a positive integer')
    if len(range(start, stop, stride)) > max_inspections:
        raise ValueError('research scan too large for slow reference implementation; narrow the range')
    # Even validation must not inspect a held-out suffix outside this cutoff.
    validate_candles(candles[:stop], base_minutes, cfg.closure_min_minutes)

    found = []
    last_key = None
    for i in range(start, stop, stride):
        prefix = candles[:i+1]
        ctx = analyze_multitimeframe(prefix, base_minutes, [htf_minutes], cfg)
        decision = decide(ctx.ltf, ctx.htf[htf_minutes], cfg,
                          now=candles[i].time + timedelta(minutes=base_minutes), live=False)
        if observer is not None:
            observer(i, decision)
        if decision.action not in (BUY, SELL):
            last_key = None
            continue
        key = (decision.action, decision.entry_zone, decision.entry, decision.stop, decision.target)
        if key != last_key:
            found.append(SignalObservation(i, decision))
        last_key = key
    return tuple(found)


def run_research(candles: Sequence[Candle], base_minutes: int, htf_minutes: int,
                 assumptions: FillAssumptions, *, cfg: EngineConfig = EngineConfig(),
                 start: int = 0, stop: Optional[int] = None, stride: int = 1,
                 max_inspections: int = 2000) -> ResearchRun:
    """Causal scan then a *single-position*, non-overlapping execution proxy.

    Observations within another simulated trade's fill-to-exit interval are
    retained as observations, but NOT simulated as additional positions.
    Incomplete trades halt further proxy outcomes; no optimistic settlement.
    """
    end = len(candles) if stop is None else stop
    # Prevent evaluation from crossing a caller-defined train/test boundary.
    # A still-open outcome at the boundary is INCOMPLETE, never force-closed.
    evaluation_candles = candles[:end]
    counts = {BUY: 0, SELL: 0, 'NO TRADE': 0}

    def count_decision(index, decision):
        counts[decision.action] += 1

    observations = scan_signals(candles, base_minutes, htf_minutes, cfg=cfg, start=start,
                                stop=stop, stride=stride, max_inspections=max_inspections,
                                observer=count_decision)
    outcomes = []
    next_available_index = -1
    for observation in observations:
        if observation.signal_index <= next_available_index:
            continue
        out = simulate_signal(observation.decision, evaluation_candles, observation.signal_index, assumptions)
        outcomes.append(out)
        if out.status == 'INCOMPLETE':
            break
        if out.exit_index is not None:
            next_available_index = out.exit_index
        elif out.status == 'NO_FILL':
            next_available_index = observation.signal_index + assumptions.max_wait_bars
    return ResearchRun(len(range(start, end, stride)), observations, tuple(outcomes),
                       summarize(outcomes), decision_counts=tuple(counts.items()))
