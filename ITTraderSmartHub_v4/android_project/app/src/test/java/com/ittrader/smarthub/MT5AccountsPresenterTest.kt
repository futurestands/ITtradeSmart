package com.ittrader.smarthub

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class MT5AccountsPresenterTest {
    private fun account(
        id: String = "ftmo-trial",
        provider: String = "FTMO",
        kind: String = "FREE_TRIAL",
        ea: Any = JSONObject.NULL
    ): JSONObject = JSONObject().apply {
        put("id", id)
        put("label", "My Trial")
        put("provider", provider)
        put("account_kind", kind)
        put("symbol", "US100.cash")
        put("connection_status", "NOT_CONNECTED")
        put("read_only", true)
        put("execution_authorized", false)
        put("ea_execution_permitted", ea)
    }

    private fun response(accounts: JSONArray = JSONArray()): JSONObject = JSONObject().apply {
        put("schema_version", 1)
        put("status", "REGISTRY_AVAILABLE")
        put("account_count", accounts.length())
        put("max_accounts", 20)
        put("execution_authorized", false)
        put("accounts", accounts)
    }

    @Test fun threeAccountsAreShownAsUnconnected() {
        val entries = JSONArray()
            .put(account())
            .put(account("fundednext-trial", "FUNDEDNEXT", "FREE_TRIAL", false))
            .put(account("independent-demo", "OTHER", "DEMO"))
        val text = MT5AccountsPresenter.summary(response(entries))
        assertTrue(text.contains("3 / 20"))
        assertTrue(text.contains("FTMO"))
        assertTrue(text.contains("FUNDEDNEXT"))
        assertTrue(text.contains("MT5: Not connected"))
        assertTrue(text.contains("Orders from SmartHub: DISABLED"))
        assertFalse(text.contains("Connected successfully"))
        assertFalse(text.contains("Buy now"))
    }

    @Test fun unconfiguredIsClearAndSafe() {
        val data = response()
        data.put("status", "NOT_CONFIGURED")
        val text = MT5AccountsPresenter.summary(data)
        assertTrue(text.contains("No broker accounts registered"))
        assertTrue(text.contains("No trading is enabled"))
    }

    @Test fun fabricatedConnectedOrExecutableAccountIsRejected() {
        val entry = account().put("connection_status", "CONNECTED")
        var text = MT5AccountsPresenter.summary(response(JSONArray().put(entry)))
        assertTrue(text.contains("unavailable"))
        assertFalse(text.contains("Connected successfully"))

        entry.put("connection_status", "NOT_CONNECTED")
        entry.put("execution_authorized", true)
        text = MT5AccountsPresenter.summary(response(JSONArray().put(entry)))
        assertTrue(text.contains("unavailable"))
    }

    @Test fun addedBrokerCredentialsOrClaimsFailClosed() {
        val entry = account().put("password", "private")
        val text = MT5AccountsPresenter.summary(response(JSONArray().put(entry)))
        assertTrue(text.contains("unavailable"))
        assertFalse(text.contains("private"))

        val forged = response(JSONArray().put(account()))
        forged.put("execution_authorized", true)
        assertTrue(MT5AccountsPresenter.summary(forged).contains("unavailable"))
    }

    @Test fun fundednextTrialMustExplicitlyProhibitEA() {
        val fundednext = account("fundednext-trial", "FUNDEDNEXT", "FREE_TRIAL")
        assertTrue(MT5AccountsPresenter.summary(response(JSONArray().put(fundednext))).contains("unavailable"))
        fundednext.put("ea_execution_permitted", false)
        assertTrue(MT5AccountsPresenter.summary(response(JSONArray().put(fundednext))).contains("FundedNext"))
    }

    @Test fun duplicateAccountIdAndInaccurateCountsAreRejected() {
        val dup = JSONArray().put(account()).put(account())
        assertTrue(MT5AccountsPresenter.summary(response(dup)).contains("unavailable"))
        val missing = response(JSONArray().put(account())).put("account_count", 5)
        assertTrue(MT5AccountsPresenter.summary(missing).contains("unavailable"))
    }
}
