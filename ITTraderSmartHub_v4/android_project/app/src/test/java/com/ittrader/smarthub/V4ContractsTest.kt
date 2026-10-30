package com.ittrader.smarthub

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class V4ContractsTest {

    @Test
    fun testDeviceEnrollmentBuilder() {
        val payload = V4ApiContracts.deviceEnroll("dev-123", "Test Phone", "PAIR-123456")
        assertEquals("dev-123", payload.getString("device_id"))
        assertEquals("Test Phone", payload.getString("device_name"))
        assertEquals("PAIR-123456", payload.getString("pairing_code"))
    }

    @Test
    fun testEndpointValidation() {
        val repo = GatewayRepository()
        assertTrue(repo.validateEndpointUrl("https://smarthub.internal").isSuccess)
        assertTrue(repo.validateEndpointUrl("http://127.0.0.1:5000").isSuccess)
        assertTrue(repo.validateEndpointUrl("http://localhost:5000").isSuccess)

        val unencrypted = repo.validateEndpointUrl("http://192.168.1.100:5000")
        assertTrue(unencrypted.isFailure)
        assertTrue(unencrypted.exceptionOrNull()?.message?.contains("Strict TLS Required") == true)
    }

    @Test
    fun testRiskContextBuilder() {
        val payload = V4ApiContracts.riskContext(1.5, "EURUSD")
        assertEquals(1, payload.getInt("schema_version"))
        assertEquals(1.5, payload.getDouble("baseline_risk_pct"), 0.0001)
        assertEquals("EURUSD", payload.getString("symbol"))
    }

    @Test
    fun testAlertQueryBuilder() {
        val payload = V4ApiContracts.alertQuery("evt-5", 10)
        assertEquals(1, payload.getInt("schema_version"))
        assertEquals("combined", payload.getString("console"))
        assertEquals(10, payload.getInt("limit"))
        assertEquals("evt-5", payload.getString("since_event_id"))
    }

    @Test
    fun testIncidentResearchBuilder() {
        val payload = V4ApiContracts.incidentResearch("2026-09-01T00:00:00Z", "2026-10-01T00:00:00Z", "rule_violation")
        assertEquals(1, payload.getInt("schema_version"))
        assertEquals("2026-09-01T00:00:00Z", payload.getString("start_utc"))
        assertEquals("rule_violation", payload.getString("outcome"))
    }

    @Test
    fun testRiskResultSummaryUnavailable() {
        val json = JSONObject().apply {
            put("status", "UNAVAILABLE")
            put("policy_version", "risk-v4.0")
            put("data_fresh", false)
            put("reason_codes", org.json.JSONArray().put("SERVER_TELEMETRY_MISSING"))
        }
        val summary = V4ApiContracts.riskResultSummary(json)
        assertTrue(summary.contains("UNAVAILABLE"))
        assertTrue(summary.contains("SERVER_TELEMETRY_MISSING"))
    }

    @Test
    fun testRiskCalculationFormula() {
        val baseRiskPct = 2.0
        val stressIndex = 40 // 40% stress
        val riskMitigationFactor = 1.0 - 0.5 * stressIndex / 100.0
        val adjustedRiskPct = baseRiskPct * riskMitigationFactor // 2.0 * (1 - 0.2) = 1.6%

        assertEquals(1.6, adjustedRiskPct, 0.001)
    }

    @Test
    fun testGatewaySessionAuthentication() {
        GatewaySession.apiToken = ""
        assertFalse(GatewaySession.isAuthenticated())

        GatewaySession.apiToken = "12345678901234567890123456789012"
        assertTrue(GatewaySession.isAuthenticated())

        GatewaySession.logout(null)
        assertFalse(GatewaySession.isAuthenticated())
    }
}
