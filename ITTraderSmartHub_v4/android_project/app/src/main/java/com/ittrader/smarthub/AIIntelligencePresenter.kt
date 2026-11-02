package com.ittrader.smarthub

import org.json.JSONObject

/** Displays advisory availability only; no trading, sizing or risk actions. */
object AIIntelligencePresenter {
    private val fields = setOf("schema_version", "connection_status", "model_status", "model_trained",
        "model", "probability", "advisory_only", "reason_code", "explanation", "execution_policy", "timebase_status")
    private val reasons = setOf("MODEL_NOT_READY", "SERVICE_UNAVAILABLE", "SERVICE_TIMEOUT",
        "INVALID_SERVICE_RESPONSE", "SERVICE_NOT_CONFIGURED")

    fun unavailable(): String = "AI Intelligence — advisory only\nConnection: Unavailable\n" +
        "Model: Model not trained\nPrediction: Unavailable\nRiskGuardian remains authoritative."

    fun summary(response: JSONObject): String {
        val keys = response.keys().asSequence().toSet()
        if (keys != fields || response.optString("schema_version") != "1.0" ||
            response.opt("advisory_only") != true || response.opt("model_trained") != false ||
            !response.isNull("model") || !response.isNull("probability") ||
            response.optString("model_status") != "MODEL_NOT_READY" ||
            response.optString("execution_policy") != "RESEARCH_ONLY_LOCKED" ||
            response.optString("timebase_status") != "TIMEBASE_UNVERIFIED" ||
            response.optString("reason_code") !in reasons ||
            (response.optString("connection_status") == "CONNECTED" && response.optString("reason_code") != "MODEL_NOT_READY") ||
            response.optString("connection_status") !in setOf("CONNECTED", "UNAVAILABLE")) {
            return unavailable() + "\nResponse rejected; no advisory is trusted."
        }
        val connection = if (response.optString("connection_status") == "CONNECTED") "Connected to local AI Lab" else "Unavailable"
        return "AI Intelligence — advisory only\nConnection: $connection\n" +
            "Model: Model not trained\nPrediction: Unavailable\n" +
            "No verified model or registered target is available.\n" +
            "AI cannot authorize trades, choose size or override RiskGuardian."
    }
}
