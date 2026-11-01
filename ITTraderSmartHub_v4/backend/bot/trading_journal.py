"""Trading Journal: Persistent audit record of all bot signals, risk decisions, orders, and performance outcomes."""
import os
import sqlite3
from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc).isoformat()


class TradingJournal:
    """SQLite Trading Journal for Signals, Decisions, Executions, and Performance Snapshots."""

    def __init__(self, database_path=None):
        self.database_path = database_path or os.environ.get("SMARTHUB_STATE_DB")
        self.signals = []
        self.decisions = []

        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS bot_signals (signal_id TEXT PRIMARY KEY, timestamp TEXT, symbol TEXT, direction TEXT, strategy TEXT, entry_price REAL, sl REAL, tp REAL, confidence REAL, reason TEXT)")
                db.execute("CREATE TABLE IF NOT EXISTS bot_decisions (decision_id TEXT PRIMARY KEY, signal_id TEXT, timestamp TEXT, approved INT, allocated_lots REAL, reasons TEXT, mode TEXT)")

    def record_signal(self, signal) -> str:
        sig_id = f"sig-{len(self.signals) + 1:05d}"
        sig_rec = {
            "signal_id": sig_id,
            "timestamp": signal.timestamp,
            "symbol": signal.symbol,
            "direction": signal.direction,
            "strategy": f"{signal.strategy_name} {signal.strategy_version}",
            "entry_price": signal.entry_price,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "confidence": signal.confidence,
            "reason": signal.reason
        }
        self.signals.append(sig_rec)

        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                db.execute("INSERT OR REPLACE INTO bot_signals VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (sig_id, signal.timestamp, signal.symbol, signal.direction, sig_rec["strategy"], signal.entry_price, signal.stop_loss, signal.take_profit, signal.confidence, signal.reason))

        return sig_id

    def record_decision(self, signal_id: str, risk_res, mode: str) -> str:
        dec_id = f"dec-{len(self.decisions) + 1:05d}"
        dec_rec = {
            "decision_id": dec_id,
            "signal_id": signal_id,
            "timestamp": utcnow(),
            "approved": 1 if risk_res.approved else 0,
            "allocated_lots": risk_res.allocated_lots,
            "reasons": ",".join(risk_res.reason_codes),
            "mode": mode
        }
        self.decisions.append(dec_rec)

        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                db.execute("INSERT OR REPLACE INTO bot_decisions VALUES (?,?,?,?,?,?,?)",
                           (dec_id, signal_id, dec_rec["timestamp"], dec_rec["approved"], risk_res.allocated_lots, dec_rec["reasons"], mode))

        return dec_id

    def get_recent_journal(self, limit: int = 20) -> dict:
        return {
            "signals": self.signals[-limit:],
            "decisions": self.decisions[-limit:]
        }
