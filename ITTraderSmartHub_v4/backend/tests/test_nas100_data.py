"""Data validation, MT5 adapter, resampling and session tests. SYNTHETIC FIXTURES ONLY."""
from datetime import datetime, timedelta, timezone

import pytest

from nas100_fixtures import MONDAY, UTC, bar, candles_from_closes, flat_series, zigzag
from nas100 import (Candle, DataValidationError, candles_from_rates, htf_closed_by, resample,
                    session_state, validate_candles)


# ---------------------------------------------------------------- validation
def test_valid_series_has_no_gaps():
    q = validate_candles(flat_series(10), 5)
    assert q.n_bars == 10 and q.gaps == () and q.fault_gaps == ()


@pytest.mark.parametrize('mutate,msg', [
    (lambda c: c.__setitem__(3, Candle(c[3].time.replace(tzinfo=None), 1, 1, 1, 1)), 'UTC'),
    (lambda c: c.__setitem__(3, Candle(c[3].time.astimezone(timezone(timedelta(hours=3))), 1, 1, 1, 1)), 'UTC'),
    (lambda c: c.__setitem__(3, Candle(c[3].time, float('nan'), 1, 1, 1)), 'non-finite'),
    (lambda c: c.__setitem__(3, Candle(c[3].time, 1, 0.5, 1, 1)), 'OHLC'),            # high < open
    (lambda c: c.__setitem__(3, Candle(c[3].time, 1, 2, 1.5, 1)), 'OHLC'),            # low > open
    (lambda c: c.__setitem__(3, Candle(c[3].time, 1, 1, 1, 1, volume=-1)), 'volume'),
    (lambda c: c.__setitem__(3, Candle(c[3].time, 1, 1, 1, 1, spread=-1)), 'spread'),
    (lambda c: c.__setitem__(3, c[2]), 'increasing'),                                 # duplicate time
    (lambda c: c.reverse(), 'increasing'),
    (lambda c: c.__setitem__(3, Candle(c[3].time + timedelta(minutes=2), 1, 1, 1, 1)), 'multiple'),
])
def test_invalid_series_rejected(mutate, msg):
    c = flat_series(8)
    mutate(c)
    with pytest.raises(DataValidationError, match=msg):
        validate_candles(c, 5)


def test_bad_timeframe_rejected():
    with pytest.raises(DataValidationError):
        validate_candles(flat_series(3), 0)


def test_missing_candles_reported_as_fault_gap():
    c = flat_series(20)
    del c[10:13]                                    # 3 missing M5 bars = 15 minutes
    q = validate_candles(c, 5)
    assert len(q.gaps) == 1
    g = q.gaps[0]
    assert (g.after_index, g.missing_bars, g.duration_minutes, g.is_market_closure) == (9, 3, 15, False)
    assert q.fault_gaps == q.gaps


def test_long_gap_is_unverified_and_remains_fault():
    c = flat_series(40)
    del c[10:34]                                    # 24 missing bars = 120 minutes
    q = validate_candles(c, 5, closure_min_minutes=60)
    assert len(q.gaps) == 1 and not q.gaps[0].is_market_closure and q.fault_gaps == q.gaps


def test_empty_series_is_valid():
    assert validate_candles([], 5).n_bars == 0


# ---------------------------------------------------------------- MT5 adapter
def _epoch(y, mo, d, h, mi):
    """MT5 encodes broker wall-clock time as if it were UTC."""
    return int(datetime(y, mo, d, h, mi, tzinfo=UTC).timestamp())


def _rate(t, price=100.0):
    return {'time': t, 'open': price, 'high': price + 1, 'low': price - 1, 'close': price,
            'tick_volume': 7, 'spread': 12}


def test_adapter_converts_server_time_winter_and_summer():
    winter = candles_from_rates([_rate(_epoch(2026, 1, 6, 10, 0))], 'Europe/Athens', time_encoding='verified_wall_clock')[0]
    summer = candles_from_rates([_rate(_epoch(2026, 7, 1, 10, 0))], 'Europe/Athens', time_encoding='verified_wall_clock')[0]
    assert winter.time == datetime(2026, 1, 6, 8, 0, tzinfo=UTC)      # UTC+2
    assert summer.time == datetime(2026, 7, 1, 7, 0, tzinfo=UTC)      # UTC+3
    assert (winter.volume, winter.spread) == (7.0, 12.0)


def test_adapter_handles_repeated_wall_clock_hour_at_dst_fallback():
    # Europe/Athens falls back 04:00 EEST -> 03:00 EET on 2026-10-25; 03:00-03:55 repeats.
    walls = [(3, 50), (3, 55), (3, 0), (3, 5)]
    rates = [_rate(_epoch(2026, 10, 25, h, m)) for h, m in walls]
    out = candles_from_rates(rates, 'Europe/Athens', time_encoding='verified_wall_clock')
    assert [c.time for c in out] == [
        datetime(2026, 10, 25, 0, 50, tzinfo=UTC), datetime(2026, 10, 25, 0, 55, tzinfo=UTC),
        datetime(2026, 10, 25, 1, 0, tzinfo=UTC), datetime(2026, 10, 25, 1, 5, tzinfo=UTC)]


def test_adapter_utc_passthrough_and_validation_of_result():
    rates = [_rate(_epoch(2026, 1, 6, 10, 5 * i)) for i in range(5)]
    out = candles_from_rates(rates, 'UTC')
    assert out[0].time == datetime(2026, 1, 6, 10, 0, tzinfo=UTC)
    assert validate_candles(out, 5).gaps == ()


def test_adapter_accepts_tuple_like_records_with_getitem_only():
    class Rec:
        def __init__(self, d):
            self.d = d

        def __getitem__(self, k):
            return self.d[k]

    out = candles_from_rates([Rec(_rate(_epoch(2026, 1, 6, 10, 0)))], 'UTC')
    assert out[0].close == 100.0


def test_adapter_missing_field_and_non_increasing_time_rejected():
    with pytest.raises(DataValidationError, match='missing field'):
        candles_from_rates([{'time': 0, 'open': 1}], 'UTC')
    t = _epoch(2026, 1, 6, 10, 0)
    with pytest.raises(DataValidationError, match='increasing'):
        candles_from_rates([_rate(t), _rate(t)], 'UTC')


def test_adapter_defaults_to_documented_mt5_utc():
    stamp = _epoch(2026, 1, 6, 10, 0)
    assert candles_from_rates([_rate(stamp)])[0].time == datetime(2026, 1, 6, 10, 0, tzinfo=UTC)


# ---------------------------------------------------------------- resampling / MTF
def test_resample_aggregates_ohlc_and_drops_unfinished_bucket():
    c = []
    for i in range(30):                              # 00:00 .. 02:25 (M5)
        c.append(bar(MONDAY + timedelta(minutes=5 * i), 100 + i, 110 + i, 90 + i, 105 + i))
    out = resample(c, 5, 60)
    assert [b.time for b in out] == [MONDAY, MONDAY + timedelta(hours=1)]   # 02:00 bucket unfinished
    first = out[0]
    assert (first.open, first.high, first.low, first.close) == (100, 121, 90, 116)
    assert first.volume == 12 * 100.0


def test_resample_min_fill_and_invalid_ratio():
    c = flat_series(30)
    del c[5:11]                                      # first hour keeps 6/12 bars
    assert len(resample(c, 5, 60, min_fill=0.5)) == 2
    assert len(resample(c, 5, 60, min_fill=0.75)) == 1
    with pytest.raises(ValueError):
        resample(c, 5, 7)
    assert resample([], 5, 60) == []


def test_resample_never_leaks_future_bars():
    c = candles_from_closes([100 + (i % 17) for i in range(150)])
    full = resample(c, 5, 60)
    for n in range(1, len(c) + 1):
        prefix = resample(c[:n], 5, 60)
        knowable_until = c[n - 1].time + timedelta(minutes=5)
        expected = [b for b in full if b.time + timedelta(minutes=60) <= knowable_until]
        assert prefix == expected


def test_htf_closed_by_filters_on_close_time():
    hourly = zigzag([100, 110, 105, 120], 4, start=MONDAY, tf=60)
    cut = MONDAY + timedelta(hours=3)
    assert [b.time for b in htf_closed_by(hourly, 60, cut)] == [MONDAY + timedelta(hours=k) for k in range(3)]


# ---------------------------------------------------------------- sessions / DST
def at(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=UTC)


def test_london_open_moves_with_uk_dst():
    assert not session_state(at(2026, 3, 27, 7, 59)).london and session_state(at(2026, 3, 27, 8, 0)).london   # GMT
    assert not session_state(at(2026, 3, 30, 6, 59)).london and session_state(at(2026, 3, 30, 7, 0)).london   # BST


def test_ny_cash_open_moves_with_us_dst():
    assert session_state(at(2026, 3, 6, 14, 30)).ny_cash and not session_state(at(2026, 3, 6, 14, 29)).ny_cash   # EST
    assert session_state(at(2026, 3, 9, 13, 30)).ny_cash and not session_state(at(2026, 3, 9, 13, 29)).ny_cash   # EDT


def test_us_uk_dst_mismatch_weeks_change_overlap():
    # Winter (both standard): overlap 13:00-16:30 UTC
    assert session_state(at(2026, 1, 6, 13, 0)).overlap and not session_state(at(2026, 1, 6, 12, 59)).overlap
    # Mismatch (US already EDT, UK still GMT), e.g. Wed 2026-03-18: overlap 12:00-16:30 UTC
    assert session_state(at(2026, 3, 18, 12, 0)).overlap and not session_state(at(2026, 3, 18, 11, 59)).overlap
    assert session_state(at(2026, 3, 18, 16, 29)).overlap and not session_state(at(2026, 3, 18, 16, 30)).overlap
    # Both daylight: London 07:00-15:30 UTC, NY 12:00-21:00 UTC -> overlap 12:00-15:30
    assert session_state(at(2026, 4, 15, 15, 29)).overlap and not session_state(at(2026, 4, 15, 15, 30)).overlap


def test_session_transition_days_are_continuous_and_valid():
    # Walk every 30 minutes across both spring transitions and the UK/US autumn gap: never raises,
    # overlap implies both sessions.
    t = at(2026, 3, 6, 0, 0)
    end = at(2026, 4, 3, 0, 0)
    while t < end:
        s = session_state(t)
        assert (not s.overlap) or (s.london and s.new_york)
        assert (not s.ny_open) or s.ny_cash
        t += timedelta(minutes=30)
    t = at(2026, 10, 20, 0, 0)
    while t < at(2026, 11, 5, 0, 0):
        session_state(t)
        t += timedelta(minutes=30)


def test_weekend_has_no_sessions_and_naive_time_rejected():
    s = session_state(at(2026, 1, 10, 14, 0))       # Saturday
    assert s.active() == () and not s.ny_cash
    with pytest.raises(ValueError):
        session_state(datetime(2026, 1, 6, 14, 0))


def test_ny_open_window_is_first_hour_of_cash_session():
    assert session_state(at(2026, 1, 6, 14, 30)).ny_open                    # 09:30 EST
    assert session_state(at(2026, 1, 6, 15, 29)).ny_open
    assert not session_state(at(2026, 1, 6, 15, 30)).ny_open and session_state(at(2026, 1, 6, 15, 30)).ny_cash
    assert not session_state(at(2026, 1, 6, 21, 0)).ny_cash                 # 16:00 EST excluded
    assert session_state(at(2026, 1, 6, 15, 59), ny_open_minutes=30).ny_open is False


def test_missing_tz_database_gives_actionable_error(monkeypatch):
    from zoneinfo import ZoneInfoNotFoundError
    import nas100.tz as tz

    def boom(name):
        raise ZoneInfoNotFoundError(name)

    monkeypatch.setattr(tz, 'ZoneInfo', boom)
    with pytest.raises(RuntimeError, match='pip install tzdata'):
        session_state(datetime(2026, 1, 6, 14, 0, tzinfo=UTC))
