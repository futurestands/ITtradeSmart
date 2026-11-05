"""Synthetic exports verify diagnostics, never market performance."""
from datetime import datetime, timezone
import json

from nas100_data_audit import audit_export, main


def write_csv(tmp_path, body):
    path = tmp_path/'fixture.csv'
    path.write_text('raw_time_epoch,open,high,low,close\n'+body, encoding='utf-8')
    return path


def test_raw_export_gaps_duplicates_prices_and_future_are_reported(tmp_path):
    path = write_csv(tmp_path, '0,100,101,99,100\n300,100,101,99,100\n1200,100,101,99,100\n1200,100,90,99,100\n')
    report = audit_export(path, 'M5', datetime.fromtimestamp(1300, timezone.utc))
    assert report['rows'] == 4 and report['invalid_ohlc'] == 1
    assert not report['strictly_ordered'] and report['duplicate_epochs'] == 1
    assert report['nonstandard_intervals'] == 2
    assert report['unclosed_or_future_against_observation'] == 2
    assert not report['research_eligible'] and report['signal_counts'] is None


def test_cli_success_retains_unverified_status(tmp_path, capsys):
    path = write_csv(tmp_path, '0,100,101,99,100\n')
    assert main(['--input', str(path), '--timeframe', 'M5', '--observed-at', '2026-11-05T00:00:00Z']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['timebase_status'] == 'TIMEBASE_UNVERIFIED'
    assert report['performance'] is None and report['model_trained'] is False


def test_cli_errors_do_not_echo_input_or_paths(tmp_path, capsys):
    path = write_csv(tmp_path, 'private-data,100,101,99,100\n')
    assert main(['--input', str(path), '--timeframe', 'M5']) == 2
    text = capsys.readouterr().out
    assert 'private-data' not in text and str(path) not in text


def test_naive_observation_rejected(tmp_path, capsys):
    path = write_csv(tmp_path, '0,100,101,99,100\n')
    assert main(['--input', str(path), '--timeframe', 'M5', '--observed-at', '2026-11-05']) == 2


def test_legacy_declared_utc_column_does_not_attest_timebase(tmp_path):
    path = tmp_path/'legacy.csv'
    path.write_text('time_utc,open,high,low,close\n2026-11-02T00:00:00+00:00,100,101,99,100\n', encoding='utf-8')
    result = audit_export(path, 'M15', datetime(2026, 11, 5, tzinfo=timezone.utc))
    assert result['time_column'] == 'time_utc' and not result['research_eligible']
