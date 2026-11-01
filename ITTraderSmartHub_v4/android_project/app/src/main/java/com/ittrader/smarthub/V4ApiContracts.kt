package com.ittrader.smarthub

import org.json.JSONArray
import org.json.JSONObject

/**
 * V4 & V5 Smart Trading API Contract Builder & Result Formatter.
 * Handles Bot Controls, Backtesting, Paper Trading, Lot Size & Pip Value Calculations, Prop Firm Drawdown Shielding, Device Pairing, Risk Fusion, Alerts, and MT5 Diagnostics.
 */
object V4ApiContracts {

    fun botModeRequest(mode: String, adminPasscode: String = ""): JSONObject = JSONObject().apply {
        put("mode", mode)
        if (adminPasscode.isNotBlank()) put("admin_passcode", adminPasscode)
    }

    fun pipnexCalculator(balance: Double, riskPct: Double, stopLossPips: Double, symbol: String): JSONObject = JSONObject().apply {
        put("balance", balance)
        put("risk_pct", riskPct)
        put("stop_loss_pips", stopLossPips)
        put("symbol", symbol)
    }

    fun pipnexPropFirm(currentEquity: Double, initialBalance: Double, dailyStartEquity: Double): JSONObject = JSONObject().apply {
        put("current_equity", currentEquity)
        put("initial_balance", initialBalance)
        put("daily_starting_equity", dailyStartEquity)
    }

    fun deviceEnroll(deviceId: String, deviceName: String, pairingCode: String): JSONObject = JSONObject().apply {
        put("device_id", deviceId)
        put("device_name", deviceName)
        put("pairing_code", pairingCode)
    }

    fun deviceRevoke(deviceId: String): JSONObject = JSONObject().apply {
        put("device_id", deviceId)
    }

    fun riskContext(baselineRiskPct: Double, symbol: String): JSONObject = JSONObject().apply {
        put("schema_version", 1)
        put("baseline_risk_pct", baselineRiskPct)
        put("symbol", symbol)
    }

    fun alertQuery(cursor: String? = null, limit: Int = 20): JSONObject = JSONObject().apply {
        put("schema_version", 1)
        put("console", "combined")
        put("limit", limit)
        if (!cursor.isNull_or_empty_cursor()) put("since_event_id", cursor)
    }

    private fun String?.isNull_or_empty_cursor(): Boolean = this == null || this.isBlank()

    fun incidentResearch(startUtc: String, endUtc: String, outcome: String): JSONObject = JSONObject().apply {
        put("schema_version", 1)
        put("start_utc", startUtc)
        put("end_utc", endUtc)
        put("outcome", outcome)
    }

    fun botStatusSummary(response: JSONObject): String {
        val mode = response.optString("mode", "OFF")
        val strat = response.optString("strategy_name", "MA_Crossover_ATR")
        val version = response.optString("strategy_version", "v5.1")
        val symbol = response.optString("active_symbol", "BTCUSD")
        val emgStopped = response.optBoolean("emergency_stopped", false)

        val paper = response.optJSONObject("paper_trading") ?: JSONObject()
        val eq = paper.optDouble("equity", 10000.0)
        val posCount = paper.optInt("open_positions_count", 0)

        val icon = if (emgStopped) "🛑 EMERGENCY STOPPED" else if (mode == "PAPER") "🟢 PAPER TRADING" else if (mode == "DEMO") "🟡 DEMO TRADING" else "⚪ OFF"

        return "[V5 TRADING BOT STATUS]\n" +
               "Bot Mode: $icon\n" +
               "Strategy: $strat ($version)\n" +
               "Active Symbol: $symbol\n" +
               "Virtual Equity: $$eq USD\n" +
               "Open Positions: $posCount"
    }

    fun botBacktestSummary(response: JSONObject): String {
        val bt = response.optJSONObject("backtest_result") ?: JSONObject()
        val mc = response.optJSONObject("monte_carlo_result") ?: JSONObject()

        val strat = bt.optString("strategy_name", "MA_Crossover_ATR")
        val netReturn = bt.optDouble("net_return_pct", 0.0)
        val winRate = bt.optDouble("win_rate_pct", 0.0)
        val profitFactor = bt.optDouble("profit_factor", 1.0)
        val maxDd = bt.optDouble("max_drawdown_pct", 0.0)
        val sharpe = bt.optDouble("sharpe_ratio", 0.0)
        val totalTrades = bt.optInt("total_trades", 0)

        val mcP95Dd = mc.optDouble("p95_max_drawdown_pct", 0.0)
        val mcStatus = mc.optString("status", "PASS")

        return "[V5 STRATEGY BACKTEST LAB]\n" +
               "Strategy: $strat\n" +
               "Net Return: $netReturn%\n" +
               "Win Rate: $winRate% ($totalTrades trades)\n" +
               "Profit Factor: $profitFactor\n" +
               "Max Drawdown: $maxDd%\n" +
               "Sharpe Ratio: $sharpe\n" +
               "Monte Carlo 95% Drawdown Limit: $mcP95Dd% ($mcStatus)"
    }

    fun pipnexCalculatorSummary(response: JSONObject): String {
        val symbol = response.optString("symbol", "FOREX")
        val lots = response.optDouble("recommended_lots", 0.01)
        val cashRisk = response.optDouble("cash_at_risk", 0.0)
        val pipVal = response.optDouble("pip_value_usd", 0.0)
        val slPips = response.optDouble("stop_loss_pips", 0.0)

        return "[PIPNEX SMART LOT SIZE CALCULATOR]\n" +
               "Symbol: $symbol\n" +
               "Exact MT5 Recommended Lots: ${String.format("%.2f", lots)} lots\n" +
               "Actual Cash at Risk: $$cashRisk USD\n" +
               "Pip Value: $$pipVal USD / pip\n" +
               "Stop Loss Distance: $slPips pips"
    }

    fun pipnexPropFirmSummary(response: JSONObject): String {
        val status = response.optString("status", "HEALTHY")
        val dailyDd = response.optDouble("daily_drawdown_pct", 0.0)
        val maxDd = response.optDouble("total_drawdown_pct", 0.0)
        val dailyBuffer = response.optDouble("daily_cash_buffer_remaining", 0.0)
        val maxBuffer = response.optDouble("total_cash_buffer_remaining", 0.0)
        val profitProgress = response.optDouble("profit_progress_pct", 0.0)

        val icon = if (response.optBoolean("is_violation", false)) "🔴" else if (response.optBoolean("is_warning", false)) "🟡" else "🟢"

        return "[PIPNEX PROP FIRM DRAWDOWN SHIELD]\n" +
               "Status: $icon $status\n" +
               "Daily Drawdown: $dailyDd% (Max Allowed: 5.0%)\n" +
               "Total Trailing Drawdown: $maxDd% (Max Allowed: 10.0%)\n" +
               "Daily Cash Buffer Remaining: $$dailyBuffer USD\n" +
               "Max Cash Buffer Remaining: $$maxBuffer USD\n" +
               "Profit Target Progress: $profitProgress%"
    }

    fun riskResultSummary(response: JSONObject): String {
        val status = response.optString("status", "UNKNOWN")
        val policyVersion = response.optString("policy_version", "v4.0")
        val reasonCodes = response.optJSONArray("reason_codes")?.toString() ?: "[]"
        val dataFresh = response.optBoolean("data_fresh", false)

        return if (status == "UNAVAILABLE") {
            "[V4 Risk Fusion Decision]\n" +
            "Status: ⚠️ UNAVAILABLE\n" +
            "Policy Version: $policyVersion\n" +
            "Data Fresh: $dataFresh\n" +
            "Reason Codes: $reasonCodes\n" +
            "Note: Decision unavailable. Do NOT treat as trade approval."
        } else {
            val effRisk = response.optDouble("effective_risk_pct", 0.0)
            val ceiling = response.optDouble("infrastructure_risk_ceiling_pct", 0.0)
            "[V4 Risk Fusion Decision]\n" +
            "Status: ✅ $status\n" +
            "Effective Advisory Risk: $effRisk%\n" +
            "Infrastructure Risk Ceiling: $ceiling%\n" +
            "Policy Version: $policyVersion"
        }
    }

    fun alertsSummary(response: JSONObject): String {
        val alerts = response.optJSONArray("alerts") ?: JSONArray()
        val nextCursor = response.optString("next_cursor", "none")
        val persistence = response.optString("persistence", "volatile")
        val serverTime = response.optString("server_time", "")

        val sb = StringBuilder()
        sb.append("[V4 Alert Center Summary]\n")
        sb.append("Server Time: $serverTime\n")
        sb.append("Persistence Mode: $persistence\n")
        sb.append("Total Alerts Fetched: ${alerts.length()}\n")
        sb.append("Next Cursor: $nextCursor\n\n")

        for (i in 0 until alerts.length()) {
            val alert = alerts.optJSONObject(i) ?: continue
            val eventId = alert.optString("event_id")
            val sev = alert.optString("technical_severity")
            val msg = alert.optString("message")
            val ts = alert.optString("recorded_at")
            sb.append("• [$sev] $eventId @ $ts: $msg\n")
        }
        return sb.toString()
    }

    fun researchSummary(response: JSONObject): String {
        val status = response.optString("status", "UNAVAILABLE")
        val analysisType = response.optString("analysis_type", "observational")
        val reasonCodes = response.optJSONArray("reason_codes")?.toString() ?: "[]"
        val policyRec = response.optString("policy_recommendation", "NO_CHANGE")

        return "[V4 Incident-to-Trade Research]\n" +
               "Status: $status\n" +
               "Analysis Type: $analysisType\n" +
               "Policy Recommendation: $policyRec\n" +
               "Reason Codes: $reasonCodes\n" +
               "Note: No synthetic analytics or invented findings."
    }

    fun mt5AnalysisSummary(response: JSONObject): String {
        val status = response.optString("status", "Success")
        val revenge = response.optInt("revenge_count", 0)
        val tilt = response.optInt("tilt_count", 0)
        val totalDeals = response.optInt("total_deals_analyzed", 0)
        val closedPositions = response.optInt("completed_positions_with_observed_exits", 0)
        val flags = response.optJSONArray("flags_detected")

        val sb = StringBuilder()
        sb.append("[MT5 Heuristic Diagnostics]\n")
        sb.append("Status: $status\n")
        sb.append("Deals Audited: $totalDeals\n")
        sb.append("Closed Positions Audited: $closedPositions\n")
        sb.append("Potential Revenge Entries: $revenge\n")
        sb.append("Volume Anomalies: $tilt\n")
        if (flags != null && flags.length() > 0) {
            sb.append("Flags Detected:\n")
            for (i in 0 until flags.length()) {
                sb.append("  - ${flags.optString(i)}\n")
            }
        }
        return sb.toString()
    }
}
