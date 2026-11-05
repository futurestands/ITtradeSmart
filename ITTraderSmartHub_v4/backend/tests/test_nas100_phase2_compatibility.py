"""Supplied Phase 1 regressions, adapted to preserved local blocker names."""
import pytest
from dataclasses import replace
from datetime import datetime, timedelta
from nas100 import (Candle, EngineConfig, DataValidationError, candles_from_rates,
    candles_from_broker_wall_rates, analyze, analyze_multitimeframe, resample, decide, BUY, NO_TRADE)
from nas100.decision import _build_candidate
from nas100_fixtures import UTC, bullish_setup_ltf, uptrend_htf
from test_nas100_data import _epoch, _rate
from test_nas100_decision import run

def test_mt5_numpy_structured_rates_use_utc_seconds_without_extra_offset():
    numpy = pytest.importorskip('numpy')
    dt = [('time', '<i8'), ('open', '<f8'), ('high', '<f8'),
          ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<u8'), ('spread', '<i4')]
    t = _epoch(2026, 7, 1, 10, 0)
    rates = numpy.array([(t, 100.0, 101.0, 99.0, 100.0, 5, 15)], dtype=dt)
    out = candles_from_rates(rates)
    assert out[0].time == datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    assert (out[0].volume, out[0].spread) == (5.0, 15.0)

def test_multitimeframe_defaults_to_full_htf_bucket_coverage():
    from nas100 import analyze_multitimeframe
    # 12 M5 bars in the hour except one missing mid-hour candle.
    hour_start = datetime(2026, 1, 6, 13, 0, tzinfo=UTC)
    src = [Candle(hour_start + timedelta(minutes=5 * i), 100, 102, 98, 101, 1, 10)
           for i in range(12) if i != 5]
    strict = analyze_multitimeframe(src, 5, [60])
    permissive = analyze_multitimeframe(src, 5, [60], min_fill=0.5)
    assert len(strict.htf[60].candles) == 0
    assert len(permissive.htf[60].candles) == 1
    with pytest.raises(ValueError, match='min_fill'):
        resample(src, 5, 60, min_fill=0)

def test_future_dated_ltf_bar_is_never_fresh_and_blocks_buy():
    as_of = datetime(2026, 1, 6, 14, 5, tzinfo=UTC)
    d = run(now=as_of - timedelta(hours=2))
    assert d.action == NO_TRADE and d.data_fresh is False
    assert 'FUTURE_DATA' in d.blockers

def test_live_mode_fails_closed_without_clock():
    a = analyze(bullish_setup_ltf(), 5)
    h = analyze(uptrend_htf(), 60, min_bars=30)
    d = decide(a, h, live=True)
    assert d.action == NO_TRADE and 'DECISION_TIME_REQUIRED' in d.blockers
    good = decide(a, h, live=True, now=a.as_of)
    assert good.action == BUY and good.data_fresh is True

def test_naive_time_is_rejected():
    a = analyze(bullish_setup_ltf(), 5)
    h = analyze(uptrend_htf(), 60, min_bars=30)
    with pytest.raises(ValueError, match='timezone-aware'):
        decide(a, h, now=datetime(2026, 1, 6, 14, 5))

def test_stale_htf_does_not_authorize_buy():
    a = analyze(bullish_setup_ltf(), 5)
    h = analyze(uptrend_htf(), 60, min_bars=30)
    old_htf = replace(h, candles=tuple(replace(c, time=c.time - timedelta(days=30)) for c in h.candles))
    d = decide(a, old_htf, now=a.as_of, live=True)
    assert d.action == NO_TRADE and 'HTF_STALE_DATA' in d.blockers

def test_htf_staleness_counts_actual_ltf_bars_not_closed_weekend_hours():
    a = analyze(bullish_setup_ltf(), 5)
    h = analyze(uptrend_htf(), 60, min_bars=30)
    # Time shift without market-active LTF bars should not count as stale by itself.
    # Shift both time series by the same number of days so the observed bar count stays fixed.
    moved = timedelta(days=7)
    late_ltf = replace(a, candles=tuple(replace(c, time=c.time + moved) for c in a.candles))
    late_htf = replace(h, candles=tuple(replace(c, time=c.time + moved) for c in h.candles))
    assert 'HTF_STALE_DATA' not in decide(late_ltf, late_htf).blockers

def test_same_timeframe_is_not_accepted_as_htf():
    a = analyze(bullish_setup_ltf(), 5)
    d = decide(a, a)
    assert 'HTF_TIMEFRAME_NOT_HIGHER' in d.blockers

def test_nonchronological_fvg_cannot_form_setup():
    a = analyze(bullish_setup_ltf(), 5)
    fvg = a.fvgs[-1]
    # A premature FVG appearing on the same bar as the structural shift.
    premature = replace(a, fvgs=(replace(fvg, detected_index=82),))
    d = _build_candidate(premature, 'bull', EngineConfig())
    assert not d.complete and 'NO_OPEN_FVG' in d.blockers
    late_shift = replace(a, events=(replace(a.events[-1], index=84),))
    d2 = _build_candidate(late_shift, 'bull', EngineConfig())
    assert not d2.complete and 'NO_OPEN_FVG' in d2.blockers

@pytest.mark.parametrize('kwargs', [
    {'swing_left': 0}, {'htf_max_lag_bars': -1}, {'min_rr': 0},
    {'low_vol_pct': .9, 'high_vol_pct': .1},
    {'max_spread_points': -10}, {'max_spread_points': float('nan')},
    {'consolidation_max_efficiency': 1.1},
    {'allowed_sessions': ('unknown',)},
])
def test_invalid_config_rejected(kwargs):
    with pytest.raises(ValueError):
        EngineConfig(**kwargs)

def test_broker_wall_adapter_rejects_nonexistent_dst_time():
    # Greece jumps from 03:00 to 04:00; 03:30 on 2026-03-29 does not exist.
    with pytest.raises(DataValidationError, match='nonexistent'):
        candles_from_broker_wall_rates([_rate(_epoch(2026, 3, 29, 3, 30))], 'Europe/Athens')

def test_mt5_adapter_rejects_nonfinite_and_subsecond_rate_time():
    for t in (float('nan'), float('inf'), True, 111.25):
        with pytest.raises(DataValidationError):
            candles_from_rates([_rate(t)])
