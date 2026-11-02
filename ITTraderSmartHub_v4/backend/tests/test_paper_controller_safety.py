"""The controller is quarantined, not an implemented PAPER simulator."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bot.bot_controller import BotController, BotMode, PaperSafetyError, PAPER_BLOCKERS
from bot.market_data import AuthenticatedQuote, SymbolSpec


@pytest.fixture
def controller(monkeypatch):
    monkeypatch.delenv("SMARTHUB_STATE_DB", raising=False)
    return BotController()


def poison_cycle_dependencies(controller):
    """Any path to broker data, strategy, risk, legacy P&L or writes must fail."""
    mocks = []
    for owner, methods in (
        (controller.market_data, ("get_authenticated_quote", "get_spec", "fetch_real_mt5_candles")),
        (controller.strategy, ("generate_signal",)),
        (controller.risk_guardian, ("validate_trade_signal",)),
        (controller.journal, ("record_signal", "record_decision")),
    ):
        for method in methods:
            trap = Mock(side_effect=AssertionError("unsafe dependency reached"))
            setattr(owner, method, trap)
            mocks.append(trap)
    controller.paper_engine = SimpleNamespace(
        open_position=Mock(side_effect=AssertionError("unsafe paper entry")),
        update_market_price=Mock(side_effect=AssertionError("legacy paper valuation")),
        close_position=Mock(side_effect=AssertionError("unsafe paper close")))
    mocks.extend((controller.paper_engine.open_position, controller.paper_engine.update_market_price,
                  controller.paper_engine.close_position))
    controller.demo_adapter.execute_demo_order = Mock(side_effect=AssertionError("unsafe demo route"))
    mocks.append(controller.demo_adapter.execute_demo_order)
    return mocks


def test_status_does_not_invent_an_instrument_or_account(controller):
    status = controller.get_status()
    assert controller.active_symbol is None
    assert controller.paper_engine is None
    assert status["mode"] == "OFF"
    assert status["paper_trading"]["status"] == "BLOCKED_INTEGRATION_UNVERIFIED"
    assert status["paper_trading"]["eligible"] is False
    assert set(status["paper_trading"]["blockers"]) == set(PAPER_BLOCKERS)
    for key in ("balance", "equity", "open_positions_count", "closed_trades_count", "total_pnl"):
        assert status["paper_trading"][key] is None


def test_paper_request_fails_closed_and_keeps_off(controller):
    mocks = poison_cycle_dependencies(controller)
    with pytest.raises(PaperSafetyError, match="PAPER_BLOCKED"):
        controller.set_mode("PAPER")
    assert controller.mode == BotMode.OFF
    assert controller.demo_adapter.enabled is False
    assert all(not mock.called for mock in mocks)


@pytest.mark.parametrize("missing", ["symbol", "economics", "account", "free_margin", "daily_baseline",
                                    "quote", "candles", "timebase", "risk_adapter", "persistence"])
def test_unavailable_required_inputs_cannot_open_paper_positions(controller, missing):
    mocks = poison_cycle_dependencies(controller)
    # Deliberately untrusted fixtures: presence alone never establishes authority.
    inputs = {name: object() for name in ("symbol", "economics", "account", "free_margin", "daily_baseline",
              "quote", "candles", "timebase", "risk_adapter", "persistence")}
    inputs[missing] = None
    controller.unverified_inputs = inputs
    controller.mode = BotMode.PAPER
    with pytest.raises(PaperSafetyError, match="TRADING_CYCLE_BLOCKED"):
        controller.tick(None)
    assert controller.mode == BotMode.OFF
    assert all(not mock.called for mock in mocks)


def test_incorrect_exact_instrument_identity_cannot_reach_legacy_engine(controller):
    controller.active_symbol = "USTECH100M"
    controller.market_data.injected_specs["USTECH100M"] = SymbolSpec("EURUSD", 100000, .0001, .00001, 1)
    controller.market_data.last_quotes["USTECH100M"] = AuthenticatedQuote(
        "EURUSD", 1.1, 1.1001, "2025-01-01T00:00:00Z", "MOCK", 1)
    mocks = poison_cycle_dependencies(controller)
    controller.mode = BotMode.PAPER
    with pytest.raises(PaperSafetyError):
        controller.tick(0)
    assert all(not mock.called for mock in mocks)


def test_approved_looking_mock_risk_or_mutable_flags_do_not_unlock_paper(controller):
    mocks = poison_cycle_dependencies(controller)
    controller.risk_guardian.validate_trade_signal.side_effect = None
    controller.risk_guardian.validate_trade_signal.return_value = SimpleNamespace(approved=True, allocated_lots=1)
    controller.verified_equity = 99999  # fixture values must never become authoritative
    controller.paper_enabled = True
    controller.mode = BotMode.PAPER
    with pytest.raises(PaperSafetyError):
        controller.tick(0)
    assert all(not mock.called for mock in mocks)


@pytest.mark.parametrize("mode", [BotMode.PAPER, BotMode.DEMO, BotMode.BACKTEST])
def test_forced_modes_cannot_execute_a_trading_cycle(controller, mode):
    mocks = poison_cycle_dependencies(controller)
    controller.mode = mode
    controller.demo_adapter.enabled = True
    with pytest.raises(PaperSafetyError):
        controller.tick(0)
    assert controller.mode == BotMode.OFF
    assert controller.demo_adapter.enabled is False
    assert all(not mock.called for mock in mocks)


def test_demo_mode_denied_even_if_enable_method_were_to_claim_success(controller):
    controller.demo_adapter.enable_demo_mode = Mock(return_value=True)
    with pytest.raises(PermissionError, match="RESEARCH_ONLY_EXECUTION_LOCK"):
        controller.set_mode("DEMO", "MOCK_ADMIN")
    controller.demo_adapter.enable_demo_mode.assert_not_called()
    assert controller.mode == BotMode.OFF


def test_off_and_emergency_stop_remain_available(controller):
    assert controller.tick()["mode"] == "OFF"
    controller.mode = BotMode.PAPER
    status = controller.emergency_stop()
    assert status["mode"] == "OFF"
    assert status["emergency_stopped"] is True
    assert status["paper_trading"]["eligible"] is False
    assert controller.set_mode("OFF")["emergency_stopped"] is True


def test_paper_rejection_does_not_modify_existing_paper_database(tmp_path, monkeypatch):
    import sqlite3
    monkeypatch.delenv("SMARTHUB_STATE_DB", raising=False)
    path = tmp_path/"existing.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE paper_positions (sentinel TEXT)")
        db.execute("INSERT INTO paper_positions VALUES ('existing MOCK record')")
    restarted = BotController(str(path))
    with pytest.raises(PaperSafetyError):
        restarted.set_mode("PAPER")
    assert restarted.paper_engine is None
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT sentinel FROM paper_positions").fetchall() == [("existing MOCK record",)]


@pytest.fixture
def api(monkeypatch, controller):
    monkeypatch.setenv("SMARTHUB_API_TOKEN", "p"*48)
    import app as module
    from v4_services import ContextStore
    monkeypatch.setattr(module, "_bot", controller)
    monkeypatch.setattr(module, "_v4_store", ContextStore())
    module.app.config["TESTING"] = True
    return module.app.test_client(), {"Authorization": "Bearer " + "p"*48}


def test_admin_paper_request_gets_explicit_503_off_state(api, controller):
    client, headers = api
    response = client.post("/api/v5/bot/mode", json={"mode": "PAPER"}, headers=headers)
    assert response.status_code == 503
    assert response.json["bot_status"]["mode"] == "OFF"
    assert response.json["bot_status"]["paper_trading"]["eligible"] is False
    assert client.post("/api/v5/bot/tick", headers=headers).json["mode"] == "OFF"


def test_forced_unsafe_cycle_has_controlled_503_not_attribute_error(api, controller):
    client, headers = api
    controller.mode = BotMode.PAPER
    response = client.post("/api/v5/bot/tick", headers=headers)
    assert response.status_code == 503
    assert "TRADING_CYCLE_BLOCKED" in response.json["error"]
    assert controller.mode == BotMode.OFF


@pytest.mark.parametrize("body", [[], None, {"mode": 123}])
def test_invalid_mode_request_fails_safely(api, body):
    import json
    client, headers = api
    response = client.post("/api/v5/bot/mode", data=json.dumps(body), content_type="application/json", headers=headers)
    assert response.status_code == 400


def test_existing_authentication_and_device_role_cannot_enable_paper_or_stop_bot(api):
    client, _ = api
    assert client.post("/api/v5/bot/mode", json={"mode": "PAPER"}).status_code == 401
    from app import _v4_store
    code = _v4_store.generate_pairing_code()["pairing_code"]
    token = _v4_store.enroll_device("dev-mock-controller", "MOCK monitor", code)["device_token"]
    headers = {"Authorization": "Bearer " + token}
    for url in ("mode", "tick", "emergency-stop"):
        assert client.post("/api/v5/bot/"+url, json={"mode": "PAPER"}, headers=headers).status_code == 403
