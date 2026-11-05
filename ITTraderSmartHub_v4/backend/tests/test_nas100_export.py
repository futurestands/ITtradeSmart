"""Fake MT5 module tests: no actual terminal is used."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import hashlib
import json
from types import SimpleNamespace
import pytest

from tools.export_mt5_nas100 import export_closed_rates


class FakeMT5:
    TIMEFRAME_M5 = 5
    def __init__(self, *, connected=True, trading=False, now=None):
        self.connected, self.trading = connected, trading
        self.now = now or datetime(2026, 8, 5, 14, 0, tzinfo=timezone.utc)
        self.calls = []

    def account_info(self):
        return SimpleNamespace(trade_allowed=self.trading, trade_expert=self.trading,
                               trade_mode=0, login=123456, server='SYNTHETIC-DEMO')

    def terminal_info(self):
        return SimpleNamespace(connected=self.connected, trade_allowed=self.trading)

    def symbol_info(self, symbol):
        return SimpleNamespace(name=symbol, point=0.1, digits=1, trade_tick_size=0.1,
                               trade_tick_value=0.1, volume_min=0.01, volume_step=0.01,
                               volume_max=50, trade_contract_size=1, trade_stops_level=0)

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
        self.calls.append((symbol, timeframe, start_pos, count))
        origin = self.now - timedelta(minutes=15)
        return [dict(time=int((origin + timedelta(minutes=5*i)).timestamp()),
                     open=100+i, high=101+i, low=99+i, close=100.5+i,
                     tick_volume=10+i, spread=2) for i in range(3)]


NOW = datetime(2026, 8, 5, 14, 0, tzinfo=timezone.utc)


def test_export_produces_valid_csv_and_metadata_without_account_info(tmp_path):
    fake = FakeMT5(now=NOW)
    csvpath, metapath, metadata = export_closed_rates(
        fake, symbol='USTECH100M', timeframe='M5', count=200,
        out_dir=tmp_path, collected_at=NOW)
    assert csvpath.exists() and metapath.exists()
    assert fake.calls == [('USTECH100M', 5, 1, 200)]  # excludes bar 0
    data = list(csv.DictReader(csvpath.open()))
    assert len(data) == 3
    assert data[0]['time_utc'].endswith('+00:00')
    assert data[0]['spread_points'] == '2.0'
    assert metadata['count'] == 3
    assert metadata['sha256_csv'] == hashlib.sha256(csvpath.read_bytes()).hexdigest()
    text = json.dumps(metadata)
    assert 'password' not in text and 'login' not in text
    assert metadata['symbol_specs_snapshot']['point'] == 0.1


@pytest.mark.parametrize('connected,trading', [(False,False), (True,True)])
def test_export_never_collects_when_session_not_read_only(tmp_path, connected, trading):
    fake = FakeMT5(connected=connected, trading=trading)
    with pytest.raises(RuntimeError, match='Read-only'):
        export_closed_rates(fake, symbol='USTECH100M', timeframe='M5',
                            count=10, out_dir=tmp_path, collected_at=NOW)
    assert fake.calls == [] and not list(tmp_path.iterdir())


def test_export_rejects_future_clock_instead_of_silently_dropping_it(tmp_path):
    fake = FakeMT5(now=NOW + timedelta(minutes=10))
    with pytest.raises(RuntimeError, match='Future bar'):
        export_closed_rates(fake, symbol='USTECH100M', timeframe='M5',
                            count=10, out_dir=tmp_path, collected_at=NOW)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('symbol', ['', '../file', 'X'*33])
def test_export_rejects_invalid_symbols(tmp_path, symbol):
    with pytest.raises(ValueError):
        export_closed_rates(FakeMT5(), symbol=symbol, timeframe='M5',
                            count=10, out_dir=tmp_path, collected_at=NOW)


def test_export_rejects_invalid_timeframe(tmp_path):
    with pytest.raises(ValueError):
        export_closed_rates(FakeMT5(), symbol='USTECH100M', timeframe='D1',
                            count=10, out_dir=tmp_path, collected_at=NOW)
