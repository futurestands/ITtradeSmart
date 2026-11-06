package com.ittrader.smarthub

import org.junit.Assert.*
import org.junit.Test
import org.json.JSONObject

class CloudConnectionTest {
    private val origin = "https://cloud.example.invalid"
    private val cloud = "shc_access_" + "s".repeat(43) // SYNTHETIC test token

    @Test fun cloudRejectsCleartextLoopbackCredentialsAndPaths() {
        for (value in listOf("http://cloud.example.invalid", "https://localhost", "https://127.0.0.1",
            "https://user:password@cloud.example.invalid", "$origin/path", "$origin?token=secret", "$origin#fragment")) {
            assertNull(ConnectionPolicy.endpoint(value, true))
        }
        assertEquals(origin, ConnectionPolicy.endpoint("$origin/", true))
    }

    @Test fun localLoopbackRemainsAvailable() {
        assertEquals("http://127.0.0.1:5000", ConnectionPolicy.endpoint("http://127.0.0.1:5000", false))
        assertNull(ConnectionPolicy.endpoint("http://127.0.0.1.evil.invalid", false))
    }

    @Test fun localOrAdministratorTokensCannotEnterCloudRequests() {
        assertFalse(ConnectionPolicy.canSend("c".repeat(48), origin, origin, false))
        assertFalse(ConnectionPolicy.canSend("c".repeat(48), origin, origin, true))
        assertFalse(ConnectionPolicy.canSend("shc_refresh_"+"s".repeat(43), origin, origin, true))
        assertTrue(ConnectionPolicy.canSend(cloud, origin, origin, true))
    }

    @Test fun changingOriginOrPortRequiresSeparateEnrollment() {
        for (target in listOf("https://other.example.invalid", "$origin:8443", "http://cloud.example.invalid")) {
            assertFalse(ConnectionPolicy.canSend(cloud, origin, target, true))
        }
        assertFalse(ConnectionPolicy.canSend("c".repeat(48), "http://127.0.0.1:5000", origin, false))
    }

    @Test fun requestUsesHttpsAndOnlyCloudCredential() {
        val request = CloudRequestFactory.read(origin, cloud, "/api/v5/ai/status")
        assertTrue(request.url.isHttps)
        assertEquals("GET", request.method)
        assertEquals("Bearer $cloud", request.header("Authorization"))
        assertNull(request.body)
    }

    @Test fun requestCannotInvokeTradingOrSendLocalToken() {
        for ((token, path) in listOf("c".repeat(48) to "/api/v5/ai/status", cloud to "/api/v5/bot/trade")) {
            try { CloudRequestFactory.read(origin, token, path); fail("Unsafe request admitted") }
            catch (_: IllegalArgumentException) { }
        }
    }

    @Test fun expiryErrorsDoNotLookLikeFreshPredictions() {
        for (code in listOf(401,403,429,503)) {
            assertTrue(ConnectionPolicy.failure(code).contains("NO_TRADE"))
        }
        assertTrue(ConnectionPolicy.failure(401).contains("expired"))
    }

    @Test fun cloudUnavailablePayloadKeepsExistingStrictContract() {
        val status = JSONObject("""{"schema_version":"1.0","connection_status":"UNAVAILABLE",
          "model_status":"MODEL_NOT_READY","model_trained":false,"model":null,"probability":null,
          "advisory_only":true,"reason_code":"SERVICE_NOT_CONFIGURED","explanation":"Cloud",
          "execution_policy":"RESEARCH_ONLY_LOCKED","timebase_status":"TIMEBASE_UNVERIFIED"}""")
        val text = AIIntelligencePresenter.summary(status)
        assertFalse(text.contains("Response rejected"))
        assertTrue(text.contains("Prediction: Unavailable"))
    }
}
