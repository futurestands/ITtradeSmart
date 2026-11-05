"""Detector tests (swings, structure, FVG, sweeps, volatility) plus look-ahead and
determinism properties. SYNTHETIC FIXTURES ONLY: these prove the algorithms do what
their documented definitions say, not that they make money on NAS100."""
import random
from datetime import timedelta

import pytest

from nas100_fixtures import MONDAY, bar, bullish_setup_ltf, candles_from_closes, flat_series, mirror, zigzag
from nas100 import Candle, EngineConfig, analyze
from nas100.fvg import detect_fvgs, fvg_status
from nas100.swings import detect_swings, trend_from_swings
from nas100.volatility import atr_series, consolidation_series, regime_series

T = lambda i: MONDAY + timedelta(minutes=5 * i)
UP_DOWN = [100, 120, 110, 130, 118, 140, 105]


# ------------------------------------------------------------------ swings
def test_swing_indices_confirmation_and_labels_on_valid_uptrend():
    sw = detect_swings(zigzag(UP_DOWN, 5), 2, 2)
    got = [(s.index, s.confirmed_index, s.kind, s.label) for s in sw]
    assert got == [(5, 7, 'high', None), (10, 12, 'low', None), (15, 17, 'high', 'HH'),
                   (20, 22, 'low', 'HL'), (25, 27, 'high', 'HH')]
    assert trend_from_swings(sw) == 'bull'


def test_lower_highs_and_lower_lows_labelled_in_downtrend():
    sw = detect_swings(zigzag([140, 110, 130, 100, 120, 90, 115], 5), 2, 2)
    highs = [s.label for s in sw if s.kind == 'high']
    lows = [s.label for s in sw if s.kind == 'low']
    assert highs == [None, 'LH'] and lows[:1] == [None] and set(lows[1:]) == {'LL'}
    assert trend_from_swings(sw) == 'bear'


def test_mixed_structure_is_range_and_sparse_is_unknown():
    sw = detect_swings(zigzag([100, 120, 110, 130, 112, 125], 5), 2, 2)   # HH then HL? lows 110,112 -> HL; highs 120,130 -> HH
    assert trend_from_swings(sw) == 'bull'
    sw2 = detect_swings(zigzag([100, 130, 110, 120, 105, 125], 5), 2, 2)  # LH (130->120) with LL (110->105)
    assert trend_from_swings(sw2) == 'bear'
    sw3 = detect_swings(zigzag([100, 130, 110, 120, 112, 125], 5), 2, 2)  # LH with HL -> contracting range
    assert trend_from_swings(sw3) == 'range'
    assert trend_from_swings([]) == 'unknown'


def test_equal_highs_are_not_swings_and_flat_market_has_none():
    assert detect_swings(flat_series(50), 2, 2) == []
    c = [bar(T(i), 100, 100 + (5 if i == 5 else 0) + (5 if i == 6 else 0), 99, 100) for i in range(12)]
    assert not [s for s in detect_swings(c, 2, 2) if s.kind == 'high']      # bars 5 and 6 tie -> neither is a pivot


def test_swing_params_validated():
    with pytest.raises(ValueError):
        detect_swings(flat_series(5), 0, 2)


def test_swing_not_reported_without_right_bars():
    sw = detect_swings(zigzag([100, 120], 5), 2, 2)       # peak is the final bar
    assert sw == []


# ------------------------------------------------------------------ structure
def test_bos_and_choch_exact_events():
    a = analyze(zigzag(UP_DOWN, 5), 5)
    got = [(e.kind, e.direction, e.index, e.level, e.initial) for e in a.events]
    assert got == [('BOS', 'bull', 14, 122.0, True),
                   ('BOS', 'bull', 24, 132.0, False),
                   ('CHoCH', 'bear', 29, 116.0, False)]
    assert a.trend == 'bear'


def test_wick_through_level_without_close_is_not_a_break():
    c = zigzag([100, 120, 110, 119], 5)                      # stays below the 122 swing high
    level = max(x.high for x in c[:8])                       # swing high price (122)
    assert level == 122 and max(x.close for x in c[8:]) < level
    spike = bar(T(len(c)), 119, level + 8, 118, level - 1)   # wick above, close below
    assert analyze(c + [spike], 5).events == ()
    # An equal close is not a break either (strictly greater required).
    eq = bar(T(len(c)), 119, level + 8, 118, level)
    assert analyze(c + [eq], 5).events == ()
    # Closing beyond it is.
    brk = bar(T(len(c)), 119, level + 8, 118, level + 1)
    ev = analyze(c + [brk], 5).events
    assert [(e.kind, e.index, e.level) for e in ev] == [('BOS', len(c), 122.0)]


def test_level_can_only_break_once_and_initial_break_is_bos_not_choch():
    a = analyze(zigzag([100, 120, 110, 130, 125, 135, 128, 150], 5), 5)
    assert a.events[0].kind == 'BOS' and a.events[0].initial
    assert len({e.swing_index for e in a.events}) == len(a.events)


def test_invalid_structure_no_events_in_tight_range():
    a = analyze(candles_from_closes([100 + (1 if i % 2 else -1) for i in range(60)]), 5)
    assert a.events == ()


def test_conflicting_double_break_emits_nothing(monkeypatch):
    from nas100.structure import detect_structure_events
    from nas100.swings import Swing
    c = [bar(T(i), 100, 101, 99, 100) for i in range(6)] + [bar(T(6), 100, 101, 99, 100)]
    swings = [Swing(1, 3, 'high', 90.0), Swing(2, 3, 'low', 110.0)]      # inverted references
    events, trend = detect_structure_events(c, swings)
    assert events == [] and set(trend) == {'none'}


# ------------------------------------------------------------------ FVG
def _atr(n, v=1.0):
    return [v] * n


def test_bullish_and_bearish_fvg_definitions():
    bull = [bar(T(0), 10, 11, 9, 10), bar(T(1), 10, 16, 10, 15), bar(T(2), 15, 17, 13, 16)]
    f = detect_fvgs(bull, _atr(3), 0.25)
    assert [(x.direction, x.detected_index, x.bottom, x.top) for x in f] == [('bull', 2, 11, 13)]
    bear = [bar(T(0), 20, 21, 19, 20), bar(T(1), 20, 20, 14, 15), bar(T(2), 15, 17, 13, 14)]
    g = detect_fvgs(bear, _atr(3), 0.25)
    assert [(x.direction, x.bottom, x.top) for x in g] == [('bear', 17, 19)]


def test_overlapping_candles_have_no_fvg_and_min_size_filters_small_gaps():
    c = [bar(T(0), 10, 12, 9, 11), bar(T(1), 11, 14, 10, 13), bar(T(2), 13, 15, 11.5, 14)]  # low 11.5 <= high0 12
    assert detect_fvgs(c, _atr(3), 0.25) == []
    tiny = [bar(T(0), 10, 11, 9, 10), bar(T(1), 10, 12, 10, 12), bar(T(2), 12, 13, 11.1, 12.5)]  # gap 0.1
    assert detect_fvgs(tiny, _atr(3, 1.0), 0.25) == []
    assert len(detect_fvgs(tiny, _atr(3, 0.2), 0.25)) == 1
    assert detect_fvgs(tiny, [None] * 3, 0.25) == []          # ATR undefined -> nothing reported


def test_price_gap_creates_fvg_scaled_by_gap_aware_atr():
    c = [bar(T(i), 100, 101, 99, 100) for i in range(20)]
    c.append(bar(T(20), 150, 152, 149, 151))                  # +49 opening gap
    c.append(bar(T(21), 151, 153, 150, 152))
    a = analyze(c, 5)
    assert any(f.direction == 'bull' and f.detected_index == 21 and f.size > 40 for f in a.fvgs)
    assert a.atr[20] > a.atr[19] + 2                           # true range includes the gap


def test_fvg_status_depends_only_on_candles_up_to_as_of():
    base = [bar(T(0), 10, 11, 9, 10), bar(T(1), 10, 16, 10, 15), bar(T(2), 15, 17, 13, 16)]
    f = detect_fvgs(base, _atr(3), 0.25)[0]                    # zone 11-13
    path = base + [bar(T(3), 16, 17, 12.5, 16.5), bar(T(4), 16, 16.5, 10.5, 11)]
    assert fvg_status(f, path, 2) == 'open'
    assert fvg_status(f, path, 3) == 'partial'
    assert fvg_status(f, path, 4) == 'filled'
    bear = [bar(T(0), 20, 21, 19, 20), bar(T(1), 20, 20, 14, 15), bar(T(2), 15, 17, 13, 14)]
    g = detect_fvgs(bear, _atr(3), 0.25)[0]                    # zone 17-19
    assert fvg_status(g, bear + [bar(T(3), 14, 18, 14, 15)], 3) == 'partial'
    assert fvg_status(g, bear + [bar(T(3), 14, 19.5, 14, 15)], 3) == 'filled'


# ------------------------------------------------------------------ sweeps
def _range_with_low(extra):
    """Down-move forming a confirmed swing low of 97 (bar index 6), then `extra` bars."""
    closes = [110, 108, 106, 104, 102, 100, 98, 100, 102, 104, 106]
    c = [bar(T(i), x, x + 1, x - 1, x) for i, x in enumerate(closes)]
    return c + extra


def test_sell_side_sweep_wick_below_low_closing_back_above():
    c = _range_with_low([bar(T(11), 105, 106, 95, 99)])        # low 95 < 97, close 99 >= 97
    a = analyze(c, 5)
    assert [(s.direction, s.side, s.index, s.level, s.extreme) for s in a.sweeps] == [('bull', 'low', 11, 97, 95)]


def test_close_below_level_is_a_break_not_a_sweep_and_level_consumed_once():
    c = _range_with_low([bar(T(11), 105, 106, 95, 96), bar(T(12), 96, 99, 94, 98)])
    assert analyze(c, 5).sweeps == ()                           # first trade-through closed beyond; no later sweep
    c2 = _range_with_low([bar(T(11), 105, 106, 95, 99), bar(T(12), 99, 100, 94, 98)])
    assert len(analyze(c2, 5).sweeps) == 1                      # second poke at same level reports nothing


def test_buy_side_sweep_and_expiry():
    mirrored = mirror(_range_with_low([bar(T(11), 105, 106, 95, 99)]), 200.0)
    a = analyze(mirrored, 5)
    assert [(s.direction, s.side) for s in a.sweeps] == [('bear', 'high')]
    cfg = EngineConfig(sweep_level_max_age=3)
    assert analyze(mirrored, 5, cfg).sweeps == ()               # level older than 3 bars has expired


# ------------------------------------------------------------------ volatility
def test_atr_wilder_matches_hand_computation():
    c = [bar(T(0), 10, 12, 8, 11), bar(T(1), 11, 15, 10, 14), bar(T(2), 14, 16, 13, 15)]
    tr = [4, max(5, 4, 1), max(3, 2, 1)]
    assert tr == [4, 5, 3]
    atr = atr_series(c, 2)
    assert atr[0] is None and atr[1] == pytest.approx(4.5) and atr[2] == pytest.approx((4.5 * 1 + 3) / 2)
    assert atr_series(c[:1], 2) == [None]
    with pytest.raises(ValueError):
        atr_series(c, 0)


def test_flat_market_regime_and_consolidation():
    a = analyze(flat_series(120), 5)
    assert a.regime[-1] == 'FLAT' and a.atr[-1] == 0 and a.consolidation[-1] is True
    assert a.swings == () and a.events == () and a.fvgs == () and a.sweeps == ()


def test_low_volatility_range_is_consolidation_but_not_flat():
    closes = [15000 + (0.5 if i % 2 else -0.5) for i in range(120)]
    a = analyze(candles_from_closes(closes, wick=0.2), 5)
    assert a.regime[-1] != 'FLAT' and a.consolidation[-1] is True


def test_trending_market_is_not_consolidation():
    a = analyze(candles_from_closes([100 + 5 * i for i in range(80)]), 5)
    assert a.consolidation[-1] is False


def test_regime_high_after_expansion_low_after_quiet_and_unknown_when_short():
    rnd = random.Random(7)
    calm = [100 + rnd.uniform(-1, 1) for _ in range(150)]
    wild = [100 + rnd.uniform(-20, 20) for _ in range(40)]
    up = analyze(candles_from_closes(calm + wild, wick=0.5), 5)
    assert up.regime[-1] == 'HIGH'
    down = analyze(candles_from_closes(wild + calm, wick=0.5), 5)
    assert down.regime[-1] == 'LOW'
    short = analyze(candles_from_closes(calm[:30]), 5)
    assert short.regime[-1] == 'UNKNOWN' and short.regime[5] == 'UNKNOWN'


# ------------------------------------------------------------------ properties
def _series_for_properties():
    rnd = random.Random(11)
    price, out = 1000.0, []
    for i in range(260):
        price += rnd.gauss(0, 6) + (4 if (i // 40) % 2 == 0 else -4)
        o = price + rnd.uniform(-3, 3)
        out.append(Candle(T(i), o, max(o, price) + rnd.uniform(0, 4), min(o, price) - rnd.uniform(0, 4),
                          price, 100.0, 10.0))
    return out


def _signature(a):
    return (a.atr, a.regime, a.consolidation, a.swings, a.events, a.trend_by_index, a.fvgs, a.sweeps)


@pytest.mark.parametrize('series', ['random', 'scenario'])
def test_no_lookahead_prefix_analysis_equals_filtered_full_analysis(series):
    c = _series_for_properties() if series == 'random' else bullish_setup_ltf()
    full = analyze(c, 5)
    assert len(full.events) + len(full.sweeps) + len(full.swings) > 0
    for n in range(1, len(c) + 1):
        p = analyze(c[:n], 5)
        k = n - 1
        assert p.swings == tuple(s for s in full.swings if s.confirmed_index <= k)
        assert p.events == tuple(e for e in full.events if e.index <= k)
        assert p.fvgs == tuple(f for f in full.fvgs if f.detected_index <= k)
        assert p.sweeps == tuple(s for s in full.sweeps if s.index <= k)
        assert p.atr == full.atr[:n] and p.regime == full.regime[:n]
        assert p.consolidation == full.consolidation[:n] and p.trend_by_index == full.trend_by_index[:n]


def test_changing_future_candles_never_changes_past_outputs():
    c = _series_for_properties()
    base = analyze(c, 5)
    rnd = random.Random(99)
    for cut in (60, 120, 200):
        future = []
        for i in range(cut, len(c)):
            p = rnd.uniform(500, 1500)
            future.append(Candle(c[i].time, p, p + 9, p - 9, p + rnd.uniform(-5, 5), 1.0, 10.0))
        alt = analyze(c[:cut] + future, 5)
        k = cut - 1
        assert alt.atr[:cut] == base.atr[:cut] and alt.regime[:cut] == base.regime[:cut]
        assert alt.events_known_at(k) == base.events_known_at(k)
        assert alt.swings_known_at(k) == base.swings_known_at(k)
        assert alt.sweeps_known_at(k) == base.sweeps_known_at(k)
        assert alt.fvgs_known_at(k) == base.fvgs_known_at(k)


def test_identical_input_gives_identical_output():
    c = _series_for_properties()
    first, second = analyze(c, 5), analyze(list(c), 5)
    assert first == second and _signature(first) == _signature(second)
    assert analyze(bullish_setup_ltf(), 5) == analyze(bullish_setup_ltf(), 5)


def test_short_and_empty_series_do_not_raise_and_report_insufficient():
    for n in (0, 1, 2, 5, 20):
        a = analyze(flat_series(n), 5)
        assert a.status == 'INSUFFICIENT_DATA' and a.quality.n_bars == n
    assert analyze([], 5).trend == 'none'
    assert analyze(flat_series(60), 5).status == 'OK'


def test_mirror_symmetry_swaps_directions():
    c = bullish_setup_ltf()
    a, m = analyze(c, 5), analyze(mirror(c), 5)
    assert [(e.kind, e.index) for e in a.events if e.direction == 'bull'] == \
           [(e.kind, e.index) for e in m.events if e.direction == 'bear']
    assert [(s.index, s.direction) for s in a.sweeps] == [(s.index, 'bear' if s.direction == 'bull' else 'bull') for s in m.sweeps]
