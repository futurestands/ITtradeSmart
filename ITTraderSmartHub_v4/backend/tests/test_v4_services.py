import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v4_services import ContextStore, risk_context, research_request
import pytest

def test_missing_telemetry_fails_closed():
    r = risk_context({'schema_version': 1, 'baseline_risk_pct': 1, 'symbol': 'EURUSD'}, ContextStore())
    assert r['effective_risk_pct'] is None and r['status'] == 'UNAVAILABLE'

def test_infrastructure_ceiling_not_trade_permission():
    s = ContextStore(); s.set_stress(100, 'authorized_telemetry_agent')
    r = risk_context({'schema_version': 1, 'baseline_risk_pct': 2, 'symbol': 'EURUSD'}, s)
    assert r['infrastructure_risk_ceiling_pct'] == 1 and r['effective_risk_pct'] is None

def test_client_cannot_supply_stress():
    with pytest.raises(ValueError):
        ContextStore().set_stress(40, 'mobile')

def test_alert_cursor():
    s = ContextStore(); s.set_stress(80, 'authorized_telemetry_agent'); s.set_stress(40, 'authorized_telemetry_agent')
    r = s.query_alerts('evt-1')
    assert len(r['alerts']) == 1 and r['next_cursor'] == 'evt-2'

def test_device_enrollment_and_verification(monkeypatch):
    monkeypatch.setenv('SMARTHUB_API_TOKEN', 'a'*48)
    store = ContextStore()
    enroll = store.enroll_device('dev-12345678', 'Tablet', 'a'*48)
    token = enroll['device_token']
    assert store.verify_token(token) is True

    # Revoke
    store.revoke_device('dev-12345678')
    assert store.verify_token(token) is False

def test_persistence_survives_restart(tmp_path, monkeypatch):
    monkeypatch.setenv('SMARTHUB_API_TOKEN', 'a'*48)
    from v4_services import ContextStore
    path = str(tmp_path / "events.sqlite3")
    a = ContextStore(path)
    a.set_stress(67, "authorized_telemetry_agent")
    dev = a.enroll_device("dev-77777777", "Phone", 'a'*48)

    b = ContextStore(path)
    assert b.get_stress()["value"] == 67
    assert len(b.query_alerts()["alerts"]) == 1
    assert b.verify_token(dev["device_token"]) is True

def test_stale_telemetry_not_used_for_risk():
    from v4_services import ContextStore, risk_context
    store = ContextStore()
    store.set_stress(70, "authorized_telemetry_agent")
    store.stress["recorded_at"] = "2020-01-01T00:00:00+00:00"
    decision = risk_context({"schema_version": 1, "baseline_risk_pct": 1.0, "symbol": "EURUSD"}, store)
    assert decision["status"] == "UNAVAILABLE"
    assert "SERVER_TELEMETRY_STALE" in decision["reason_codes"]
    assert decision["infrastructure_risk_ceiling_pct"] is None
