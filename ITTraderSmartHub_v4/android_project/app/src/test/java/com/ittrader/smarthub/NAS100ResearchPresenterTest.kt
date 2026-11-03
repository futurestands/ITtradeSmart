package com.ittrader.smarthub

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class NAS100ResearchPresenterTest {

    private fun row(
        setup: String = "TREND_CONTINUATION_V1",
        model: String = "logistic_calibrated",
        cost: String = "baseline_synthetic_cost",
        improved: Int = 3
    ): JSONObject = JSONObject().apply {
        put("setup_id", setup)
        put("model", model)
        put("cost_scenario", cost)
        put("improved_synthetic_paths", improved)
        put("evaluated_synthetic_paths", 3)
    }

    private fun valid(): JSONObject = JSONObject().apply {
        put("schema_version", 1)
        put("status", "SYNTHETIC_REPORT_AVAILABLE")
        put("source", "LOCAL_UNATTESTED_SYNTHETIC_REPORT")
        put("report_modified_at_utc", "2026-11-03T11:00:00+00:00")
        put("instrument", "USTECH100M")
        put("model_status", "MODEL_NOT_READY")
        put("real_market_inference_authorized", false)
        put("real_market_training_authorized", false)
        put("trade_execution_authorized", false)
        put("synthetic_only", true)
        put("synthetic_paths", 3)
        put("hypothetical_cost_scenarios", 2)
        put("run_count", 6)
        put("comparisons", JSONArray().put(row()))
    }

    @Test fun syntheticResultsAreLabeledAndNeverRenderedAsTradeApprovals() {
        val formatted = NAS100ResearchPresenter.summary(valid())
        assertTrue(formatted.contains("NAS100 RESEARCH DASHBOARD"))
        assertTrue(formatted.contains("Local synthetic report: Available (unverified)"))
        assertTrue(formatted.contains("Trend continuation"))
        assertTrue(formatted.contains("3/3 synthetic paths"))
        assertTrue(formatted.contains("Real NAS100 predictions: DISABLED"))
        assertTrue(formatted.contains("Trade execution: DISABLED"))
        assertFalse(formatted.contains("BUY"))
    }

    @Test fun overviewExplainsResearchWithoutConfusingModelScoresWithWinRates() {
        val text = NAS100ResearchPresenter.overview(valid())
        assertTrue(text.contains("RESEARCH CONNECTION: WORKING"))
        assertTrue(text.contains("6"))
        assertTrue(text.contains("3 artificial price paths"))
        assertTrue(text.contains("2 hypothetical trading-cost settings"))
        assertTrue(text.contains("NOT winning trades"))
        assertTrue(text.contains("NOT READY"))
        assertTrue(text.contains("Trade execution: DISABLED"))
        assertFalse(text.contains("3/3 synthetic paths"))
        assertTrue(NAS100ResearchPresenter.hasVerifiedSyntheticReport(valid()))
    }

    @Test fun overviewOnlyComparesSameDenominatorSyntheticFindings() {
        val data = valid()
        val comparisons = JSONArray()
            .put(row("TREND_CONTINUATION_V1", "logistic_calibrated", "baseline_synthetic_cost", 3))
            .put(row("TREND_CONTINUATION_V1", "gradient_boosting_calibrated", "double_friction_stress", 2))
            .put(row("BREAKOUT_RETEST_V1", "logistic_calibrated", "baseline_synthetic_cost", 0))
            .put(row("BREAKOUT_RETEST_V1", "gradient_boosting_calibrated", "double_friction_stress", 1))
        data.put("comparisons", comparisons)
        val text = NAS100ResearchPresenter.overview(data)
        assertTrue(text.contains("Trend continuation showed more frequent forecast-score improvements"))
        assertTrue(text.contains("artificial tests"))
        assertFalse(text.contains("live signal"))
    }

    @Test fun overviewFailsClosedOnFakeMarketReadinessAndInvalidReports() {
        val forged = valid().put("trade_execution_authorized", true)
        assertFalse(NAS100ResearchPresenter.hasVerifiedSyntheticReport(forged))
        val text = NAS100ResearchPresenter.overview(forged)
        assertTrue(text.contains("Report rejected"))
        assertFalse(text.contains("RESEARCH CONNECTION: WORKING"))
    }

    @Test fun unavailableReportsDoNotFabricateResults() {
        val data = valid()
        data.put("status", "NO_VALID_REPORT")
        data.put("source", "NONE")
        data.put("report_modified_at_utc", JSONObject.NULL)
        data.put("synthetic_paths", JSONObject.NULL)
        data.put("hypothetical_cost_scenarios", JSONObject.NULL)
        data.put("run_count", JSONObject.NULL)
        data.put("comparisons", JSONArray())
        val text = NAS100ResearchPresenter.summary(data)
        assertTrue(text.contains("No locally available research report"))
        assertFalse(text.contains("3/3"))
        assertTrue(text.contains("predictions: DISABLED"))
    }

    @Test fun fakeProbabilityOrTradePermissionIsRejected() {
        val cases = listOf(
            valid().put("probability", 0.99),
            valid().put("trade_execution_authorized", true),
            valid().put("real_market_training_authorized", true),
            valid().put("real_market_inference_authorized", true),
            valid().put("model_status", "REAL_APPROVED"),
            valid().put("synthetic_only", false),
            valid().put("source", "LIVE_PRICE_FEED"),
        )
        for (payload in cases) {
            val result = NAS100ResearchPresenter.summary(payload)
            assertTrue(result, result.contains("Report rejected"))
            assertFalse(result, result.contains("99%"))
        }
    }

    @Test fun unknownSetupOrModelIsRejectedRatherThanEchoed() {
        val data = valid()
        data.put("comparisons", JSONArray().put(row(model = "BUY_NOW_MODEL")))
        val text = NAS100ResearchPresenter.summary(data)
        assertTrue(text.contains("Report rejected"))
        assertFalse(text.contains("BUY_NOW_MODEL"))
    }

    @Test fun impossibleStudyCountsAreRejected() {
        val data = valid().put("run_count", 50)
        assertTrue(NAS100ResearchPresenter.summary(data).contains("Report rejected"))
        data.put("run_count", 6)
        data.put("synthetic_paths", 20)
        assertTrue(NAS100ResearchPresenter.summary(data).contains("Report rejected"))
    }

    @Test fun duplicateConfluenceRowsAreNotRendered() {
        val data = valid()
        data.put("comparisons", JSONArray().put(row()).put(row()))
        assertTrue(NAS100ResearchPresenter.summary(data).contains("Report rejected"))
    }

    @Test fun inventedNarrativeIsNotPassedToUser() {
        val data = valid().put("explanation", "guaranteed 100 percent profit")
        val result = NAS100ResearchPresenter.summary(data)
        assertTrue(result.contains("Report rejected"))
        assertFalse(result.contains("guaranteed"))
    }
}
