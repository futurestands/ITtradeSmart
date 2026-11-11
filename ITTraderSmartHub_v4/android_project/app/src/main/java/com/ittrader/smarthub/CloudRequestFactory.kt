package com.ittrader.smarthub

import okhttp3.Request

/** Only cloud device tokens and allowlisted read-only paths can enter requests. */
object CloudRequestFactory {
    fun read(endpoint: String, access: String, path: String): Request {
        val origin = ConnectionPolicy.endpoint(endpoint, true)
            ?: throw IllegalArgumentException("Cloud HTTPS origin required")
        require(ConnectionPolicy.canSend(access, origin, origin, true))
        require(path in setOf("/api/v5/ai/status", "/api/v5/ai/research-progress", "/api/v5/ai/paper-trial"))
        return Request.Builder().url(origin+path).header("Authorization", "Bearer $access")
            .header("Cache-Control", "no-cache, no-store").get().build()
    }
}
