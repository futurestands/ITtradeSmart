import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from bot import (
    MarketDataManager, TrendFollowingMACrossoverStrategy, BacktestEngine,
    PaperTradingEngine, RiskGuardian, DemoMT5ExecutionAdapter, BotController, Signal
)

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('SMARTHUB_API_TOKEN', 'a'*48)
    monkeypatch.setenv('SMARTHUB_TELEMETRY_TOKEN', 'b'*48)
    monkeypatch.setenv('SMARTHUB_TEST_MODE', '1')
    from app import app, _v4_store, _bot
    _v4_store.devices.clear()
    _v4_store.pairing_codes.clear()
    _v4_store.audit_logs.clear()
    _bot.set_mode("OFF")
    app.config['TESTING'] = True
    return app.test_client()

ADMIN_H = {'Authorization': 'Bearer ' + 'a'*48}

def test_strategy_signal_generation():
    md = MarketDataManager()
    candles = md.generate_test_candles("BTCUSD", num_bars=60)
    strat = TrendFollowingMACrossoverStrategy()
    sig = strat.generate_signal("BTCUSD", candles)
    assert sig.symbol == "BTCUSD"
    assert sig.direction in ("BUY", "SELL", "FLAT")

def test_backtesting_and_monte_carlo():
    md = MarketDataManager()
    candles = md.generate_test_candles("BTCUSD", num_bars=100)
    strat = TrendFollowingMACrossoverStrategy()
    engine = BacktestEngine(10000.0)

    res = engine.run_backtest(strat, candles)
    assert res.total_trades >= 0
    assert res.net_return_pct is not None

    mc = engine.run_monte_carlo(res, iterations=20)
    assert mc["iterations"] == 20
    assert mc["status"] in ("PASS", "FAIL_HIGH_DRAWDOWN")

def test_paper_trading_engine():
    engine = PaperTradingEngine(10000.0)
    pos = engine.open_position("BTCUSD", "BUY", 0.1, 65000.0, 64000.0, 67000.0)
    assert len(engine.positions) == 1

    engine.update_market_price("BTCUSD", 67500.0)
    assert len(engine.positions) == 0
    assert len(engine.closed_trades) == 1
    assert engine.balance > 10000.0

def test_risk_guardian_limits():
    md = MarketDataManager()
    spec = md.get_spec("BTCUSD")
    rg = RiskGuardian(max_trade_risk_pct=0.5, max_daily_loss_pct=2.0, max_open_positions=2)
    valid_sig = Signal("BTCUSD", "BUY", 65000.0, 64000.0, 67000.0, "2026-11-01T00:00:00Z", "MA", "v5.1", 0.9, "Bullish")

    # Rejects when open positions limit reached
    res = rg.validate_trade_signal(valid_sig, 10000.0, 10000.0, open_positions_count=2, symbol_spec=spec)
    assert res.approved is False
    assert "MAX_OPEN_POSITIONS_REACHED" in res.reason_codes

def test_risk_guardian_min_lot_rejection():
    md = MarketDataManager()
    spec = md.get_spec("EURUSD")
    rg = RiskGuardian(max_trade_risk_pct=0.001)  # Extremely tiny risk allowance
    sig = Signal("EURUSD", "BUY", 1.0850, 1.0750, 1.1050, "2026-11-01T00:00:00Z", "MA", "v5.1", 0.9, "Bullish")

    res = rg.validate_trade_signal(sig, 1000.0, 1000.0, open_positions_count=0, symbol_spec=spec)
    assert res.approved is False
    assert any("MIN_LOT_EXCEEDS_RISK_LIMIT" in code for code in res.reason_codes)

def test_demo_adapter_safeguards():
    adapter = DemoMT5ExecutionAdapter()
    assert adapter.enabled is False

    with pytest.raises(PermissionError):
        adapter.execute_demo_order("order-1", "BTCUSD", "BUY", 0.1, 65000.0, 64000.0, 67000.0)

def test_bot_endpoints(client):
    res_status = client.get('/api/v5/bot/status', headers=ADMIN_H)
    assert res_status.status_code == 200
    assert res_status.json['mode'] == 'OFF'

    res_mode = client.post('/api/v5/bot/mode', json={'mode': 'PAPER'}, headers=ADMIN_H)
    assert res_mode.status_code == 200
    assert res_mode.json['mode'] == 'PAPER'

    res_tick = client.post('/api/v5/bot/tick', json={'price': 65000.0}, headers=ADMIN_H)
    assert res_tick.status_code == 200

    res_stop = client.post('/api/v5/bot/emergency-stop', headers=ADMIN_H)
    assert res_stop.status_code == 200
    assert res_stop.json['mode'] == 'OFF'
