"""Read-only discovery; never logs identity, logs in, selects symbols or sends orders."""
import hashlib
import json
import re
import csv
from math import isfinite
from datetime import datetime, timezone
from pathlib import Path


def discover(mt5, checkpoint=lambda report: None, data_directory=None):
    report = {"observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "status": "BLOCKED_MT5_CONNECTION", "candidates": [],
              "sessions": "NOT AVAILABLE through MT5 Python API; needs broker specification",
              "costs": "Historical commissions/financing not supplied by rates API"}
    report["stage"] = "initialize"
    checkpoint(report)
    if not mt5.initialize(timeout=10000):
        report["error_code"] = mt5.last_error()[0]
        return report
    try:
        account = mt5.account_info()
        if account is None or account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            report["status"] = "BLOCKED_EXPECTED_DEMO_ACCOUNT"
            return report
        identity = (account.login, account.server)

        def assert_identity():
            current = mt5.account_info()
            if current is None or (current.login, current.server) != identity:
                raise RuntimeError("BLOCKED_ACCOUNT_CHANGED")

        report["account_mode"] = "DEMO"
        report["account_currency"] = account.currency
        report["package_version"] = mt5.__version__
        term = mt5.terminal_info()
        report["terminal_connected"] = bool(term and term.connected)
        symbols = mt5.symbols_get()
        if symbols is None:
            report["status"] = "BLOCKED_SYMBOL_INVENTORY"
            return report
        report["symbols_scanned"] = len(symbols)
        report["stage"] = "symbol_inventory"
        checkpoint(report)
        pattern = re.compile(r"NAS.?100|US.?100|USTEC|\bNDX\b|NASDAQ|NASDQ|USA.?100", re.I)
        fields = ("name", "description", "path", "trade_contract_size", "trade_tick_size",
                  "trade_tick_value", "trade_tick_value_profit", "trade_tick_value_loss",
                  "point", "digits", "currency_profit", "currency_margin", "volume_min",
                  "volume_max", "volume_step", "margin_initial", "margin_maintenance",
                  "trade_calc_mode", "trade_mode", "spread", "spread_float", "visible",
                  "trade_stops_level", "swap_mode", "swap_long", "swap_short", "chart_mode")
        for item in symbols:
            if not pattern.search(item.name + " " + item.description):
                continue
            assert_identity()
            info = mt5.symbol_info(item.name)
            row = {key: getattr(info, key, None) for key in fields}
            row["classification"] = "CANDIDATE_ONLY; financial equivalence unverified"
            row["timeframes"] = {}
            report["candidates"].append(row)
            if re.search(r"ETF|ETN|Stock|Shares", getattr(info, "path", "") + " " + item.description, re.I):
                row["classification"] = "EXCLUDED_ETF_OR_SHARE: not a comparable index CFD"
            checkpoint(report)
        report["stage"] = "inventory_complete"
        checkpoint(report)
        for row in report["candidates"]:
            if row["classification"].startswith("EXCLUDED"):
                continue
            name = row["name"]
            info = mt5.symbol_info(name)
            tick = mt5.symbol_info_tick(name)
            row["quote"] = ({"bid": tick.bid, "ask": tick.ask, "time": tick.time}
                            if tick else None)
            if tick is None or tick.ask <= 0 or tick.bid <= 0:
                # Preserve the prior timed-out probe separately. Do not keep
                # retrying unquoted symbols in the bounded collection run.
                row["history_status"] = "NOT_RUN_UNQUOTED_SYMBOL; see prior timeout evidence"
                checkpoint(report)
                continue
            row["margin_buy_min_volume"] = (mt5.order_calc_margin(
                mt5.ORDER_TYPE_BUY, name, info.volume_min, tick.ask)
                if info and tick and tick.ask > 0 else None)
            if info and tick and tick.ask > 0:
                row["current_environment_profit_check"] = {
                    "volume": info.volume_min, "entry": tick.ask,
                    "exit": tick.ask + 10 * info.trade_tick_size,
                    "broker_profit_account_currency": mt5.order_calc_profit(
                        mt5.ORDER_TYPE_BUY, name, info.volume_min, tick.ask,
                        tick.ask + 10 * info.trade_tick_size),
                    "linear_tick_expectation": 10 * info.trade_tick_value_profit * info.volume_min,
                    "scope": "current environment only; excludes fees; no historical reconciliation"}
            for label in ("D1", "H4", "H1", "M30", "M15", "M5", "M1"):
                report["stage"] = "history:" + name + ":" + label
                checkpoint(report)
                assert_identity()
                rates = mt5.copy_rates_from_pos(name, getattr(mt5, "TIMEFRAME_" + label), 1, 5000)
                summary = {"requested_closed_bars": 5000, "count": 0}
                if rates is not None and len(rates):
                    times = [int(r["time"]) for r in rates]
                    summary.update(count=len(rates),
                                   first_utc=datetime.fromtimestamp(times[0], timezone.utc).isoformat(),
                                   last_utc=datetime.fromtimestamp(times[-1], timezone.utc).isoformat(),
                                   strictly_ordered=all(a < b for a, b in zip(times, times[1:])),
                                   invalid_ohlc=sum(not (all(isfinite(float(r[k])) for k in ("open", "high", "low", "close")) and
                                                       0 < r["low"] <= min(r["open"], r["close"])
                                                       <= max(r["open"], r["close"]) <= r["high"])
                                                    for r in rates),
                                   raw_array_sha256=hashlib.sha256(rates.tobytes()).hexdigest())
                    if data_directory is not None:
                        destination = Path(data_directory) / (name + "_" + label + ".csv")
                        temporary_csv = destination.with_suffix(".csv.tmp")
                        with temporary_csv.open("w", newline="", encoding="utf-8") as handle:
                            writer = csv.writer(handle)
                            writer.writerow(["time_utc", "open", "high", "low", "close", "tick_volume", "spread_points", "real_volume"])
                            for rate in rates:
                                writer.writerow([datetime.fromtimestamp(int(rate["time"]), timezone.utc).isoformat()] +
                                                [rate[k] for k in ("open", "high", "low", "close", "tick_volume", "spread", "real_volume")])
                        temporary_csv.replace(destination)
                        summary["csv_file"] = destination.name
                        summary["csv_sha256"] = hashlib.sha256(destination.read_bytes()).hexdigest()
                else:
                    summary["error_code"] = mt5.last_error()[0]
                row["timeframes"][label] = summary
                checkpoint(report)
        assert_identity()
        report["stage"] = "complete"
        report["status"] = ("CANDIDATES_REQUIRE_SPECIFICATION_REVIEW" if any(
                            c["timeframes"] for c in report["candidates"])
                            else "BLOCKED_MISSING_COMPARABLE_INDEX_DATA")
        return report
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    import subprocess
    import sys
    import MetaTrader5 as mt5
    target = Path(__file__).parent / "evidence" / "nas100_discovery.json"
    target.parent.mkdir(exist_ok=True)

    if "--worker" not in sys.argv:
        # A parent process can enforce a timeout even if a native MT5 call holds
        # the worker GIL. A Python timer thread cannot guarantee that bound.
        try:
            completed = subprocess.run([sys.executable, "-u", __file__, "--worker"], timeout=90)
            sys.exit(completed.returncode)
        except subprocess.TimeoutExpired:
            partial = json.loads(target.read_text(encoding="utf-8"))
            partial["status"] = "BLOCKED_PROBE_TIMEOUT"
            target.write_text(json.dumps(partial, indent=2), encoding="utf-8")
            print("Probe timed out; partial evidence retained. Terminal not terminated.")
            sys.exit(2)

    def checkpoint(report):
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2), encoding="utf-8")
        temporary.replace(target)
        if report.get("stage") != getattr(checkpoint, "last_stage", None):
            print("Discovery stage:", report.get("stage"), flush=True)
            checkpoint.last_stage = report.get("stage")
    result = discover(mt5, checkpoint, target.parent)
    checkpoint(result)
    print(result["status"], "Evidence:", target.name)
