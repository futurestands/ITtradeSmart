"""ITTrader SmartHub v5 — Automated Trading & Risk Intelligence Package."""
from .market_data import MarketDataManager
from .strategies import BaseStrategy, TrendFollowingMACrossoverStrategy, Signal
from .backtesting import BacktestEngine
from .paper_trading import PaperTradingEngine
from .risk_guardian import RiskGuardian
from .demo_execution import DemoMT5ExecutionAdapter
from .bot_controller import BotController, BotMode
from .trading_journal import TradingJournal
from .analytics import PerformanceAnalytics

__all__ = [
    'MarketDataManager',
    'BaseStrategy',
    'TrendFollowingMACrossoverStrategy',
    'Signal',
    'BacktestEngine',
    'PaperTradingEngine',
    'RiskGuardian',
    'DemoMT5ExecutionAdapter',
    'BotController',
    'BotMode',
    'TradingJournal',
    'PerformanceAnalytics'
]
