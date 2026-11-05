"""Break of Structure (BOS) and Change of Character (CHoCH).

DEFINITIONS (close-based, sequential, non-repainting)
    Reference levels: at each candle t the reference swing high H is the MOST
    RECENTLY CONFIRMED swing high (confirmed_index <= t) that has not yet been
    broken; the reference swing low L likewise.

    A bullish break occurs at candle t when close[t] > H.price.
    A bearish break occurs at candle t when close[t] < L.price.
    (A wick through the level without a close beyond it is NOT a break; see
    liquidity.py for that case.)

    Trend state starts 'none'. On a break:
        * bullish break while state in ('none', 'bull') -> BOS (bull), state = bull
        * bullish break while state == 'bear'           -> CHoCH (bull), state = bull
        * bearish break while state in ('none', 'bear') -> BOS (bear), state = bear
        * bearish break while state == 'bull'           -> CHoCH (bear), state = bear
    The first break from 'none' is labelled BOS with `initial=True`: with no
    prior trend it cannot be a character change.
    A broken level is consumed and cannot be broken again; a new reference of that
    kind only exists once a later swing of that kind is confirmed.
    If a single close would break both references (only possible when they are
    inverted), nothing is emitted and both are consumed (conflicting information).

    NO LOOK-AHEAD: events are stamped `index = t` (the breaking close). Only swings
    with confirmed_index <= t are considered, so truncating the series after t
    cannot change any event at or before t.
"""
from dataclasses import dataclass
from typing import List, Optional, Sequence

from .candles import Candle
from .swings import Swing


@dataclass(frozen=True)
class StructureEvent:
    kind: str            # 'BOS' | 'CHoCH'
    direction: str       # 'bull' | 'bear'
    index: int           # candle whose close broke the level (= detected_index)
    level: float
    swing_index: int     # origin swing of the broken level
    initial: bool = False


def detect_structure_events(candles: Sequence[Candle], swings: Sequence[Swing]):
    """Return (events, trend_by_index) where trend_by_index[t] is the trend state
    after processing candle t ('none' | 'bull' | 'bear')."""
    by_confirm = {}
    for s in swings:
        by_confirm.setdefault(s.confirmed_index, []).append(s)
    ref_high: Optional[Swing] = None
    ref_low: Optional[Swing] = None
    trend = 'none'
    events: List[StructureEvent] = []
    trend_by_index: List[str] = []
    for t, c in enumerate(candles):
        for s in sorted(by_confirm.get(t, ()), key=lambda x: (x.index, x.kind)):
            if s.kind == 'high':
                ref_high = s
            else:
                ref_low = s
        up = ref_high is not None and c.close > ref_high.price
        down = ref_low is not None and c.close < ref_low.price
        if up and down:
            ref_high = ref_low = None
        elif up:
            kind = 'CHoCH' if trend == 'bear' else 'BOS'
            events.append(StructureEvent(kind, 'bull', t, ref_high.price, ref_high.index,
                                         initial=(trend == 'none')))
            trend, ref_high = 'bull', None
        elif down:
            kind = 'CHoCH' if trend == 'bull' else 'BOS'
            events.append(StructureEvent(kind, 'bear', t, ref_low.price, ref_low.index,
                                         initial=(trend == 'none')))
            trend, ref_low = 'bear', None
        trend_by_index.append(trend)
    return events, trend_by_index
