package com.ittrader.smarthub

import java.time.Instant
import org.json.JSONObject

/** Recorded experiment counts only. Never renders a trade signal or live status. */
object PaperTrialPresenter {
    fun unavailable() = "Paper evidence unavailable. This does not mean testing succeeded. NO_TRADE."

    fun summary(value: JSONObject, now: Instant = Instant.now()): String {
        return try {
            require(value.opt("schema_version") is Int && value.getInt("schema_version") == 1)
            require(value.opt("execution_authorized") == false && value.opt("model_status") == "MODEL_NOT_READY")
            require(value.opt("decision") == "NO_TRADE" && value.opt("scope") == "PUBLISHED_PAPER_EVIDENCE_NOT_LIVE_STATUS")
            require(value.opt("costs_certified") == false && value.opt("clock_certified") == false)
            if (value.getString("status") != "PAPER_EVIDENCE_AVAILABLE") return unavailable()
            val captured = Instant.parse(value.getString("captured_at_utc"))
            require(!captured.isAfter(now.plusSeconds(300)))
            val state = value.getString("run_state")
            require(state in setOf("IN_PROGRESS_AT_CAPTURE", "COMPLETED", "STOPPED"))
            val array = value.getJSONArray("tracks")
            require(array.length() == 3)
            val names = mutableSetOf<String>()
            val details = (0 until array.length()).map { index ->
                val track = array.getJSONObject(index)
                val model = track.getString("model")
                require(model in setOf("empirical_prior", "logistic", "gradient_boosting") && names.add(model))
                fun count(key: String): Int {
                    require(track.opt(key) is Int)
                    return track.getInt(key).also { require(it in 0..1_000_000) }
                }
                val scored = count("directional_scored"); val correct = count("direction_correct")
                val entries = count("paper_entries"); val waits = count("paper_waits")
                val closed = count("paper_closed"); val wins = count("paper_profitable")
                val losses = count("paper_losing"); val flat = count("paper_flat")
                val unknown = count("paper_unknown"); val pending = count("paper_pending")
                require(correct <= scored && wins + losses + flat + unknown == closed && closed + pending == entries)
                "$model\nDirection: $correct correct / ${scored-correct} wrong / $scored scored\n" +
                    "Paper: $entries entries · $waits waits · $wins positive · $losses negative · $flat flat\n" +
                    "Unknown: $unknown · Pending: $pending"
            }
            "Recorded snapshot: $captured\nState at capture: $state\n" +
                "${if (captured.isBefore(now.minusSeconds(86400))) "Historical snapshot — over 24 hours old.\n" else ""}" +
                "Not a live worker connection or verified account return.\n\n" + details.joinToString("\n\n") +
                "\n\nHypothetical costs; model NOT READY. NO_TRADE."
        } catch (_: Exception) { unavailable() }
    }
}
