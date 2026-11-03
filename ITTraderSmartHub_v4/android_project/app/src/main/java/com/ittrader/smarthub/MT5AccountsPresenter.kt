package com.ittrader.smarthub

import org.json.JSONObject

/**
 * Presents registered aliases, NOT live or simulated MT5 sessions.
 * Never prints broker credentials or claims that orders are authorized.
 */
object MT5AccountsPresenter {
    private val fields = setOf("schema_version", "status", "account_count", "max_accounts", "execution_authorized", "accounts")
    private val accountFields = setOf("id", "label", "provider", "account_kind", "symbol",
        "connection_status", "read_only", "execution_authorized", "ea_execution_permitted")
    private val kinds = setOf("FREE_TRIAL", "DEMO", "EVALUATION", "FUNDED", "LIVE")
    private val providers = setOf("FTMO", "FUNDEDNEXT", "OTHER")
    private val safeId = Regex("^[a-z][a-z0-9_-]{2,31}$")
    private val safeSymbol = Regex("^[A-Za-z0-9._-]{2,32}$")

    fun unavailable(): String =
        "Account overview unavailable. Check the Windows Gateway and enrolled device.\n" +
        "No MT5 connection or broker trading has been verified."

    fun summary(response: JSONObject): String {
        if (response.keys().asSequence().toSet() != fields ||
            response.opt("schema_version") !is Int || response.optInt("schema_version") != 1 ||
            response.opt("account_count") !is Int ||
            response.opt("max_accounts") !is Int ||
            response.optInt("max_accounts") != 20 ||
            response.opt("execution_authorized") != false
        ) return unavailable()

        val status = response.optString("status")
        if (status !in setOf("REGISTRY_AVAILABLE", "NOT_CONFIGURED", "INVALID_CONFIG")) {
            return unavailable()
        }
        val count = response.optInt("account_count")
        val accounts = response.optJSONArray("accounts") ?: return unavailable()
        if (count !in 0..20 || accounts.length() != count ||
            (status != "REGISTRY_AVAILABLE" && count != 0)
        ) return unavailable()

        if (status == "NOT_CONFIGURED") {
            return "MULTI-ACCOUNT MONITOR\nNo broker accounts registered on the Windows Gateway.\n" +
                "Supports up to 20 account aliases. No trading is enabled."
        }
        if (status == "INVALID_CONFIG") {
            return "MULTI-ACCOUNT MONITOR\nWindows broker account configuration was rejected.\n" +
                "No broker connection or trading has been enabled."
        }

        val seen = mutableSetOf<String>()
        val rows = mutableListOf<String>()
        for (i in 0 until count) {
            val item = accounts.optJSONObject(i) ?: return unavailable()
            if (item.keys().asSequence().toSet() != accountFields) return unavailable()
            val id = item.optString("id")
            val label = item.optString("label")
            val provider = item.optString("provider")
            val kind = item.optString("account_kind")
            val symbol = item.optString("symbol")
            if (!safeId.matches(id) || !seen.add(id) ||
                label.length !in 1..40 || label.any { it.code < 32 || it.code > 126 } ||
                provider !in providers || kind !in kinds ||
                !safeSymbol.matches(symbol) ||
                item.optString("connection_status") != "NOT_CONNECTED" ||
                item.opt("read_only") != true ||
                item.opt("execution_authorized") != false
            ) return unavailable()

            val ea = item.opt("ea_execution_permitted")
            if (provider == "FUNDEDNEXT" && kind == "FREE_TRIAL") {
                if (ea != false) return unavailable()
            } else if (!item.isNull("ea_execution_permitted")) {
                return unavailable()
            }

            rows.add("$label · $provider · $kind\nInstrument: $symbol\nMT5: Not connected")
        }
        return buildString {
            append("MULTI-ACCOUNT MONITOR\n")
            append("Accounts registered on Windows: $count / 20\n")
            append("Registered does not mean connected to MetaTrader 5.\n\n")
            if (rows.isEmpty()) append("No account aliases have been added yet.\n")
            else rows.forEach { append(it).append("\n\n") }
            append("Orders from SmartHub: DISABLED\n")
            append("FundedNext Free Trial: automated trading prohibited.\n")
            append("FTMO: broker connection and EA permissions not yet verified.")
        }
    }
}
