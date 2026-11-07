package com.ittrader.smarthub

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import org.json.JSONObject
import java.security.MessageDigest
import java.util.UUID

/** Existing local preference keys are preserved; cloud sessions are origin-bound. */
object GatewaySession {
    private var prefs: SharedPreferences? = null
    private var localToken = ""
    private var localUrl = "https://127.0.0.1:5000"
    private var localIssuedAt = localUrl
    private var cloudUrl = "https://ittrader-smarthub-phase3-phone-preview-futurestands.vercel.app"
    private var cloudToken = ""
    private var cloudRefresh = ""
    private var cloudExpiry = 0L
    private var cloudIssuedAt = ""
    private var id = ""
    var isCloud: Boolean = false
        private set

    private fun encrypted(context: Context): SharedPreferences = EncryptedSharedPreferences.create(
        context, "smarthub_secure_session",
        MasterKey.Builder(context).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM)

    private fun prefix(url: String): String = "cloud_" + MessageDigest.getInstance("SHA-256")
        .digest(url.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }

    @Synchronized fun init(context: Context) {
        try {
            prefs = encrypted(context)
            localUrl = prefs!!.getString("gateway_url", localUrl) ?: localUrl
            localIssuedAt = localUrl
            localToken = prefs!!.getString("api_token", "") ?: ""
            cloudUrl = prefs!!.getString("cloud_gateway_url", cloudUrl) ?: cloudUrl
            id = prefs!!.getString("device_id", "") ?: ""
            if (id.isBlank()) {
                id = "dev-" + UUID.randomUUID().toString().take(12)
                if (!prefs!!.edit().putString("device_id", id).commit()) throw IllegalStateException()
            }
            isCloud = prefs!!.getBoolean("cloud_mode", false)
            loadCloud()
        } catch (_: Exception) {
            prefs = null
            localToken = ""
            cloudToken = ""
            cloudRefresh = ""
            if (id.isBlank()) id = "dev-" + UUID.randomUUID().toString().take(12)
        }
    }

    private fun loadCloud() {
        val normalized = ConnectionPolicy.endpoint(cloudUrl, true)
        val key = normalized?.let { prefix(it) }
        cloudToken = key?.let { prefs?.getString(it + "_access", "") } ?: ""
        cloudRefresh = key?.let { prefs?.getString(it + "_refresh", "") } ?: ""
        cloudExpiry = key?.let { prefs?.getLong(it + "_expiry", 0) } ?: 0
        cloudIssuedAt = normalized ?: ""
    }

    @Synchronized fun selectCloud(enabled: Boolean): Boolean {
        try {
            if (prefs?.edit()?.putBoolean("cloud_mode", enabled)?.commit() != true) return false
        } catch (_: Exception) { return false }
        isCloud = enabled
        loadCloud()
        return true
    }

    var gatewayUrl: String
        @Synchronized get() = if (isCloud) cloudUrl else localUrl
        @Synchronized set(value) {
            if (isCloud) {
                cloudUrl = value.trim().trimEnd('/')
                loadCloud()
                prefs?.edit()?.putString("cloud_gateway_url", cloudUrl)?.commit()
            } else localUrl = value.trim().trimEnd('/')
        }

    var apiToken: String
        @Synchronized get() {
            val token = if (isCloud) cloudToken else localToken
            val issuedAt = if (isCloud) cloudIssuedAt else localIssuedAt
            return if (ConnectionPolicy.canSend(token, issuedAt, gatewayUrl, isCloud)) token else ""
        }
        @Synchronized set(value) {
            // Legacy test/local API only; it cannot import an administrator token into cloud mode.
            if (!isCloud) { localToken = value; localIssuedAt = localUrl }
        }

    @Synchronized fun saveSession(context: Context?, token: String, gatewayUrl: String): Boolean {
        if (isCloud) return false
        val url = ConnectionPolicy.endpoint(gatewayUrl, false) ?: return false
        return try {
            val storage = prefs ?: context?.let { encrypted(it) } ?: return false
            if (!storage.edit().putString("api_token", token.trim()).putString("gateway_url", url).commit()) return false
            prefs = storage
            localToken = token.trim(); localUrl = url; localIssuedAt = url
            true
        } catch (_: Exception) { false }
    }

    @Synchronized fun saveCloudSession(response: JSONObject, endpoint: String): Boolean {
        val url = ConnectionPolicy.endpoint(endpoint, true) ?: return false
        if (!isCloud || url != ConnectionPolicy.endpoint(cloudUrl, true)) return false
        val access = response.optString("device_token")
        val refresh = response.optString("refresh_token")
        val expires = response.optLong("expires_at", 0)
        if (!access.startsWith("shc_access_") || access.length < 40 ||
            !refresh.startsWith("shc_refresh_") || refresh.length < 40 ||
            expires <= System.currentTimeMillis()/1000) return false
        val storage = prefs ?: return false
        val key = prefix(url)
        if (!storage.edit().putString(key + "_access", access)
                .putString(key + "_refresh", refresh).putLong(key + "_expiry", expires)
                .putString("cloud_gateway_url", url).commit()) return false
        cloudUrl = url; cloudIssuedAt = url; cloudToken = access
        cloudRefresh = refresh; cloudExpiry = expires
        return true
    }

    val refreshToken: String @Synchronized get() = if (isCloud &&
        cloudIssuedAt == ConnectionPolicy.endpoint(cloudUrl, true)) cloudRefresh else ""
    fun needsRenewal(): Boolean = isCloud && cloudExpiry <= System.currentTimeMillis()/1000 + 30
    val deviceId: String get() = if (id.isNotBlank()) id else "dev-default"
    fun isAuthenticated(): Boolean = apiToken.isNotBlank() && (!isCloud || !needsRenewal())

    @Synchronized fun logout(context: Context?): Boolean {
        return try {
            val storage = prefs ?: context?.let { encrypted(it) }
            if (isCloud) {
                val key = prefix(cloudIssuedAt)
                cloudToken = ""; cloudRefresh = ""; cloudExpiry = 0
                storage?.edit()?.remove(key + "_access")?.remove(key + "_refresh")?.remove(key + "_expiry")?.commit() ?: (context == null)
            } else {
                localToken = ""
                storage?.edit()?.remove("api_token")?.commit() ?: (context == null)
            }
        } catch (_: Exception) { false }
    }
}
