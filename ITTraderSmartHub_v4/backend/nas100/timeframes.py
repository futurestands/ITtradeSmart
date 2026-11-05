"""Multi-timeframe resampling that never exposes an unfinished higher-timeframe bar.

DEFINITION
    Buckets are aligned to multiples of the target timeframe since the Unix epoch
    (UTC). NOTE: this is NOT necessarily the broker's own H4/D1 alignment (brokers
    align to server time); compare against terminal charts before relying on H4+.
    A bucket [start, start+target) is emitted only when
        1. the source series extends to or past the bucket end
           (last source close time >= bucket end), and
        2. it holds at least `min_fill` * expected source candles
           (default 1.0, requiring all source slots; partial buckets need explicit opt-in).
    The emitted bar's `time` is the bucket START; its information is available at
    the bucket END, which is what `htf_closed_by` compares against.
    The source series must be validated first (see candles.validate_candles).
"""
from datetime import datetime, timedelta, timezone
from typing import List, Sequence

from math import isfinite
from .candles import Candle, validate_candles

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def resample(candles: Sequence[Candle], base_minutes: int, target_minutes: int,
             min_fill: float = 1.0) -> List[Candle]:
    if (type(target_minutes) is not int or type(base_minutes) is not int or
            target_minutes <= 0 or base_minutes <= 0 or target_minutes % base_minutes != 0):
        raise ValueError('target timeframe must be a positive multiple of the base timeframe')
    if type(min_fill) not in (int, float) or not isfinite(min_fill) or not 0 < min_fill <= 1:
        raise ValueError('min_fill must be in (0, 1]')
    validate_candles(candles, base_minutes)
    if any((c.time - _EPOCH).total_seconds() % (base_minutes * 60) for c in candles):
        raise ValueError('source candle must align to the UTC base timeframe grid')
    if not candles:
        return []
    ratio = target_minutes // base_minutes
    series_end = candles[-1].time + timedelta(minutes=base_minutes)
    buckets = {}
    order = []
    for c in candles:
        key = int((c.time - _EPOCH).total_seconds() // (target_minutes * 60))
        if key not in buckets:
            buckets[key] = []
            order.append(key)
        buckets[key].append(c)
    out: List[Candle] = []
    for key in order:
        group = buckets[key]
        start = _EPOCH + timedelta(minutes=key * target_minutes)
        end = start + timedelta(minutes=target_minutes)
        if end > series_end or len(group) < min_fill * ratio:
            continue
        spreads = [g.spread for g in group if g.spread is not None]
        out.append(Candle(start, group[0].open, max(g.high for g in group),
                          min(g.low for g in group), group[-1].close,
                          sum(g.volume for g in group), max(spreads) if spreads else None))
    return out


def htf_closed_by(htf: Sequence[Candle], target_minutes: int, as_of: datetime) -> List[Candle]:
    """Higher-timeframe bars whose close time is <= `as_of`."""
    delta = timedelta(minutes=target_minutes)
    return [b for b in htf if b.time + delta <= as_of]
