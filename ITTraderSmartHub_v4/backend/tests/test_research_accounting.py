"""Hand-worked examples are MOCK-TESTED fixtures, never broker specifications."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from bot.accounting import ResearchInstrument, ResearchCosts
from bot.backtesting import BacktestEngine
from bot.market_data import Candle, MarketDataManager
from bot.strategies import Signal
from bot.demo_execution import DemoMT5ExecutionAdapter
from bot.bot_controller import BotController
from bot.time_integrity import TimebaseEvidence


def index_spec():
    return ResearchInstrument("NAS100.fixture", .25, .25, .5, .5, 2,
                              .1, 100, .1, "USD", "USD", "MOCK hand-worked linear CFD")


def bars():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return [Candle("NAS100.fixture", (start+timedelta(hours=i)).isoformat(),
                   20000, 20002, 19998, 20000, 10, 4) for i in range(45)]


class OneSignal:
    name = "deterministic fixture"

    def __init__(self, direction="BUY", repeated=False):
        self.direction, self.repeated = direction, repeated

    def generate_signal(self, symbol, candles):
        assert all(c.time_utc < bars()[len(candles)].time_utc for c in candles)
        if len(candles) != 35 and not self.repeated:
            return None
        buy = self.direction == "BUY"
        return Signal(symbol, self.direction, 20000, 19990 if buy else 20010,
                      20010 if buy else 19990, candles[34].time_utc,
                      self.name, "1", 0, "test")


def engine(financing=0):
    return BacktestEngine(instrument=index_spec(), costs=ResearchCosts(.25, 2, financing), volume=.5,
                          timebase=TimebaseEvidence("VERIFIED_UTC", "MOCK financial fixture only",
                              "2025-01-03T00:00:00+00:00", "H1", 0, 0))


@pytest.mark.parametrize("direction,exit_price,expected", [
    ("BUY", 20010, 10), ("SELL", 19990, 10),
    ("BUY", 19990, -10), ("SELL", 20010, -10)])
def test_index_tick_cash_example(direction, exit_price, expected):
    # 10 index points / .25 tick * $.50 per lot per tick * .5 lots = $10.
    assert index_spec().pnl(direction, .5, 20000, exit_price) == pytest.approx(expected)


def test_secondary_eurusd_pip_example():
    spec = ResearchInstrument("EURUSD.fixture", .00001, .00001, 1, 1,
                              100000, .01, 100, .01, "USD", "USD", "MOCK EURUSD")
    # 10 pips * $10 per pip per lot * .1 lot = $10.
    assert spec.pnl("BUY", .1, 1.1000, 1.1010) == pytest.approx(10)


@pytest.mark.parametrize("direction", ["BUY", "SELL"])
def test_round_trip_bid_ask_slippage_commission_financing(direction):
    result = engine(.2).run_backtest(OneSignal(direction), bars())
    # Flat Bid market: $1 spread + $.25 entry + $.25 exit = $1.50
    # at $1 per point for .5 lot; $1 commission; $.50 financing for 5 bars.
    assert result.total_trades == 1
    assert result.net_profit_usd == pytest.approx(-3)
    assert result.trade_ledger[0]["entry_time"] == bars()[35].time_utc
    assert result.trade_ledger[0]["exit_bar_time"] == bars()[39].time_utc
    assert result.max_drawdown_pct == pytest.approx(.03)
    assert result.profit_factor == 0


def test_entry_uses_next_open_not_next_close_and_can_stop_on_entry_bar():
    data = bars()
    data[35] = replace(data[35], close=20001, high=20020, low=19980)
    result = engine().run_backtest(OneSignal(), data)
    row = result.trade_ledger[0]
    assert row["entry_price"] == 20001.25
    assert row["exit_reason"] == "STOP"
    assert row["exit_price"] == 19989.75
    assert row["pnl_usd"] == pytest.approx(-12.5)


def test_stop_gap_fills_at_worse_open():
    data = bars()
    data[36] = replace(data[36], open=19980, high=19985, low=19975, close=19980)
    row = engine().run_backtest(OneSignal(), data).trade_ledger[0]
    assert row["exit_reason"] == "STOP_GAP"
    assert row["exit_price"] == 19979.75
    assert row["pnl_usd"] == pytest.approx(-22.5)


def test_sell_stop_uses_ask_high():
    data = bars()
    data[35] = replace(data[35], high=20009.5)  # Bid below SL, Ask 20010.5 touches
    row = engine().run_backtest(OneSignal("SELL"), data).trade_ledger[0]
    assert row["exit_reason"] == "STOP"
    assert row["exit_price"] == 20010.25


def test_target_gap_never_grants_better_than_limit():
    data = bars()
    data[36] = replace(data[36], open=20020, high=20025, low=20015, close=20020)
    row = engine().run_backtest(OneSignal(), data).trade_ledger[0]
    assert row["exit_price"] == 20010
    assert row["exit_reason"] == "TARGET_GAP_LIMIT"


def test_duplicate_signal_and_no_overlap():
    result = engine().run_backtest(OneSignal(repeated=True), bars())
    assert result.total_trades == 1


@pytest.mark.parametrize("volume", [.01, .15, 101, float("nan")])
def test_invalid_volume_rejected(volume):
    with pytest.raises(ValueError):
        index_spec().validate_volume(volume)


@pytest.mark.parametrize("fields", [{"tick_value_loss": 0}, {"tick_size": float("nan")},
                                      {"account_currency": "KES"}, {"profit_currency": "EUR"},
                                      {"tick_value_profit": 1}, {"provenance": ""}])
def test_unknown_or_unsupported_economics_rejected(fields):
    with pytest.raises(ValueError):
        replace(index_spec(), **fields)


def test_missing_economics_and_legacy_pips_fail_closed():
    with pytest.raises(RuntimeError, match="BLOCKED_RESEARCH_ACCOUNTING"):
        BacktestEngine().run_backtest(OneSignal(), bars())
    with pytest.raises(ValueError, match="Legacy pip"):
        BacktestEngine(spread_pips=1.2)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1])
def test_bad_costs_rejected(bad):
    with pytest.raises(ValueError):
        ResearchCosts(bad, 0, 0)


def test_naive_timestamp_or_nan_ohlc_rejected():
    data = bars()
    for field in ({"time_utc": "2025-01-01T00:00:00"}, {"close": float("nan")}):
        data[0] = replace(bars()[0], **field)
        with pytest.raises(ValueError):
            engine().run_backtest(OneSignal(), data)


def test_export_and_no_fake_monte_carlo_or_sharpe(tmp_path):
    result = engine().run_backtest(OneSignal(), bars())
    engine().export_result(result, tmp_path)
    assert json.loads((tmp_path/"result.json").read_text())["net_profit_usd"] == pytest.approx(-2.5)
    assert len((tmp_path/"trades.csv").read_text().splitlines()) == 2
    assert result.sharpe_ratio is None
    assert engine().run_monte_carlo(result)["status"] == "NOT_IMPLEMENTED"


def test_execution_lock_survives_valid_admin_and_forced_enabled(monkeypatch):
    monkeypatch.setenv("SMARTHUB_API_TOKEN", "x"*48)
    calls = []
    monkeypatch.setitem(sys.modules, "MetaTrader5", SimpleNamespace(order_send=lambda *x: calls.append(x)))
    adapter = DemoMT5ExecutionAdapter()
    assert adapter.enable_demo_mode("x"*48) is False
    adapter.enabled = True
    with pytest.raises(PermissionError, match="RESEARCH_ONLY_EXECUTION_LOCK"):
        adapter.execute_demo_order("test", "NAS100.fixture", "BUY", .5, 20000, 19990, 20010)
    with pytest.raises(PermissionError):
        BotController().set_mode("DEMO", "x"*48)
    assert calls == []


def test_closed_bar_fetch_keeps_exact_symbol_and_timeframe(monkeypatch):
    calls = []
    fake = SimpleNamespace(initialize=lambda: True, shutdown=lambda: None, TIMEFRAME_H4=123,
        copy_rates_from_pos=lambda *args: calls.append(args) or [dict(time=1735689600,
            open=20000, high=20001, low=19999, close=20000, tick_volume=1, spread=4)])
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    timebase = TimebaseEvidence("VERIFIED_UTC", "MOCK fetch fixture only", "2025-01-02T00:00:00Z", "H4", 0, 0)
    assert MarketDataManager(timebase=timebase).fetch_real_mt5_candles("NAS100.fixture", "H4", 1)
    assert calls == [("NAS100.fixture", 123, 1, 1)]
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        MarketDataManager().fetch_real_mt5_candles("NAS100.fixture", "H2", 1)


def test_multiple_distinct_signals_do_not_overlap():
    class EveryBar(OneSignal):
        def generate_signal(self, symbol, candles):
            return replace(super().generate_signal(symbol, candles), timestamp=candles[-1].time_utc)
    result = engine().run_backtest(EveryBar(repeated=True), bars())
    assert result.total_trades == 2
    assert result.trade_ledger[1]["entry_time"] > result.trade_ledger[0]["exit_bar_time"]


def test_protective_level_off_tick_grid_rejected():
    class BadGrid(OneSignal):
        def generate_signal(self, symbol, candles):
            return replace(super().generate_signal(symbol, candles), take_profit=20010.13)
    with pytest.raises(ValueError, match="tick grid"):
        engine().run_backtest(BadGrid(), bars())


def test_persistent_results_do_not_collide_or_overwrite_legacy_records(tmp_path):
    import sqlite3
    test_engine = engine()
    test_engine.database_path = str(tmp_path / "research.sqlite")
    for _ in range(2):
        test_engine.run_backtest(OneSignal(), bars())
    with sqlite3.connect(test_engine.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM research_backtest_runs").fetchone()[0] == 2
        stored = json.loads(db.execute("SELECT result_json FROM research_backtest_runs LIMIT 1").fetchone()[0])
    assert stored["trade_ledger"][0]["pnl_usd"] == pytest.approx(-2.5)


def test_admin_cannot_unlock_execution_or_get_unconfigured_performance(monkeypatch):
    monkeypatch.setenv("SMARTHUB_API_TOKEN", "x"*48)
    from app import app
    client = app.test_client()
    headers = {"Authorization": "Bearer " + "x"*48}
    response = client.post("/api/v5/bot/mode", json={"mode": "DEMO", "admin_passcode": "x"*48}, headers=headers)
    assert response.status_code == 403
    blocked = client.post("/api/v5/bot/backtest", json={"symbol": "USTEC"}, headers=headers)
    assert blocked.status_code == 503
    assert blocked.json["status"] == "BLOCKED_RESEARCH_ACCOUNTING"


def test_future_signal_timestamp_is_rejected():
    class Future(OneSignal):
        def generate_signal(self, symbol, candles):
            return replace(super().generate_signal(symbol, candles), timestamp=bars()[36].time_utc)
    with pytest.raises(ValueError, match="outside available history"):
        engine().run_backtest(Future(), bars())


def test_tick_rounding_does_not_charge_extra_tick_for_binary_noise():
    spec = replace(index_spec(), tick_size=.1, tick_value_profit=.2, tick_value_loss=.2)
    assert spec.fill(.1 + .2, True) == .3
    assert spec.fill(.1 + .2, False) == .3
    assert spec.fill(.31, True) == .4
    assert spec.fill(.31, False) == .3
