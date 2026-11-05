"""Orchestration: run every detector over one series, and over several timeframes.

`analyze` is a pure function of (candles, timeframe, config): identical input gives
an identical (==) result. Each output carries the index at which it became knowable,
so `Analysis.events_known_at(i)` etc. reproduce exactly what an observer at candle i
could have seen. Tests assert that analysing a prefix equals filtering the full
analysis (no look-ahead / no repainting).
"""
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from .candles import Candle, DataQuality, validate_candles
from .config import EngineConfig
from .fvg import FVG, detect_fvgs, fvg_status
from .liquidity import SweepEvent, detect_sweeps
from .structure import StructureEvent, detect_structure_events
from .swings import Swing, detect_swings
from .timeframes import resample
from .volatility import atr_series, consolidation_series, regime_series


@dataclass(frozen=True)
class Analysis:
    timeframe_minutes: int
    candles: Tuple[Candle, ...]
    quality: DataQuality
    status: str                              # 'OK' | 'INSUFFICIENT_DATA'
    atr: Tuple[Optional[float], ...]
    regime: Tuple[str, ...]
    consolidation: Tuple[bool, ...]
    swings: Tuple[Swing, ...]
    events: Tuple[StructureEvent, ...]
    trend_by_index: Tuple[str, ...]
    fvgs: Tuple[FVG, ...]
    sweeps: Tuple[SweepEvent, ...]

    @property
    def last_index(self) -> int:
        return len(self.candles) - 1

    @property
    def trend(self) -> str:
        return self.trend_by_index[-1] if self.trend_by_index else 'none'

    @property
    def as_of(self):
        """Close time of the last candle (when this analysis became knowable)."""
        return self.candles[-1].time + timedelta(minutes=self.timeframe_minutes)

    def swings_known_at(self, index: int) -> List[Swing]:
        return [s for s in self.swings if s.confirmed_index <= index]

    def events_known_at(self, index: int) -> List[StructureEvent]:
        return [e for e in self.events if e.index <= index]

    def fvgs_known_at(self, index: int) -> List[FVG]:
        return [f for f in self.fvgs if f.detected_index <= index]

    def sweeps_known_at(self, index: int) -> List[SweepEvent]:
        return [s for s in self.sweeps if s.index <= index]

    def fvg_status(self, fvg: FVG, as_of: Optional[int] = None) -> str:
        return fvg_status(fvg, self.candles, self.last_index if as_of is None else as_of)


def analyze(candles: Sequence[Candle], timeframe_minutes: int,
            cfg: EngineConfig = EngineConfig(), min_bars: Optional[int] = None) -> Analysis:
    """Run all detectors. Raises DataValidationError on structurally invalid data;
    sparse/short data is reported through `status` and `quality`, never guessed."""
    quality = validate_candles(candles, timeframe_minutes, cfg.closure_min_minutes)
    need = cfg.min_bars if min_bars is None else min_bars
    atr = atr_series(candles, cfg.atr_period)
    swings = detect_swings(candles, cfg.swing_left, cfg.swing_right)
    events, trend_by_index = detect_structure_events(candles, swings)
    return Analysis(
        timeframe_minutes=timeframe_minutes,
        candles=tuple(candles),
        quality=quality,
        status='OK' if len(candles) >= need else 'INSUFFICIENT_DATA',
        atr=tuple(atr),
        regime=tuple(regime_series(candles, atr, cfg.regime_lookback, cfg.regime_min_history,
                                   cfg.low_vol_pct, cfg.high_vol_pct, cfg.flat_atr_over_price)),
        consolidation=tuple(consolidation_series(candles, atr, cfg.consolidation_window,
                                                 cfg.consolidation_range_atr,
                                                 cfg.consolidation_max_efficiency)),
        swings=tuple(swings),
        events=tuple(events),
        trend_by_index=tuple(trend_by_index),
        fvgs=tuple(detect_fvgs(candles, atr, cfg.fvg_min_atr)),
        sweeps=tuple(detect_sweeps(candles, swings, cfg.sweep_level_max_age)),
    )


@dataclass(frozen=True)
class MultiTimeframeAnalysis:
    ltf: Analysis
    htf: Dict[int, Analysis]     # keyed by timeframe minutes; closed bars only


def analyze_multitimeframe(candles: Sequence[Candle], base_minutes: int,
                           htf_minutes: Sequence[int],
                           cfg: EngineConfig = EngineConfig(),
                           min_fill: float = 1.0) -> MultiTimeframeAnalysis:
    """Analyse the base series and each higher timeframe built from it.

    Higher-timeframe bars are resampled so only CLOSED buckets appear (see
    timeframes.py), hence nothing from the future of the base series leaks in."""
    ltf = analyze(candles, base_minutes, cfg)
    htf: Dict[int, Analysis] = {}
    for tf in htf_minutes:
        bars = resample(candles, base_minutes, tf, min_fill=min_fill)
        htf[tf] = analyze(bars, tf, replace(cfg), min_bars=cfg.htf_min_bars)
    return MultiTimeframeAnalysis(ltf, htf)
