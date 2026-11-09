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
    private var cloudPrefs: SharedPreferences? = null
    private const val DEFAULT_CLOUD_URL = "https://ittrader-smarthub-phase3-phone-preview-futurestands.vercel.app"
    var storageStatus: String = "NOT_INITIALIZED"
        private set
    private var localToken = ""
    private var localUrl = "https://127.0.0.1:5000"
    private var localIssuedAt = localUrl
    private var cloudUrl = DEFAULT_CLOUD_URL
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

    private fun encryptedCloud(context: Context): SharedPreferences = EncryptedSharedPreferences.create(
        context, "smarthub_cloud_session_v1",
        MasterKey.Builder(context, "smarthub_cloud_master_key_v1")
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build(),
        EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
        EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM)

    private fun prefix(url: String): String = "cloud_" + MessageDigest.getInstance("SHA-256")
        .digest(url.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }

    @Synchronized fun init(context: Context) {
        initStores({ encrypted(context) }, { encryptedCloud(context) })
    }

    // Storage providers permit failure-injection tests without an Android
    // Keystore or touching the installed user's preferences or key aliases.
    @Synchronized internal fun initStores(legacy: () -> SharedPreferences, cloud: () -> SharedPreferences) {
        prefs = null; cloudPrefs = null
        localUrl = "https://127.0.0.1:5000"; localIssuedAt = localUrl; localToken = ""
        cloudUrl = DEFAULT_CLOUD_URL; cloudToken = ""; cloudRefresh = ""; cloudExpiry = 0
        cloudIssuedAt = ""; isCloud = false; id = ""; storageStatus = "NOT_INITIALIZED"
        try {
            prefs = legacy()
            localUrl = prefs!!.getString("gateway_url", localUrl) ?: localUrl
            localIssuedAt = localUrl
            localToken = prefs!!.getString("api_token", "") ?: ""
            cloudUrl = prefs!!.getString("cloud_gateway_url", cloudUrl) ?: cloudUrl
            id = prefs!!.getString("device_id", "") ?: ""
        } catch (_: Exception) {
            prefs = null
            localToken = ""
            // Preserve the legacy file and key. It must not block the separate
            // cloud realm or be silently erased as a recovery technique.
        }
        try {
            val storage = cloud()
            if (!storage.getBoolean("cloud_storage_v1", false)) {
                val url = ConnectionPolicy.endpoint(cloudUrl, true) ?: DEFAULT_CLOUD_URL
                val key = prefix(url)
                val legacyMode = try { prefs?.getBoolean("cloud_mode", false) ?: false } catch (_: Exception) { false }
                val legacySession = try {
                    Triple(prefs?.getString(key + "_access", "") ?: "",
                        prefs?.getString(key + "_refresh", "") ?: "",
                        prefs?.getLong(key + "_expiry", 0) ?: 0)
                } catch (_: Exception) { Triple("", "", 0L) }
                val editor = storage.edit().putBoolean("cloud_storage_v1", true)
                    .putString("cloud_gateway_url", url)
                    .putBoolean("cloud_mode", legacyMode)
                // Copy only the currently selected cloud origin from readable
                // encrypted legacy storage. Never import the local API token.
                editor.putString(key + "_access", legacySession.first)
                    .putString(key + "_refresh", legacySession.second)
                    .putLong(key + "_expiry", legacySession.third)
                if (!editor.commit()) throw IllegalStateException("Cloud migration commit failed")
            }
            cloudUrl = storage.getString("cloud_gateway_url", DEFAULT_CLOUD_URL) ?: DEFAULT_CLOUD_URL
            if (id.isBlank()) id = storage.getString("device_id", "") ?: ""
            if (id.isBlank()) id = "dev-" + UUID.randomUUID().toString().take(12)
            if (!storage.edit().putString("device_id", id).commit()) throw IllegalStateException("Cloud identity commit failed")
            cloudPrefs = storage
            loadCloud()
            isCloud = storage.getBoolean("cloud_mode", false)
            storageStatus = if (prefs == null) "CLOUD_READY_LEGACY_UNAVAILABLE" else "READY"
        } catch (error: Exception) {
            cloudPrefs = null; cloudToken = ""; cloudRefresh = ""; cloudExpiry = 0; isCloud = false
            // Class names are diagnostics; exception messages may contain data.
            storageStatus = "CLOUD_STORAGE_UNAVAILABLE:" + error.javaClass.simpleName
        }
        if (id.isBlank()) id = "dev-" + UUID.randomUUID().toString().take(12)
    }

    private fun loadCloud() {
        val normalized = ConnectionPolicy.endpoint(cloudUrl, true)
        val key = normalized?.let { prefix(it) }
        cloudToken = key?.let { cloudPrefs?.getString(it + "_access", "") } ?: ""
        cloudRefresh = key?.let { cloudPrefs?.getString(it + "_refresh", "") } ?: ""
        cloudExpiry = key?.let { cloudPrefs?.getLong(it + "_expiry", 0) } ?: 0
        cloudIssuedAt = normalized ?: ""
    }

    @Synchronized fun selectCloud(enabled: Boolean): Boolean {
        try {
            loadCloud()
            if (cloudPrefs?.edit()?.putBoolean("cloud_mode", enabled)?.commit() != true) {
                if (cloudPrefs != null) storageStatus = "CLOUD_STORAGE_COMMIT_FAILED"
                return false
            }
        } catch (error: Exception) {
            storageStatus = "CLOUD_STORAGE_UNAVAILABLE:" + error.javaClass.simpleName
            return false
        }
        isCloud = enabled
        return true
    }

    var gatewayUrl: String
        @Synchronized get() = if (isCloud) cloudUrl else localUrl
        @Synchronized set(value) {
            if (isCloud) {
                cloudUrl = value.trim().trimEnd('/')
                loadCloud()
                cloudPrefs?.edit()?.putString("cloud_gateway_url", cloudUrl)?.commit()
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
        val storage = cloudPrefs ?: return false
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
            val storage = if (isCloud) cloudPrefs else prefs ?: context?.let { encrypted(it) }
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
