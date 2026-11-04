"""Regression: Donchian ATR uses the immediately preceding candle, not i-1 from sliced enumerate."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.strategies import DonchianBreakoutStrategy


def test_donchian_uses_actual_previous_candle_close():
    # Alternating previous closes deliberately distinguish one-bar vs two-bar
    # lookback. Every high/low is internally consistent with the close.
    prices = [100.0, 105.0, 100.0, 105.0, 100.0, 105.0, 100.0, 120.0]
    candles = [
        SimpleNamespace(high=p+1, low=p-1, close=p, time_utc=f"T{i}")
        for i, p in enumerate(prices)
    ]
    strategy = DonchianBreakoutStrategy(
        channel_period=4, atr_period=4, atr_multiplier=1.0, reward_risk_ratio=2.0,
    )
    signal = strategy.generate_signal("US100", candles)
    assert signal.direction == "BUY"
    # Correct latest true ranges = 6,6,6,21; ATR=9.75.
    assert signal.stop_loss == 110.25
    assert signal.take_profit == 139.50


def test_donchian_atr_ignores_wrapped_last_bar_at_history_start():
    # A huge last-bar close must not become the previous close of candles[1].
    # This also detects future-data leakage into the first true-range sample.
    prices = [100.0, 103.0, 106.0, 109.0, 112.0, 115.0, 118.0, 170.0]
    candles = [
        SimpleNamespace(high=p + 0.5, low=p - 0.5, close=p, time_utc=f"T{i}")
        for i, p in enumerate(prices)
    ]
    strategy = DonchianBreakoutStrategy(
        channel_period=4, atr_period=6, atr_multiplier=1.0, reward_risk_ratio=1.0,
    )
    signal = strategy.generate_signal("US100", candles)
    assert signal.direction == "BUY"
    # True ranges for i=2..7: 3.5,3.5,3.5,3.5,3.5,52.5 = 11.66666...
    expected = (3.5*5 + 52.5) / 6
    assert abs(signal.stop_loss - round(170.0 - expected, 5)) < 1e-9
