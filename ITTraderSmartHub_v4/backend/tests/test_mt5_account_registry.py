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
