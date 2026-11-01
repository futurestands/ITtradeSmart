"""Bot Controller: Mode state machine (OFF / BACKTEST / PAPER / DEMO), lifecycle scheduling, and emergency stop handler."""
from enum import Enum
from threading import RLock
from .market_data import MarketDataManager
from .strategies import TrendFollowingMACrossoverStrategy
from .risk_guardian import RiskGuardian
from .paper_trading import PaperTradingEngine
from .demo_execution import DemoMT5ExecutionAdapter
from .trading_journal import TradingJournal


class BotMode(str, Enum):
    OFF = "OFF"
    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    DEMO = "DEMO"


class BotController:
    """Central Controller for ITTrader SmartHub v5 Automated Bot."""

    def __init__(self, database_path=None):
        self.lock = RLock()
        self.mode = BotMode.OFF
        self.market_data = MarketDataManager()
        self.strategy = TrendFollowingMACrossoverStrategy()
        self.risk_guardian = RiskGuardian()
        self.paper_engine = PaperTradingEngine(10000.0, database_path)
        self.demo_adapter = DemoMT5ExecutionAdapter(database_path)
        self.journal = TradingJournal(database_path)
        self.active_symbol = "BTCUSD"

    def set_mode(self, mode_str: str, admin_passcode: str = None) -> dict:
        with self.lock:
            mode_upper = mode_str.upper()
            if mode_upper == "DEMO":
                if not admin_passcode or not self.demo_adapter.enable_demo_mode(admin_passcode):
                    raise PermissionError("Admin authorization failed. Cannot switch to DEMO mode without valid master passcode.")
                self.mode = BotMode.DEMO
            elif mode_upper == "PAPER":
                self.demo_adapter.disable_demo_mode()
                self.mode = BotMode.PAPER
            elif mode_upper == "BACKTEST":
                self.demo_adapter.disable_demo_mode()
                self.mode = BotMode.BACKTEST
            else:
                self.demo_adapter.disable_demo_mode()
                self.mode = BotMode.OFF

            return self.get_status()

    def emergency_stop(self) -> dict:
        with self.lock:
            self.mode = BotMode.OFF
            self.demo_adapter.trigger_emergency_stop()
            return self.get_status()

    def tick(self, current_price: float, infrastructure_stress: int = 0) -> dict:
        """Executes one automated bot cycle."""
        with self.lock:
            self.market_data.update_price(self.active_symbol, current_price)

            if self.mode == BotMode.PAPER:
                self.paper_engine.update_market_price(self.active_symbol, current_price)

            if self.mode == BotMode.OFF:
                return self.get_status()

            # Generate Strategy Signal
            candles = self.market_data.generate_synthetic_candles(self.active_symbol, num_bars=50, base_price=current_price)
            sig = self.strategy.generate_signal(self.active_symbol, candles)
            sig_id = self.journal.record_signal(sig)

            # Evaluate Risk Layer
            account_balance = self.paper_engine.balance if self.mode == BotMode.PAPER else 10000.0
            daily_start = 10000.0
            open_pos = len(self.paper_engine.positions) if self.mode == BotMode.PAPER else 0

            risk_res = self.risk_guardian.validate_trade_signal(
                sig, account_balance, daily_start, open_pos, infrastructure_stress
            )
            dec_id = self.journal.record_decision(sig_id, risk_res, self.mode.value)

            # Execution Routing
            execution_res = None
            if risk_res.approved and sig.direction in ("BUY", "SELL"):
                if self.mode == BotMode.PAPER:
                    pos = self.paper_engine.open_position(
                        self.active_symbol, sig.direction, risk_res.allocated_lots,
                        current_price, sig.stop_loss, sig.take_profit
                    )
                    execution_res = {"status": "PAPER_POSITION_OPENED", "position_id": pos.position_id}
                elif self.mode == BotMode.DEMO:
                    execution_res = self.demo_adapter.execute_demo_order(
                        f"order-{dec_id}", self.active_symbol, sig.direction,
                        risk_res.allocated_lots, current_price, sig.stop_loss, sig.take_profit
                    )

            status = self.get_status()
            status["last_cycle"] = {
                "signal_id": sig_id,
                "direction": sig.direction,
                "approved": risk_res.approved,
                "allocated_lots": risk_res.allocated_lots,
                "execution": execution_res
            }
            return status

    def get_status(self) -> dict:
        with self.lock:
            return {
                "mode": self.mode.value,
                "strategy_name": self.strategy.name,
                "strategy_version": "v5.1",
                "active_symbol": self.active_symbol,
                "demo_adapter_enabled": self.demo_adapter.enabled,
                "emergency_stopped": self.demo_adapter.emergency_stopped,
                "paper_trading": self.paper_engine.get_summary()
            }
