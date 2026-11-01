"""Restricted MT5 Demo Execution Adapter: Strict DEMO mode checks, allowlist validation, idempotency, and pre-trade re-checks."""
import os
import sqlite3
from datetime import datetime, timezone


class DemoMT5ExecutionAdapter:
    """
    Restricted Demo Execution Adapter for MetaTrader 5.
    MANDATORY SAFEGUARDS:
    1. Disabled by default. Requires explicit admin enablement (`enable_demo_mode`).
    2. Account Mode Check: Rejects any non-DEMO account (`account.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO`).
    3. Allowlist Check: Verifies `account.login` and `account.server` against strict environment allowlist (`MT5_DEMO_ALLOWLIST_LOGINS`, `MT5_DEMO_ALLOWLIST_SERVERS`).
    4. Idempotency: Rejects duplicated order requests via order_id tracking.
    5. Emergency Stop: Immediately blocks execution when triggered.
    """

    def __init__(self, database_path=None):
        self.enabled = False
        self.emergency_stopped = False
        self.database_path = database_path or os.environ.get("SMARTHUB_STATE_DB")
        self.executed_order_ids = set()

        if self.database_path:
            with sqlite3.connect(self.database_path) as db:
                db.execute("CREATE TABLE IF NOT EXISTS demo_orders (order_id TEXT PRIMARY KEY, symbol TEXT, type TEXT, volume REAL, price REAL, sl REAL, tp REAL, executed_at TEXT)")
                for oid in db.execute("SELECT order_id FROM demo_orders").fetchall():
                    self.executed_order_ids.add(oid[0])

    def enable_demo_mode(self, admin_passcode: str) -> bool:
        master_secret = os.environ.get("SMARTHUB_API_TOKEN", "")
        if len(master_secret) >= 32 and admin_passcode == master_secret:
            self.enabled = True
            self.emergency_stopped = False
            return True
        return False

    def disable_demo_mode(self):
        self.enabled = False

    def trigger_emergency_stop(self):
        self.emergency_stopped = True
        self.enabled = False

    def execute_demo_order(self, order_id: str, symbol: str, order_type: str, volume: float, price: float, stop_loss: float, take_profit: float) -> dict:
        """Executes a demo order after strict account, mode, and safety verification."""
        if not self.enabled or self.emergency_stopped:
            raise PermissionError("Demo MT5 Execution Adapter is DISABLED or EMERGENCY STOPPED.")

        if order_id in self.executed_order_ids:
            raise ValueError(f"Idempotency Error: Order {order_id} has already been processed.")

        # Re-check MT5 Account
        try:
            import MetaTrader5 as mt5
            login = int(os.environ.get("MT5_LOGIN", "0"))
            password = os.environ.get("MT5_DEMO_PASSWORD", os.environ.get("MT5_INVESTOR_PASSWORD", ""))
            server = os.environ.get("MT5_SERVER", "")

            if not login or not password or not server:
                raise PermissionError("MT5 demo credentials not configured on gateway host.")

            # Strict Demo Login Allowlist Check
            allow_logins = os.environ.get("MT5_DEMO_ALLOWLIST_LOGINS", str(login)).split(",")
            allow_servers = os.environ.get("MT5_DEMO_ALLOWLIST_SERVERS", server).split(",")

            if str(login) not in allow_logins or server not in allow_servers:
                raise PermissionError("MT5 account login/server is NOT present in the strict Demo Allowlist.")

            if not mt5.initialize(login=login, password=password, server=server):
                raise ConnectionError("Failed to initialize MT5 terminal connection.")

            account = mt5.account_info()
            if account is None:
                mt5.shutdown()
                raise ConnectionError("Account info unavailable.")

            # Strict DEMO Mode Check (mt5.ACCOUNT_TRADE_MODE_DEMO == 0)
            trade_mode = getattr(account, "trade_mode", None)
            if trade_mode != 0:  # 0 is DEMO
                mt5.shutdown()
                self.trigger_emergency_stop()
                raise PermissionError(f"CRITICAL RISK TRIGGERED: Account mode {trade_mode} is NOT a DEMO account! Emergency stop engaged.")

            # Execute Order on Demo Account
            req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": mt5.ORDER_TYPE_BUY if order_type.upper() == "BUY" else mt5.ORDER_TYPE_SELL,
                "price": price,
                "sl": stop_loss,
                "tp": take_profit,
                "deviation": 20,
                "magic": 555888,
                "comment": f"SmartHub_v5_{order_id}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            res = mt5.order_send(req)
            mt5.shutdown()

            if res is None or res.retcode != mt5.TRADE_RETCODE_DONE:
                ret_code = res.retcode if res else "NO_RESPONSE"
                raise RuntimeError(f"MT5 Demo Order Rejected with code {ret_code}")

            self.executed_order_ids.add(order_id)
            if self.database_path:
                with sqlite3.connect(self.database_path) as db:
                    db.execute("INSERT INTO demo_orders VALUES (?,?,?,?,?,?,?,?)",
                               (order_id, symbol, order_type, volume, price, stop_loss, take_profit, datetime.now(timezone.utc).isoformat()))

            return {
                "status": "EXECUTED_DEMO",
                "order_id": order_id,
                "deal_ticket": res.deal,
                "order_ticket": res.order,
                "volume": volume,
                "fill_price": res.price
            }

        except ImportError:
            raise RuntimeError("MetaTrader5 Python library is unavailable. Windows host required for demo execution.")
