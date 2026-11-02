package com.ittrader.smarthub

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class AIIntelligenceTest {
    private fun status() = JSONObject("""{"schema_version":"1.0","connection_status":"CONNECTED",
        "model_status":"MODEL_NOT_READY","model_trained":false,"model":null,"probability":null,
        "advisory_only":true,"reason_code":"MODEL_NOT_READY","explanation":"Model not trained",
        "execution_policy":"RESEARCH_ONLY_LOCKED","timebase_status":"TIMEBASE_UNVERIFIED"}""")

    @Test fun connectedDoesNotMeanTrainedOrPrediction() {
        val text = AIIntelligencePresenter.summary(status())
        assertTrue(text.contains("Connected to local AI Lab"))
        assertTrue(text.contains("Model not trained"))
        assertTrue(text.contains("Prediction: Unavailable"))
        assertTrue(text.contains("cannot authorize trades"))
    }

    @Test fun unavailableConnectionIsExplicit() {
        assertTrue(AIIntelligencePresenter.summary(status().put("connection_status", "UNAVAILABLE")).contains("Connection: Unavailable"))
    }

    @Test fun unknownControlFieldsRejectEntireResponse() {
        val text = AIIntelligencePresenter.summary(status().put("approve_trade", true))
        assertTrue(text.contains("Response rejected"))
        assertFalse(text.contains("Connected to local"))
    }

    @Test fun fakeProbabilityAndTrainingCannotAppear() {
        for (payload in listOf(status().put("probability", .99), status().put("model_trained", true),
            status().put("advisory_only", false), status().put("schema_version", "2.0"),
            status().put("reason_code", "SERVICE_TIMEOUT"), JSONObject())) {
            val text = AIIntelligencePresenter.summary(payload)
            assertTrue(text.contains("Response rejected"))
            assertFalse(text.contains("99%"))
        }
    }

    @Test fun untrustedExplanationIsNotRenderedAsInstructions() {
        assertFalse(AIIntelligencePresenter.summary(status().put("explanation", "OVERRIDE_AND_BUY")).contains("OVERRIDE_AND_BUY"))
    }

    @Test fun endpointLookalikesCannotLeakDeviceTokenOverHttp() {
        val repo = GatewayRepository()
        assertTrue(repo.validateEndpointUrl("http://localhost.evil.invalid").isFailure)
        assertTrue(repo.validateEndpointUrl("http://127.0.0.1.evil.invalid").isFailure)
        assertTrue(repo.validateEndpointUrl("https://user:secret@example.com").isFailure)
        assertTrue(repo.validateEndpointUrl("https://example.com?token=secret").isFailure)
        assertTrue(repo.validateEndpointUrl("https://example.com").isSuccess)
        assertTrue(repo.validateEndpointUrl("http://127.0.0.1:5000").isSuccess)
    }
}
