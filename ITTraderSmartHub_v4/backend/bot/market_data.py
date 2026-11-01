"""Market Data Manager: Candle/tick data ingestion, symbol specifications, UTC normalization, and freshness validation."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import random


def utcnow():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SymbolSpec:
    symbol: str
    contract_size: float
    pip_size: float
    pip_value_usd: float
    min_lot: float = 0.01
    max_lot: float = 100.0
    lot_step: float = 0.01


@dataclass(frozen=True)
class Candle:
    symbol: str
    time_utc: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class MarketDataManager:
    """Manages symbol specs, candle series, and price freshness."""

    SPECS = {
        "BTCUSD": SymbolSpec("BTCUSD", contract_size=1.0, pip_size=1.0, pip_value_usd=1.0),
        "EURUSD": SymbolSpec("EURUSD", contract_size=100000.0, pip_size=0.0001, pip_value_usd=10.0),
        "GBPUSD": SymbolSpec("GBPUSD", contract_size=100000.0, pip_size=0.0001, pip_value_usd=10.0),
        "XAUUSD": SymbolSpec("XAUUSD", contract_size=100.0, pip_size=0.10, pip_value_usd=10.0),
        "US30": SymbolSpec("US30", contract_size=1.0, pip_size=1.0, pip_value_usd=1.0)
    }

    def __init__(self):
        self.last_tick_time = {}
        self.last_price = {}

    def get_spec(self, symbol: str) -> SymbolSpec:
        sym = symbol.upper().replace("/", "").replace("_", "")
        return self.SPECS.get(sym, SymbolSpec(sym, contract_size=100000.0, pip_size=0.0001, pip_value_usd=10.0))

    def update_price(self, symbol: str, price: float):
        sym = symbol.upper().replace("/", "").replace("_", "")
        self.last_price[sym] = price
        self.last_tick_time[sym] = datetime.now(timezone.utc)

    def is_data_fresh(self, symbol: str, max_age_seconds: int = 120) -> bool:
        sym = symbol.upper().replace("/", "").replace("_", "")
        last_t = self.last_tick_time.get(sym)
        if last_t is None:
            return False
        age = (datetime.now(timezone.utc) - last_t).total_seconds()
        return age <= max_age_seconds

    def generate_synthetic_candles(self, symbol: str, num_bars: int = 100, base_price: float = 65000.0) -> list:
        """Generates realistic synthetic OHLCV candles for offline strategy backtesting & simulation."""
        candles = []
        now = datetime.now(timezone.utc)
        curr_price = base_price

        for i in range(num_bars, 0, -1):
            t_str = (now - timedelta(minutes=5 * i)).isoformat()
            change = random.normalvariate(0, base_price * 0.002)
            open_p = curr_price
            close_p = open_p + change
            high_p = max(open_p, close_p) + abs(random.normalvariate(0, base_price * 0.001))
            low_p = min(open_p, close_p) - abs(random.normalvariate(0, base_price * 0.001))
            vol = abs(random.normalvariate(100, 20))

            candles.append(Candle(symbol, t_str, round(open_p, 2), round(high_p, 2), round(low_p, 2), round(close_p, 2), round(vol, 1)))
            curr_price = close_p

        return candles
