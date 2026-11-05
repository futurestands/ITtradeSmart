"""M1 adversarial regressions for the conservative research simulator.

SYNTHETIC BARS ONLY. These are software-correctness checks on the OHLC proxy
simulator and causal as-of alignment. They are NOT broker data, NOT a NAS100
backtest, and provide no evidence of market edge, execution quality or profit.

Gaps covered here that the pre-M1 suite did not pin down:
  * exact stop-first accounting (gross R, one-off cost, net R) on ambiguous bars;
  * favourable gaps never improve a target exit, adverse gaps worsen a stop exit;
  * NO_FILL / INCOMPLETE(never filled) / INCOMPLETE(filled, still open) separation;
  * spread floor, slippage, commission and per-bar spreads charged once per R;
  * HTF close-time boundaries and rejection of unclosed/future HTF context.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from nas100.analysis import analyze, analyze_multitimeframe
from nas100.backtest import FillAssumptions, simulate_signal, summarize
from nas100.candles import Candle
from nas100.config import EngineConfig
from nas100.decision import BUY, SELL, NO_TRADE, Decision, decide
from nas100.timeframes import htf_closed_by, resample

T0 = datetime(2026, 8, 5, 13, 0, tzinfo=timezone.utc)


def cs(*bars):
    """Synthetic 5-minute UTC bars. Tuples are (o,h,l,c[,volume,spread])."""
    return [Candle(T0 + timedelta(minutes=5 * i), *b) for i, b in enumerate(bars)]


def dec(action=BUY, entry=100., stop=98., target=104., as_of=None):
    return Decision(action, 5, as_of or T0 + timedelta(minutes=5), True,
                    'NORMAL', 'bull', 'setup', None, entry, stop, target, 2., (), (), None)


BASE = FillAssumptions(point_size=0.1, spread_points=2, slippage_points_per_side=1,
                       commission_points_round_trip=0, max_wait_bars=2, max_hold_bars=3)


def trend_bars(n=30):
    return [Candle(T0 + timedelta(minutes=5 * i), 200 + i * .1, 200.3 + i * .1,
                   199.7 + i * .1, 200.1 + i * .1, 100, 2) for i in range(n)]


# ---------------------------------------------------------------------------
# 1. Stop-first ambiguous-bar accounting
# ---------------------------------------------------------------------------

def test_ambiguous_bar_stop_first_exact_accounting():
    # Bar 1 trades through BOTH the 104 target and the 98 stop. The open is
    # marketable at the 100 limit, so the target is genuinely reachable in this
    # bar; stop-first must still win, and costs must be charged exactly once.
    bars = cs((100, 101, 99, 100), (100, 105, 97, 102))
    r = simulate_signal(dec(), bars, 0, BASE)
    assert bars[1].high >= 104 and bars[1].low <= 98
    assert r.status == 'STOP'
    assert r.entry_index == 1 and r.exit_index == 1
    assert r.entry_price == 100
    assert r.exit_price == 98                      # min(stop, open), never 104
    assert r.gross_r == pytest.approx(-1.0)
    assert r.costs_r == pytest.approx(.2)         # 0.1*(2+2*1+0)/2, once
    assert r.net_r == pytest.approx(-1.2)
    assert r.spread_points_applied == 2


def test_ambiguous_bar_never_grants_favourable_target_exit():
    # High runs far beyond target; no price improvement may be credited.
    bars = cs((100, 101, 99, 100), (100, 110, 97, 109))
    r = simulate_signal(dec(), bars, 0, BASE)
    assert r.status == 'STOP'
    assert r.exit_price == 98 and r.exit_price != 110
    assert r.gross_r == pytest.approx(-1.0)


def test_sell_ambiguous_bar_stop_first_exact_accounting():
    bars = cs((100, 101, 99, 100), (100, 105, 95, 96))
    r = simulate_signal(dec(SELL, 100, 102, 96), bars, 0, BASE)
    # SELL: high >= stop 102 and low <= target 96 in the same bar.
    assert bars[1].high >= 102 and bars[1].low <= 96
    assert r.status == 'STOP'
    assert r.exit_price == 102                    # max(stop, open=100)
    assert r.gross_r == pytest.approx(-1.0)
    assert r.net_r == pytest.approx(-1.2)


def test_favourable_gap_beyond_target_still_exits_at_target():
    # Bar 2 gaps up to 108; a target at 104 must not be improved to 108.
    bars = cs((100, 101, 99, 100), (100, 101, 99, 100), (108, 109, 107, 108))
    r = simulate_signal(dec(), bars, 0, BASE)
    assert r.status == 'TARGET'
    assert r.exit_price == 104
    assert r.gross_r == pytest.approx(2.0)
    assert r.net_r == pytest.approx(1.8)


def test_sell_favourable_gap_beyond_target_still_exits_at_target():
    bars = cs((100, 101, 99, 100), (100, 101, 99, 100), (92, 93, 91, 92))
    r = simulate_signal(dec(SELL, 100, 102, 96), bars, 0, BASE)
    assert r.status == 'TARGET' and r.exit_price == 96
    assert r.gross_r == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# 2. Adverse gap-fill behaviour
# ---------------------------------------------------------------------------

def test_adverse_gap_on_fill_bar_uses_worse_open_for_buy():
    # A gap-down open through both entry and stop. The limit still fills at the
    # specified 100 (no favourable improvement), and the stop exits at the open.
    bars = cs((100, 101, 99, 100), (96, 101, 95, 100))
    r = simulate_signal(dec(), bars, 0, BASE)
    assert r.status == 'STOP'
    assert r.entry_price == 100
    assert r.exit_price == 96                     # min(stop=98, open=96)
    assert r.gross_r == pytest.approx(-2.0)
    assert r.net_r == pytest.approx(-2.2)


def test_adverse_gap_on_fill_bar_uses_worse_open_for_sell():
    bars = cs((100, 101, 99, 100), (105, 106, 99, 100))
    r = simulate_signal(dec(SELL, 100, 102, 96), bars, 0, BASE)
    assert r.status == 'STOP'
    assert r.entry_price == 100
    assert r.exit_price == 105                    # max(stop=102, open=105)
    assert r.gross_r == pytest.approx(-2.5)


def test_adverse_gap_on_later_bar_buy_and_sell():
    buy = simulate_signal(dec(), cs((100, 101, 99, 100), (100, 101, 99, 100),
                                    (96, 97, 95, 96)), 0, BASE)
    sell = simulate_signal(dec(SELL, 100, 102, 96),
                           cs((100, 101, 99, 100), (100, 101, 99, 100),
                              (105, 106, 104, 105)), 0, BASE)
    assert buy.status == 'STOP' and buy.exit_price == 96 and buy.exit_index == 2
    assert sell.status == 'STOP' and sell.exit_price == 105 and sell.exit_index == 2


def test_adverse_gap_never_reduces_charged_costs():
    bars = cs((100, 101, 99, 100, 100, 2), (100, 101, 99, 100, 100, 2),
              (96, 97, 95, 96, 100, 2))
    r = simulate_signal(dec(), bars, 0, BASE)
    assert r.status == 'STOP'
    assert r.costs_r == pytest.approx(.2)         # unchanged by the gap
    assert r.spread_points_applied == 2


# ---------------------------------------------------------------------------
# 3. NO_FILL vs INCOMPLETE separation
# ---------------------------------------------------------------------------

def test_no_fill_requires_the_entire_wait_window_to_be_observed():
    never = (104, 105, 103, 104)
    full_window = cs((100, 101, 99, 100), never, never)   # last == 0 + max_wait_bars
    truncated = cs((100, 101, 99, 100), never)            # last <  0 + max_wait_bars
    a = simulate_signal(dec(), full_window, 0, BASE)
    b = simulate_signal(dec(), truncated, 0, BASE)
    assert a.status == 'NO_FILL' and a.entry_index is None and a.costs_r is None
    assert b.status == 'INCOMPLETE' and b.entry_index is None and b.costs_r is None
    assert a.net_r is None and b.net_r is None

    tighter = replace(BASE, max_wait_bars=1)
    assert simulate_signal(dec(), truncated, 0, tighter).status == 'NO_FILL'
    assert simulate_signal(dec(), truncated, 0, replace(BASE, max_wait_bars=2)).status == 'INCOMPLETE'


def test_incomplete_after_fill_has_entry_but_no_realised_outcome():
    bars = cs((100, 101, 99, 100), (100, 101, 99, 100.5))
    r = simulate_signal(dec(), bars, 0, BASE)
    assert r.status == 'INCOMPLETE'
    assert r.entry_index == 1 and r.entry_price == 100
    assert r.exit_index is None and r.exit_price is None
    assert r.gross_r is None and r.net_r is None
    assert r.costs_r == pytest.approx(.2)         # scenario cost, not a realised P&L
    assert r.spread_points_applied == 2


def test_summary_never_treats_unfilled_or_open_outcomes_as_wins_or_losses():
    from nas100.backtest import Outcome
    outcomes = (
        Outcome(0, BUY, 'NO_FILL', None, None, None, None, None, None, None),
        Outcome(2, BUY, 'INCOMPLETE', None, None, None, None, None, None, None),
        Outcome(4, BUY, 'INCOMPLETE', 5, None, 100, None, None, None, .2),
    )
    s = summarize(outcomes)
    assert (s.signals, s.completed, s.no_fill, s.incomplete) == (3, 0, 1, 2)
    assert (s.wins, s.losses) == (0, 0)
    assert s.expectancy_r is None and s.gross_r is None and s.net_r is None
    assert s.max_drawdown_r is None
    assert s.validation == 'UNVALIDATED_RESEARCH_ONLY'


# ---------------------------------------------------------------------------
# 4. Spread / slippage / commission stress
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('overrides, expected_cost_r', [
    ({}, .2),
    ({'slippage_points_per_side': 5}, .6),       # 0.1*(2+2*5+0)/2
    ({'commission_points_round_trip': 10}, .7),  # 0.1*(2+2+10)/2
    ({'point_size': 1.0}, 2.0),                  # 1.0*(2+2)/2
    ({'spread_points': 8}, .5),                  # 0.1*(8+2)/2
])
def test_round_trip_costs_charged_once_and_scale_linearly(overrides, expected_cost_r):
    cfg = replace(BASE, **overrides)
    bars = cs((100, 101, 99, 100), (102, 103, 100, 101), (101, 104, 101, 103))
    r = simulate_signal(dec(), bars, 0, cfg)
    assert r.status == 'TARGET'
    assert r.gross_r == pytest.approx(2.0)
    assert cfg.total_cost_price == pytest.approx(expected_cost_r * 2)   # risk = 2
    assert r.costs_r == pytest.approx(expected_cost_r)
    assert r.net_r == pytest.approx(2.0 - expected_cost_r)
    assert abs(r.net_r - (r.gross_r - r.costs_r)) < 1e-12


def test_exit_bar_spread_widens_never_narrows_cost_floor():
    # Entry bar spread 50 and exit bar spread 2: the floor must stay at 50.
    bars = cs((100, 101, 99, 100, 100, 2),
              (102, 103, 100, 101, 100, 50),
              (101, 104, 101, 103, 100, 2))
    r = simulate_signal(dec(), bars, 0, BASE)
    assert r.status == 'TARGET'
    assert r.spread_points_applied == 50
    assert r.costs_r == pytest.approx(2.6)       # 0.1*(50+2)/2
    assert r.gross_r == pytest.approx(2.0)       # gross win preserved
    assert r.net_r == pytest.approx(-.6)         # ...but net loss; no clamping


def test_small_observed_spread_cannot_reduce_configured_floor():
    bars = cs((100, 101, 99, 100, 100, 1),
              (102, 103, 100, 101, 100, 1),
              (101, 104, 101, 103, 100, 1))
    r = simulate_signal(dec(), bars, 0, BASE)
    assert r.spread_points_applied == 2
    assert r.costs_r == pytest.approx(.2)


def test_extreme_costs_are_finite_and_never_silently_dropped():
    cfg = FillAssumptions(point_size=1.0, spread_points=200, slippage_points_per_side=0,
                          commission_points_round_trip=0, max_wait_bars=2, max_hold_bars=3)
    bars = cs((100, 101, 99, 100), (102, 103, 100, 101), (101, 104, 101, 103))
    r = simulate_signal(dec(), bars, 0, cfg)
    assert r.costs_r == pytest.approx(100.0)
    assert r.net_r == pytest.approx(-98.0)
    assert r.gross_r == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# 5. HTF as-of alignment and future-data leakage
# ---------------------------------------------------------------------------

def test_htf_closed_by_includes_only_bars_closed_at_or_before_as_of():
    b0 = Candle(T0, 100, 101, 99, 100, 100, 2)
    b1 = Candle(T0 + timedelta(minutes=15), 100, 101, 99, 100, 100, 2)
    bars = [b0, b1]
    assert htf_closed_by(bars, 15, T0 + timedelta(minutes=15)) == [b0]
    assert htf_closed_by(bars, 15, T0 + timedelta(minutes=14)) == []
    assert htf_closed_by(bars, 15, T0 + timedelta(minutes=30)) == bars
    assert htf_closed_by(bars, 15, T0) == []


def test_htf_closed_by_uses_target_timeframe_not_candle_timeframe():
    bar = Candle(T0, 100, 101, 99, 100, 100, 2)
    assert htf_closed_by([bar], 60, T0 + timedelta(minutes=15)) == []
    assert htf_closed_by([bar], 60, T0 + timedelta(minutes=60)) == [bar]


def test_resample_never_publishes_an_unfinished_bucket():
    one = (100, 101, 99, 100, 100, 2)
    assert resample(cs(one, one), 5, 15) == []
    source = cs(one, one, one)
    out = resample(source, 5, 15)
    assert len(out) == 1 and out[0].time == T0
    # The emitted bar's close equals the last constituent bar's close: its
    # information is knowable only then, not at the bucket start.
    assert out[0].time + timedelta(minutes=15) == source[-1].time + timedelta(minutes=5)


def test_multitimeframe_htf_never_closes_after_ltf():
    cfg = EngineConfig(min_bars=10, htf_min_bars=3, regime_min_history=5, regime_lookback=10)
    bars = trend_bars(30)
    for n in (20, 23, 30):
        ctx = analyze_multitimeframe(bars[:n], 5, [15], cfg)
        assert ctx.htf[15].as_of <= ctx.ltf.as_of, f'future HTF bar at prefix {n}'


def test_future_clock_blocks_decision():
    cfg = EngineConfig(min_bars=10, htf_min_bars=3, regime_min_history=5, regime_lookback=10)
    ltf = analyze(trend_bars(30), 5, cfg)
    d = decide(ltf, None, cfg, now=ltf.as_of - timedelta(minutes=1), live=False)
    assert d.action == NO_TRADE
    assert 'FUTURE_DATA' in d.blockers
    assert d.data_fresh is False


def test_unclosed_future_htf_context_is_rejected():
    cfg = EngineConfig(min_bars=10, htf_min_bars=3, regime_min_history=5, regime_lookback=10)
    bars = trend_bars(30)
    ltf = analyze(bars[:20], 5, cfg)
    htf = analyze(resample(bars, 5, 15), 15, cfg, min_bars=3)
    assert htf.as_of > ltf.as_of
    d = decide(ltf, htf, cfg, now=ltf.as_of, live=False)
    assert d.action == NO_TRADE
    assert 'HTF_BAR_NOT_CLOSED' in d.blockers


def test_completed_outcome_is_invariant_to_appended_future_bars():
    base = cs((100, 101, 99, 100), (102, 103, 100, 101), (101, 104, 101, 103))
    future = [Candle(T0 + timedelta(minutes=5 * i), 300 + i, 301 + i, 299 + i,
                     300 + i, 100, 2) for i in range(3, 13)]
    first = simulate_signal(dec(), base, 0, BASE)
    extended = simulate_signal(dec(), base + future, 0, BASE)
    assert first.status == 'TARGET'
    assert first == extended, 'a completed outcome must not depend on later bars'


def test_decision_timestamp_must_equal_signal_candle_close():
    bars = cs((100, 101, 99, 100), (100, 101, 99, 100))
    for wrong in (T0, T0 + timedelta(minutes=10), T0 + timedelta(minutes=15)):
        with pytest.raises(ValueError, match='timestamp'):
            simulate_signal(dec(as_of=wrong), bars, 0, BASE)
    missing = Decision(BUY, 5, None, True, 'NORMAL', 'bull', 'setup', None,
                       100., 98., 104., 2., (), (), None)
    with pytest.raises(ValueError, match='timestamp'):
        simulate_signal(missing, bars, 0, BASE)
