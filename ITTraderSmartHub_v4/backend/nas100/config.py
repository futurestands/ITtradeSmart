"""All tunable parameters in one place.

IMPORTANT: every default below is an UNOPTIMISED, conventional starting value. None
has been fitted to NAS100 data. Changing them to improve a backtest would be
parameter-mining; any such search belongs in a walk-forward study (see
docs/ML_DESIGN.md), not here.
"""
from dataclasses import dataclass
from math import isfinite


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
    htf_max_lag_bars: int = 1          # preserve the local wall-clock freshness ceiling
    gap_lookback_bars: int = 30        # data-fault gaps this recent block a decision

    # Decision framework (preliminary, rule-based, UNVALIDATED)
    setup_window_bars: int = 20        # sweep -> structure shift -> FVG must occur within this
    stop_buffer_atr: float = 0.25
    min_rr: float = 2.0
    max_stop_atr: float = 4.0
    max_spread_points: float = None    # None disables the spread filter
    max_data_age_minutes: int = 15     # only enforced when the caller passes `now`
    allowed_sessions: tuple = ('london', 'new_york')

    def __post_init__(self):
        for name in ('swing_left', 'swing_right', 'atr_period', 'regime_lookback',
                     'regime_min_history', 'consolidation_window', 'sweep_level_max_age',
                     'closure_min_minutes', 'min_bars', 'htf_min_bars', 'htf_max_lag_bars',
                     'gap_lookback_bars', 'setup_window_bars', 'max_data_age_minutes'):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f'{name} must be a positive integer')
        for name in ('flat_atr_over_price', 'consolidation_range_atr',
                     'consolidation_max_efficiency', 'fvg_min_atr', 'stop_buffer_atr',
                     'min_rr', 'max_stop_atr', 'low_vol_pct', 'high_vol_pct'):
            value = getattr(self, name)
            if type(value) not in (int, float) or not isfinite(value) or value < 0:
                raise ValueError(f'{name} must be finite and nonnegative')
        if not 0 <= self.low_vol_pct < self.high_vol_pct <= 1:
            raise ValueError('volatility percentiles must be ordered in [0, 1]')
        if not 0 <= self.consolidation_max_efficiency <= 1:
            raise ValueError('consolidation efficiency must be in [0, 1]')
        if self.min_rr <= 0 or self.max_stop_atr <= 0:
            raise ValueError('risk/reward thresholds must be positive')
        if self.max_spread_points is not None:
            value = self.max_spread_points
            if type(value) not in (int, float) or not isfinite(value) or value < 0:
                raise ValueError('spread ceiling must be finite and nonnegative')
        known = ('asia', 'london', 'new_york', 'ny_cash', 'ny_open', 'overlap')
        if (not isinstance(self.allowed_sessions, tuple) or not self.allowed_sessions
                or any(name not in known for name in self.allowed_sessions)):
            raise ValueError('allowed_sessions must be a nonempty tuple of known sessions')
