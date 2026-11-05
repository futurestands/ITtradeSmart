"""All tunable parameters in one place.

IMPORTANT: every default below is an UNOPTIMISED, conventional starting value. None
has been fitted to NAS100 data. Changing them to improve a backtest would be
parameter-mining; any such search belongs in a walk-forward study (see
docs/ML_DESIGN.md), not here.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class EngineConfig:
    # Swings (fractal): a swing high needs `swing_left` strictly lower highs before
    # and `swing_right` strictly lower highs after it. Confirmed `swing_right` bars later.
    swing_left: int = 2
    swing_right: int = 2

    # Volatility
    atr_period: int = 14
    regime_lookback: int = 200        # trailing ATR history used for percentile rank
    regime_min_history: int = 50
    low_vol_pct: float = 0.25
    high_vol_pct: float = 0.75
    flat_atr_over_price: float = 1e-6  # ATR/close at or below this => FLAT

    # Consolidation: BOTH conditions required over the trailing window
    consolidation_window: int = 20
    consolidation_range_atr: float = 3.5   # window range <= this many ATRs
    consolidation_max_efficiency: float = 0.30

    # Fair Value Gap
    fvg_min_atr: float = 0.25          # gap size must be >= this many ATRs

    # Liquidity sweep: levels expire after this many bars
    sweep_level_max_age: int = 100

    # Data quality
    closure_min_minutes: int = 60      # legacy compatibility only; never exempts unknown gaps
    min_bars: int = 60                 # fewer bars => INSUFFICIENT_DATA
    htf_min_bars: int = 30             # same rule for the higher-timeframe series
    gap_lookback_bars: int = 30        # data-fault gaps this recent block a decision

    # Decision framework (preliminary, rule-based, UNVALIDATED)
    setup_window_bars: int = 20        # sweep -> structure shift -> FVG must occur within this
    stop_buffer_atr: float = 0.25
    min_rr: float = 2.0
    max_stop_atr: float = 4.0
    max_spread_points: float = None    # None disables the spread filter
    max_data_age_minutes: int = 15     # only enforced when the caller passes `now`
    allowed_sessions: tuple = ('london', 'new_york')
