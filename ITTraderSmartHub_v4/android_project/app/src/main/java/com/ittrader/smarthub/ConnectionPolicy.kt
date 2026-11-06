package com.ittrader.smarthub

import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

/** Pure policy: cloud credentials and local credentials never share a realm. */
object ConnectionPolicy {
    fun endpoint(value: String, cloud: Boolean): String? {
        val url = value.trim().toHttpUrlOrNull() ?: return null
        if (url.username.isNotEmpty() || url.password.isNotEmpty() || url.query != null ||
            url.fragment != null || url.encodedPath != "/") return null
        val loopback = url.host in setOf("127.0.0.1", "localhost", "::1")
        if (cloud && (!url.isHttps || loopback)) return null
        if (!cloud && !url.isHttps && !loopback) return null
        return url.toString().trimEnd('/')
    }

    fun canSend(token: String, issuedAt: String, target: String, cloud: Boolean): Boolean =
        token.length >= 32 && endpoint(issuedAt, cloud) != null &&
            endpoint(issuedAt, cloud) == endpoint(target, cloud) &&
            (cloud || issuedAt.toHttpUrlOrNull()?.host in setOf("127.0.0.1", "localhost", "::1")) &&
            (!cloud || token.startsWith("shc_access_"))

    fun failure(code: Int): String = when (code) {
        401 -> "Cloud session expired or revoked. Renew or pair again. NO_TRADE."
        403 -> "Cloud access denied. Check deployment protection and device role. NO_TRADE."
        429 -> "Cloud request limit reached. Retry later. NO_TRADE."
        else -> "Cloud unavailable (HTTP $code). NO_TRADE."
    }
}
