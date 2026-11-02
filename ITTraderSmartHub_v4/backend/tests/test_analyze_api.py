"""Flask regression tests; all MT5 dependencies/configuration are MOCK fixtures."""
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ADMIN = {"Authorization": "Bearer " + "c"*48}
SECRET = "MOCK_INVESTOR_PASSWORD_SENTINEL"


class FakeMT5:
    def __init__(self):
        self.account = SimpleNamespace(login=123456, server="MOCK-DEMO", trade_allowed=False, trade_expert=False)
        self.deals = ()
        self.calls = []
        self.initialize_result = True
        self.raise_on = None
        self.change_after_history = None

    def invoke(self, name):
        self.calls.append(name)
        if self.raise_on == name:
            raise RuntimeError(SECRET)

    def initialize(self, **kwargs):
        self.invoke("initialize")
        assert kwargs == dict(login=123456, password=SECRET, server="MOCK-DEMO")
        return self.initialize_result

    def account_info(self):
        self.invoke("account_info")
        return self.account

    def history_deals_get(self, start, end):
        self.invoke("history_deals_get")
        assert start.utcoffset().total_seconds() == end.utcoffset().total_seconds() == 0
        assert (end-start).days == 7
        if self.change_after_history:
            self.change_after_history(self.account)
        return self.deals

    def shutdown(self):
        self.invoke("shutdown")

    def order_send(self, *args, **kwargs):
        pytest.fail("MT5 order submission must never occur")


@pytest.fixture
def api(monkeypatch):
    monkeypatch.delenv("SMARTHUB_STATE_DB", raising=False)
    monkeypatch.setenv("SMARTHUB_API_TOKEN", "c"*48)
    monkeypatch.setenv("MT5_LOGIN", "123456")
    monkeypatch.setenv("MT5_INVESTOR_PASSWORD", SECRET)
    monkeypatch.setenv("MT5_SERVER", "MOCK-DEMO")
    fake = FakeMT5()
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    import app as module
    from v4_services import ContextStore
    monkeypatch.setattr(module, "_v4_store", ContextStore())
    module.app.config["TESTING"] = True
    return module.app.test_client(), fake, module


@pytest.mark.parametrize("body", ["{", "", "null", "[]", "[{}]", '"text"', "0", "false"])
def test_malformed_or_nonobject_json_rejected_before_mt5(api, body):
    client, fake, _ = api
    response = client.post("/analyze", data=body, content_type="application/json", headers=ADMIN)
    assert response.status_code == 400
    assert response.is_json
    assert fake.calls == []


def test_non_json_and_oversized_bodies_fail_safely(api):
    client, fake, _ = api
    assert client.post("/analyze", data="{}", content_type="text/plain", headers=ADMIN).status_code == 400
    response = client.post("/analyze", json={"password": SECRET*2000}, headers=ADMIN)
    assert response.status_code == 413
    assert SECRET not in response.get_data(as_text=True)
    assert fake.calls == []


def test_excessive_json_nesting_is_a_controlled_bad_request(api):
    client, fake, _ = api
    response = client.post("/analyze", data="["*2000+"0"+"]"*2000,
                           content_type="application/json", headers=ADMIN)
    assert response.status_code == 400
    assert response.is_json
    assert fake.calls == []


@pytest.mark.parametrize("body", [
    {"password": SECRET}, {"login": "MOCK"}, {"server": "MOCK"},
    {"PASSWORD": SECRET}, {"MT5_LOGIN": "MOCK"}, {"broker": {"password": SECRET}},
    {"options": [{"server": "MOCK"}]}, {"symbol": "USTECH100M"},
])
def test_no_request_credentials_aliases_or_broker_options_used_or_logged(api, caplog, body):
    client, fake, _ = api
    response = client.post("/analyze", json=body, headers=ADMIN)
    assert response.status_code == 400
    assert SECRET not in response.get_data(as_text=True) + caplog.text
    assert fake.calls == []


@pytest.mark.parametrize("name", ["MT5_LOGIN", "MT5_INVESTOR_PASSWORD", "MT5_SERVER"])
def test_missing_host_configuration(api, monkeypatch, name):
    client, fake, _ = api
    monkeypatch.delenv(name)
    response = client.post("/analyze", json={}, headers=ADMIN)
    assert response.status_code == 503
    assert response.json["error"] == "MT5 not configured on gateway host"
    assert fake.calls == []


@pytest.mark.parametrize("name,value", [("MT5_LOGIN", "-1"), ("MT5_LOGIN", "0"),
    ("MT5_LOGIN", "invalid"), ("MT5_SERVER", "  "), ("MT5_INVESTOR_PASSWORD", "")])
def test_invalid_host_configuration(api, monkeypatch, name, value):
    client, fake, _ = api
    monkeypatch.setenv(name, value)
    assert client.post("/analyze", json={}, headers=ADMIN).status_code == 503
    assert fake.calls == []


def test_unavailable_mt5_library(api, monkeypatch):
    client, fake, _ = api
    monkeypatch.setitem(sys.modules, "MetaTrader5", None)
    response = client.post("/analyze", json={}, headers=ADMIN)
    assert response.status_code == 503
    assert "library unavailable" in response.json["error"]
    assert fake.calls == []


def test_native_library_load_failure_is_sanitized(api, monkeypatch, caplog):
    import builtins
    client, fake, _ = api
    original_import = builtins.__import__

    def fail_native_import(name, *args, **kwargs):
        if name == "MetaTrader5":
            raise OSError(SECRET)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fail_native_import)
    response = client.post("/analyze", json={}, headers=ADMIN)
    assert response.status_code == 503
    assert SECRET not in response.get_data(as_text=True) + caplog.text
    assert fake.calls == []


def test_initialization_failure_does_not_fetch_history(api):
    client, fake, _ = api
    fake.initialize_result = False
    assert client.post("/analyze", json={}, headers=ADMIN).status_code == 503
    assert fake.calls == ["initialize"]


def test_missing_account_state_is_unavailable_and_shuts_down(api):
    client, fake, _ = api
    fake.account = None
    assert client.post("/analyze", json={}, headers=ADMIN).status_code == 503
    assert fake.calls == ["initialize", "account_info", "shutdown"]


@pytest.mark.parametrize("allowed,expert", [(True, False), (False, True), (True, True),
                                         (None, False), (False, None), (0, 0), ("false", False)])
def test_read_only_permissions_must_be_explicit_false_booleans(api, allowed, expert):
    client, fake, _ = api
    fake.account.trade_allowed, fake.account.trade_expert = allowed, expert
    response = client.post("/analyze", json={}, headers=ADMIN)
    assert response.status_code == 403
    assert "read-only investor" in response.json["error"]
    assert fake.calls == ["initialize", "account_info", "shutdown"]


def test_missing_permission_fields_are_not_treated_as_read_only(api):
    client, fake, _ = api
    del fake.account.trade_allowed
    assert client.post("/analyze", json={}, headers=ADMIN).status_code == 403
    assert "history_deals_get" not in fake.calls
    assert fake.calls[-1] == "shutdown"


@pytest.mark.parametrize("field,value", [("login", 999999), ("server", "OTHER-MOCK"), ("login", None), ("login", 123456.0)])
def test_unexpected_account_identity_rejected_without_exposure(api, field, value):
    client, fake, _ = api
    setattr(fake.account, field, value)
    response = client.post("/analyze", json={}, headers=ADMIN)
    assert response.status_code == 403
    assert response.json["error"] == "Unexpected broker account identity"
    assert fake.calls == ["initialize", "account_info", "shutdown"]


def test_history_unavailable_is_not_a_successful_empty_history(api):
    client, fake, _ = api
    fake.deals = None
    assert client.post("/analyze", json={}, headers=ADMIN).status_code == 503
    assert fake.calls[-1] == "shutdown"


@pytest.mark.parametrize("stage", ["initialize", "account_info", "history_deals_get", "shutdown"])
def test_provider_exceptions_never_echo_or_log_credentials(api, caplog, stage):
    client, fake, _ = api
    fake.raise_on = stage
    response = client.post("/analyze", json={}, headers=ADMIN)
    assert response.status_code == 503
    assert SECRET not in response.get_data(as_text=True) + caplog.text
    assert "Traceback" not in caplog.text
    if stage != "initialize":
        assert fake.calls[-1] == "shutdown"


def test_read_only_success_is_heuristics_and_does_not_certify_timebase(api):
    client, fake, _ = api
    response = client.post("/analyze", json={}, headers=ADMIN)
    assert response.status_code == 200
    assert response.json["total_deals_analyzed"] == 0
    assert response.json["analysis_type"] == "DEAL_HEURISTICS"
    assert response.json["timebase_status"] == "TIMEBASE_UNVERIFIED"
    assert fake.calls == ["initialize", "account_info", "history_deals_get", "account_info", "shutdown"]


@pytest.mark.parametrize("field,value", [("login", 999999), ("server", "OTHER-MOCK"), ("trade_allowed", True)])
def test_account_change_during_history_is_rejected_before_results_are_exposed(api, field, value):
    client, fake, _ = api
    fake.change_after_history = lambda account: setattr(account, field, value)
    response = client.post("/analyze", json={}, headers=ADMIN)
    assert response.status_code == 403
    assert "total_deals_analyzed" not in response.json
    assert fake.calls[-1] == "shutdown"


def test_authentication_still_precedes_request_and_broker_handling(api):
    client, fake, _ = api
    response = client.post("/analyze", json={"password": SECRET})
    assert response.status_code == 401
    assert fake.calls == []


def test_enrolled_monitoring_device_retains_read_only_analysis_access(api):
    client, fake, module = api
    code = module._v4_store.generate_pairing_code()["pairing_code"]
    token = module._v4_store.enroll_device("dev-mock-monitor", "MOCK device", code)["device_token"]
    response = client.post("/analyze", json={}, headers={"Authorization": "Bearer " + token})
    assert response.status_code == 200
    assert fake.calls[-1] == "shutdown"
