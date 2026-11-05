"""Candle model, validation and data-source adapters.

This module is deliberately free of I/O and of any MetaTrader5 import. Market-data
acquisition (the MT5 gateway) produces plain rate records; `candles_from_rates`
converts them. Analysis modules only ever see `Candle` objects.

TIME CONVENTION (applies to the whole package)
    * `Candle.time` is the candle OPEN time, timezone-aware UTC.
    * A candle's information is first available at its CLOSE: time + timeframe.
      Every detector stamps its output with `detected_index`, the index of the
      candle whose close made the information knowable. Nothing is ever stamped
      with an earlier index than the information supports (no look-ahead).
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Iterable, List, Optional, Sequence, Tuple

from .tz import get_zone


class DataValidationError(ValueError):
    """Raised when candle data is structurally invalid (not merely sparse)."""


@dataclass(frozen=True)
class Candle:
    time: datetime              # open time, tz-aware UTC
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    spread: Optional[float] = None   # broker points, if known


@dataclass(frozen=True)
class Gap:
    """Missing candles between series positions `after_index` and `after_index + 1`."""
    after_index: int
    missing_bars: int
    duration_minutes: int
    is_market_closure: bool     # requires external session evidence; never inferred


@dataclass(frozen=True)
class DataQuality:
    n_bars: int
    gaps: Tuple[Gap, ...]

    @property
    def fault_gaps(self) -> Tuple[Gap, ...]:
        """Gaps that look like missing data rather than a market closure."""
        return tuple(g for g in self.gaps if not g.is_market_closure)


def validate_candles(candles: Sequence[Candle], timeframe_minutes: int,
                     closure_min_minutes: int = 60) -> DataQuality:
    """Validate structure; report (not fix) missing candles.

    Raises DataValidationError for: non-UTC/naive times, non-increasing times,
    non-finite prices, OHLC inconsistency, negative volume. Missing candles are
    reported in `DataQuality.gaps`. Duration alone cannot establish a market
    closure. The legacy closure_min_minutes argument no longer exempts gaps.
    """
    if type(timeframe_minutes) is not int or timeframe_minutes <= 0:
        raise DataValidationError('timeframe_minutes must be positive')
    gaps: List[Gap] = []
    tf = timedelta(minutes=timeframe_minutes)
    prev: Optional[Candle] = None
    for i, c in enumerate(candles):
        if c.time.tzinfo is None or c.time.utcoffset() != timedelta(0):
            raise DataValidationError(f'candle {i}: time must be timezone-aware UTC')
        vals = (c.open, c.high, c.low, c.close)
        if not all(type(v) in (int, float) and isfinite(v) and v > 0 for v in vals):
            raise DataValidationError(f'candle {i}: non-finite price')
        if c.high < max(c.open, c.close, c.low) or c.low > min(c.open, c.close, c.high):
            raise DataValidationError(f'candle {i}: inconsistent OHLC')
        if c.volume is not None and (not isfinite(c.volume) or c.volume < 0):
            raise DataValidationError(f'candle {i}: invalid volume')
        if c.spread is not None and (not isfinite(c.spread) or c.spread < 0):
            raise DataValidationError(f'candle {i}: invalid spread')
        if prev is not None:
            delta = c.time - prev.time
            if delta <= timedelta(0):
                raise DataValidationError(f'candle {i}: times must be strictly increasing')
            if delta % tf != timedelta(0):
                raise DataValidationError(f'candle {i}: spacing is not a multiple of the timeframe')
            if delta > tf:
                missing = int(delta / tf) - 1
                dur = int((delta - tf).total_seconds() // 60)
                gaps.append(Gap(i - 1, missing, dur, False))
        prev = c
    return DataQuality(len(candles), tuple(gaps))


def candle_close_time(candle: Candle, timeframe_minutes: int) -> datetime:
    return candle.time + timedelta(minutes=timeframe_minutes)


def candles_from_rates(rates: Iterable, server_tz: str, *,
                       time_encoding: str = 'utc') -> List[Candle]:
    """Convert MT5-style rate records into UTC `Candle`s (pure, no MT5 import).

    `rates` items may be dicts or numpy records exposing 'time', 'open', 'high',
    'low', 'close' and optionally 'tick_volume' / 'real_volume' / 'spread'.

    Official MT5 Python API timestamps are UTC. Use server_tz='UTC' for them.
    Non-API datasets explicitly verified as wall-clock encoded must opt into
    time_encoding='verified_wall_clock' and supply their verified IANA zone.
    This conversion is not independent evidence of actual broker clock accuracy.
    """
    if time_encoding not in ('utc', 'verified_wall_clock'):
        raise DataValidationError('unsupported time encoding')
    if time_encoding == 'utc' and server_tz != 'UTC':
        raise DataValidationError('MT5 API rates require UTC; wall-clock encoding needs explicit verification')
    zone = get_zone(server_tz)
    out: List[Candle] = []
    prev_utc: Optional[datetime] = None
    for r in rates:
        stamp = _get(r, 'time')
        # numpy integer scalars implement __index__; floats and booleans do not
        # represent an unambiguous integer epoch.
        if isinstance(stamp, bool) or not hasattr(stamp, '__index__'):
            raise DataValidationError('rate time must be an integer epoch')
        wall = datetime.fromtimestamp(stamp.__index__(), timezone.utc).replace(tzinfo=None)
        utc = _resolve_wall_time(wall, zone, prev_utc)
        volume = _get(r, 'tick_volume', None)
        if volume is None:
            volume = _get(r, 'real_volume', 0.0)
        spread = _get(r, 'spread', None)
        out.append(Candle(utc, float(_get(r, 'open')), float(_get(r, 'high')),
                          float(_get(r, 'low')), float(_get(r, 'close')),
                          float(volume or 0.0), None if spread is None else float(spread)))
        prev_utc = utc
    return out


def _get(record, key, default=...):
    try:
        return record[key]
    except (KeyError, IndexError, ValueError):
        if default is ...:
            raise DataValidationError(f'rate record is missing field {key!r}')
        return default


def _resolve_wall_time(wall: datetime, zone, prev_utc: Optional[datetime]) -> datetime:
    candidates = []
    for fold in (0, 1):
        utc = wall.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None) == wall and utc not in candidates:
            candidates.append(utc)
    for utc in sorted(candidates):
        if prev_utc is None or utc > prev_utc:
            return utc
    raise DataValidationError('nonexistent wall time or series is not increasing after DST resolution')
