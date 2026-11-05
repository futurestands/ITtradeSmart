"""Swing highs/lows, HH/HL/LH/LL labelling.

DEFINITIONS
    Swing high at index i (with L = swing_left, R = swing_right):
        high[i] > high[j] for every j in [i-L, i-1]   (strictly)
        high[i] > high[j] for every j in [i+1, i+R]   (strictly)
    Swing low is the mirror image using lows.
    Strict inequality means equal highs/lows are NOT swings (they are treated as
    resting liquidity elsewhere, never as pivots), and a perfectly flat market
    produces no swings at all.

    NO LOOK-AHEAD: a swing at i needs R later candles, so it is only knowable when
    candle i+R closes. `confirmed_index = i + R` and consumers must ignore a swing
    until that index. A swing is never repainted or deleted once confirmed.

    Label (computed at confirmation, relative to the previous confirmed swing of
    the same kind): HH / LH / EQH for highs, HL / LL / EQL for lows. The first
    swing of each kind has label None.
"""
from dataclasses import dataclass
from typing import List, Optional, Sequence

from .candles import Candle


@dataclass(frozen=True)
class Swing:
    index: int
    confirmed_index: int
    kind: str          # 'high' | 'low'
    price: float
    label: Optional[str] = None   # HH, LH, EQH, HL, LL, EQL


def detect_swings(candles: Sequence[Candle], left: int, right: int) -> List[Swing]:
    if left < 1 or right < 1:
        raise ValueError('swing_left and swing_right must be >= 1')
    n = len(candles)
    found: List[Swing] = []
    for i in range(left, n - right):
        hi, lo = candles[i].high, candles[i].low
        if all(hi > candles[j].high for j in range(i - left, i)) and \
           all(hi > candles[j].high for j in range(i + 1, i + right + 1)):
            found.append(Swing(i, i + right, 'high', hi))
        if all(lo < candles[j].low for j in range(i - left, i)) and \
           all(lo < candles[j].low for j in range(i + 1, i + right + 1)):
            found.append(Swing(i, i + right, 'low', lo))
    # Process in the order the information became available.
    found.sort(key=lambda s: (s.confirmed_index, s.index, s.kind))
    return _label(found)


def _label(swings: List[Swing]) -> List[Swing]:
    last = {'high': None, 'low': None}
    out = []
    for s in swings:
        prev = last[s.kind]
        label = None
        if prev is not None:
            if s.kind == 'high':
                label = 'HH' if s.price > prev else 'LH' if s.price < prev else 'EQH'
            else:
                label = 'HL' if s.price > prev else 'LL' if s.price < prev else 'EQL'
        out.append(Swing(s.index, s.confirmed_index, s.kind, s.price, label))
        last[s.kind] = s.price
    return out


def swings_known_at(swings: Sequence[Swing], index: int) -> List[Swing]:
    """Swings whose confirmation candle has closed at or before `index`."""
    return [s for s in swings if s.confirmed_index <= index]


def trend_from_swings(swings: Sequence[Swing]) -> str:
    """'bull' if the latest high is HH and latest low is HL; 'bear' if LH and LL;
    otherwise 'range' (mixed/equal) or 'unknown' (not enough labelled swings)."""
    hi = [s for s in swings if s.kind == 'high' and s.label]
    lo = [s for s in swings if s.kind == 'low' and s.label]
    if not hi or not lo:
        return 'unknown'
    if hi[-1].label == 'HH' and lo[-1].label == 'HL':
        return 'bull'
    if hi[-1].label == 'LH' and lo[-1].label == 'LL':
        return 'bear'
    return 'range'
