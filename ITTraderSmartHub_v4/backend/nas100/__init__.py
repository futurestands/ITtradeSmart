"""NAS100 market-structure engine (standalone, read-only analysis).

* No broker I/O, no MetaTrader5 import, no order functions, no credentials.
* Market-data acquisition lives elsewhere and hands in `Candle` lists
  (see candles.candles_from_rates).
* Outputs are deterministic and look-ahead free; the decision framework is
  rule-based and UNVALIDATED. See README.md in this folder for definitions.
"""
from .analysis import Analysis, MultiTimeframeAnalysis, analyze, analyze_multitimeframe
from .candles import (Candle, DataQuality, DataValidationError, candles_from_rates,
                      candles_from_broker_wall_rates, validate_candles)
from .config import EngineConfig
from .decision import BUY, NO_TRADE, SELL, Decision, decide
from .sessions import SessionState, session_state
from .timeframes import htf_closed_by, resample

__all__ = ['Analysis', 'MultiTimeframeAnalysis', 'analyze', 'analyze_multitimeframe', 'Candle',
           'DataQuality', 'DataValidationError', 'candles_from_rates',
           'candles_from_broker_wall_rates', 'validate_candles',
           'EngineConfig', 'BUY', 'SELL', 'NO_TRADE', 'Decision', 'decide', 'SessionState',
           'session_state', 'htf_closed_by', 'resample']
