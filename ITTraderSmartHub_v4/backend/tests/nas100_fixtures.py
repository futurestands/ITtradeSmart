"""SYNTHETIC TEST FIXTURES ONLY.

Everything here is artificial price data built to exercise detector logic. Nothing
in this file is NAS100 data and no result derived from it says anything about
profitability or real-market behaviour.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nas100 import Candle  # noqa: E402

UTC = timezone.utc
MONDAY = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)   # a Monday, standard time in UK and US


def leg_path(waypoints, bars_per_leg):
    """Closes moving linearly through `waypoints`, `bars_per_leg` bars per leg."""
    closes = [float(waypoints[0])]
    for a, b in zip(waypoints, waypoints[1:]):
        for k in range(1, bars_per_leg + 1):
            closes.append(a + (b - a) * k / bars_per_leg)
    return closes


def candles_from_closes(closes, start=MONDAY, tf=5, wick=2.0):
    """open = midpoint of previous/current close so equal-tie highs never occur;
    high/low = body extreme +/- wick."""
    out, prev = [], closes[0]
    for i, c in enumerate(closes):
        o = (prev + c) / 2.0
        out.append(Candle(start + timedelta(minutes=tf * i), o, max(o, c) + wick,
                          min(o, c) - wick, c, 100.0, 10.0))
        prev = c
    return out


def zigzag(waypoints, bars_per_leg=5, start=MONDAY, tf=5, wick=2.0):
    return candles_from_closes(leg_path(waypoints, bars_per_leg), start, tf, wick)


def bar(t, o, h, l, c, spread=10.0):
    return Candle(t, o, h, l, c, 100.0, spread)


def flat_series(n, price=100.0, start=MONDAY, tf=5):
    return [Candle(start + timedelta(minutes=tf * i), price, price, price, price, 0.0, 10.0)
            for i in range(n)]


def mirror(candles, k=4000.0):
    """Price-mirror a series around k (bull scenario -> bear scenario)."""
    return [Candle(c.time, k - c.open, k - c.low, k - c.high, k - c.close, c.volume, c.spread)
            for c in candles]


def bullish_setup_ltf(last_open=datetime(2026, 1, 6, 14, 0, tzinfo=UTC), tf=5):
    """85 M5 bars: uptrend -> pullback -> sell-side sweep -> displacement + FVG.
    The last candle opens at `last_open` (default Tue 14:00 UTC = London+NY overlap, winter)."""
    wps = [800, 900, 860, 960, 920, 1040, 1000, 1200, 1100, 1125, 1105]
    closes = leg_path(wps, 8)                         # 81 closes (idx 0..80)
    n = 85
    start = last_open - timedelta(minutes=tf * (n - 1))
    c = candles_from_closes(closes, start, tf, wick=2.0)
    t = lambda i: start + timedelta(minutes=tf * i)
    c.append(bar(t(81), 1104, 1107, 1094, 1106))      # sweep of the 1100 swing low, close back above
    c.append(bar(t(82), 1106, 1131, 1105, 1129))      # displacement: closes above swing high (shift)
    c.append(bar(t(83), 1130, 1138, 1122, 1135))      # low[83] > high[81] -> bullish FVG
    c.append(bar(t(84), 1135, 1136, 1118, 1120))      # pullback toward (not through) the FVG
    return c


def uptrend_htf(tf=60):
    start = datetime(2026, 1, 4, 13, 0, tzinfo=UTC)
    wps = [1000, 1100, 1060, 1180, 1140, 1260, 1220, 1340, 1300]
    return zigzag(wps, 6, start=start, tf=tf, wick=3.0)
