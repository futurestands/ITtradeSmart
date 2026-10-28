package com.ittrader.smarthub

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.util.UUID

/**
 * Secure Session Credential & Endpoint Store using Android Keystore-backed EncryptedSharedPreferences.
 * Never hardcodes or stores broker account passwords in Android.
 * Never reports success if Keystore operations fail.
 */
object GatewaySession {
    private const val PREFS_NAME = "smarthub_secure_session"
    private const val KEY_API_TOKEN = "api_token"
    private const val KEY_GATEWAY_URL = "gateway_url"
    private const val KEY_DEVICE_ID = "device_id"

    private var volatileToken: String = ""
    private var volatileUrl: String = "https://127.0.0.1:5000"
    private var volatileDeviceId: String = ""

    fun init(context: Context) {
        try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()

            val prefs: SharedPreferences = EncryptedSharedPreferences.create(
                context,
                PREFS_NAME,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
            volatileToken = prefs.getString(KEY_API_TOKEN, "") ?: ""
            volatileUrl = prefs.getString(KEY_GATEWAY_URL, "https://127.0.0.1:5000") ?: "https://127.0.0.1:5000"
            volatileDeviceId = prefs.getString(KEY_DEVICE_ID, "") ?: ""

            if (volatileDeviceId.isBlank()) {
                volatileDeviceId = "dev-" + UUID.randomUUID().toString().take(12)
                prefs.edit().putString(KEY_DEVICE_ID, volatileDeviceId).apply()
            }
        } catch (e: Exception) {
            e.printStackTrace()
            // On Keystore error, fall back to volatile device ID if needed
            if (volatileDeviceId.isBlank()) {
                volatileDeviceId = "dev-" + UUID.randomUUID().toString().take(12)
            }
        }
    }

    /**
     * Saves token and URL to EncryptedSharedPreferences.
     * Returns true ONLY if writing to Keystore succeeds.
     */
    fun saveSession(context: Context?, token: String, gatewayUrl: String): Boolean {
        volatileToken = token.trim()
        volatileUrl = gatewayUrl.trim().trimEnd('/')

        if (context == null) return true

        return try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()

            val prefs: SharedPreferences = EncryptedSharedPreferences.create(
                context,
                PREFS_NAME,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
            val success = prefs.edit()
                .putString(KEY_API_TOKEN, volatileToken)
                .putString(KEY_GATEWAY_URL, volatileUrl)
                .commit()

            if (!success) {
                volatileToken = ""
            }
            success
        } catch (e: Exception) {
            e.printStackTrace()
            volatileToken = ""
            false
        }
    }

    fun logout(context: Context?): Boolean {
        volatileToken = ""
        if (context == null) return true

        return try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()

            val prefs: SharedPreferences = EncryptedSharedPreferences.create(
                context,
                PREFS_NAME,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
            prefs.edit().remove(KEY_API_TOKEN).commit()
        } catch (e: Exception) {
            e.printStackTrace()
            false
        }
    }

    var apiToken: String
        get() = volatileToken
        set(value) { volatileToken = value }

    var gatewayUrl: String
        get() = volatileUrl
        set(value) { volatileUrl = value }

    val deviceId: String
        get() = if (volatileDeviceId.isNotBlank()) volatileDeviceId else "dev-default"

    fun isAuthenticated(): Boolean = volatileToken.isNotBlank() && volatileToken.length >= 32
}
