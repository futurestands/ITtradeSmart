"""ATR, volatility regime and consolidation classification (all causal).

ATR (Wilder, period n)
    TR[0] = high[0]-low[0];  TR[i] = max(h-l, |h-close[i-1]|, |l-close[i-1]|)
    ATR[n-1] = mean(TR[0..n-1]);  ATR[i] = (ATR[i-1]*(n-1) + TR[i]) / n
    ATR[i] is None for i < n-1. TR uses the previous close, so price gaps are included.

REGIME at candle t (uses only ATR values in the trailing `regime_lookback` window
ending at t)
    'UNKNOWN'  ATR undefined or fewer than `regime_min_history` ATR values
    'FLAT'     ATR[t]/close[t] <= flat_atr_over_price (no meaningful movement)
    otherwise rank = (#hist < ATR[t] + 0.5 * #hist == ATR[t]) / #hist, then
    'LOW' if rank <= low_vol_pct, 'HIGH' if rank >= high_vol_pct, else 'NORMAL'.

CONSOLIDATION at candle t (window w = consolidation_window); BOTH must hold
    (max high - min low over the last w candles) <= consolidation_range_atr * ATR[t]
    Kaufman efficiency ratio  |close[t]-close[t-w]| / sum|close[i]-close[i-1]|  <= max_efficiency
    Requiring both avoids labelling a tight but one-directional move as a range.
    False when fewer than w+1 candles or ATR is undefined.
"""
from typing import List, Optional, Sequence

from .candles import Candle


def true_ranges(candles: Sequence[Candle]) -> List[float]:
    out: List[float] = []
    for i, c in enumerate(candles):
        if i == 0:
            out.append(c.high - c.low)
        else:
            pc = candles[i - 1].close
            out.append(max(c.high - c.low, abs(c.high - pc), abs(c.low - pc)))
    return out


def atr_series(candles: Sequence[Candle], period: int) -> List[Optional[float]]:
    if period < 1:
        raise ValueError('atr_period must be >= 1')
    tr = true_ranges(candles)
    out: List[Optional[float]] = [None] * len(candles)
    if len(candles) < period:
        return out
    val = sum(tr[:period]) / period
    out[period - 1] = val
    for i in range(period, len(candles)):
        val = (val * (period - 1) + tr[i]) / period
        out[i] = val
    return out


def regime_series(candles: Sequence[Candle], atr: Sequence[Optional[float]], lookback: int,
                  min_history: int, low_pct: float, high_pct: float,
                  flat_atr_over_price: float) -> List[str]:
    out: List[str] = []
    for t, c in enumerate(candles):
        a = atr[t]
        if a is None:
            out.append('UNKNOWN')
            continue
        if c.close > 0 and a / c.close <= flat_atr_over_price:
            out.append('FLAT')
            continue
        hist = [x for x in atr[max(0, t - lookback + 1): t + 1] if x is not None]
        if len(hist) < min_history:
            out.append('UNKNOWN')
            continue
        less = sum(1 for x in hist if x < a)
        equal = sum(1 for x in hist if x == a)
        rank = (less + 0.5 * equal) / len(hist)
        out.append('LOW' if rank <= low_pct else 'HIGH' if rank >= high_pct else 'NORMAL')
    return out


def consolidation_series(candles: Sequence[Candle], atr: Sequence[Optional[float]], window: int,
                         range_atr: float, max_efficiency: float) -> List[bool]:
    out: List[bool] = []
    for t in range(len(candles)):
        a = atr[t]
        if a is None or t < window:
            out.append(False)
            continue
        seg = candles[t - window + 1: t + 1]
        rng = max(c.high for c in seg) - min(c.low for c in seg)
        path = sum(abs(candles[i].close - candles[i - 1].close) for i in range(t - window + 1, t + 1))
        net = abs(candles[t].close - candles[t - window].close)
        efficiency = 0.0 if path == 0 else net / path
        out.append(rng <= range_atr * a and efficiency <= max_efficiency)
    return out
