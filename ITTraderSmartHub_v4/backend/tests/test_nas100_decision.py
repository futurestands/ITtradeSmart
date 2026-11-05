"""Decision-framework tests. SYNTHETIC FIXTURES ONLY: they show the checklist logic
behaves as documented; they say nothing about real NAS100 profitability."""
import re
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import pytest

from nas100_fixtures import (MONDAY, UTC, bar, bullish_setup_ltf, flat_series, mirror,
                             uptrend_htf, zigzag)
from nas100 import (BUY, NO_TRADE, SELL, EngineConfig, analyze, analyze_multitimeframe,
                    decide)
from nas100.decision import VALIDATION_STATUS, _Candidate


def run(ltf=None, htf=None, cfg=EngineConfig(), now=None):
    ltf = bullish_setup_ltf() if ltf is None else ltf
    if htf is None:
        htf = uptrend_htf()
        if ltf:
            # Provide a genuinely current closed HTF fixture for each LTF date.
            end = (ltf[-1].time + timedelta(minutes=5)).replace(minute=0, second=0, microsecond=0)
            delta = end - (htf[-1].time + timedelta(hours=1))
            htf = [replace(c, time=c.time + delta) for c in htf]
    return decide(analyze(ltf, 5, cfg), analyze(htf, 60, cfg, min_bars=cfg.htf_min_bars), cfg, now)


# ------------------------------------------------------------------ happy paths
def test_buy_decision_is_complete_explainable_and_unvalidated():
    d = run()
    assert d.action == BUY and d.blockers == ()
    assert d.htf_bias == 'bull' and d.regime == 'NORMAL'
    assert d.entry_zone == (1107, 1122) and d.entry == 1114.5
    assert d.stop < 1094 < d.entry < d.target == 1202.0          # stop below the sweep extreme
    assert d.risk_reward == pytest.approx((d.target - d.entry) / (d.entry - d.stop))
    assert d.risk_reward >= 2.0
    assert any('liquidity swept' in r for r in d.reasons) and any('FVG' in r for r in d.reasons)
    assert 'Close below stop' in d.invalidation
    # Never claims a probability or validation it does not have.
    assert d.model_confidence is None and d.validation_status == VALIDATION_STATUS
    assert d.timeframe_minutes == 5 and d.as_of == datetime(2026, 1, 6, 14, 5, tzinfo=UTC)


def test_sell_is_exact_mirror_of_buy():
    b = run()
    s = run(mirror(bullish_setup_ltf()), mirror(uptrend_htf()))
    assert s.action == SELL and s.htf_bias == 'bear'
    assert s.entry == pytest.approx(4000 - b.entry) and s.stop == pytest.approx(4000 - b.stop)
    assert s.target == pytest.approx(4000 - b.target) and s.risk_reward == pytest.approx(b.risk_reward)
    assert 'Close above stop' in s.invalidation


def test_end_to_end_multitimeframe_pipeline_runs_and_is_deterministic():
    c = bullish_setup_ltf()
    m1 = analyze_multitimeframe(c, 5, [60])
    m2 = analyze_multitimeframe(list(c), 5, [60])
    assert m1 == m2 and 60 in m1.htf
    # Too little history to form an HTF bias from this short series -> must not trade.
    d = decide(m1.ltf, m1.htf[60])
    assert d.action == NO_TRADE and 'HTF_INSUFFICIENT_DATA' in d.blockers


# ------------------------------------------------------------------ blockers
def test_no_htf_context_or_unclosed_htf_bar_blocks():
    a = analyze(bullish_setup_ltf(), 5)
    assert 'NO_HTF_CONTEXT' in decide(a, None).blockers
    late = analyze(zigzag([1000, 1100, 1060, 1180, 1140, 1260, 1220, 1340, 1300], 6,
                          start=datetime(2026, 1, 6, 0, 0, tzinfo=UTC), tf=60, wick=3.0), 60, min_bars=30)
    assert late.as_of > a.as_of                       # fixture built so its last bar closes in the future
    d = decide(a, late)
    assert d.action == NO_TRADE and 'HTF_BAR_NOT_CLOSED' in d.blockers


def test_counter_trend_setup_is_blocked():
    d = run(htf=mirror(uptrend_htf()))                # bullish LTF setup, bearish HTF
    assert d.action == NO_TRADE and d.blockers == ('COUNTER_TREND_TO_HTF_BIAS',)
    assert any('liquidity swept' in r for r in d.reasons)     # explains what it saw


def test_outside_session_and_weekend_block():
    asia = datetime(2026, 1, 6, 3, 0, tzinfo=UTC)
    assert 'OUTSIDE_ALLOWED_SESSION' in run(bullish_setup_ltf(last_open=asia)).blockers
    sat = datetime(2026, 1, 10, 14, 0, tzinfo=UTC)
    assert 'OUTSIDE_ALLOWED_SESSION' in run(bullish_setup_ltf(last_open=sat)).blockers


def test_session_filter_follows_daylight_saving():
    # 12:30 UTC is inside the NY session (08:00-17:00 ET) in July (EDT opens at 12:00 UTC) but not in
    # January (EST opens at 13:00 UTC). A NY-only config isolates the DST effect from London.
    cfg = EngineConfig(allowed_sessions=('new_york',))
    jul = run(bullish_setup_ltf(last_open=datetime(2026, 7, 7, 12, 30, tzinfo=UTC)), cfg=cfg)
    jan = run(bullish_setup_ltf(last_open=datetime(2026, 1, 6, 12, 30, tzinfo=UTC)), cfg=cfg)
    assert 'OUTSIDE_ALLOWED_SESSION' not in jul.blockers
    assert 'OUTSIDE_ALLOWED_SESSION' in jan.blockers


def test_stale_data_blocks_only_when_now_supplied():
    ltf = bullish_setup_ltf()
    as_of = datetime(2026, 1, 6, 14, 5, tzinfo=UTC)
    assert run(ltf, now=as_of + timedelta(minutes=1)).data_fresh is True
    stale = run(ltf, now=as_of + timedelta(hours=1))
    assert stale.action == NO_TRADE and 'STALE_DATA' in stale.blockers and stale.data_fresh is False
    assert run(ltf).data_fresh is None


def test_spread_filter():
    ltf = bullish_setup_ltf()
    ltf[-1] = replace(ltf[-1], spread=50.0)
    assert 'SPREAD_TOO_WIDE' in run(ltf, cfg=EngineConfig(max_spread_points=20.0)).blockers
    assert run(ltf).action == BUY                      # filter disabled by default
    ltf[-1] = replace(ltf[-1], spread=None)
    assert 'UNKNOWN_SPREAD' in run(ltf, cfg=EngineConfig(max_spread_points=20.0)).blockers


def test_insufficient_data_never_trades():
    for n in (0, 1, 30, 59):
        d = decide(analyze(flat_series(n), 5), None)
        assert d.action == NO_TRADE and d.blockers == ('INSUFFICIENT_DATA',)
    d = decide(analyze(bullish_setup_ltf()[:50], 5), analyze(uptrend_htf(), 60, min_bars=30))
    assert d.action == NO_TRADE and 'INSUFFICIENT_DATA' in d.blockers


def test_flat_market_blocks_with_regime_and_consolidation():
    d = decide(analyze(flat_series(150), 5), analyze(uptrend_htf(), 60, min_bars=30))
    assert d.action == NO_TRADE and 'REGIME_FLAT' in d.blockers and 'CONSOLIDATION' in d.blockers


def test_recent_missing_candles_block_but_old_ones_do_not():
    recent = bullish_setup_ltf()
    del recent[70:73]                                  # 15 minutes missing, inside the recent lookback
    d = run(recent)
    assert d.action == NO_TRADE and 'DATA_GAP_RECENT' in d.blockers
    old = bullish_setup_ltf()
    del old[14:17]                                     # same fault, but long before the decision window
    assert analyze(old, 5).quality.fault_gaps and run(old).action == BUY


def test_old_long_gap_is_reported_without_inferring_closure():
    c = bullish_setup_ltf()
    gap = timedelta(hours=2)
    c = c[:20] + [replace(x, time=x.time + gap) for x in c[20:]]
    a = analyze(c, 5)
    assert a.quality.gaps and a.quality.fault_gaps == a.quality.gaps
    assert 'DATA_GAP_RECENT' not in decide(a, analyze(uptrend_htf(), 60, min_bars=30)).blockers


def test_reward_risk_and_stop_width_gates():
    assert run(cfg=EngineConfig(min_rr=50.0)).blockers == ('RR_BELOW_MINIMUM',)
    assert run(cfg=EngineConfig(max_stop_atr=0.5)).blockers == ('STOP_TOO_WIDE',)


def test_filled_fvg_or_invalidated_setup_is_no_trade():
    filled = bullish_setup_ltf() + [bar(datetime(2026, 1, 6, 14, 5, tzinfo=UTC), 1120, 1121, 1100, 1105)]
    d = run(filled)
    assert d.action == NO_TRADE and d.blockers == ('NO_SETUP',)            # FVG 1107-1122 fully taken at 1100
    broken = bullish_setup_ltf() + [bar(datetime(2026, 1, 6, 14, 5, tzinfo=UTC), 1120, 1121, 1050, 1060)]
    assert run(broken).action == NO_TRADE


def test_no_setup_in_plain_trend_is_no_trade():
    d = decide(analyze(zigzag([800, 900, 860, 960, 920, 1040, 1000, 1200, 1150], 8, start=datetime(2026, 1, 6, 6, 0, tzinfo=UTC)), 5),
               analyze(uptrend_htf(), 60, min_bars=30))
    assert d.action == NO_TRADE and d.entry is None and d.stop is None and d.target is None


def test_conflicting_setups_force_no_trade():
    def fake(ltf, d, cfg):
        return _Candidate(d, True, (), (f'{d} setup',), (1.0, 2.0), 1.5, 1.0, 9.0, 8.0)

    with mock.patch('nas100.decision._build_candidate', side_effect=fake):
        d = run()
    assert d.action == NO_TRADE and 'CONFLICTING_SETUPS' in d.blockers


def test_gap_scenario_does_not_crash_and_decision_stays_conservative():
    c = bullish_setup_ltf()
    c[-1] = replace(c[-1], open=1180.0, high=1185.0, low=1170.0, close=1175.0)     # large price gap on last bar
    d = run(c)
    assert d.action in (BUY, NO_TRADE)                 # defined outcome, no exception
    assert d.action == NO_TRADE or d.stop < d.entry < d.target


def test_decision_is_deterministic():
    assert run() == run() and run(now=datetime(2026, 1, 6, 14, 6, tzinfo=UTC)) == run(now=datetime(2026, 1, 6, 14, 6, tzinfo=UTC))


def test_decision_ignores_candles_after_its_own_as_of():
    base = bullish_setup_ltf()
    early = run(base)
    # Appending candles later produces a different (later) decision but cannot rewrite the earlier one.
    later = run(base + [bar(datetime(2026, 1, 6, 14, 5, tzinfo=UTC), 1120, 1121, 1100, 1105)])
    assert early.action == BUY and later.action == NO_TRADE
    assert run(base) == early


# ------------------------------------------------------------------ safety guard
def test_package_has_no_execution_network_or_credential_code():
    root = Path(__file__).resolve().parents[1] / 'nas100'
    banned = re.compile(r'import\s+MetaTrader5|from\s+MetaTrader5|order_send|order_check|os\.environ|'
                        r'\bsocket\b|\brequests\b|urllib|subprocess|\bopen\(|password|api[_-]?key', re.I)
    offenders = []
    for path in root.glob('*.py'):
        for n, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if banned.search(line):
                offenders.append(f'{path.name}:{n}: {line.strip()}')
    assert offenders == []
