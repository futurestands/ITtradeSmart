"""Synthetic regression cases for independently discovered integration defects."""
from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from nas100 import analyze, candles_from_rates, DataValidationError, decide, resample
from nas100.fvg import FVG
from nas100.decision import _build_candidate
from nas100 import EngineConfig
from nas100_fixtures import UTC, bullish_setup_ltf, flat_series, uptrend_htf


def test_future_candles_fail_freshness_gate():
    ltf = analyze(bullish_setup_ltf(), 5)
    decision = decide(ltf, analyze(uptrend_htf(), 60, min_bars=30), now=ltf.as_of-timedelta(seconds=1))
    assert decision.action == 'NO TRADE' and not decision.data_fresh
    assert 'FUTURE_DATA' in decision.blockers


def test_naive_observation_time_rejected():
    with pytest.raises(ValueError, match='timezone-aware'):
        decide(analyze(bullish_setup_ltf(), 5), None, now=datetime(2026, 1, 6))


def test_htf_must_be_current_and_higher():
    ltf = analyze(bullish_setup_ltf(), 5)
    htf = analyze(uptrend_htf(), 60, min_bars=30)
    old = analyze([replace(c, time=c.time-timedelta(hours=1)) for c in htf.candles], 60, min_bars=30)
    assert 'HTF_STALE_DATA' in decide(ltf, old).blockers
    assert 'HTF_TIMEFRAME_NOT_HIGHER' in decide(ltf, ltf).blockers


def test_recent_htf_gap_is_not_ignored():
    data = uptrend_htf()
    del data[-10:-8]
    assert 'HTF_DATA_GAP_RECENT' in decide(analyze(bullish_setup_ltf(), 5), analyze(data, 60, min_bars=30)).blockers


def test_recent_long_outage_blocks_decisions():
    data = bullish_setup_ltf()
    data = data[:70] + [replace(c, time=c.time+timedelta(hours=2)) for c in data[70:]]
    assert 'DATA_GAP_RECENT' in decide(analyze(data, 5), None).blockers


def test_fvg_must_form_after_structure_shift():
    ltf = analyze(bullish_setup_ltf(), 5)
    # A still-open FVG before the sweep's structure shift is not an ordered setup.
    old = FVG('bull', 81, 1000, 1001)
    cand = _build_candidate(replace(ltf, fvgs=(old,)), 'bull', EngineConfig())
    assert not cand.complete and 'NO_OPEN_FVG' in cand.blockers


@pytest.mark.parametrize('fill', [0, -1, 1.1, float('nan'), float('inf'), True])
def test_invalid_resampling_fill_rejected(fill):
    with pytest.raises(ValueError, match='min_fill'):
        resample(flat_series(12), 5, 60, min_fill=fill)


def test_resampling_rejects_shifted_grid_and_duplicate_bars():
    bars = [replace(c, time=c.time+timedelta(minutes=2)) for c in flat_series(12)]
    with pytest.raises(ValueError, match='grid'):
        resample(bars, 5, 60)
    bars = flat_series(12)
    bars[2] = bars[1]
    with pytest.raises(DataValidationError, match='increasing'):
        resample(bars, 5, 60)


def test_resampling_requires_full_buckets_by_default():
    bars = flat_series(24)
    del bars[3]
    assert len(resample(bars, 5, 60)) == 1


def rate(stamp):
    return dict(time=stamp, open=100, high=101, low=99, close=100)


@pytest.mark.parametrize('stamp', [True, 1.5, '123'])
def test_rate_epoch_cannot_be_truncated_or_coerced(stamp):
    with pytest.raises(DataValidationError, match='integer epoch'):
        candles_from_rates([rate(stamp)], 'UTC')


def test_mt5_api_utc_cannot_be_silently_shifted():
    with pytest.raises(DataValidationError, match='require UTC'):
        candles_from_rates([rate(1790000000)], 'Europe/Athens')


def test_nonexistent_dst_wall_time_rejected():
    stamp = int(datetime(2026, 3, 29, 3, 30, tzinfo=UTC).timestamp())
    with pytest.raises(DataValidationError, match='nonexistent'):
        candles_from_rates([rate(stamp)], 'Europe/Athens', time_encoding='verified_wall_clock')
