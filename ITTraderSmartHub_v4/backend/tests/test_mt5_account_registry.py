"""Multi-account registration: fail-closed, read-only, no broker credentials."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mt5_account_registry import read_mt5_accounts, MAX_ACCOUNTS


def account(alias="ftmo-trial", provider="FTMO", kind="FREE_TRIAL"):
    return {
        "id": alias,
        "label": alias.replace("-", " ").title(),
        "provider": provider,
        "account_kind": kind,
        "symbol": "US100.cash",
    }


def registry(tmp_path, records=None):
    path = tmp_path / "local-mt5-accounts.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "accounts": records if records is not None else [
            account(),
            account("fundednext-trial", "FUNDEDNEXT"),
            account("demo-three", "OTHER", "DEMO"),
        ],
    }), encoding="utf-8")
    return path


def test_unconfigured_or_missing_accounts_fail_closed(tmp_path):
    assert read_mt5_accounts("")["status"] == "NOT_CONFIGURED"
    assert read_mt5_accounts(tmp_path / "missing.json")["status"] == "INVALID_CONFIG"


def test_three_independent_account_aliases_without_connection_or_credentials(tmp_path):
    result = read_mt5_accounts(registry(tmp_path))
    assert result["status"] == "REGISTRY_AVAILABLE"
    assert result["account_count"] == 3
    assert result["max_accounts"] == 20
    assert result["execution_authorized"] is False
    assert all(a["connection_status"] == "NOT_CONNECTED" for a in result["accounts"])
    assert all(a["read_only"] is True and a["execution_authorized"] is False for a in result["accounts"])
    assert result["accounts"][1]["ea_execution_permitted"] is False
    assert result["accounts"][0]["ea_execution_permitted"] is None
    rendered = json.dumps(result).lower()
    for sensitive in ("password", "login", "token", "terminal_path", "investor"):
        assert sensitive not in rendered


@pytest.mark.parametrize("records", [
    [account("same"), account("same")],
    [account() for _ in range(MAX_ACCOUNTS + 1)],
    [{**account(), "password": "secret"}],
    [{**account(), "login": 123456}],
    [{**account(), "server": "real-broker-server"}],
    [{**account(), "terminal": r"C:\terminal64.exe"}],
    [{**account(), "label": "Sensitive\nLog"}],
    [{**account(), "id": "../escape"}],
    [{**account(), "provider": "UNKNOWN"}],
    [{**account(), "account_kind": "UNKNOWN"}],
    [{**account(), "symbol": "../../private"}],
])
def test_reject_unsafe_or_oversized_roster_atomically(tmp_path, records):
    path = registry(tmp_path, records)
    result = read_mt5_accounts(path)
    assert result["status"] == "INVALID_CONFIG"
    assert result["account_count"] == 0
    assert result["accounts"] == []


@pytest.mark.parametrize("raw", [
    b'{"schema_version":1,"accounts":[],"accounts":[]}',
    b'{"schema_version":1,"accounts":NaN}',
    b'{"schema_version":true,"accounts":[]}',
    b'{"schema_version":1,"accounts":[],"trading_enabled":true}',
    b'{"schema_version":1,"accounts":[]}' + b" " * (65536 + 1),
    b"\xff\xfe",
])
def test_malformed_registry_documents_rejected(tmp_path, raw):
    path = tmp_path / "invalid.json"
    path.write_bytes(raw)
    assert read_mt5_accounts(path)["status"] == "INVALID_CONFIG"


def test_symlink_not_accepted(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("Filesystem symlinks unsupported")
    real = registry(tmp_path)
    link = tmp_path / "linked.json"
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("Symlink unavailable on this Windows installation")
    assert read_mt5_accounts(link)["status"] == "INVALID_CONFIG"


def test_device_authenticated_route_does_not_enable_bots(monkeypatch, tmp_path):
    monkeypatch.setenv("SMARTHUB_MT5_ACCOUNTS_FILE", str(registry(tmp_path)))
    monkeypatch.delenv("SMARTHUB_STATE_DB", raising=False)
    import app as gateway
    from v4_services import ContextStore
    from bot import BotController

    monkeypatch.setattr(gateway, "_v4_store", ContextStore())
    monkeypatch.setattr(gateway, "_bot", BotController())
    gateway.app.config["TESTING"] = True
    client = gateway.app.test_client()
    assert client.get("/api/v5/mt5/accounts").status_code == 401
    pairing = gateway._v4_store.generate_pairing_code()["pairing_code"]
    token = gateway._v4_store.enroll_device("multi-account-android-test", "TEST", pairing)["device_token"]
    headers = {"Authorization": "Bearer " + token}
    state_before = gateway._bot.get_status()
    result = client.get("/api/v5/mt5/accounts", headers=headers)
    assert result.status_code == 200
    assert result.json["account_count"] == 3
    assert result.json["execution_authorized"] is False
    assert "no-store" in result.headers["Cache-Control"]
    assert gateway._bot.get_status() == state_before
    assert client.post("/api/v5/bot/mode", headers=headers, json={"mode": "DEMO"}).status_code == 403



def test_gateway_write_requires_opt_in_and_enrolled_device(monkeypatch, tmp_path):
    monkeypatch.setenv("SMARTHUB_MT5_ACCOUNTS_FILE", str(tmp_path / "mt5_accounts.local.json"))
    monkeypatch.delenv("SMARTHUB_ACCOUNT_PROFILE_EDITING", raising=False)
    monkeypatch.delenv("SMARTHUB_STATE_DB", raising=False)
    import app as gateway
    from v4_services import ContextStore
    from bot import BotController
    monkeypatch.setattr(gateway, "_v4_store", ContextStore())
    monkeypatch.setattr(gateway, "_bot", BotController())
    gateway.app.config["TESTING"] = True
    client = gateway.app.test_client()
    body = account()
    assert client.post("/api/v5/mt5/accounts", json=body).status_code == 401
    code = gateway._v4_store.generate_pairing_code()["pairing_code"]
    token = gateway._v4_store.enroll_device("broker-profile-test-device", "TEST", code)["device_token"]
    headers = {"Authorization": "Bearer " + token}
    assert client.post("/api/v5/mt5/accounts", json=body, headers=headers).status_code == 403
    assert not (tmp_path / "mt5_accounts.local.json").exists()
    monkeypatch.setenv("SMARTHUB_ACCOUNT_PROFILE_EDITING", "1")
    assert client.post("/api/v5/mt5/accounts", json=body).status_code == 401

    state_before = gateway._bot.get_status()
    result = client.post("/api/v5/mt5/accounts", json=body, headers=headers)
    assert result.status_code == 200
    assert result.json["account_count"] == 1
    assert result.json["accounts"][0]["connection_status"] == "NOT_CONNECTED"
    assert result.json["accounts"][0]["execution_authorized"] is False
    assert "no-store" in result.headers["Cache-Control"]
    assert gateway._bot.get_status() == state_before
    assert client.post("/api/v5/bot/mode", headers=headers, json={"mode": "PAPER"}).status_code == 403


def test_profile_add_edit_delete_atomic_and_persistent(monkeypatch, tmp_path):
    from mt5_account_registry import upsert_mt5_profile, delete_mt5_profile
    path = tmp_path / "mt5_accounts.local.json"
    monkeypatch.setenv("SMARTHUB_MT5_ACCOUNTS_FILE", str(path))
    assert upsert_mt5_profile(account("ftmo-trial"))["account_count"] == 1
    assert upsert_mt5_profile(account("fundednext-trial", "FUNDEDNEXT"))["account_count"] == 2
    assert upsert_mt5_profile(account("third-demo", "OTHER", "DEMO"))["account_count"] == 3
    changed = account("ftmo-trial")
    changed["symbol"] = "US100"
    assert upsert_mt5_profile(changed)["account_count"] == 3
    reread = read_mt5_accounts(path)
    assert reread["accounts"][0]["symbol"] == "US100"
    assert reread["accounts"][0]["read_only"] is True
    assert delete_mt5_profile("third-demo")["account_count"] == 2
    assert read_mt5_accounts(path)["account_count"] == 2
    assert not list(tmp_path.glob(".mt5-accounts-*.tmp"))


@pytest.mark.parametrize("extra", [
    {"login": 12345678}, {"password": "demo-secret"},
    {"terminal_path": r"C:\MT5\terminal64.exe"},
    {"allow_trades": True}, {"stop_loss": 100.0},
    {"server": "broker-live"}, {"api_token": "in-app-secret"},
])
def test_in_app_profile_rejects_operational_and_credential_fields(tmp_path, monkeypatch, extra):
    from mt5_account_registry import upsert_mt5_profile, ProfileConfigError
    path = tmp_path / "mt5_accounts.local.json"
    monkeypatch.setenv("SMARTHUB_MT5_ACCOUNTS_FILE", str(path))
    with pytest.raises(ProfileConfigError):
        upsert_mt5_profile({**account(), **extra})
    assert not path.exists()


def test_corrupt_file_cannot_be_overwritten_by_apk(monkeypatch, tmp_path):
    from mt5_account_registry import upsert_mt5_profile, ProfileConfigError
    path = tmp_path / "mt5_accounts.local.json"
    path.write_text('{"schema_version":1,"accounts":[],"accounts":[]}', encoding="utf-8")
    monkeypatch.setenv("SMARTHUB_MT5_ACCOUNTS_FILE", str(path))
    with pytest.raises(ProfileConfigError):
        upsert_mt5_profile(account())
    assert "accounts\":[]" in path.read_text(encoding="utf-8")


def test_admin_opt_in_still_restricts_to_loopback(monkeypatch, tmp_path):
    monkeypatch.setenv("SMARTHUB_MT5_ACCOUNTS_FILE", str(tmp_path / "mt5_accounts.local.json"))
    monkeypatch.setenv("SMARTHUB_ACCOUNT_PROFILE_EDITING", "1")
    import app as gateway
    from v4_services import ContextStore
    monkeypatch.setattr(gateway, "_v4_store", ContextStore())
    gateway.app.config["TESTING"] = True
    client = gateway.app.test_client()
    code = gateway._v4_store.generate_pairing_code()["pairing_code"]
    token = gateway._v4_store.enroll_device("profile-nonloopback-device", "TEST", code)["device_token"]
    res = client.post("/api/v5/mt5/accounts",
        headers={"Authorization": "Bearer " + token}, json=account(),
        environ_overrides={"REMOTE_ADDR": "192.0.2.8"})
    assert res.status_code == 403
