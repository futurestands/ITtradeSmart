"""Unit tests with SYNTHETIC bars, not historical NAS100 performance data."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import pytest

from nas100.backtest import FillAssumptions, Outcome, simulate_signal, summarize
from nas100.candles import Candle
from nas100.decision import Decision, BUY, SELL, NO_TRADE

T0 = datetime(2026, 8, 5, 13, 0, tzinfo=timezone.utc)


def cs(*bars):
    return [Candle(T0 + timedelta(minutes=5*i), *b) for i, b in enumerate(bars)]


def dec(action=BUY, entry=100., stop=98., target=104., as_of=None):
    return Decision(action, 5, as_of or T0 + timedelta(minutes=5), True,
                    'NORMAL', 'bull', 'setup', None, entry, stop, target, 2., (), (), None)


BASE = FillAssumptions(point_size=0.1, spread_points=2, slippage_points_per_side=1,
                       commission_points_round_trip=0, max_wait_bars=2, max_hold_bars=3)


def test_signal_is_never_filled_on_its_own_candle():
    bars = cs((100, 110, 90, 100), (108, 109, 107, 108), (107, 108, 106, 107))
    r = simulate_signal(dec(), bars, 0, BASE)
    assert r.status == 'NO_FILL'


def test_signal_future_knowledge_timestamp_rejected():
    bars = cs((100, 101, 99, 100), (100, 101, 99, 100))
    with pytest.raises(ValueError, match='timestamp'):
        simulate_signal(dec(as_of=T0 + timedelta(minutes=10)), bars, 0, BASE)


def test_buy_target_cost_deducted_once():
    bars = cs((100, 101, 99, 100), (102, 103, 100, 101), (101, 104, 101, 103))
    r = simulate_signal(dec(), bars, 0, BASE)
    assert r.status == 'TARGET'
    assert r.entry_index == 1 and r.exit_index == 2
    assert r.gross_r == 2
    assert r.costs_r == pytest.approx(.2)
    assert r.net_r == pytest.approx(1.8)


def test_buy_stop_first_when_both_hit_in_same_bar():
    bars = cs((100, 101, 99, 100), (100, 105, 97, 102))
    r = simulate_signal(dec(), bars, 0, BASE)
    assert r.status == 'STOP'
    assert r.net_r < -1


def test_buy_stop_gap_uses_worse_open():
    bars = cs((100, 101, 99, 100), (99.5, 101, 99, 100), (96, 97, 95, 96))
    r = simulate_signal(dec(), bars, 0, BASE)
    assert r.status == 'STOP' and r.exit_price == 96
    assert r.gross_r == -2


def test_sell_target():
    bars = cs((100, 101, 99, 100), (99, 100, 98, 99), (98, 99, 94, 95))
    r = simulate_signal(dec(SELL, 100, 102, 96), bars, 0, BASE)
    assert r.status == 'TARGET' and r.net_r == pytest.approx(1.8)


def test_sell_stop_gap():
    bars = cs((100, 101, 99, 100), (100, 101, 99, 100), (105, 106, 104, 105))
    r = simulate_signal(dec(SELL, 100, 102, 96), bars, 0, BASE)
    assert r.status == 'STOP' and r.exit_price == 105


def test_timeout_measured_on_fill_index():
    cfg = replace(BASE, max_hold_bars=2)
    bars = cs((100, 101, 99, 100), (100, 101, 99, 100.5),
              (100.5, 103, 99.5, 101.0), (101, 102, 100, 100.5))
    r = simulate_signal(dec(), bars, 0, cfg)
    assert r.status == 'TIMEOUT' and r.exit_index == 2
    assert r.gross_r == pytest.approx(.5)


def test_open_position_at_end_is_incomplete_not_profitable():
    bars = cs((100, 101, 99, 100), (100, 101, 99, 100.5))
    r = simulate_signal(dec(), bars, 0, BASE)
    assert r.status == 'INCOMPLETE' and r.net_r is None


def test_unfilled_order_at_end_is_incomplete():
    bars = cs((100, 101, 99, 100), (104, 105, 103, 104))
    r = simulate_signal(dec(), bars, 0, BASE)
    assert r.status == 'INCOMPLETE' and r.entry_index is None


def test_non_trade_rejected():
    bars = cs((100, 101, 99, 100), (100, 101, 99, 100))
    with pytest.raises(ValueError, match='actionable'):
        simulate_signal(dec(NO_TRADE), bars, 0, BASE)


@pytest.mark.parametrize('bad', [
    dict(point_size=0), dict(spread_points=-1), dict(spread_points=float('nan')),
    dict(slippage_points_per_side=float('inf')), dict(max_wait_bars=0),
    dict(max_hold_bars=True), dict(commission_points_round_trip=-1),
])
def test_invalid_execution_assumptions_fail_closed(bad):
    with pytest.raises(ValueError):
        replace(BASE, **bad)


def test_bad_geometry_rejected():
    bars = cs((100, 101, 99, 100), (100, 101, 99, 100))
    with pytest.raises(ValueError, match='geometry'):
        simulate_signal(dec(entry=100, stop=101, target=104), bars, 0, BASE)


def test_summary_includes_no_fills_and_no_fake_win_rate():
    outcomes = (Outcome(0, BUY, 'TARGET', 1, 2, 100, 104, 2, 1.8, .2),
                Outcome(4, BUY, 'STOP', 5, 6, 100, 98, -1, -1.2, .2),
                Outcome(8, BUY, 'NO_FILL', None, None, None, None, None, None, None),
                Outcome(10, BUY, 'INCOMPLETE', 11, None, 100, None, None, None, .2))
    s = summarize(outcomes)
    assert (s.signals, s.completed, s.no_fill, s.incomplete) == (4, 2, 1, 1)
    assert (s.wins, s.losses) == (1, 1)
    assert s.expectancy_r == pytest.approx(.3)
    assert s.max_drawdown_r == pytest.approx(1.2)
    empty = summarize([])
    assert empty.expectancy_r is None and empty.max_drawdown_r is None
