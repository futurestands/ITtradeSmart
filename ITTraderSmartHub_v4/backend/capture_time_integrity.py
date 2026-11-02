"""Bounded, read-only time investigation. Never changes clocks, symbols or trading state."""
from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess
import sys
import time


def utc():
    return datetime.now(timezone.utc).isoformat()


def capture(output):
    import MetaTrader5 as mt5
    result = {"status": "TIMEBASE_UNVERIFIED", "started_utc": utc(), "calls": []}

    def save():
        temp = output / "capture.json.tmp"
        temp.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
        temp.replace(output / "capture.json")

    def call(label, operation, convert):
        before, start = utc(), time.monotonic()
        value = operation()
        after = utc()
        row = {"operation": label, "observed_before_utc": before, "observed_after_utc": after,
               "elapsed_monotonic_seconds": time.monotonic() - start,
               "value": convert(value)}
        result["calls"].append(row)
        save()
        print(label, flush=True)
        return value

    save()
    initialized = call("initialize", lambda: mt5.initialize(timeout=10000), bool)
    if not initialized:
        result["connection_error_code"] = mt5.last_error()[0]
        save()
        return
    try:
        account = mt5.account_info()
        if account is None or account.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            result["connection"] = "BLOCKED_EXPECTED_DEMO_ACCOUNT"
            save()
            return
        identity = (account.login, account.server)
        result["account_mode"] = "DEMO"
        result["account_currency"] = account.currency
        result["mt5_version"] = mt5.__version__
        call("terminal_state", mt5.terminal_info,
             lambda v: None if v is None else {k: getattr(v, k, None) for k in
                 ("connected", "trade_allowed", "tradeapi_disabled", "ping_last", "build")})

        def check_identity():
            current = mt5.account_info()
            if current is None or (current.login, current.server) != identity:
                raise RuntimeError("ACCOUNT_CHANGED")

        fields = ("name", "description", "trade_mode", "trade_calc_mode", "chart_mode",
                  "point", "trade_tick_size", "trade_tick_value_profit", "trade_tick_value_loss",
                  "trade_contract_size", "volume_min", "volume_max", "volume_step", "currency_profit",
                  "currency_margin", "margin_initial", "margin_maintenance", "trade_stops_level",
                  "spread", "swap_mode", "swap_long", "swap_short")

        def tick(value):
            return None if value is None else {k: getattr(value, k) for k in ("time", "time_msc", "bid", "ask", "flags")}

        def rates(value):
            return None if value is None else [
                {k: (int(row[k]) if k in ("time", "tick_volume", "spread", "real_volume") else float(row[k]))
                 for k in value.dtype.names} for row in value]

        for iteration in range(3):
            for name in ("USTECH100M", "USTEC", "EURUSD"):
                check_identity()
                if iteration == 0:
                    call("spec:" + name, lambda n=name: mt5.symbol_info(n),
                         lambda v: None if v is None else {k: getattr(v, k, None) for k in fields})
                call("tick:" + name, lambda n=name: mt5.symbol_info_tick(n), tick)
            if iteration < 2:
                time.sleep(1)
        for label, count in (("M15", 256), ("M30", 128), ("H1", 64), ("H4", 16)):
            check_identity()
            result["pending_operation"] = "rates:USTECH100M:" + label
            save()
            captured = call(result["pending_operation"], lambda l=label, c=count: mt5.copy_rates_from_pos(
                "USTECH100M", getattr(mt5, "TIMEFRAME_" + l), 0, c), rates)
            if label == "M15" and captured is not None and len(captured) >= 2:
                prior_m15_open = int(captured[-2]["time"])
        if "prior_m15_open" in locals():
            for relative in (0, 3600):
                check_identity()
                result["pending_operation"] = "ticks:USTECH100M:bar_plus_" + str(relative)
                save()
                call(result["pending_operation"], lambda offset=relative: mt5.copy_ticks_range(
                    "USTECH100M", datetime.fromtimestamp(prior_m15_open+offset, timezone.utc),
                    datetime.fromtimestamp(prior_m15_open+offset+900, timezone.utc), mt5.COPY_TICKS_ALL),
                    lambda v: None if v is None else [{k: (int(t[k]) if k in ("time", "time_msc", "flags") else float(t[k]))
                                                       for k in ("time", "time_msc", "bid", "ask", "flags")} for t in v])
        check_identity()
        result["finished_utc"] = utc()
        result["capture_complete"] = True
        result["note"] = "Position zero deliberately captured for investigation, NOT eligible closed research bars. Raw integers preserved."
        save()
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        capture(Path(sys.argv[2]))
    else:
        output = Path(__file__).parent / "evidence" / "time_integrity" / datetime.now(timezone.utc).strftime("capture_%Y%m%dT%H%M%S_%fZ")
        output.mkdir(parents=True, exist_ok=False)
        try:
            completed = subprocess.run([sys.executable, "-u", __file__, "--worker", str(output)], timeout=90)
            print("Output:", output.name, "exit:", completed.returncode)
            sys.exit(completed.returncode)
        except subprocess.TimeoutExpired:
            # Parent kills/reaps only its own worker; never the terminal.
            (output / "timeout.json").write_text(json.dumps({"status": "TIMEBASE_UNVERIFIED",
                "reason": "PROBE_TIMEOUT", "observed_utc": utc()}), encoding="utf-8")
            print("Probe timed out; original and partial evidence preserved:", output.name)
            sys.exit(2)
