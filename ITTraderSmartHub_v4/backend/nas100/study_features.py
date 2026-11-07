"""Closed-bar research features from existing detectors, never a trade signal.

These are implementation hypotheses for subsequent annotation and evaluation,
not a claim to encode Michael Huddleston's complete/discretionary methodology.
No data-certification or training gate is relaxed by creating a snapshot.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence, Tuple

from .analysis import analyze
from .candles import Candle, validate_candles
from .config import EngineConfig


@dataclass(frozen=True)
class StudySnapshot:
    decision_at: datetime
    available_at: Optional[datetime]
    closed_bars: int
    feature_items: Tuple[Tuple[str, Optional[float]], ...]
    blockers: Tuple[str, ...]
    feature_version: str = 'ict-proxy-study-v1'
    methodology_status: str = 'IMPLEMENTATION_HYPOTHESES_NOT_VERIFIED_ICT_EQUIVALENCE'
    execution_mode: str = 'RESEARCH_ONLY'
    model_status: str = 'MODEL_NOT_READY'
    decision: str = 'NO_TRADE'
    training_eligible: bool = False
    trade_authorized: bool = False


def closed_bar_snapshot(candles: Sequence[Candle], timeframe_minutes: int, *,
                        decision_at: datetime, cfg: EngineConfig = EngineConfig()) -> StudySnapshot:
    """Create one as-of snapshot; exclude open/future bars before detectors run.

    Timestamps must be aware UTC. Missing bars stay missing: closures are never
    inferred, nor are prices forward-filled. Null features mean unavailable,
    not a bearish/neutral label. All snapshots remain uncertified for training.
    """
    if (not isinstance(decision_at, datetime) or decision_at.tzinfo is None
            or decision_at.utcoffset() != timedelta(0)):
        raise ValueError('decision_at must be aware UTC')
    if type(timeframe_minutes) is not int or timeframe_minutes <= 0:
        raise ValueError('timeframe_minutes must be a positive integer')
    span = timedelta(minutes=timeframe_minutes)
    closed = []
    for candle in candles:
        if (not isinstance(candle.time, datetime) or candle.time.tzinfo is None
                or candle.time.utcoffset() != timedelta(0)):
            raise ValueError('candle times must be aware UTC')
        if candle.time + span <= decision_at:
            closed.append(candle)
    quality = validate_candles(closed, timeframe_minutes)
    blockers = ['DATASET_NOT_CERTIFIED', 'COST_MODEL_NOT_CERTIFIED', 'ICT_ANNOTATIONS_NOT_VALIDATED']
    features = {name: None for name in (
        'atr_over_close', 'structure_direction', 'consolidation',
        'last_sweep_direction', 'last_sweep_age_bars',
        'open_bull_fvg_count', 'open_bear_fvg_count',
        'confirmed_high_distance_atr', 'confirmed_low_distance_atr')}
    available = None
    if not closed:
        blockers.append('NO_CLOSED_BARS')
    else:
        analysis = analyze(closed, timeframe_minutes, cfg)
        available = closed[-1].time + span
        if available != decision_at:
            blockers.append('LATEST_BAR_NOT_CURRENT_AT_DECISION')
        if quality.gaps:
            blockers.append('UNEXPLAINED_MISSING_CANDLES')
        if analysis.status != 'OK':
            blockers.append('INSUFFICIENT_HISTORY')
        # Preserve missingness during warm-up and on gaps instead of fabricating
        # a clean training vector from an incomplete sequence.
        if analysis.status == 'OK' and not quality.gaps:
            atr = analysis.atr[-1]
            if atr is None or len(closed) < cfg.consolidation_window:
                blockers.append('FEATURE_WARMUP_INCOMPLETE')
            features['atr_over_close'] = atr / closed[-1].close if atr is not None else None
            features['structure_direction'] = {'bull': 1.0, 'bear': -1.0}.get(analysis.trend)
            if atr is not None and len(closed) >= cfg.consolidation_window:
                features['consolidation'] = float(analysis.consolidation[-1])
            if analysis.sweeps:
                sweep = analysis.sweeps[-1]
                features['last_sweep_direction'] = 1.0 if sweep.direction == 'bull' else -1.0
                features['last_sweep_age_bars'] = float(analysis.last_index - sweep.index)
            for direction in ('bull', 'bear'):
                if atr is not None:
                    features[f'open_{direction}_fvg_count'] = float(sum(
                        f.direction == direction and analysis.fvg_status(f) != 'filled'
                        for f in analysis.fvgs))
            for kind in ('high', 'low'):
                levels = [s for s in analysis.swings if s.kind == kind]
                if levels and atr is not None and atr > 0:
                    # Signed distance to latest confirmed pivot, not a claim that
                    # liquidity still rests there (it may already be consumed).
                    features[f'confirmed_{kind}_distance_atr'] = (levels[-1].price - closed[-1].close) / atr
    return StudySnapshot(decision_at.astimezone(timezone.utc), available, len(closed),
                         tuple(sorted(features.items())), tuple(blockers))
