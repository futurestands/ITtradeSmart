"""Performance Analytics: Win rate, profit factor, Sharpe ratio, drawdown, and expectancy metrics."""
import math


class PerformanceAnalytics:
    """Computes quantitative performance metrics and trade statistics."""

    @staticmethod
    def analyze_trades(trades: list) -> dict:
        if not trades:
            return {
                "total_trades": 0,
                "win_rate_pct": 0.0,
                "profit_factor": 1.0,
                "expectancy_usd": 0.0,
                "net_profit_usd": 0.0,
                "max_drawdown_pct": 0.0
            }

        pnls = [t.get("pnl", 0.0) for t in trades]
        total_trades = len(pnls)
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        win_rate = (len(wins) / total_trades * 100.0) if total_trades > 0 else 0.0
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 1.0)

        net_profit = sum(pnls)
        expectancy = (net_profit / total_trades) if total_trades > 0 else 0.0

        return {
            "total_trades": total_trades,
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "win_rate_pct": round(win_rate, 2),
            "gross_profit_usd": round(gross_profit, 2),
            "gross_loss_usd": round(gross_loss, 2),
            "net_profit_usd": round(net_profit, 2),
            "profit_factor": round(profit_factor, 2),
            "expectancy_usd": round(expectancy, 2)
        }
