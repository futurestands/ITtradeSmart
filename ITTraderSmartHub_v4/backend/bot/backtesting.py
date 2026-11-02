"""Bounded single-position research replay; not a validated profitability engine."""
from dataclasses import asdict, dataclass
from datetime import datetime
from math import isfinite
import csv
import hashlib
import json
import os
from .market_data import MarketDataManager
from .accounting import ResearchInstrument, ResearchCosts


@dataclass
class BacktestResult:
    dataset_version: str
    strategy_name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    net_profit_usd: float
    net_return_pct: float
    max_drawdown_pct: float
    profit_factor: float | None
    expectancy_usd: float
    sharpe_ratio: float | None
    max_consecutive_losses: int
    average_win_usd: float
    average_loss_usd: float
    assumptions: dict
    trade_ledger: list
    equity_curve: list


class BacktestEngine:
    """Bid OHLC, bar spread in broker points; one position, five bars maximum.

    Unknown economics/costs fail closed. Closed trades determine drawdown: this
    is NOT intrabar/floating account drawdown or a funded-account compliance test.
    Legacy pip arguments are rejected rather than interpreted as index units.
    """
    def __init__(self, initial_balance=10000.0, spread_pips=None, slippage_pips=None,
                 database_path=None, *, instrument: ResearchInstrument = None,
                 costs: ResearchCosts = None, volume=None):
        if not isfinite(initial_balance) or initial_balance <= 0:
            raise ValueError("Initial balance must be finite and positive")
        if spread_pips is not None or slippage_pips is not None:
            raise ValueError("Legacy pip costs unsupported; supply explicit price costs and bar spreads")
        self.initial_balance = initial_balance
        self.instrument = instrument
        self.costs = costs
        self.volume = volume
        self.database_path = database_path or os.environ.get("SMARTHUB_STATE_DB")

    def run_backtest(self, strategy, candles: list, symbol: str = None) -> BacktestResult:
        spec, costs = self.instrument, self.costs
        if spec is None or costs is None or self.volume is None:
            raise RuntimeError("BLOCKED_RESEARCH_ACCOUNTING: explicit instrument, volume and cost assumptions required")
        symbol = symbol or spec.symbol
        if symbol != spec.symbol or any(c.symbol != symbol for c in candles):
            raise ValueError("Exact broker symbol mismatch")
        spec.validate_volume(self.volume)
        MarketDataManager.validate_dataset(candles)
        for c in candles:
            stamp = datetime.fromisoformat(c.time_utc)
            if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
                raise ValueError("UTC-aware candles required")
            if not all(isfinite(x) for x in (c.open, c.high, c.low, c.close, c.spread)) or c.spread < 0:
                raise ValueError("Invalid candle or spread")
        dataset_hash = hashlib.sha256(json.dumps([asdict(c) for c in candles],
                                                 sort_keys=True).encode()).hexdigest()
        balance = self.initial_balance
        equity = [{"time_utc": candles[0].time_utc, "balance_usd": balance}]
        ledger, seen = [], set()
        i = 35
        while i < len(candles) and balance > 0:
            # Strategy sees only bars that closed BEFORE the next opening fill.
            signal = strategy.generate_signal(symbol, candles[:i])
            if not signal or signal.direction not in ("BUY", "SELL"):
                i += 1
                continue
            signal_time = datetime.fromisoformat(signal.timestamp)
            if signal_time.utcoffset() is None or signal_time > datetime.fromisoformat(candles[i-1].time_utc):
                raise ValueError("Signal timestamp outside available history")
            key = (signal.symbol, signal.strategy_name, signal.strategy_version,
                   signal.timestamp, signal.direction)
            if signal.symbol != symbol:
                raise ValueError("Signal symbol mismatch")
            if key in seen:
                i += 1
                continue
            seen.add(key)
            buy = signal.direction == "BUY"
            bar = candles[i]
            spread = bar.spread * spec.point
            entry = spec.fill(bar.open + (spread if buy else 0)
                              + (costs.slippage_price if buy else -costs.slippage_price), buy)
            sl, tp = signal.stop_loss, signal.take_profit
            if not all(isfinite(x) and x > 0 for x in (sl, tp)):
                raise ValueError("Invalid protective levels")
            for level in (sl, tp):
                from decimal import Decimal
                ticks = Decimal(str(level)) / Decimal(str(spec.tick_size))
                if ticks != ticks.to_integral_value():
                    raise ValueError("Protective level violates broker tick grid")
            # Skip stale signals gapped beyond their protective bracket.
            if not (sl < entry < tp if buy else tp < entry < sl):
                i += 1
                continue
            last = min(i + 4, len(candles) - 1)
            for j in range(i, last + 1):
                bar = candles[j]
                ask_offset = 0 if buy else bar.spread * spec.point
                op, hi, lo = (bar.open + ask_offset, bar.high + ask_offset, bar.low + ask_offset)
                reason = "TIME_EXIT"
                limit_fill = False
                if (op <= sl if buy else op >= sl):
                    raw_exit, reason = op, "STOP_GAP"
                elif (op >= tp if buy else op <= tp):
                    raw_exit, reason, limit_fill = tp, "TARGET_GAP_LIMIT", True
                elif (lo <= sl if buy else hi >= sl):
                    # If both stop and target touch, pessimistically stop first.
                    raw_exit, reason = sl, "STOP"
                elif (hi >= tp if buy else lo <= tp):
                    raw_exit, reason, limit_fill = tp, "TARGET", True
                else:
                    raw_exit = bar.close + ask_offset
                if reason != "TIME_EXIT" or j == last:
                    # Target modeled as limit: do not slip below its limit.
                    adjusted = raw_exit if limit_fill else raw_exit + (-costs.slippage_price if buy else costs.slippage_price)
                    exit_price = spec.fill(adjusted, not buy)
                    gross = spec.pnl(signal.direction, self.volume, entry, exit_price)
                    commission = costs.commission_round_trip_per_lot * self.volume
                    financing = costs.financing_per_lot_per_bar * self.volume * (j-i+1)
                    pnl = gross - commission - financing
                    balance += pnl
                    ledger.append(dict(symbol=symbol, direction=signal.direction,
                                       signal_time=signal.timestamp, entry_time=candles[i].time_utc,
                                       exit_bar_time=bar.time_utc, entry_price=entry,
                                       exit_price=exit_price, volume=self.volume,
                                       gross_pnl_usd=gross, commission_usd=commission,
                                       financing_usd=financing, pnl_usd=pnl, exit_reason=reason))
                    equity.append({"time_utc": bar.time_utc, "balance_usd": balance})
                    i = j + 1  # no overlap or re-entry on the exit candle
                    break
        pnls = [t["pnl_usd"] for t in ledger]
        wins, losses = [p for p in pnls if p > 0], [p for p in pnls if p < 0]
        peak, max_dd, streak, max_streak = self.initial_balance, 0.0, 0, 0
        for row in equity:
            peak = max(peak, row["balance_usd"])
            max_dd = max(max_dd, (peak-row["balance_usd"])/peak*100)
        for p in pnls:
            streak = streak + 1 if p < 0 else 0
            max_streak = max(max_streak, streak)
        total = len(pnls)
        net = sum(pnls)
        result = BacktestResult(
            dataset_hash, strategy.name, total, len(wins), len(losses),
            len(wins)/total*100 if total else 0.0, net,
            net/self.initial_balance*100, max_dd,
            sum(wins)/abs(sum(losses)) if losses else None,
            net/total if total else 0.0, None, max_streak,
            sum(wins)/len(wins) if wins else 0.0,
            sum(losses)/len(losses) if losses else 0.0,
            {"instrument": asdict(spec), "costs": asdict(costs),
             "spread": "bar spread in broker points; constant within each bar",
             "price_basis": "BID OHLC REQUIRED", "holding_bars": 5,
             "positions": "one at a time", "drawdown": "closed-trade balance only",
             "financing": "fixed charge per lot per bar; NOT historical broker swap",
             "sharpe": "NOT COMPUTED: no regular return series",
             "out_of_sample": "NOT IMPLEMENTED", "tester_reconciliation": "NOT RUN",
             "eligibility": "RESEARCH_ONLY_NOT_VALIDATED"}, ledger, equity)
        if self.database_path:
            import sqlite3
            from uuid import uuid4
            with sqlite3.connect(self.database_path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS research_backtest_runs (run_id TEXT PRIMARY KEY, result_json TEXT NOT NULL)")
                db.execute("INSERT INTO research_backtest_runs VALUES (?, ?)",
                           (str(uuid4()), json.dumps(asdict(result), allow_nan=False)))
        return result

    def run_monte_carlo(self, backtest_res, iterations=50):
        # Do not issue invented drawdowns or readiness PASS labels.
        return {"status": "NOT_IMPLEMENTED", "reason": "Trade resampling pending independent validation"}

    @staticmethod
    def export_result(result, directory):
        from pathlib import Path
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "result.json").write_text(json.dumps(asdict(result), indent=2, allow_nan=False), encoding="utf-8")
        for name, rows in (("trades", result.trade_ledger), ("equity", result.equity_curve)):
            with (directory / (name + ".csv")).open("w", newline="", encoding="utf-8") as handle:
                if rows:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
