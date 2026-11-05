"""Preliminary, explainable BUY / SELL / NO TRADE framework.

STATUS: rule-based and UNVALIDATED. It has not been backtested on real NAS100 data,
carries no probability, and `model_confidence` is always None. It is a structured
checklist, not a prediction. NO TRADE is the default outcome.

BUY requires ALL of the following, evaluated only from data closed by the last candle:
    1. Data quality: enough bars, no recent missing-candle fault, ATR defined,
       data fresh and not future-dated (when `now` is supplied), spread known and
       within limit when a spread limit is configured. Offline calls without
       `now` do not verify freshness and must never be presented as live signals.
    2. Regime: not FLAT/UNKNOWN and not in consolidation.
    3. Session: last candle opened in an allowed session (default London / New York).
    4. Higher-timeframe bias: HTF structure trend is 'bull' (SELL: 'bear'), computed
       from closed HTF bars only.
    5. Setup within the last `setup_window_bars` candles, in this order:
         a. a bullish liquidity sweep (confirmed swing low traded through, close back above),
         b. then a bullish BOS or CHoCH (close above a confirmed swing high),
         c. then a bullish FVG (formed at/after the sweep) that is not yet filled.
    6. Geometry: entry = FVG midpoint; stop = sweep extreme - stop_buffer_atr*ATR;
       target = nearest confirmed swing high above entry; risk <= max_stop_atr*ATR;
       reward/risk >= min_rr; last close still above the stop.
    SELL is the exact mirror. If fully-formed buy AND sell setups both exist the
    result is NO TRADE (conflicting signals). A setup against the HTF bias is blocked.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from .analysis import Analysis
from .config import EngineConfig
from .sessions import session_state

BUY, SELL, NO_TRADE = 'BUY', 'SELL', 'NO TRADE'
VALIDATION_STATUS = 'UNVALIDATED_RULES_NOT_BACKTESTED'


@dataclass(frozen=True)
class Decision:
    action: str
    timeframe_minutes: int
    as_of: Optional[datetime]
    data_fresh: Optional[bool]
    regime: str
    htf_bias: str
    setup: Optional[str]
    entry_zone: Optional[Tuple[float, float]]
    entry: Optional[float]
    stop: Optional[float]
    target: Optional[float]
    risk_reward: Optional[float]
    reasons: Tuple[str, ...]
    blockers: Tuple[str, ...]
    invalidation: Optional[str]
    model_confidence: Optional[float] = None
    validation_status: str = VALIDATION_STATUS


@dataclass(frozen=True)
class _Candidate:
    direction: str
    complete: bool                 # sweep + shift + FVG all present
    blockers: Tuple[str, ...]
    reasons: Tuple[str, ...]
    zone: Optional[Tuple[float, float]] = None
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    rr: Optional[float] = None


def _no_trade(ltf: Analysis, regime, bias, blockers, fresh=None, reasons=()) -> Decision:
    as_of = ltf.as_of if ltf.candles else None
    return Decision(NO_TRADE, ltf.timeframe_minutes, as_of, fresh, regime, bias, None, None,
                    None, None, None, None, tuple(reasons), tuple(blockers), None)


def decide(ltf: Analysis, htf: Optional[Analysis], cfg: EngineConfig = EngineConfig(),
           now: Optional[datetime] = None, *, live: bool = False) -> Decision:
    """Historical checklist by default; live mode also requires an aware clock."""
    if now is not None and (not isinstance(now, datetime) or now.utcoffset() is None):
        raise ValueError('now must be timezone-aware')
    n = len(ltf.candles)
    if n == 0 or ltf.status != 'OK' or ltf.atr[-1] is None:
        return _no_trade(ltf, 'UNKNOWN', 'unknown', ['INSUFFICIENT_DATA'])
    last = ltf.last_index
    c = ltf.candles[last]
    atr = ltf.atr[last]
    regime = ltf.regime[last]
    blockers: List[str] = []

    # --- data quality ---------------------------------------------------------
    if any(g.after_index + 1 >= n - cfg.gap_lookback_bars for g in ltf.quality.fault_gaps):
        blockers.append('DATA_GAP_RECENT')
    fresh = None
    if live and now is None:
        blockers.append('DECISION_TIME_REQUIRED')
    if now is not None:
        if now.utcoffset() is None:
            raise ValueError('now must be timezone-aware')
        age = now - ltf.as_of
        fresh = timedelta(0) <= age <= timedelta(minutes=cfg.max_data_age_minutes)
        if age < timedelta(0):
            blockers.append('FUTURE_DATA')
        elif not fresh:
            blockers.append('STALE_DATA')
    if cfg.max_spread_points is not None:
        if c.spread is None:
            blockers.append('UNKNOWN_SPREAD')
        elif c.spread > cfg.max_spread_points:
            blockers.append('SPREAD_TOO_WIDE')

    # --- regime ---------------------------------------------------------------
    if regime in ('FLAT', 'UNKNOWN'):
        blockers.append('REGIME_' + regime)
    if ltf.consolidation[last]:
        blockers.append('CONSOLIDATION')

    # --- session --------------------------------------------------------------
    state = session_state(c.time)
    if not any(getattr(state, name) for name in cfg.allowed_sessions):
        blockers.append('OUTSIDE_ALLOWED_SESSION')

    # --- higher-timeframe bias ------------------------------------------------
    bias = 'unknown'
    if htf is None:
        blockers.append('NO_HTF_CONTEXT')
    elif htf.status != 'OK' or not htf.candles:
        blockers.append('HTF_INSUFFICIENT_DATA')
    elif htf.as_of > ltf.as_of:
        blockers.append('HTF_BAR_NOT_CLOSED')     # leak guard: HTF must be closed by now
    elif htf.timeframe_minutes <= ltf.timeframe_minutes:
        blockers.append('HTF_TIMEFRAME_NOT_HIGHER')
    elif htf.timeframe_minutes % ltf.timeframe_minutes:
        blockers.append('HTF_INVALID_TIMEFRAME')
    elif ltf.as_of - htf.as_of >= timedelta(minutes=htf.timeframe_minutes * cfg.htf_max_lag_bars):
        blockers.append('HTF_STALE_DATA')
    elif any(g.after_index + 1 >= len(htf.candles) - cfg.gap_lookback_bars
             for g in htf.quality.gaps):
        blockers.append('HTF_DATA_GAP_RECENT')
    else:
        bias = htf.trend
        if bias == 'none':
            blockers.append('NO_HTF_BIAS')

    # --- setups ---------------------------------------------------------------
    cands = {d: _build_candidate(ltf, d, cfg) for d in ('bull', 'bear')}
    if all(cands[d].complete for d in cands):
        blockers.append('CONFLICTING_SETUPS')

    if blockers:
        seen = [r for d in cands for r in cands[d].reasons if cands[d].complete]
        return _no_trade(ltf, regime, bias, blockers, fresh, seen)

    chosen = [cands[d] for d in cands if cands[d].complete]
    if not chosen:
        return _no_trade(ltf, regime, bias, ['NO_SETUP'], fresh)
    cand = chosen[0]
    problems = list(cand.blockers)
    if cand.direction != bias:
        problems.append('COUNTER_TREND_TO_HTF_BIAS')
    if problems:
        return _no_trade(ltf, regime, bias, problems, fresh, cand.reasons)

    action = BUY if cand.direction == 'bull' else SELL
    reasons = list(cand.reasons) + [
        f'HTF structure bias: {bias}',
        f'Regime {regime}; session ok ({", ".join(state.active()) or "ny_cash"})',
        f'Reward/risk {cand.rr:.2f} >= {cfg.min_rr}']
    invalid = (f'Close {"below" if action == BUY else "above"} stop {cand.stop:.2f}, '
               f'or FVG fully filled before entry')
    return Decision(action, ltf.timeframe_minutes, ltf.as_of, fresh, regime, bias,
                    'liquidity sweep -> structure shift -> FVG', cand.zone, cand.entry,
                    cand.stop, cand.target, cand.rr, tuple(reasons), (), invalid)


def _build_candidate(ltf: Analysis, d: str, cfg: EngineConfig) -> _Candidate:
    last = ltf.last_index
    atr = ltf.atr[last]
    lo = last - cfg.setup_window_bars + 1
    bull = d == 'bull'
    sweeps = [s for s in ltf.sweeps if s.direction == d and s.index >= lo]
    if not sweeps:
        return _Candidate(d, False, ('NO_SWEEP',), ())
    sw = sweeps[-1]
    shifts = [e for e in ltf.events if e.direction == d and e.index > sw.index and e.index >= lo]
    if not shifts:
        return _Candidate(d, False, ('NO_STRUCTURE_SHIFT',), ())
    shift = shifts[-1]
    fvgs = [f for f in ltf.fvgs if f.direction == d and f.detected_index > shift.index and f.detected_index >= lo
            and ltf.fvg_status(f) != 'filled']
    if not fvgs:
        return _Candidate(d, False, ('NO_OPEN_FVG',), ())
    fvg = fvgs[-1]

    side = 'sell-side' if bull else 'buy-side'
    reasons = [
        f'{side.capitalize()} liquidity swept at {sw.level:.2f} (bar {sw.index}) and rejected',
        f'{"Bullish" if bull else "Bearish"} {shift.kind} through {shift.level:.2f} (bar {shift.index})',
        f'Open {"bullish" if bull else "bearish"} FVG {fvg.bottom:.2f}-{fvg.top:.2f} (bar {fvg.detected_index})']
    zone = (fvg.bottom, fvg.top)
    entry = fvg.midpoint
    problems: List[str] = []
    # Targets: confirmed swing levels beyond entry that price has NOT yet traded
    # through since the swing formed (a taken level is no longer resting liquidity).
    known = ltf.swings_known_at(last)

    def untouched(s):
        later = ltf.candles[s.index + 1: last + 1]
        return all((c.high < s.price) if s.kind == 'high' else (c.low > s.price) for c in later)

    if bull:
        stop = sw.extreme - cfg.stop_buffer_atr * atr
        targets = [s.price for s in known if s.kind == 'high' and s.price > entry and untouched(s)]
        target = min(targets) if targets else None
        risk = entry - stop
        invalidated = ltf.candles[last].close <= stop
    else:
        stop = sw.extreme + cfg.stop_buffer_atr * atr
        targets = [s.price for s in known if s.kind == 'low' and s.price < entry and untouched(s)]
        target = max(targets) if targets else None
        risk = stop - entry
        invalidated = ltf.candles[last].close >= stop
    rr = None
    if invalidated:
        problems.append('SETUP_INVALIDATED')
    if risk <= 0:
        problems.append('NON_POSITIVE_RISK')
    elif risk > cfg.max_stop_atr * atr:
        problems.append('STOP_TOO_WIDE')
    if target is None:
        problems.append('NO_TARGET')
    elif risk > 0:
        rr = abs(target - entry) / risk
        if rr < cfg.min_rr:
            problems.append('RR_BELOW_MINIMUM')
    return _Candidate(d, True, tuple(problems), tuple(reasons), zone, entry, stop, target, rr)
