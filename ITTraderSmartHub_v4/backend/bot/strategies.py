"""Candidate Trading Strategies for Quantitative Backtesting and Paper Testing."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Signal:
    symbol: str
    direction: str  # 'BUY', 'SELL', 'FLAT'
    entry_price: float
    stop_loss: float
    take_profit: float
    timestamp: str
    strategy_name: str
    strategy_version: str
    confidence: float
    reason: str


class BaseStrategy(ABC):
    @abstractmethod
    def generate_signal(self, symbol: str, candles: list) -> Signal:
        pass


class TrendFollowingMACrossoverStrategy(BaseStrategy):
    """Candidate A: Moving Average Crossover with ATR Stops."""
    def __init__(self, fast_period: int = 10, slow_period: int = 30, atr_period: int = 14,
                 atr_multiplier: float = 1.5, reward_risk_ratio: float = 2.0):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.reward_risk_ratio = reward_risk_ratio
        self.name = "Candidate_A_MA_ATR"
        self.version = "v5.2"

    def _sma(self, prices: list, period: int) -> float:
        if len(prices) < period:
            return 0.0
        return sum(prices[-period:]) / period

    def _atr(self, candles: list, period: int) -> float:
        if len(candles) < period + 1:
            return 0.0010
        tr_list = []
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_close = candles[i-1].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
        return sum(tr_list[-period:]) / period

    def generate_signal(self, symbol: str, candles: list) -> Signal:
        if len(candles) < self.slow_period + 2:
            now_t = candles[-1].time_utc if candles else datetime.now(timezone.utc).isoformat()
            return Signal(symbol, "FLAT", 0.0, 0.0, 0.0, now_t, self.name, self.version, 0.0, "Insufficient candle history")

        closes = [c.close for c in candles]
        curr_price = closes[-1]
        last_candle_time = candles[-1].time_utc

        fast_curr = self._sma(closes[:-1], self.fast_period)
        slow_curr = self._sma(closes[:-1], self.slow_period)
        fast_prev = self._sma(closes[:-2], self.fast_period)
        slow_prev = self._sma(closes[:-2], self.slow_period)

        atr_val = self._atr(candles[:-1], self.atr_period)
        sl_dist = atr_val * self.atr_multiplier
        tp_dist = sl_dist * self.reward_risk_ratio

        if fast_prev <= slow_prev and fast_curr > slow_curr:
            sl = round(curr_price - sl_dist, 5)
            tp = round(curr_price + tp_dist, 5)
            return Signal(symbol, "BUY", curr_price, sl, tp, last_candle_time, self.name, self.version, 0.85, f"Bullish MA Crossover ({self.fast_period}/{self.slow_period})")

        if fast_prev >= slow_prev and fast_curr < slow_curr:
            sl = round(curr_price + sl_dist, 5)
            tp = round(curr_price - tp_dist, 5)
            return Signal(symbol, "SELL", curr_price, sl, tp, last_candle_time, self.name, self.version, 0.85, f"Bearish MA Crossover ({self.fast_period}/{self.slow_period})")

        return Signal(symbol, "FLAT", curr_price, 0.0, 0.0, last_candle_time, self.name, self.version, 0.0, "No Crossover Detected")


class DonchianBreakoutStrategy(BaseStrategy):
    """Candidate B: Donchian Channel 20-period Breakout with Volatility Filter."""
    def __init__(self, channel_period: int = 20, atr_period: int = 14, atr_multiplier: float = 1.5, reward_risk_ratio: float = 2.0):
        self.channel_period = channel_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.reward_risk_ratio = reward_risk_ratio
        self.name = "Candidate_B_Donchian_Breakout"
        self.version = "v5.2"

    def generate_signal(self, symbol: str, candles: list) -> Signal:
        if len(candles) < self.channel_period + 2:
            now_t = candles[-1].time_utc if candles else datetime.now(timezone.utc).isoformat()
            return Signal(symbol, "FLAT", 0.0, 0.0, 0.0, now_t, self.name, self.version, 0.0, "Insufficient history")

        closes = [c.close for c in candles]
        highs = [c.high for c in candles[:-1]]
        lows = [c.low for c in candles[:-1]]

        curr_price = closes[-1]
        last_candle_time = candles[-1].time_utc

        upper_channel = max(highs[-self.channel_period:])
        lower_channel = min(lows[-self.channel_period:])

        # Calculate ATR
        # i must start at 1 because candles[1:] is offset by one bar.
        # Starting at zero accidentally reads candles[-1] (future candle) first
        # and compares subsequent bars against two bars earlier.
        tr_list = [
            max(c.high - c.low,
                abs(c.high - candles[i - 1].close),
                abs(c.low - candles[i - 1].close))
            for i, c in enumerate(candles[1:], start=1)
        ]
        atr_val = sum(tr_list[-self.atr_period:]) / self.atr_period if len(tr_list) >= self.atr_period else 0.0010

        sl_dist = atr_val * self.atr_multiplier
        tp_dist = sl_dist * self.reward_risk_ratio

        if curr_price > upper_channel:
            sl = round(curr_price - sl_dist, 5)
            tp = round(curr_price + tp_dist, 5)
            return Signal(symbol, "BUY", curr_price, sl, tp, last_candle_time, self.name, self.version, 0.80, f"Donchian Upper Breakout ({upper_channel:.5f})")

        if curr_price < lower_channel:
            sl = round(curr_price + sl_dist, 5)
            tp = round(curr_price - tp_dist, 5)
            return Signal(symbol, "SELL", curr_price, sl, tp, last_candle_time, self.name, self.version, 0.80, f"Donchian Lower Breakout ({lower_channel:.5f})")

        return Signal(symbol, "FLAT", curr_price, 0.0, 0.0, last_candle_time, self.name, self.version, 0.0, "Inside Donchian Channel")


class MeanReversionRSIStrategy(BaseStrategy):
    """Candidate C: RSI Mean-Reversion with SMA Regime Filter."""
    def __init__(self, rsi_period: int = 14, overbought: float = 70.0, oversold: float = 30.0, sma_regime: int = 100):
        self.rsi_period = rsi_period
        self.overbought = overbought
        self.oversold = oversold
        self.sma_regime = sma_regime
        self.name = "Candidate_C_RSI_MeanReversion"
        self.version = "v5.2"

    def _rsi(self, closes: list) -> float:
        if len(closes) < self.rsi_period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i-1]
            gains.append(diff if diff > 0 else 0)
            losses.append(abs(diff) if diff < 0 else 0)

        avg_gain = sum(gains[-self.rsi_period:]) / self.rsi_period
        avg_loss = sum(losses[-self.rsi_period:]) / self.rsi_period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def generate_signal(self, symbol: str, candles: list) -> Signal:
        if len(candles) < self.sma_regime + 1:
            now_t = candles[-1].time_utc if candles else datetime.now(timezone.utc).isoformat()
            return Signal(symbol, "FLAT", 0.0, 0.0, 0.0, now_t, self.name, self.version, 0.0, "Insufficient history")

        closes = [c.close for c in candles]
        curr_price = closes[-1]
        last_candle_time = candles[-1].time_utc

        rsi_val = self._rsi(closes[:-1])
        sma_val = sum(closes[-self.sma_regime:]) / self.sma_regime

        sl_dist = curr_price * 0.01  # 1% stop loss
        tp_dist = curr_price * 0.02  # 2% take profit

        if rsi_val < self.oversold and curr_price > sma_val:
            sl = round(curr_price - sl_dist, 5)
            tp = round(curr_price + tp_dist, 5)
            return Signal(symbol, "BUY", curr_price, sl, tp, last_candle_time, self.name, self.version, 0.75, f"RSI Oversold ({rsi_val:.1f}) in Bullish Regime")

        if rsi_val > self.overbought and curr_price < sma_val:
            sl = round(curr_price + sl_dist, 5)
            tp = round(curr_price - tp_dist, 5)
            return Signal(symbol, "SELL", curr_price, sl, tp, last_candle_time, self.name, self.version, 0.75, f"RSI Overbought ({rsi_val:.1f}) in Bearish Regime")

        return Signal(symbol, "FLAT", curr_price, 0.0, 0.0, last_candle_time, self.name, self.version, 0.0, f"RSI Neutral ({rsi_val:.1f})")


class PassiveBuyAndHoldBenchmark(BaseStrategy):
    """Passive Buy and Hold Benchmark."""
    def __init__(self):
        self.name = "Passive_Buy_And_Hold_Benchmark"
        self.version = "v1.0"

    def generate_signal(self, symbol: str, candles: list) -> Signal:
        if not candles:
            return Signal(symbol, "FLAT", 0.0, 0.0, 0.0, datetime.now(timezone.utc).isoformat(), self.name, self.version, 0.0, "No data")

        curr = candles[-1].close
        return Signal(symbol, "BUY", curr, curr * 0.5, curr * 2.0, candles[-1].time_utc, self.name, self.version, 1.0, "Passive Buy & Hold")
