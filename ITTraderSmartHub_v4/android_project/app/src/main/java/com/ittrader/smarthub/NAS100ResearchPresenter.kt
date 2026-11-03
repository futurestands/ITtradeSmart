package com.ittrader.smarthub

import org.json.JSONArray
import org.json.JSONObject

/**
 * Displays ONLY local, synthetic NAS100 experiment summaries.
 * No live quotes, win probabilities, trade approval or bot mode controls.
 */
object NAS100ResearchPresenter {
    private val fields = setOf(
        "schema_version", "status", "source", "report_modified_at_utc",
        "instrument", "model_status", "real_market_inference_authorized",
        "real_market_training_authorized", "trade_execution_authorized",
        "synthetic_only", "synthetic_paths", "hypothetical_cost_scenarios",
        "run_count", "comparisons"
    )
    private val rowFields = setOf(
        "setup_id", "model", "cost_scenario",
        "improved_synthetic_paths", "evaluated_synthetic_paths"
    )
    private val statuses = setOf(
        "NOT_CONFIGURED", "NO_VALID_REPORT", "INVALID_REPORT",
        "SYNTHETIC_REPORT_AVAILABLE"
    )
    private val setupNames = mapOf(
        "TREND_CONTINUATION_V1" to "Trend continuation",
        "BREAKOUT_RETEST_V1" to "Breakout / retest"
    )
    private val modelNames = mapOf(
        "logistic_calibrated" to "Logistic",
        "gradient_boosting_calibrated" to "Gradient boosting"
    )
    private val costNames = mapOf(
        "baseline_synthetic_cost" to "Baseline friction",
        "double_friction_stress" to "Doubled friction"
    )

    fun unavailable(): String = "NAS100 RESEARCH DASHBOARD\n" +
        "Connection/report: Unavailable\n" +
        "Model: NOT READY\n" +
        "No real-market predictions or trade approvals."

    private fun rejected(): String = unavailable() + "\nReport rejected by safety checks."

    private fun hasExactFields(data: JSONObject, expected: Set<String>): Boolean =
        data.keys().asSequence().toSet() == expected

    private fun strictCount(data: JSONObject, name: String, minimum: Int, maximum: Int): Int? {
        val value = data.opt(name)
        if (value !is Int || value !in minimum..maximum) return null
        return value
    }

    fun summary(response: JSONObject): String {
        if (!hasExactFields(response, fields) ||
            response.opt("schema_version") != 1 ||
            response.optString("instrument") != "USTECH100M" ||
            response.optString("model_status") != "MODEL_NOT_READY" ||
            response.opt("real_market_inference_authorized") != false ||
            response.opt("real_market_training_authorized") != false ||
            response.opt("trade_execution_authorized") != false ||
            response.opt("synthetic_only") != true ||
            response.optString("status") !in statuses
        ) return rejected()

        val status = response.optString("status")
        val comparisons = response.optJSONArray("comparisons") ?: return rejected()
        if (status != "SYNTHETIC_REPORT_AVAILABLE") {
            if (response.optString("source") != "NONE" ||
                !response.isNull("report_modified_at_utc") ||
                !response.isNull("synthetic_paths") ||
                !response.isNull("hypothetical_cost_scenarios") ||
                !response.isNull("run_count") ||
                comparisons.length() != 0
            ) return rejected()
            val reason = when (status) {
                "NOT_CONFIGURED" -> "Lab report folder not configured on Gateway"
                "NO_VALID_REPORT" -> "No locally available research report"
                else -> "Local research report failed validation"
            }
            return "NAS100 RESEARCH DASHBOARD\n" +
                "Report: $reason\n" +
                "Model: NOT READY\nReal NAS100 predictions: DISABLED\n" +
                "Research and trading remain separate."
        }

        if (response.optString("source") != "LOCAL_UNATTESTED_SYNTHETIC_REPORT" ||
            response.isNull("report_modified_at_utc")
        ) return rejected()
        val paths = strictCount(response, "synthetic_paths", 2, 6) ?: return rejected()
        val costCases = strictCount(response, "hypothetical_cost_scenarios", 2, 2) ?: return rejected()
        val studies = strictCount(response, "run_count", 4, 12) ?: return rejected()
        if (studies != paths * costCases || comparisons.length() > 8) return rejected()

        val rowText = mutableListOf<String>()
        val seen = mutableSetOf<String>()
        for (i in 0 until comparisons.length()) {
            val row = comparisons.optJSONObject(i) ?: return rejected()
            if (!hasExactFields(row, rowFields)) return rejected()
            val setup = setupNames[row.optString("setup_id")] ?: return rejected()
            val model = modelNames[row.optString("model")] ?: return rejected()
            val cost = costNames[row.optString("cost_scenario")] ?: return rejected()
            val total = strictCount(row, "evaluated_synthetic_paths", 1, paths) ?: return rejected()
            val improved = strictCount(row, "improved_synthetic_paths", 0, total) ?: return rejected()
            val identity = "$setup/$model/$cost"
            if (!seen.add(identity)) return rejected()
            rowText.add("$setup · $model · $cost: $improved/$total synthetic paths")
        }

        return buildString {
            append("NAS100 RESEARCH DASHBOARD\n")
            append("Local synthetic report: Available (unverified)\n")
            append("Synthetic paths: $paths | Friction scenarios: $costCases\n")
            append("Completed synthetic experiments: $studies\n\n")
            if (rowText.isEmpty()) append("No sufficiently scored comparisons.\n")
            else rowText.forEach { append(it).append("\n") }
            append("\nModel: NOT READY\n")
            append("Real NAS100 predictions: DISABLED\n")
            append("Trade execution: DISABLED\n")
            append("Synthetic Brier comparisons are NOT win rates or live evidence.")
        }
    }
}
