package com.ittrader.smarthub

import org.json.JSONArray
import org.json.JSONObject

/**
 * V4 API Contract Builder & Result Formatter.
 * Ensures strict schema enforcement for Risk Fusion, Alerts, Research, and MT5 diagnostics.
 */
object V4ApiContracts {

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
