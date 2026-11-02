"""Contract, loopback transport and auth tests. Lab runtime is mocked here;
verify_ai_connection.py separately runs the actual installed Python 3.12 Lab.
"""
from copy import deepcopy
import http.client
import json
from pathlib import Path
import socket
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai_contract import ContractError, health, strict_json, unavailable, validate, MAX_BYTES
from ai_lab_adapter import AILabAdapter
import ai_lab_service

LOCAL_TOKEN = "l"*48
ADMIN = {"Authorization": "Bearer " + "g"*48}


@pytest.fixture
def candidate():
    return {"schema_version": "1.0", "request_id": "MOCK_CONNECTION_ONLY",
        "instrument": {"symbol": "EXAMPLE_NOT_MARKET_DATA", "provider": "MOCK"},
        "prediction_timestamp_utc": "2025-01-01T00:00:00Z",
        "candidate": {"side": "BUY", "setup_id": "MOCK_NOT_A_TRADE", "entry_timeframe": "M15"},
        "timeframe_context": {"M15": {"last_closed_bar_time_utc": "2024-12-31T23:45:00Z", "features": {}}},
        "feature_set_version": "MOCK_UNTRAINED"}


@pytest.fixture
def local_server(monkeypatch):
    monkeypatch.setenv("SMARTHUB_API_TOKEN", "g"*48)
    monkeypatch.setenv("SMARTHUB_AI_LAB_TOKEN", LOCAL_TOKEN)
    monkeypatch.setattr(ai_lab_service, "load_lab_runtime", lambda _: validate)
    server = ai_lab_service.create_server("MOCK_ROOT", LOCAL_TOKEN, 0)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .02}, daemon=True)
    thread.start()
    url = "http://127.0.0.1:" + str(server.server_port)
    try:
        yield server, AILabAdapter(url, LOCAL_TOKEN)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_loopback_health_is_connected_but_not_trained(local_server):
    server, adapter = local_server
    assert server.server_address[0] == "127.0.0.1"
    status = adapter.status()
    assert status["connection_status"] == "CONNECTED"
    assert status["model_status"] == "MODEL_NOT_READY"
    assert status["probability"] is None and status["model_trained"] is False


def test_model_not_ready_is_a_real_contract_refusal(local_server, candidate):
    _, adapter = local_server
    response = adapter.advisory(candidate)
    validate("response", response)
    assert response["request_id"] == candidate["request_id"]
    assert response["status"] == "UNAVAILABLE"
    assert response["probability"] is None and response["model"] is None
    assert response["reasons"][0]["code"] == "MODEL_NOT_READY"


def test_service_rejects_missing_token_and_browser_origin(local_server):
    server, _ = local_server
    for headers, code in (({}, 401), ({"Authorization": "Bearer " + LOCAL_TOKEN, "Origin": "https://evil.invalid"}, 403)):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=1)
        conn.request("GET", "/v1/health", headers=headers)
        response = conn.getresponse()
        assert response.status == code
        response.read(); conn.close()


def test_service_rejects_malformed_and_unknown_fields(local_server, candidate):
    server, _ = local_server
    for raw in (b"{", b"null", b'{"schema_version":"2.0"}', json.dumps(dict(candidate, order_send=True)).encode()):
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=1)
        conn.request("POST", "/v1/predict", body=raw, headers={"Authorization": "Bearer "+LOCAL_TOKEN, "Content-Type": "application/json"})
        response = conn.getresponse()
        assert response.status == 400
        response.read(); conn.close()


@pytest.mark.parametrize("url", ["http://localhost:8765", "https://127.0.0.1:8765", "http://evil.invalid:8765",
    "http://127.0.0.1.evil.invalid:8765", "http://127.0.0.1:8765/path", "http://user:pass@127.0.0.1:8765",
    "http://127.0.0.1:8765?redirect=evil", "http://127.0.0.1:8765#fragment"])
def test_gateway_cannot_be_used_for_remote_urls_or_redirect_targets(monkeypatch, url):
    trap = Mock(side_effect=AssertionError("network must not be reached"))
    monkeypatch.setattr(http.client, "HTTPConnection", trap)
    assert AILabAdapter(url, LOCAL_TOKEN).status()["connection_status"] == "UNAVAILABLE"
    trap.assert_not_called()


def test_missing_or_shared_secret_fails_closed(monkeypatch):
    monkeypatch.setenv("SMARTHUB_API_TOKEN", LOCAL_TOKEN)
    assert AILabAdapter("http://127.0.0.1:8765", LOCAL_TOKEN).status()["reason_code"] == "SERVICE_NOT_CONFIGURED"
    with pytest.raises(ValueError):
        ai_lab_service.create_server("not-read", LOCAL_TOKEN, 0)
    monkeypatch.delenv("SMARTHUB_AI_LAB_TOKEN", raising=False)
    assert AILabAdapter().status()["connection_status"] == "UNAVAILABLE"


@pytest.mark.parametrize("failure,reason", [(ConnectionRefusedError("private marker"), "SERVICE_UNAVAILABLE"),
    (socket.timeout("private marker"), "SERVICE_TIMEOUT")])
def test_unavailable_and_timeout_are_contract_compliant_without_error_echo(monkeypatch, candidate, failure, reason):
    connection = Mock()
    connection.request.side_effect = failure
    monkeypatch.setattr(http.client, "HTTPConnection", Mock(return_value=connection))
    response = AILabAdapter("http://127.0.0.1:8765", LOCAL_TOKEN).advisory(candidate)
    assert response["reasons"][0]["code"] == reason
    assert response["probability"] is None
    assert "private marker" not in json.dumps(response)
    connection.close.assert_called_once()


def fake_transport(monkeypatch, payload, status=200, content_type="application/json"):
    response = SimpleNamespace(status=status, getheader=lambda *_: content_type, read=Mock(return_value=payload))
    connection = Mock()
    connection.getresponse.return_value = response
    monkeypatch.setattr(http.client, "HTTPConnection", Mock(return_value=connection))
    return connection, response


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(approve_trade=True), lambda r: r.update(lot_size=10),
    lambda r: r["validation"].update(risk_override=True), lambda r: r["reasons"][0].update(order_send=True),
    lambda r: r.update(schema_version="2.0"), lambda r: r.update(advisory_only=False),
    lambda r: r.update(request_id="OTHER_REQUEST"), lambda r: r.update(prediction_timestamp_utc="2024-01-01T00:00:00Z"),
])
def test_malicious_or_unbound_response_never_reaches_advisory(monkeypatch, candidate, mutate):
    result = unavailable(candidate)
    mutate(result)
    fake_transport(monkeypatch, json.dumps(result).encode())
    response = AILabAdapter("http://127.0.0.1:8765", LOCAL_TOKEN).advisory(candidate)
    assert response["reasons"][0]["code"] == "INVALID_SERVICE_RESPONSE"
    assert response["status"] == "UNAVAILABLE" and response["probability"] is None
    assert "lot_size" not in response and "approve_trade" not in response


def test_even_schema_valid_ok_is_blocked_without_an_approved_model(monkeypatch, candidate):
    result = unavailable(candidate)
    result.update(status="OK", probability=.9, model={"model_id": "MOCK_UNAPPROVED", "version": "1"},
                  validation={"status": "PASS", "checks": []}, reasons=[])
    validate("response", result)
    fake_transport(monkeypatch, json.dumps(result).encode())
    assert AILabAdapter("http://127.0.0.1:8765", LOCAL_TOKEN).advisory(candidate)["probability"] is None


@pytest.mark.parametrize("raw", [b"{", b"null", b"[]", b'{"probability":NaN}', b'{"key":1,"key":2}', b"x"*(MAX_BYTES+1)])
def test_malformed_nonfinite_duplicate_or_oversized_service_json_fails_closed(monkeypatch, candidate, raw):
    fake_transport(monkeypatch, raw)
    response = AILabAdapter("http://127.0.0.1:8765", LOCAL_TOKEN).advisory(candidate)
    assert response["reasons"][0]["code"] == "INVALID_SERVICE_RESPONSE"


def test_redirects_and_wrong_content_types_are_not_followed(monkeypatch, candidate):
    for status, media in ((302, "application/json"), (200, "text/html")):
        connection, result = fake_transport(monkeypatch, b"do not read", status, media)
        assert AILabAdapter("http://127.0.0.1:8765", LOCAL_TOKEN).advisory(candidate)["probability"] is None
        result.read.assert_not_called()
        assert connection.request.call_count == 1


def test_invalid_health_schema_and_mismatched_contract_hashes_are_not_connected(monkeypatch):
    for change in ({"model_ready": True}, {"schema_version": "2.0"}, {"risk_override": True}, {"contract_hashes": {}}):
        result = health();result.update(change)
        fake_transport(monkeypatch, json.dumps(result).encode())
        assert AILabAdapter("http://127.0.0.1:8765", LOCAL_TOKEN).status()["connection_status"] == "UNAVAILABLE"


@pytest.fixture
def gateway(monkeypatch, local_server):
    monkeypatch.delenv("SMARTHUB_STATE_DB", raising=False)
    monkeypatch.setenv("SMARTHUB_API_TOKEN", "g"*48)
    import app as module
    from v4_services import ContextStore
    from bot import BotController
    monkeypatch.setattr(module, "_v4_store", ContextStore())
    monkeypatch.setattr(module, "_bot", BotController())
    monkeypatch.setattr(module, "_ai_lab", local_server[1])
    module.app.config["TESTING"] = True
    return module, module.app.test_client()


def test_gateway_unauthorized_requests_do_not_contact_lab(gateway, monkeypatch, candidate):
    module, client = gateway
    trap = Mock(side_effect=AssertionError("unauthorized upstream request"))
    monkeypatch.setattr(module._ai_lab, "exchange", trap)
    assert client.get("/api/v5/ai/status").status_code == 401
    assert client.post("/api/v5/ai/advisory", json=candidate).status_code == 401
    trap.assert_not_called()


def test_monitoring_device_can_read_ai_without_any_trade_or_risk_side_effect(gateway, monkeypatch, candidate):
    module, client = gateway
    code = module._v4_store.generate_pairing_code()["pairing_code"]
    token = module._v4_store.enroll_device("dev-ai-monitor", "MOCK", code)["device_token"]
    headers = {"Authorization": "Bearer " + token}
    before = module._bot.get_status()
    risk = Mock(side_effect=AssertionError("AI must not call risk/size"))
    monkeypatch.setattr(module._bot.risk_guardian, "validate_trade_signal", risk)
    assert client.get("/api/v5/ai/status", headers=headers).json["connection_status"] == "CONNECTED"
    response = client.post("/api/v5/ai/advisory", json=candidate, headers=headers)
    validate("response", response.json)
    assert response.json["probability"] is None
    assert module._bot.get_status() == before
    risk.assert_not_called()
    assert client.post("/api/v5/bot/mode", json={"mode": "PAPER"}, headers=headers).status_code == 403


@pytest.mark.parametrize("body", [b"{", b"[]", b'{"schema_version":"2.0"}', b'{"foo":Infinity}'])
def test_gateway_malformed_advisory_is_not_forwarded(gateway, monkeypatch, body):
    module, client = gateway
    trap = Mock(side_effect=AssertionError("invalid input forwarded"))
    monkeypatch.setattr(module._ai_lab, "exchange", trap)
    assert client.post("/api/v5/ai/advisory", data=body, content_type="application/json", headers=ADMIN).status_code == 400
    trap.assert_not_called()


def test_gateway_service_outage_stays_advisory_unavailable(gateway, monkeypatch, candidate):
    module, client = gateway
    monkeypatch.setattr(http.client, "HTTPConnection", Mock(side_effect=ConnectionRefusedError("secret-marker")))
    status = client.get("/api/v5/ai/status", headers=ADMIN)
    assert status.status_code == 200 and status.json["connection_status"] == "UNAVAILABLE"
    response = client.post("/api/v5/ai/advisory", json=candidate, headers=ADMIN)
    assert response.status_code == 200 and response.json["status"] == "UNAVAILABLE"
    assert response.json["probability"] is None
    assert "secret-marker" not in response.get_data(as_text=True)


def test_impossible_calendar_date_is_rejected(candidate):
    candidate["prediction_timestamp_utc"] = "2025-02-30T00:00:00Z"
    with pytest.raises(ContractError):validate("request", candidate)


def test_real_slow_local_service_hits_the_exchange_deadline():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import time

    class Slow(BaseHTTPRequestHandler):
        def log_message(self, *_):pass
        def do_GET(self):
            time.sleep(.2)
            try:
                self.send_response(200);self.end_headers();self.wfile.write(b"{}")
            except OSError:
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Slow)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": .02}, daemon=True)
    thread.start()
    try:
        started = time.monotonic()
        result = AILabAdapter("http://127.0.0.1:"+str(server.server_port), LOCAL_TOKEN, timeout=.05).status()
        assert time.monotonic()-started < .5
        assert result["reason_code"] == "SERVICE_TIMEOUT"
        assert result["probability"] is None
    finally:
        server.shutdown();server.server_close();thread.join(timeout=1)
