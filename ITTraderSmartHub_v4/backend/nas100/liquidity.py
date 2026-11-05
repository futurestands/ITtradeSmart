"""Liquidity sweeps of confirmed swing levels.

DEFINITION
    A confirmed swing high is resting buy-side liquidity; a confirmed swing low is
    resting sell-side liquidity. A level is ACTIVE from the candle after its
    confirmation until it is first traded through or it expires
    (`max_age` bars after the swing candle).

    At candle t, an active high level p is SWEPT when
        high[t] > p   (traded through)   AND   close[t] <= p   (rejected)
    -> SweepEvent(direction='bear', side='high'): buy-side liquidity taken, closed
       back below. If close[t] > p the level is merely broken (that is a structure
       break, see structure.py) and no sweep is reported.
    An active low level p is swept when low[t] < p AND close[t] >= p
    -> SweepEvent(direction='bull', side='low').
    Any trade-through consumes the level, so each level yields at most one event.

    `direction` is the implied reversal direction, not a forecast: a bull sweep is
    a candidate long context only when combined with other conditions (decision.py).

    NO LOOK-AHEAD: stamped `index = t`; only levels confirmed before t are used.
"""
from dataclasses import dataclass
from typing import List, Sequence

from .candles import Candle
from .swings import Swing


@dataclass(frozen=True)
class SweepEvent:
    direction: str      # 'bull' (lows swept) | 'bear' (highs swept)
    side: str           # 'low' | 'high'
    index: int
    level: float
    swing_index: int
    extreme: float      # the candle's high (bear) or low (bull) reached beyond the level


def detect_sweeps(candles: Sequence[Candle], swings: Sequence[Swing],
                  max_age: int) -> List[SweepEvent]:
    by_confirm = {}
    for s in swings:
        by_confirm.setdefault(s.confirmed_index, []).append(s)
    active: List[Swing] = []
    events: List[SweepEvent] = []
    for t, c in enumerate(candles):
        still: List[Swing] = []
        for s in active:
            if t - s.index > max_age:
                continue                      # expired
            if s.kind == 'high' and c.high > s.price:
                if c.close <= s.price:
                    events.append(SweepEvent('bear', 'high', t, s.price, s.index, c.high))
                continue                      # consumed either way
            if s.kind == 'low' and c.low < s.price:
                if c.close >= s.price:
                    events.append(SweepEvent('bull', 'low', t, s.price, s.index, c.low))
                continue
            still.append(s)
        # Swings confirmed at t become active only for candles AFTER t.
        still.extend(sorted(by_confirm.get(t, ()), key=lambda x: (x.index, x.kind)))
        active = still
    return events
