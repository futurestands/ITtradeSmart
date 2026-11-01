"""Market Data Manager: Authoritative broker symbol specifications, fail-closed historical fetching, and authenticated quote provider."""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from math import isfinite
import hashlib
import os
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


@dataclass(frozen=True)
class AuthenticatedQuote:
    symbol: str
    bid: float
    ask: float
    timestamp_utc: str
    source: str
    account_login: int


class MarketDataManager:
    """Manages authoritative broker symbol specs, authenticated quotes, and fail-closed historical data."""

    def __init__(self, database_path=None, symbol_specs: dict = None):
        self.database_path = database_path or os.environ.get("SMARTHUB_STATE_DB")
        self.injected_specs = symbol_specs or {}
        self.last_quotes = {}  # symbol -> AuthenticatedQuote

        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS mt5_candles (symbol TEXT, timeframe TEXT, time_utc TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL, spread REAL, checksum TEXT, PRIMARY KEY (symbol, timeframe, time_utc))")

    def get_spec(self, symbol: str) -> SymbolSpec:
        sym = symbol.upper().replace("/", "").replace("_", "")

        # 1. Check injected test adapter mocks first
        if sym in self.injected_specs:
            return self.injected_specs[sym]

        # 2. Obtain broker-authoritative symbol info from MetaTrader 5
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

        raise RuntimeError(f"BLOCKED_BROKER_SYMBOL_METADATA: Authoritative broker specification for {sym} unavailable. No default tick values substituted.")

    def ingest_authenticated_quote(self, quote: AuthenticatedQuote):
        """Ingests an authenticated broker quote with strict identity and freshness validation."""
        if quote.bid <= 0 or quote.ask <= 0 or quote.ask < quote.bid:
            raise ValueError("Invalid authenticated quote bid/ask pricing")
        if not quote.source or not quote.account_login:
            raise ValueError("Quote missing authenticated source or account login")

        # Check freshness (< 10 seconds)
        try:
            q_time = datetime.fromisoformat(quote.timestamp_utc.replace('Z', '+00:00'))
            age = (datetime.now(timezone.utc) - q_time).total_seconds()
            if abs(age) > 10.0:
                raise ValueError(f"Quote timestamp is stale (age: {age:.1f}s)")
        except Exception as e:
            if "stale" in str(e):
                raise
            raise ValueError(f"Invalid quote timestamp format: {quote.timestamp_utc}")

        sym = quote.symbol.upper().replace("/", "").replace("_", "")
        self.last_quotes[sym] = quote

    def get_authenticated_quote(self, symbol: str) -> AuthenticatedQuote:
        sym = symbol.upper().replace("/", "").replace("_", "")
        quote = self.last_quotes.get(sym)
        if quote is None:
            raise RuntimeError(f"No authenticated quote available for {sym}")

        # Re-verify freshness
        q_time = datetime.fromisoformat(quote.timestamp_utc.replace('Z', '+00:00'))
        if (datetime.now(timezone.utc) - q_time).total_seconds() > 10.0:
            raise RuntimeError(f"Authenticated quote for {sym} has expired (>10s)")
        return quote

    def fetch_real_mt5_candles(self, symbol: str, timeframe_str: str = "H1", num_bars: int = 500) -> list:
        """Fetches real historical candles from MT5 or SQLite cache. NO synthetic fallback."""
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

        raise RuntimeError(f"FATAL: Real MT5 market data unavailable for symbol {sym}. Fail-closed active.")

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
