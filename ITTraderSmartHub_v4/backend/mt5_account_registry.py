"""Local, read-only MT5 account registry for SmartHub device dashboards.

This registers account aliases only. A registered record is NOT a connected
terminal and cannot authorize broker operations. Never accept credentials,
account login numbers, terminal paths or arbitrary user-supplied file paths
via the registry or the Android interface.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

MAX_CONFIG_BYTES = 64 * 1024
MAX_ACCOUNTS = 20
_ID = re.compile(r"^[a-z][a-z0-9_-]{2,31}$")
_SYMBOL = re.compile(r"^[A-Za-z0-9._-]{2,32}$")
_PROVIDERS = {"FTMO", "FUNDEDNEXT", "OTHER"}
_KINDS = {"FREE_TRIAL", "DEMO", "EVALUATION", "FUNDED", "LIVE"}
_ENTRY_KEYS = {"id", "label", "provider", "account_kind", "symbol"}
_FLAG_FIELDS = {"password", "login", "token", "secret", "server", "path", "terminal"}


def _reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON keys")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("Nonfinite JSON values prohibited")


def _empty(status):
    return {
        "schema_version": 1,
        "status": status,
        "account_count": 0,
        "max_accounts": MAX_ACCOUNTS,
        "execution_authorized": False,
        "accounts": [],
    }


def read_mt5_accounts(config_path=None):
    """Return an allowlisted and sanitized *unconnected* account roster.

    Configuration path is controlled by Windows Gateway operator only.
    All entries must validate atomically; never echo invalid content to device.
    """
    raw_path = config_path if config_path is not None else os.environ.get("SMARTHUB_MT5_ACCOUNTS_FILE", "")
    if not isinstance(raw_path, (str, os.PathLike)) or not str(raw_path).strip():
        return _empty("NOT_CONFIGURED")
    try:
        file = Path(raw_path)
        if file.is_symlink() or not file.is_file():
            return _empty("INVALID_CONFIG")
        size = file.stat().st_size
        if size <= 0 or size > MAX_CONFIG_BYTES:
            return _empty("INVALID_CONFIG")
        raw = file.read_bytes()
        if len(raw) > MAX_CONFIG_BYTES:
            return _empty("INVALID_CONFIG")
        payload = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
        if type(payload) is not dict or set(payload) != {"schema_version", "accounts"}:
            return _empty("INVALID_CONFIG")
        if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
            return _empty("INVALID_CONFIG")
        items = payload["accounts"]
        if type(items) is not list or len(items) > MAX_ACCOUNTS:
            return _empty("INVALID_CONFIG")

        output = []
        ids = set()
        for item in items:
            if type(item) is not dict or set(item) != _ENTRY_KEYS:
                return _empty("INVALID_CONFIG")
            alias = item["id"]
            label = item["label"]
            provider = item["provider"]
            kind = item["account_kind"]
            symbol = item["symbol"]
            if (
                type(alias) is not str or _ID.fullmatch(alias) is None or alias in ids
                or type(label) is not str or not 1 <= len(label) <= 40
                or any(ord(c) < 32 or ord(c) > 126 for c in label)
                or type(provider) is not str or provider not in _PROVIDERS
                or type(kind) is not str or kind not in _KINDS
                or type(symbol) is not str or _SYMBOL.fullmatch(symbol) is None
            ):
                return _empty("INVALID_CONFIG")
            ids.add(alias)
            output.append({
                "id": alias,
                "label": label,
                "provider": provider,
                "account_kind": kind,
                "symbol": symbol,
                "connection_status": "NOT_CONNECTED",
                "read_only": True,
                "execution_authorized": False,
                "ea_execution_permitted": False if provider == "FUNDEDNEXT" and kind == "FREE_TRIAL" else None,
            })
        return {
            "schema_version": 1,
            "status": "REGISTRY_AVAILABLE",
            "account_count": len(output),
            "max_accounts": MAX_ACCOUNTS,
            "execution_authorized": False,
            "accounts": output,
        }
    except (OSError, ValueError, TypeError, UnicodeError, OverflowError):
        return _empty("INVALID_CONFIG")
