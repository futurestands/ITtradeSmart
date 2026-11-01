"""Bot Controller: Mode state machine (OFF / BACKTEST / PAPER / DEMO), lifecycle scheduling, and authoritative broker price feeding."""
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
    """Central Controller for ITTrader SmartHub v5 Automated Bot. Prohibits client-injected prices."""

    def __init__(self, database_path=None):
        self.lock = RLock()
        self.mode = BotMode.OFF
        self.market_data = MarketDataManager(database_path)
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

    def tick(self, infrastructure_stress: int = 0) -> dict:
        """Executes one automated bot cycle using authoritative broker prices. Never accepts client-supplied prices."""
        with self.lock:
            if self.mode == BotMode.OFF:
                return self.get_status()

            # Retrieve authoritative price from broker/market manager feed
            curr_price = self.market_data.last_price.get(self.active_symbol)
            if curr_price is None or not self.market_data.is_data_fresh(self.active_symbol):
                raise RuntimeError(f"Authoritative market feed for {self.active_symbol} is missing or stale. Fail-closed active.")

            if self.mode == BotMode.PAPER:
                self.paper_engine.update_market_price(self.active_symbol, curr_price)

            # Fetch candles for active symbol
            candles = self.market_data.fetch_real_mt5_candles(self.active_symbol, timeframe_str="H1", num_bars=50)
            sig = self.strategy.generate_signal(self.active_symbol, candles)
            sig_id = self.journal.record_signal(sig)

            # Evaluate Risk Layer with Symbol Spec and Freshness Check
            sym_spec = self.market_data.get_spec(self.active_symbol)
            is_fresh = self.market_data.is_data_fresh(self.active_symbol)

            account_balance = self.paper_engine.balance if self.mode == BotMode.PAPER else 10000.0
            daily_start = 10000.0
            open_pos = len(self.paper_engine.positions) if self.mode == BotMode.PAPER else 0

            risk_res = self.risk_guardian.validate_trade_signal(
                sig, account_balance, daily_start, open_pos, sym_spec, infrastructure_stress, is_fresh
            )
            dec_id = self.journal.record_decision(sig_id, risk_res, self.mode.value)

            # Execution Routing
            execution_res = None
            if risk_res.approved and sig.direction in ("BUY", "SELL"):
                if self.mode == BotMode.PAPER:
                    pos = self.paper_engine.open_position(
                        self.active_symbol, sig.direction, risk_res.allocated_lots,
                        curr_price, sig.stop_loss, sig.take_profit
                    )
                    execution_res = {"status": "PAPER_POSITION_OPENED", "position_id": pos.position_id}
                elif self.mode == BotMode.DEMO:
                    execution_res = self.demo_adapter.execute_demo_order(
                        f"order-{dec_id}", self.active_symbol, sig.direction,
                        risk_res.allocated_lots, curr_price, sig.stop_loss, sig.take_profit
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
                "strategy_version": "v5.3",
                "active_symbol": self.active_symbol,
                "demo_adapter_enabled": self.demo_adapter.enabled,
                "emergency_stopped": self.demo_adapter.emergency_stopped,
                "paper_trading": self.paper_engine.get_summary()
            }
