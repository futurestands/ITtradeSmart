"""Time eligibility tests use explicit synthetic UTC evidence, never broker approval."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest
from bot.time_integrity import (TimebaseEvidence, TimeIntegrityError, validate_bar_times,
    alignment_report, require_complete_alignment, PERIOD_SECONDS)
from bot.market_data import Candle, MarketDataManager
from bot.backtesting import BacktestEngine
from bot.accounting import ResearchInstrument, ResearchCosts


def candle(time="2025-01-01T00:00:00Z"):
    return Candle("NAS.fixture", time, 100, 102, 99, 101, 1, 0)


def evidence(**values):
    return replace(TimebaseEvidence("VERIFIED_UTC", "MOCK independently timed fixture",
                                    "2025-01-02T00:00:00Z", "H1", 0, 0), **values)


@pytest.mark.parametrize("timeframe", ["M15", "M30", "H1", "H4"])
def test_future_to_observation_rejected(timeframe):
    with pytest.raises(TimeIntegrityError, match="FUTURE_BAR"):
        validate_bar_times([candle("2025-01-02T04:00:00Z")], evidence(timeframe=timeframe))


@pytest.mark.parametrize("timeframe,seconds", [("M15", 900), ("M30", 1800), ("H1", 3600), ("H4", 14400)])
def test_open_in_past_but_bar_not_complete_rejected(timeframe, seconds):
    obs = datetime.fromtimestamp(1735689600 + seconds - 1, timezone.utc).isoformat()
    with pytest.raises(TimeIntegrityError, match="INCOMPLETE_BAR"):
        validate_bar_times([candle()], evidence(timeframe=timeframe, observed_at_utc=obs))


def test_clock_uncertainty_does_not_allow_early_closed_bar():
    context = evidence(observed_at_utc="2025-01-01T01:00:00Z", clock_uncertainty_seconds=1)
    with pytest.raises(TimeIntegrityError, match="INCOMPLETE_BAR"):
        validate_bar_times([candle()], context)
    validate_bar_times([candle()], replace(context, observed_at_utc="2025-01-01T01:00:01Z"))


@pytest.mark.parametrize("stamp", ["2026-10-25T02:30:00", "2025-01-01T03:00:00+03:00", "not-a-date"])
def test_ambiguous_naive_or_unconverted_local_timestamp_rejected(stamp):
    with pytest.raises(TimeIntegrityError, match="AMBIGUOUS"):
        validate_bar_times([candle(stamp)], evidence())


def test_unverified_dst_policy_is_not_fixed_by_relabeling_as_z():
    with pytest.raises(TimeIntegrityError, match="TIMEBASE_UNVERIFIED"):
        validate_bar_times([candle()], evidence(status="TIMEBASE_UNVERIFIED"))


def test_non_hour_grid_open_rejected():
    with pytest.raises(TimeIntegrityError, match="MISALIGNED_BAR_OPEN"):
        validate_bar_times([candle("2025-01-01T00:15:00Z")], evidence())


def test_explicit_shifted_h4_grid_is_required_not_assumed():
    data = [candle("2025-01-01T02:00:00Z")]
    with pytest.raises(TimeIntegrityError, match="MISALIGNED"):
        validate_bar_times(data, evidence(timeframe="H4"))
    validate_bar_times(data, evidence(timeframe="H4", grid_origin_epoch_seconds=7200))


def test_missing_bars_need_exact_independent_session_evidence():
    data = [candle(), candle("2025-01-01T02:00:00Z")]
    with pytest.raises(TimeIntegrityError, match="MISSING_BAR"):
        validate_bar_times(data, evidence())
    validate_bar_times(data, evidence(allowed_gaps=(("2025-01-01T01:00:00Z", "2025-01-01T02:00:00Z"),)))


def test_duplicate_bar_times_are_ambiguous():
    with pytest.raises(TimeIntegrityError, match="DUPLICATE"):
        validate_bar_times([candle(), candle()], evidence())


def series():
    lower = [dict(time=1735689600+i*900, open=100+i, high=102+i, low=99+i, close=101+i) for i in range(4)]
    higher = [dict(time=1735689600, open=100, high=105, low=99, close=104)]
    return lower, higher


def test_identical_price_movements_align_at_raw_open():
    low, high = series()
    report = alignment_report(low, high, 900, 3600)
    require_complete_alignment(report)
    assert report["matching_windows"] == 1


def test_wrong_relative_offset_missing_slots_and_price_mismatch_rejected():
    low, high = series()
    for report in (alignment_report(low, high, 900, 3600, 3600),
                   alignment_report(low[:-1], high, 900, 3600),
                   alignment_report(low, [dict(high[0], close=103)], 900, 3600)):
        with pytest.raises(TimeIntegrityError, match="ALIGNMENT"):
            require_complete_alignment(report)


def test_common_offset_cannot_be_resolved_by_price_alignment():
    low, high = series()
    shifted_low = [dict(row, time=row["time"]+7200) for row in low]
    shifted_high = [dict(row, time=row["time"]+7200) for row in high]
    assert alignment_report(low, high, 900, 3600)["matching_windows"] == 1
    assert alignment_report(shifted_low, shifted_high, 900, 3600)["matching_windows"] == 1
    assert "UTC/DST NOT established" in alignment_report(low, high, 900, 3600)["scope"]


def test_duplicate_alignment_bar_never_silently_overwrites():
    low, high = series()
    with pytest.raises(TimeIntegrityError, match="Ambiguous"):
        alignment_report([low[0]]+low, high, 900, 3600)


def test_backtest_requires_time_evidence_even_when_financial_economics_exist():
    spec = ResearchInstrument("NAS.fixture", 1, 1, 1, 1, 1, .1, 10, .1,
                              "USD", "USD", "MOCK financial model")
    engine = BacktestEngine(instrument=spec, costs=ResearchCosts(0, 0, 0), volume=1)
    with pytest.raises(TimeIntegrityError, match="TIMEBASE_UNVERIFIED"):
        engine.run_backtest(SimpleNamespace(name="mock"), [candle()])


def test_market_loader_blocks_unverified_timebase_before_broker_access(monkeypatch):
    calls = []
    monkeypatch.setitem(sys.modules, "MetaTrader5", SimpleNamespace(initialize=lambda: calls.append(1)))
    with pytest.raises(TimeIntegrityError, match="TIMEBASE_UNVERIFIED"):
        MarketDataManager().fetch_real_mt5_candles("USTECH100M", "M15", 1)
    assert calls == []


def test_future_broker_bar_cannot_fall_back_to_older_sqlite_cache(tmp_path, monkeypatch):
    manager = MarketDataManager(str(tmp_path/"cache.sqlite"), timebase=evidence(observed_at_utc="2025-01-01T02:00:00Z"))
    manager.store_candles_in_db("NAS.fixture", "H1", [candle()])
    fake = SimpleNamespace(initialize=lambda: True, shutdown=lambda: None, TIMEFRAME_H1=1,
        copy_rates_from_pos=lambda *args: [dict(time=1735700400, open=100, high=102, low=99, close=101,
                                              tick_volume=1, spread=0)])
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake)
    with pytest.raises(TimeIntegrityError, match="FUTURE_BAR"):
        manager.fetch_real_mt5_candles("NAS.fixture", "H1", 1)


def test_timeframe_cannot_be_replaced_under_verified_context():
    with pytest.raises(TimeIntegrityError, match="TIMEFRAME_EVIDENCE_MISMATCH"):
        MarketDataManager(timebase=evidence()).fetch_real_mt5_candles("NAS.fixture", "M15", 1)


def test_independent_audit_future_bar_example_is_rejected():
    with pytest.raises(TimeIntegrityError, match="FUTURE_BAR"):
        validate_bar_times([candle("2026-11-02T10:30:00Z")], evidence(
            observed_at_utc="2026-11-02T08:46:53Z", timeframe="M15"))
    # Conversion itself preserves the raw integer; it cannot establish broker UTC.
    assert datetime.fromtimestamp(1793616499, timezone.utc).isoformat() == "2026-11-02T10:48:19+00:00"


def test_future_stored_quote_cannot_pass_freshness_recheck():
    from bot.market_data import AuthenticatedQuote
    from datetime import timedelta
    manager = MarketDataManager()
    manager.last_quotes["USTECH100M"] = AuthenticatedQuote("USTECH100M", 100, 101,
        (datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(), "MOCK", 1)
    with pytest.raises(RuntimeError, match="future-dated"):
        manager.get_authenticated_quote("USTECH100M")


def test_fractional_or_boolean_alignment_timestamp_rejected():
    lower, higher = series()
    for stamp in (True, float(lower[0]["time"])+.5):
        with pytest.raises(TimeIntegrityError, match="noninteger"):
            alignment_report([dict(lower[0], time=stamp)]+lower[1:], higher, 900, 3600)
