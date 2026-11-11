package com.ittrader.smarthub

import java.time.Instant
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PaperTrialPresenterTest {
    private val now = Instant.parse("2026-11-11T08:00:00Z")
    private fun snapshot(): JSONObject {
        val tracks = listOf("empirical_prior","logistic","gradient_boosting").map {
            """{"model":"$it","directional_scored":2,"direction_correct":1,"paper_entries":0,
            "paper_waits":3,"paper_closed":0,"paper_profitable":0,"paper_losing":0,
            "paper_flat":0,"paper_unknown":0,"paper_pending":0}"""
        }.joinToString(",")
        return JSONObject("""{"schema_version":1,"status":"PAPER_EVIDENCE_AVAILABLE",
          "execution_authorized":false,"model_status":"MODEL_NOT_READY","decision":"NO_TRADE",
          "scope":"PUBLISHED_PAPER_EVIDENCE_NOT_LIVE_STATUS","costs_certified":false,"clock_certified":false,
          "captured_at_utc":"2026-11-11T07:00:00Z","run_state":"IN_PROGRESS_AT_CAPTURE","tracks":[$tracks]}""")
    }
    @Test fun rendersRecordedMistakesAndWaitsWithoutTradingClaims() {
        val text = PaperTrialPresenter.summary(snapshot(),now)
        assertTrue(text.contains("1 correct / 1 wrong / 2 scored"))
        assertTrue(text.contains("0 entries · 3 waits"))
        assertTrue(text.contains("Not a live worker connection"))
        assertTrue(text.contains("NOT READY"))
    }
    @Test fun readinessOverridesAndBadCountsRejected() {
        val unsafe = snapshot().put("execution_authorized",true)
        assertEquals(PaperTrialPresenter.unavailable(),PaperTrialPresenter.summary(unsafe,now))
        val bad = snapshot();bad.getJSONArray("tracks").getJSONObject(0).put("paper_losing",1)
        assertEquals(PaperTrialPresenter.unavailable(),PaperTrialPresenter.summary(bad,now))
    }
    @Test fun oldSnapshotIsLabelledAndFutureSnapshotRejected() {
        assertTrue(PaperTrialPresenter.summary(snapshot(),now.plusSeconds(172800)).contains("Historical snapshot"))
        assertEquals(PaperTrialPresenter.unavailable(),PaperTrialPresenter.summary(snapshot(),now.minusSeconds(36000)))
    }
    @Test fun cloudPaperRequestIsReadOnlyAndStillRejectsOrderPaths() {
        val request = CloudRequestFactory.read("https://cloud.example.invalid","shc_access_"+"s".repeat(43),"/api/v5/ai/paper-trial")
        assertEquals("GET",request.method);assertNull(request.body)
        assertThrows(IllegalArgumentException::class.java) {
            CloudRequestFactory.read("https://cloud.example.invalid","shc_access_"+"s".repeat(43),"/api/v5/bot/trade")
        }
    }
}
