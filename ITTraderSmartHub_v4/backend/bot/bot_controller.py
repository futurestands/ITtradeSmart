"""Research controller. PAPER entry/valuation are blocked pending verified integration."""
from enum import Enum
from threading import RLock
from .market_data import MarketDataManager
from .strategies import TrendFollowingMACrossoverStrategy
from .risk_guardian import RiskGuardian
from .demo_execution import DemoMT5ExecutionAdapter
from .trading_journal import TradingJournal


class BotMode(str, Enum):
    OFF = "OFF"
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    DEMO = "DEMO"


class PaperSafetyError(RuntimeError):
    """A controlled unavailable state, not a simulated risk decision."""


PAPER_BLOCKERS = (
    "VERIFIED_EXACT_INSTRUMENT_AND_ECONOMICS_REQUIRED",
    "AUTHORITATIVE_ACCOUNT_IDENTITY_EQUITY_FREE_MARGIN_AND_DAILY_STATE_REQUIRED",
    "AUTHORITATIVE_QUOTE_AND_CLOSED_CANDLE_TIMEBASE_REQUIRED",
    "VERIFIED_RISK_INPUT_ADAPTER_REQUIRED",
    "ACCURATE_PAPER_VALUATION_AND_RESTART_PERSISTENCE_NOT_IMPLEMENTED",
)


class BotController:
    """No PAPER unlock path is provided by this milestone.

    Offline research replay remains in BacktestEngine. The legacy paper
    engine is deliberately not instantiated or used for balances, fills or P&L.
    """

    def __init__(self, database_path=None):
        self.lock = RLock()
        self.mode = BotMode.OFF
        self.market_data = MarketDataManager(database_path)
        self.strategy = TrendFollowingMACrossoverStrategy()
        self.risk_guardian = RiskGuardian()
        self.paper_engine = None
        self.demo_adapter = DemoMT5ExecutionAdapter(database_path)
        self.journal = TradingJournal(database_path)
        self.active_symbol = None  # exact broker symbol has not been verified/configured

    def set_mode(self, mode_str: str, admin_passcode: str = None) -> dict:
        with self.lock:
            if not isinstance(mode_str, str):
                raise ValueError("Invalid bot mode")
            mode_upper = mode_str.upper()
            if mode_upper == "DEMO":
                # Neither credentials nor mutable adapter flags can enable it.
                self.mode = BotMode.OFF
                self.demo_adapter.disable_demo_mode()
                raise PermissionError("RESEARCH_ONLY_EXECUTION_LOCK: DEMO execution is prohibited.")
            if mode_upper == "PAPER":
                self.mode = BotMode.OFF
                self.demo_adapter.disable_demo_mode()
                raise PaperSafetyError("PAPER_BLOCKED: verified inputs, accounting and persistence integration required.")
            self.demo_adapter.disable_demo_mode()
            self.mode = BotMode.BACKTEST if mode_upper == "BACKTEST" else BotMode.OFF
            return self.get_status()

    def emergency_stop(self) -> dict:
        with self.lock:
            self.mode = BotMode.OFF
            self.demo_adapter.trigger_emergency_stop()
            return self.get_status()

    def tick(self, infrastructure_stress=None) -> dict:
        """No broker reads, strategy/risk calls, paper mutations or orders from tick.

        Even a forced PAPER/DEMO mode or injected adapters cannot bypass this
        gate. Adding verified input adapters alone must not unlock legacy P&L.
        """
        with self.lock:
            if self.mode == BotMode.OFF:
                return self.get_status()
            self.mode = BotMode.OFF
            self.demo_adapter.disable_demo_mode()
            raise PaperSafetyError("TRADING_CYCLE_BLOCKED: PAPER integration unverified; backtests are offline only; MT5 execution locked.")

    def get_status(self) -> dict:
        with self.lock:
            return {
                "mode": self.mode.value,
                "strategy_name": self.strategy.name,
                "strategy_version": self.strategy.version,
                "active_symbol": self.active_symbol,
                "demo_adapter_enabled": self.demo_adapter.enabled,
                "execution_policy": "RESEARCH_ONLY_LOCKED",
                "emergency_stopped": self.demo_adapter.emergency_stopped,
                "paper_trading": {
                    "mode": "PAPER_BLOCKED",
                    "status": "BLOCKED_INTEGRATION_UNVERIFIED",
                    "eligible": False,
                    "blockers": list(PAPER_BLOCKERS),
                    "balance": None,
                    "equity": None,
                    "open_positions_count": None,
                    "closed_trades_count": None,
                    "total_pnl": None,
                },
            }
