"""Synthetic integration regressions; no terminal, broker or trained model used."""
from dataclasses import replace
from datetime import timedelta
import hashlib
import json
from pathlib import Path

import pytest

from nas100.backtest import FillAssumptions, simulate_signal
from nas100.research import run_research, scan_signals
from nas100 import EngineConfig
from tools.export_mt5_nas100 import ExportSafetyError, export_closed_rates
from tools.run_nas100_research import main, verify_real_dataset
from test_nas100_backtest import BASE, cs, dec
from test_nas100_export import FakeMT5, NOW
from test_nas100_research import synthetic_bars


@pytest.mark.parametrize('direction', ['BUY', 'SELL'])
def test_intrabar_entry_does_not_earn_target_reached_before_fill(direction):
    bars = cs((100, 101, 99, 100), (102, 105, 99, 101))
    decision = dec()
    if direction == 'SELL':
        bars = [replace(c, open=200-c.open, high=200-c.low, low=200-c.high, close=200-c.close) for c in bars]
        decision = dec('SELL', 100, 102, 96)
    outcome = simulate_signal(decision, bars, 0, BASE)
    assert outcome.status == 'INCOMPLETE' and outcome.net_r is None


def test_fill_bar_close_can_prove_target_after_entry():
    bars = cs((100, 101, 99, 100), (102, 105, 99, 104.5))
    assert simulate_signal(dec(), bars, 0, BASE).status == 'TARGET'


def test_historical_spread_floor_applies_once_at_wider_exit_spread():
    bars = cs((100, 101, 99, 100), (100, 101, 99, 100), (101, 104, 101, 103))
    bars[1] = replace(bars[1], spread=10)
    bars[2] = replace(bars[2], spread=20)
    result = simulate_signal(dec(), bars, 0, BASE)
    assert result.spread_points_applied == 20
    # .1 price/point * (20 spread + 1 slippage each side) / 2 initial risk.
    assert result.costs_r == pytest.approx(1.1)
    assert result.net_r == pytest.approx(.9)


def test_combined_cost_overflow_rejected():
    with pytest.raises(ValueError, match='finite'):
        FillAssumptions(point_size=1e308, spread_points=1e308)


def test_scanner_does_not_validate_or_read_the_held_out_suffix():
    bars = synthetic_bars()
    cfg = EngineConfig(min_bars=15, htf_min_bars=3, regime_min_history=5)
    expected = scan_signals(bars[:60], 5, 15, cfg=cfg, start=30)
    bars[65] = replace(bars[65], close=float('nan'))
    assert scan_signals(bars, 5, 15, cfg=cfg, start=30, stop=60) == expected


def test_raw_decision_counts_are_separate_from_deduplicated_proxy_signals():
    run = run_research(synthetic_bars(), 5, 15, BASE, start=50)
    counts = dict(run.decision_counts)
    assert set(counts) == {'BUY', 'SELL', 'NO TRADE'}
    assert sum(counts.values()) == run.inspected == 22


class RealAccount(FakeMT5):
    def account_info(self):
        return replace_namespace(super().account_info(), trade_mode=2)


def replace_namespace(value, **changes):
    from types import SimpleNamespace
    return SimpleNamespace(**(vars(value) | changes))


def test_non_demo_account_blocks_before_history_or_files(tmp_path):
    api = RealAccount()
    with pytest.raises(ExportSafetyError) as exc:
        export_closed_rates(api, symbol='USTECH100M', timeframe='M5', count=10,
                            out_dir=tmp_path, collected_at=NOW)
    assert exc.value.code == 'DEMO_ACCOUNT_REQUIRED'
    assert api.calls == [] and not list(tmp_path.iterdir())


def test_account_switch_during_history_blocks_publication(tmp_path):
    class Switching(FakeMT5):
        changed = False

        def account_info(self):
            return replace_namespace(super().account_info(), login=999 if self.changed else 123456)

        def copy_rates_from_pos(self, *args):
            result = super().copy_rates_from_pos(*args)
            self.changed = True
            return result

    with pytest.raises(ExportSafetyError) as exc:
        export_closed_rates(Switching(), symbol='USTECH100M', timeframe='M5', count=10,
                            out_dir=tmp_path, collected_at=NOW)
    assert exc.value.code == 'SESSION_CHANGED' and not list(tmp_path.iterdir())


def test_current_unclosed_bar_is_excluded_and_disclosed(tmp_path):
    _, _, metadata = export_closed_rates(FakeMT5(now=NOW+timedelta(minutes=5)),
        symbol='USTECH100M', timeframe='M5', count=10, out_dir=tmp_path, collected_at=NOW)
    assert metadata['count'] == 2 and metadata['excluded_unclosed_bars'] == 1
    assert metadata['timebase_status'] == 'TIMEBASE_UNVERIFIED'
    assert not metadata['research_eligible']


def test_existing_capture_is_never_replaced(tmp_path):
    path = tmp_path/'USTECH100M_M5.csv'
    path.write_text('existing user capture', encoding='utf-8')
    with pytest.raises(FileExistsError):
        export_closed_rates(FakeMT5(), symbol='USTECH100M', timeframe='M5', count=10,
                            out_dir=tmp_path, collected_at=NOW)
    assert path.read_text(encoding='utf-8') == 'existing user capture'


@pytest.mark.parametrize('field,value', [('point', 0), ('volume_step', -1), ('trade_tick_size', float('nan'))])
def test_invalid_specs_block_history(tmp_path, field, value):
    class Invalid(FakeMT5):
        def symbol_info(self, symbol):
            return replace_namespace(super().symbol_info(symbol), **{field: value})

    api = Invalid()
    with pytest.raises(RuntimeError, match='specification'):
        export_closed_rates(api, symbol='USTECH100M', timeframe='M5', count=10,
                            out_dir=tmp_path, collected_at=NOW)
    assert api.calls == [] and not list(tmp_path.iterdir())


def fixture_csv(tmp_path):
    path = tmp_path/'SYNTHETIC_FIXTURE.csv'
    rows = ['time_utc,open,high,low,close,tick_volume,spread_points']
    rows += [f'{b.time.isoformat()},{b.open},{b.high},{b.low},{b.close},{b.volume},{b.spread}' for b in synthetic_bars()]
    path.write_text('\n'.join(rows)+'\n', encoding='utf-8')
    return path


def test_cli_blocks_unverified_csv_without_measuring_zero_signals(tmp_path, capsys):
    path = fixture_csv(tmp_path)
    code = main(['--csv', str(path), '--point-size', '.1', '--spread-points', '2', '--start', '50'])
    report = json.loads(capsys.readouterr().out)
    assert code == 2 and report['status'] == 'BLOCKED_DATASET_ELIGIBILITY'
    assert report['decision_counts'] is None and report['summary'] is None


def test_explicit_synthetic_cli_smoke_never_claims_real_validation(tmp_path, capsys):
    path = fixture_csv(tmp_path)
    code = main(['--csv', str(path), '--point-size', '.1', '--spread-points', '2',
                 '--start', '50', '--synthetic-fixture'])
    report = json.loads(capsys.readouterr().out)
    assert code == 0 and report['source_kind'] == 'SYNTHETIC_FIXTURE_UNATTESTED'
    assert not report['model_trained'] and not report['performance_validated']
    assert sum(report['decision_counts'].values()) == 22


def test_real_dataset_gate_checks_exact_point_size_and_hash(tmp_path):
    from tools.run_nas100_research import read_candles
    path = fixture_csv(tmp_path)
    bars = read_candles(path, 5)
    observed = bars[-1].time+timedelta(minutes=5)
    evidence = tmp_path/'timebase.json'
    evidence.write_text(json.dumps(dict(status='VERIFIED_UTC', source='SYNTHETIC_TEST_ONLY',
        observed_at_utc=observed.isoformat(), timeframe='M5', grid_origin_epoch_seconds=0,
        clock_uncertainty_seconds=0)), encoding='utf-8')
    metadata = tmp_path/'metadata.json'
    metadata.write_text(json.dumps(dict(sha256_csv=hashlib.sha256(path.read_bytes()).hexdigest(),
        symbol='USTECH100M', timeframe='M5', count=len(bars), account_mode='DEMO',
        read_only_gates_passed=True, symbol_specs_snapshot={'point': .1})), encoding='utf-8')
    verify_real_dataset(path, bars, 5, .1, evidence, metadata)
    with pytest.raises(ValueError, match='POINT_SIZE_MISMATCH'):
        verify_real_dataset(path, bars, 5, 1, evidence, metadata)
    path.write_text(path.read_text()+'\n', encoding='utf-8')
    with pytest.raises(ValueError, match='HASH_MISMATCH'):
        verify_real_dataset(path, bars, 5, .1, evidence, metadata)
