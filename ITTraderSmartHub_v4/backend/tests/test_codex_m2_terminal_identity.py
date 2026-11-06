"""Exact-image fallback regressions: no broker SDK, login, flags or orders."""
from types import SimpleNamespace

import pytest

from tools import export_mt5_nas100 as exporter


@pytest.fixture(autouse=True)
def windows_contract(monkeypatch):
    monkeypatch.setattr(exporter.sys, 'platform', 'win32')


def test_exact_native_image_can_resolve_empty_powershell_metadata(tmp_path, monkeypatch):
    terminal = tmp_path/'terminal64.exe'
    terminal.write_bytes(b'SYNTHETIC_NONEXECUTABLE_FIXTURE')
    monkeypatch.setattr(exporter.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=''))
    monkeypatch.setattr(exporter, '_native_terminal_images', lambda: [str(terminal)], raising=False)
    assert exporter.terminal_already_running(str(terminal))


def test_same_basename_at_another_path_is_not_identity(tmp_path, monkeypatch):
    expected = tmp_path/'terminal64.exe'
    expected.write_bytes(b'SYNTHETIC_NONEXECUTABLE_FIXTURE')
    monkeypatch.setattr(exporter.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=''))
    monkeypatch.setattr(exporter, '_native_terminal_images', lambda: [str(tmp_path/'other'/'terminal64.exe')], raising=False)
    assert not exporter.terminal_already_running(str(expected))


def test_no_image_metadata_remains_blocked(tmp_path, monkeypatch):
    terminal = tmp_path/'terminal64.exe'
    terminal.write_bytes(b'SYNTHETIC_NONEXECUTABLE_FIXTURE')
    monkeypatch.setattr(exporter.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=''))
    monkeypatch.setattr(exporter, '_native_terminal_images', lambda: [], raising=False)
    assert not exporter.terminal_already_running(str(terminal))


@pytest.mark.parametrize('unknown', [True, False])
def test_unreadable_or_duplicate_native_candidates_remain_blocked(tmp_path, monkeypatch, unknown):
    terminal = tmp_path/'terminal64.exe'
    terminal.write_bytes(b'SYNTHETIC_NONEXECUTABLE_FIXTURE')
    monkeypatch.setattr(exporter.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=''))
    candidates = [str(terminal), '' if unknown else str(terminal)]
    monkeypatch.setattr(exporter, '_native_terminal_images', lambda: candidates, raising=False)
    assert not exporter.terminal_already_running(str(terminal))


def test_powershell_failure_can_use_exact_read_only_fallback(tmp_path, monkeypatch):
    terminal = tmp_path/'terminal64.exe'
    terminal.write_bytes(b'SYNTHETIC_NONEXECUTABLE_FIXTURE')

    def denied(*args, **kwargs):
        raise PermissionError('SYNTHETIC_DENIAL')

    monkeypatch.setattr(exporter.subprocess, 'run', denied)
    monkeypatch.setattr(exporter, '_native_terminal_images', lambda: [str(terminal)], raising=False)
    assert exporter.terminal_already_running(str(terminal))
