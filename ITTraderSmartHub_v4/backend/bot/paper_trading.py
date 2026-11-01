"""Paper Trading Engine: Virtual account simulation, orders, positions, and journal persistence without calling live order execution."""
from dataclasses import dataclass
from datetime import datetime, timezone
import sqlite3
import os


def utcnow():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PaperPosition:
    position_id: str
    symbol: str
    direction: str  # 'BUY' or 'SELL'
    volume: float
    entry_price: float
    stop_loss: float
    take_profit: float
    open_time: str
    unrealized_pnl: float = 0.0


class PaperTradingEngine:
    """Persistent paper trading portfolio simulator. Zero calls to live MetaTrader5.order_send()."""

    def __init__(self, initial_balance: float = 10000.0, database_path=None):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.equity = initial_balance
        self.positions = {}  # position_id -> PaperPosition
        self.closed_trades = []
        self.database_path = database_path or os.environ.get("SMARTHUB_STATE_DB")

        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS paper_positions (position_id TEXT PRIMARY KEY, symbol TEXT, direction TEXT, volume REAL, entry_price REAL, stop_loss REAL, take_profit REAL, open_time TEXT)")
                db.execute("CREATE TABLE IF NOT EXISTS paper_history (trade_id TEXT PRIMARY KEY, symbol TEXT, direction TEXT, volume REAL, entry_price REAL, exit_price REAL, pnl REAL, open_time TEXT, close_time TEXT)")

    def open_position(self, symbol: str, direction: str, volume: float, price: float, stop_loss: float, take_profit: float) -> PaperPosition:
        pos_id = f"paper-{len(self.positions) + len(self.closed_trades) + 1:04d}"
        pos = PaperPosition(pos_id, symbol, direction, volume, price, stop_loss, take_profit, utcnow())
        self.positions[pos_id] = pos

        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                db.execute("INSERT OR REPLACE INTO paper_positions VALUES (?,?,?,?,?,?,?,?)",
                           (pos_id, symbol, direction, volume, price, stop_loss, take_profit, pos.open_time))

        return pos

    def update_market_price(self, symbol: str, current_price: float):
        """Checks virtual positions against market ticks for SL/TP hits and updates unrealized PnL."""
        total_unrealized = 0.0

        for pos_id, pos in list(self.positions.items()):
            if pos.symbol.upper() != symbol.upper():
                continue

            # Calculate PnL
            diff = (current_price - pos.entry_price) if pos.direction == "BUY" else (pos.entry_price - current_price)
            pos.unrealized_pnl = diff * pos.volume * 1.0  # $1/point scaling
            total_unrealized += pos.unrealized_pnl

            # Stop Loss Trigger
            sl_hit = (pos.direction == "BUY" and current_price <= pos.stop_loss) or (pos.direction == "SELL" and current_price >= pos.stop_loss)
            # Take Profit Trigger
            tp_hit = (pos.direction == "BUY" and current_price >= pos.take_profit) or (pos.direction == "SELL" and current_price <= pos.take_profit)

            if sl_hit or tp_hit:
                self.close_position(pos_id, current_price, "SL_HIT" if sl_hit else "TP_HIT")

        self.equity = self.balance + total_unrealized

    def close_position(self, position_id: str, exit_price: float, reason: str = "MANUAL") -> dict:
        pos = self.positions.pop(position_id, None)
        if not pos:
            return None

        diff = (exit_price - pos.entry_price) if pos.direction == "BUY" else (pos.entry_price - exit_price)
        realized_pnl = round(diff * pos.volume * 1.0, 2)
        self.balance += realized_pnl
        self.equity = self.balance

        close_rec = {
            "trade_id": pos.position_id,
            "symbol": pos.symbol,
            "direction": pos.direction,
            "volume": pos.volume,
            "entry_price": pos.entry_price,
            "exit_price": exit_price,
            "pnl": realized_pnl,
            "reason": reason,
            "open_time": pos.open_time,
            "close_time": utcnow()
        }
        self.closed_trades.append(close_rec)

        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                db.execute("DELETE FROM paper_positions WHERE position_id=?", (position_id,))
                db.execute("INSERT INTO paper_history VALUES (?,?,?,?,?,?,?,?,?)",
                           (pos.position_id, pos.symbol, pos.direction, pos.volume, pos.entry_price, exit_price, realized_pnl, pos.open_time, close_rec["close_time"]))

        return close_rec

    def get_summary(self) -> dict:
        return {
            "mode": "PAPER_TRADING",
            "balance": round(self.balance, 2),
            "equity": round(self.equity, 2),
            "open_positions_count": len(self.positions),
            "closed_trades_count": len(self.closed_trades),
            "total_pnl": round(self.balance - self.initial_balance, 2)
        }
