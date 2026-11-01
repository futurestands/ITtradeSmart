import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from datetime import datetime, timezone
from bot import (
    MarketDataManager, TrendFollowingMACrossoverStrategy, BacktestEngine,
    PaperTradingEngine, RiskGuardian, DemoMT5ExecutionAdapter, BotController, Signal
)
from bot.market_data import AuthenticatedQuote, SymbolSpec, Candle

@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    monkeypatch.setenv('SMARTHUB_API_TOKEN', 'a'*48)
    monkeypatch.setenv('SMARTHUB_TELEMETRY_TOKEN', 'b'*48)

@pytest.fixture
def client():
    from app import app, _v4_store, _bot
    _v4_store.devices.clear()
    _v4_store.pairing_codes.clear()
    _v4_store.audit_logs.clear()
    _bot.set_mode("OFF")
    app.config['TESTING'] = True
    return app.test_client()

ADMIN_H = {'Authorization': 'Bearer ' + 'a'*48}

def test_ordinary_device_forbidden_from_v5_bot(client):
    res = client.post('/api/v4/admin/pairing-code', json={'ttl_minutes': 10}, headers=ADMIN_H)
    assert res.status_code == 200
    code = res.json['pairing_code']
    res2 = client.post('/api/v4/device/enroll', json={'device_id': 'device-pixel8-1234', 'device_name': 'Pixel 8', 'pairing_code': code})
    assert res2.status_code == 200
    token = res2.json['device_token']
    device_h = {'Authorization': 'Bearer ' + token}

    res_mode = client.post('/api/v5/bot/mode', json={'mode': 'PAPER'}, headers=device_h)
    assert res_mode.status_code == 403

    res_tick = client.post('/api/v5/bot/tick', headers=device_h)
    assert res_tick.status_code == 403

def test_risk_guardian_fails_closed_missing_terminal_calculations():
    md = MarketDataManager(symbol_specs={"BTCUSD": SymbolSpec("BTCUSD", 1.0, 1.0, 0.01, 1.0)})
    spec = md.get_spec("BTCUSD")
    rg = RiskGuardian()
    sig = Signal("BTCUSD", "BUY", 65000.0, 64000.0, 67000.0, datetime.now(timezone.utc).isoformat(), "MA", "v5.4", 0.9, "Bullish")

    # Without MT5 terminal and no gateway client, RiskGuardian must fail closed with FAIL_CLOSED_BROKER_CALCULATION_UNAVAILABLE
    res = rg.validate_trade_signal(sig, 10000.0, 10000.0, 10000.0, 0, spec, infrastructure_stress=10, mt5_gateway_client=None)
    assert res.approved is False
    assert "FAIL_CLOSED_BROKER_CALCULATION_UNAVAILABLE" in res.reason_codes

def test_risk_guardian_insufficient_margin():
    rg = RiskGuardian()
    spec = SymbolSpec("BTCUSD", 1.0, 1.0, 0.01, 1.0)
    sig = Signal("BTCUSD", "BUY", 65000.0, 64000.0, 67000.0, datetime.now(timezone.utc).isoformat(), "MA", "v5.4", 0.9, "Bullish")

    class MockGatewayClient:
        def calc_order(self, action, symbol, volume, entry, sl):
            return -100.0, 5000.0  # $5000 margin required per lot

    gateway = MockGatewayClient()
    # Free margin is only $1000, but margin required is $5000
    res = rg.validate_trade_signal(sig, 10000.0, 1000.0, 10000.0, 0, spec, infrastructure_stress=10, mt5_gateway_client=gateway)
    assert res.approved is False
    assert "INSUFFICIENT_FREE_MARGIN" in res.reason_codes

def test_authenticated_quote_provider():
    md = MarketDataManager()
    now_str = datetime.now(timezone.utc).isoformat()
    quote = AuthenticatedQuote("BTCUSD", 64995.0, 65005.0, now_str, "MT5_GATEWAY", 123456)

    md.ingest_authenticated_quote(quote)
    retrieved = md.get_authenticated_quote("BTCUSD")
    assert retrieved.bid == 64995.0
    assert retrieved.account_login == 123456

def test_fail_closed_market_data():
    md = MarketDataManager()
    with pytest.raises(RuntimeError, match="FATAL: Real MT5 market data unavailable"):
        md.fetch_real_mt5_candles("EURUSD", "H1", 50)
