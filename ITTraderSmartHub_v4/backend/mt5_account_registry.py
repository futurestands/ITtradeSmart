"""Credential-free MT5 account profiles for SmartHub device dashboards.

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
import tempfile
from threading import RLock

MAX_CONFIG_BYTES = 64 * 1024
MAX_ACCOUNTS = 20
_ID = re.compile(r"^[a-z][a-z0-9_-]{2,31}$")
_SYMBOL = re.compile(r"^[A-Za-z0-9._-]{2,32}$")
_BROKER = re.compile(r"^[A-Z][A-Z0-9 ._-]{1,39}$")
_KINDS = {"FREE_TRIAL", "DEMO", "EVALUATION", "FUNDED", "LIVE"}
_ENTRY_KEYS = {"id", "label", "provider", "account_kind", "symbol"}
_WRITE_LOCK = RLock()



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
    # Default is an ignored file next to this module. The Gateway can see a
    # newly created roster on the next GET, without restarting and losing its
    # already paired in-memory device session.
    if config_path is not None:
        raw_path = config_path
    else:
        raw_path = os.environ.get("SMARTHUB_MT5_ACCOUNTS_FILE", "").strip()
        if not raw_path:
            local = Path(__file__).with_name("mt5_accounts.local.json")
            if not local.exists() and not local.is_symlink():
                return _empty("NOT_CONFIGURED")
            raw_path = local
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
                or type(provider) is not str or _BROKER.fullmatch(provider) is None
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


class ProfileConfigError(ValueError):
    """Intentionally generic so rejected profile inputs are never echoed."""


def _profile_path():
    """Gateway-controlled path; caller can never provide a path or terminal ID."""
    selected = os.environ.get("SMARTHUB_MT5_ACCOUNTS_FILE", "").strip()
    return Path(selected) if selected else Path(__file__).with_name("mt5_accounts.local.json")


def _validate_profile(profile):
    """No account number, login/server, broker credentials, or execution settings."""
    if type(profile) is not dict or set(profile) != _ENTRY_KEYS:
        raise ProfileConfigError("Only alias, label, provider, account type and symbol are allowed")
    alias, label, provider, kind, symbol = (profile[k] for k in
        ("id", "label", "provider", "account_kind", "symbol"))
    if type(provider) is str:
        provider = provider.upper()
    if (
        type(alias) is not str or _ID.fullmatch(alias) is None
        or type(label) is not str or not 1 <= len(label) <= 40
        or any(ord(c) < 32 or ord(c) > 126 for c in label)
        or type(provider) is not str or provider not in _PROVIDERS
        or type(kind) is not str or kind not in _KINDS
        or type(symbol) is not str or _SYMBOL.fullmatch(symbol) is None
    ):
        raise ProfileConfigError("Invalid broker profile format")
    clean = {key: profile[key] for key in ("id", "label", "provider", "account_kind", "symbol")}
    clean["provider"] = clean["provider"].upper()
    return clean


def _read_entries_for_mutation(path):
    if path.is_symlink() or path.parent.is_symlink() or not path.parent.is_dir():
        raise ProfileConfigError("Account profile location is unavailable")
    # Never overwrite a malformed or inaccessible existing file.
    if path.exists():
        source = read_mt5_accounts(path)
        if source["status"] != "REGISTRY_AVAILABLE":
            raise ProfileConfigError("Existing account profiles failed validation")
        return [
            {key: entry[key] for key in ("id", "label", "provider", "account_kind", "symbol")}
            for entry in source["accounts"]
        ]
    return []


def _write_entries(path, entries):
    if path.is_symlink() or path.parent.is_symlink() or not path.parent.is_dir():
        raise ProfileConfigError("Account profile location is unavailable")
    if len(entries) > MAX_ACCOUNTS:
        raise ProfileConfigError("Maximum 20 broker profiles")
    payload = json.dumps(
        {"schema_version": 1, "accounts": entries},
        indent=2, ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    if len(payload) > MAX_CONFIG_BYTES:
        raise ProfileConfigError("Broker profile registry is too large")
    fd, temp_path = tempfile.mkstemp(prefix=".mt5-accounts-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # Prevent symlink replacement at the destination.
        if path.is_symlink():
            raise ProfileConfigError("Unsafe broker registry file")
        os.replace(temp_path, path)
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass


def upsert_mt5_profile(profile):
    """Add or update an alias only; does not initialize MT5 or activate trades."""
    clean = _validate_profile(profile)
    with _WRITE_LOCK:
        path = _profile_path()
        entries = _read_entries_for_mutation(path)
        for i, entry in enumerate(entries):
            if entry["id"] == clean["id"]:
                entries[i] = clean
                break
        else:
            entries.append(clean)
        _write_entries(path, entries)
        return read_mt5_accounts(path)


def delete_mt5_profile(account_id):
    """Remove a display alias only, never close an MT5 terminal or position."""
    if type(account_id) is not str or _ID.fullmatch(account_id) is None:
        raise ProfileConfigError("Invalid profile alias")
    with _WRITE_LOCK:
        path = _profile_path()
        entries = _read_entries_for_mutation(path)
        remaining = [entry for entry in entries if entry["id"] != account_id]
        if len(remaining) == len(entries):
            raise ProfileConfigError("Broker profile does not exist")
        _write_entries(path, remaining)
        return read_mt5_accounts(path)
