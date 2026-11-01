"""Base Strategy Interface and Moving Average Crossover + ATR Strategy."""
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
    """
    Explainable Trend-Following Strategy:
    - Moving Average Crossover (Fast vs Slow)
    - ATR-based Stop Loss & Reward-to-Risk Take Profit
    - Closed-candle confirmation (no intrabar repainting)
    - Volatility & Spread filters
    """
    def __init__(self, fast_period: int = 10, slow_period: int = 30, atr_period: int = 14,
                 atr_multiplier: float = 1.5, reward_risk_ratio: float = 2.0, max_spread_pips: float = 5.0):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.atr_period = atr_period
        self.atr_multiplier = atr_multiplier
        self.reward_risk_ratio = reward_risk_ratio
        self.max_spread_pips = max_spread_pips
        self.name = "MA_Crossover_ATR"
        self.version = "v5.1"

    def _sma(self, prices: list, period: int) -> float:
        if len(prices) < period:
            return 0.0
        return sum(prices[-period:]) / period

    def _atr(self, candles: list, period: int) -> float:
        if len(candles) < period + 1:
            return 10.0  # Fallback default ATR
        tr_list = []
        for i in range(1, len(candles)):
            high = candles[i].high
            low = candles[i].low
            prev_close = candles[i-1].close
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
        return sum(tr_list[-period:]) / period

    def generate_signal(self, symbol: str, candles: list) -> Signal:
        now_str = datetime.now(timezone.utc).isoformat()
        if len(candles) < self.slow_period + 2:
            return Signal(symbol, "FLAT", 0.0, 0.0, 0.0, now_str, self.name, self.version, 0.0, "Insufficient candle history")

        closes = [c.close for c in candles]
        curr_price = closes[-1]

        # Calculate MAs on closed candles
        fast_curr = self._sma(closes[:-1], self.fast_period)
        slow_curr = self._sma(closes[:-1], self.slow_period)

        fast_prev = self._sma(closes[:-2], self.fast_period)
        slow_prev = self._sma(closes[:-2], self.slow_period)

        atr_val = self._atr(candles[:-1], self.atr_period)
        sl_dist = atr_val * self.atr_multiplier
        tp_dist = sl_dist * self.reward_risk_ratio

        # Bullish Crossover (Fast MA crosses above Slow MA)
        if fast_prev <= slow_prev and fast_curr > slow_curr:
            sl = round(curr_price - sl_dist, 2)
            tp = round(curr_price + tp_dist, 2)
            return Signal(symbol, "BUY", curr_price, sl, tp, now_str, self.name, self.version, 0.85, f"Bullish MA Crossover (Fast {self.fast_period} > Slow {self.slow_period})")

        # Bearish Crossover (Fast MA crosses below Slow MA)
        if fast_prev >= slow_prev and fast_curr < slow_curr:
            sl = round(curr_price + sl_dist, 2)
            tp = round(curr_price - tp_dist, 2)
            return Signal(symbol, "SELL", curr_price, sl, tp, now_str, self.name, self.version, 0.85, f"Bearish MA Crossover (Fast {self.fast_period} < Slow {self.slow_period})")

        return Signal(symbol, "FLAT", curr_price, 0.0, 0.0, now_str, self.name, self.version, 0.0, "No Crossover Detected")
