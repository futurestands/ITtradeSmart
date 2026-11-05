"""Fair Value Gap (FVG) detection.

DEFINITION (three-candle imbalance, candles i-2, i-1, i)
    Bullish FVG: low[i] > high[i-2]        zone = [high[i-2], low[i]]
    Bearish FVG: high[i] < low[i-2]        zone = [high[i], low[i-2]]
    The middle candle's body is irrelevant to the test. The zone must be at least
    `min_atr` * ATR[i] tall (ATR as of candle i); if ATR is not yet defined no FVG
    is reported (conservative).

    NO LOOK-AHEAD: the pattern is complete, and `detected_index = i`, when candle i
    closes. Zone bounds never change afterwards.

    Fill status is a function of an explicit `as_of` index and uses only candles
    after the formation up to and including `as_of`:
        bullish: 'filled' if min(low) <= bottom, 'partial' if min(low) < top, else 'open'
        bearish: 'filled' if max(high) >= top,   'partial' if max(high) > bottom, else 'open'
    A price gap (open far from the previous close) is handled naturally: it simply
    produces a large FVG, and ATR (true range includes the gap) scales the filter.
"""
from dataclasses import dataclass
from typing import List, Optional, Sequence

from .candles import Candle


@dataclass(frozen=True)
class FVG:
    direction: str       # 'bull' | 'bear'
    detected_index: int  # candle i whose close completed the pattern
    bottom: float
    top: float

    @property
    def size(self) -> float:
        return self.top - self.bottom

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2.0


def detect_fvgs(candles: Sequence[Candle], atr: Sequence[Optional[float]],
                min_atr: float) -> List[FVG]:
    out: List[FVG] = []
    for i in range(2, len(candles)):
        a = atr[i]
        if a is None:
            continue
        first, cur = candles[i - 2], candles[i]
        if cur.low > first.high and (cur.low - first.high) >= min_atr * a:
            out.append(FVG('bull', i, first.high, cur.low))
        elif cur.high < first.low and (first.low - cur.high) >= min_atr * a:
            out.append(FVG('bear', i, cur.high, first.low))
    return out


def fvg_status(fvg: FVG, candles: Sequence[Candle], as_of: int) -> str:
    """'open' | 'partial' | 'filled' using candles in (detected_index, as_of]."""
    later = candles[fvg.detected_index + 1: as_of + 1]
    if not later:
        return 'open'
    if fvg.direction == 'bull':
        low = min(c.low for c in later)
        return 'filled' if low <= fvg.bottom else 'partial' if low < fvg.top else 'open'
    high = max(c.high for c in later)
    return 'filled' if high >= fvg.top else 'partial' if high > fvg.bottom else 'open'
