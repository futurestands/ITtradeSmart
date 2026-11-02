"""Research-only execution interlock; restoring execution requires a reviewed code change."""

class DemoMT5ExecutionAdapter:
    """Preserves controller interface without MT5 imports or submission pathways."""
    def __init__(self, database_path=None):
        self.enabled = False
        self.emergency_stopped = False
        self.database_path = database_path

    def enable_demo_mode(self, admin_passcode: str) -> bool:
        self.enabled = False
        return False

    def disable_demo_mode(self):
        self.enabled = False

    def trigger_emergency_stop(self):
        self.emergency_stopped = True
        self.enabled = False

    def execute_demo_order(self, order_id: str, symbol: str, order_type: str,
                           volume: float, price: float, stop_loss: float,
                           take_profit: float) -> dict:
        raise PermissionError("RESEARCH_ONLY_EXECUTION_LOCK: MT5 order submission prohibited.")
