"""Research scanner causal tests: synthetic bars only."""
from datetime import datetime, timedelta, timezone
import pytest

from nas100 import Candle, EngineConfig
from nas100.backtest import FillAssumptions
from nas100.research import run_research, scan_signals
from tools.run_nas100_research import read_candles

T0 = datetime(2026, 8, 3, 12, tzinfo=timezone.utc)


def synthetic_bars(n=72):
    return [Candle(T0 + timedelta(minutes=5*i),
                   200+i*0.1, 200.3+i*0.1, 199.7+i*0.1, 200.1+i*0.1, 100, 2)
            for i in range(n)]


def test_reference_scanner_has_no_future_dependency():
    bars = synthetic_bars()
    cfg = EngineConfig(min_bars=15, htf_min_bars=3, regime_min_history=5, regime_lookback=10)
    early = scan_signals(bars[:60], 5, 15, cfg=cfg, start=30, max_inspections=100)
    full = scan_signals(bars, 5, 15, cfg=cfg, start=30, stop=60, max_inspections=100)
    assert early == full


def test_research_summary_reports_zero_signals_honestly():
    bars = synthetic_bars()
    cfg = EngineConfig(min_bars=20, htf_min_bars=3, regime_min_history=5, regime_lookback=10)
    run = run_research(bars, 5, 15, FillAssumptions(point_size=.1, spread_points=2),
                       cfg=cfg, start=50, max_inspections=100)
    assert run.inspected == 22
    assert run.summary.completed <= len(run.actionable)
    if not run.actionable:
        assert run.summary.expectancy_r is None


def test_large_scan_requires_explicit_range():
    bars = synthetic_bars()
    with pytest.raises(ValueError, match='too large'):
        scan_signals(bars, 5, 15, start=0, max_inspections=20)


def test_invalid_htf_rejected():
    with pytest.raises(ValueError, match='htf_minutes'):
        scan_signals(synthetic_bars(), 5, 7)


def test_csv_reader_rejects_non_utc(tmp_path):
    path = tmp_path / 'bad.csv'
    path.write_text('time_utc,open,high,low,close,tick_volume,spread_points\n'
                    '2026-08-05T12:00:00+03:00,1,2,0,1,100,2\n')
    with pytest.raises(ValueError, match='UTC'):
        read_candles(path, 5)


def test_csv_reader_roundtrip(tmp_path):
    path = tmp_path / 'ok.csv'
    path.write_text('time_utc,open,high,low,close,tick_volume,spread_points\n'
                    '2026-08-05T12:00:00+00:00,100,102,99,101,100,2\n'
                    '2026-08-05T12:05:00+00:00,101,103,100,102,120,3\n')
    bars = read_candles(path, 5)
    assert len(bars) == 2 and bars[-1].spread == 3


def test_run_does_not_peek_beyond_evaluation_cutoff(monkeypatch):
    from nas100.research import SignalObservation
    from nas100.decision import Decision, BUY
    import nas100.research as research
    bars = synthetic_bars(12)
    action = Decision(BUY, 5, bars[9].time + timedelta(minutes=5), True,
                      'NORMAL', 'bull', 'setup', None, 201, 200, 204, 3, (), (), None)
    monkeypatch.setattr(research, 'scan_signals', lambda *args, **kwargs:
                        (SignalObservation(9, action),))
    result = research.run_research(bars, 5, 15,
                                  FillAssumptions(point_size=.1, spread_points=1),
                                  stop=10)
    assert result.executed_proxy[0].status == 'INCOMPLETE'
    assert result.summary.completed == 0
