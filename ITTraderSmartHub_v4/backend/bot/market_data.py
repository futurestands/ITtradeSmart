"""Market Data Manager: Real MT5 historical data ingestion, symbol specifications, fail-closed data integrity, and strict separation of production vs test candles."""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from math import isfinite
import hashlib
import os
import random
import sqlite3


def utcnow():
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class SymbolSpec:
    symbol: str
    contract_size: float
    pip_size: float
    tick_size: float
    tick_value: float
    min_lot: float = 0.01
    max_lot: float = 100.0
    lot_step: float = 0.01
    currency: str = "USD"


@dataclass(frozen=True)
class Candle:
    symbol: str
    time_utc: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    spread: float = 0.0


class MarketDataManager:
    """Manages real MT5 market data ingestion and fail-closed freshness checks. Synthetic data is prohibited in production."""

    SPECS = {
        "EURUSD": SymbolSpec("EURUSD", contract_size=100000.0, pip_size=0.0001, tick_size=0.00001, tick_value=1.0, min_lot=0.01, max_lot=100.0, lot_step=0.01),
        "GBPUSD": SymbolSpec("GBPUSD", contract_size=100000.0, pip_size=0.0001, tick_size=0.00001, tick_value=1.0, min_lot=0.01, max_lot=100.0, lot_step=0.01),
        "USDJPY": SymbolSpec("USDJPY", contract_size=100000.0, pip_size=0.01, tick_size=0.001, tick_value=0.91, min_lot=0.01, max_lot=100.0, lot_step=0.01),
        "XAUUSD": SymbolSpec("XAUUSD", contract_size=100.0, pip_size=0.10, tick_size=0.01, tick_value=1.0, min_lot=0.01, max_lot=100.0, lot_step=0.01),
        "BTCUSD": SymbolSpec("BTCUSD", contract_size=1.0, pip_size=1.0, tick_size=0.01, tick_value=1.0, min_lot=0.01, max_lot=100.0, lot_step=0.01),
        "US30": SymbolSpec("US30", contract_size=1.0, pip_size=1.0, tick_size=1.0, tick_value=1.0, min_lot=0.01, max_lot=100.0, lot_step=0.01)
    }

    def __init__(self, database_path=None):
        self.database_path = database_path or os.environ.get("SMARTHUB_STATE_DB")
        self.last_tick_time = {}
        self.last_price = {}

        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS mt5_candles (symbol TEXT, timeframe TEXT, time_utc TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL, spread REAL, checksum TEXT, PRIMARY KEY (symbol, timeframe, time_utc))")

    def get_spec(self, symbol: str) -> SymbolSpec:
        sym = symbol.upper().replace("/", "").replace("_", "")
        spec = self.SPECS.get(sym)
        if spec is None:
            # Query live MT5 symbol info if available
            try:
                import MetaTrader5 as mt5
                if mt5.initialize():
                    info = mt5.symbol_info(sym)
                    mt5.shutdown()
                    if info is not None:
                        return SymbolSpec(
                            symbol=sym,
                            contract_size=float(getattr(info, "trade_contract_size", 100000.0)),
                            pip_size=float(getattr(info, "point", 0.0001)) * 10.0,
                            tick_size=float(getattr(info, "trade_tick_size", 0.00001)),
                            tick_value=float(getattr(info, "trade_tick_value", 1.0)),
                            min_lot=float(getattr(info, "volume_min", 0.01)),
                            max_lot=float(getattr(info, "volume_max", 100.0)),
                            lot_step=float(getattr(info, "volume_step", 0.01)),
                            currency=str(getattr(info, "currency_profit", "USD"))
                        )
            except Exception:
                pass
            raise ValueError(f"Unknown or unavailable symbol specification for {sym}")
        return spec

    def update_price(self, symbol: str, price: float):
        if price <= 0 or not isfinite(price):
            raise ValueError("Price must be a positive finite number")
        sym = symbol.upper().replace("/", "").replace("_", "")
        self.last_price[sym] = price
        self.last_tick_time[sym] = datetime.now(timezone.utc)

    def is_data_fresh(self, symbol: str, max_age_seconds: int = 120) -> bool:
        """Fail-closed data freshness check."""
        sym = symbol.upper().replace("/", "").replace("_", "")
        last_t = self.last_tick_time.get(sym)
        if last_t is None:
            return False
        age = (datetime.now(timezone.utc) - last_t).total_seconds()
        return age <= max_age_seconds

    def fetch_real_mt5_candles(self, symbol: str, timeframe_str: str = "H1", num_bars: int = 500) -> list:
        """Fetches real historical candles from MT5 terminal or SQLite cache. PROHIBITS synthetic fallback in production."""
        sym = symbol.upper().replace("/", "").replace("_", "")

        try:
            import MetaTrader5 as mt5
            tf_map = {"M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "H1": mt5.TIMEFRAME_H1, "D1": mt5.TIMEFRAME_D1}
            tf = tf_map.get(timeframe_str, mt5.TIMEFRAME_H1)

            if mt5.initialize():
                rates = mt5.copy_rates_from_pos(sym, tf, 0, num_bars)
                mt5.shutdown()
                if rates is not None and len(rates) > 0:
                    candles = []
                    for r in rates:
                        t_utc = datetime.fromtimestamp(int(r['time']), timezone.utc).isoformat()
                        c = Candle(sym, t_utc, float(r['open']), float(r['high']), float(r['low']), float(r['close']), float(r['tick_volume']), float(r['spread']))
                        candles.append(c)

                    self.validate_dataset(candles)
                    self.store_candles_in_db(sym, timeframe_str, candles)
                    return candles
        except Exception:
            pass

        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                rows = db.execute("SELECT symbol, time_utc, open, high, low, close, volume, spread FROM mt5_candles WHERE symbol=? AND timeframe=? ORDER BY time_utc DESC LIMIT ?",
                                  (sym, timeframe_str, num_bars)).fetchall()[::-1]
                if rows:
                    candles = [Candle(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]) for r in rows]
                    self.validate_dataset(candles)
                    return candles

        # STRICT FAIL-CLOSED: If test mode is enabled explicitly, allow test candles; otherwise raise RuntimeError.
        if os.environ.get("SMARTHUB_TEST_MODE") == "1":
            return self.generate_test_candles(sym, num_bars=num_bars)

        raise RuntimeError(f"FATAL: Real MT5 market data unavailable for symbol {sym}. Fail-closed active. No synthetic data permitted in production.")

    def store_candles_in_db(self, symbol: str, timeframe: str, candles: list):
        if not self.database_path or not candles:
            return
        with sqlite3.connect(self.database_path) as db:
            for c in candles:
                checksum = hashlib.sha256(f"{c.symbol}:{c.time_utc}:{c.close}".encode('utf-8')).hexdigest()
                db.execute("INSERT OR REPLACE INTO mt5_candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (symbol, timeframe, c.time_utc, c.open, c.high, c.low, c.close, c.volume, c.spread, checksum))

    @staticmethod
    def validate_dataset(candles: list):
        if not candles:
            raise ValueError("Empty dataset")

        seen_timestamps = set()
        prev_time = None

        for c in candles:
            if c.open <= 0 or c.high <= 0 or c.low <= 0 or c.close <= 0:
                raise ValueError(f"Structurally invalid candle with non-positive prices at {c.time_utc}")
            if c.high < c.low or c.high < c.open or c.high < c.close or c.low > c.open or c.low > c.close:
                raise ValueError(f"Invalid OHLC high/low bounds at {c.time_utc}")

            if c.time_utc in seen_timestamps:
                raise ValueError(f"Duplicate bar timestamp detected at {c.time_utc}")
            seen_timestamps.add(c.time_utc)

            curr_time = datetime.fromisoformat(c.time_utc)
            if prev_time and curr_time <= prev_time:
                raise ValueError(f"Unordered bar timestamps: {c.time_utc} is not greater than {prev_time.isoformat()}")
            prev_time = curr_time

    @staticmethod
    def generate_test_candles(symbol: str = "EURUSD", num_bars: int = 200, base_price: float = 1.0850) -> list:
        """EXPLICIT TEST-ONLY HELPER: Generates synthetic candles for unit tests when SMARTHUB_TEST_MODE=1. Prohibited in production."""
        candles = []
        now = datetime.now(timezone.utc)
        curr_price = base_price

        for i in range(num_bars, 0, -1):
            t_str = (now - timedelta(hours=i)).isoformat()
            change = random.normalvariate(0, 0.0010)
            open_p = curr_price
            close_p = max(0.5000, open_p + change)
            high_p = max(open_p, close_p) + abs(random.normalvariate(0, 0.0005))
            low_p = min(open_p, close_p) - abs(random.normalvariate(0, 0.0005))
            vol = abs(random.normalvariate(500, 50))

            candles.append(Candle(symbol, t_str, round(open_p, 5), round(high_p, 5), round(low_p, 5), round(close_p, 5), round(vol, 1), spread=1.2))
            curr_price = close_p

        return candles
