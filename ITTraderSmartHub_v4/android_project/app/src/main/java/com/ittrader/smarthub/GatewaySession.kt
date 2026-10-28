package com.ittrader.smarthub

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Secure Session Credential & Endpoint Store.
 * Uses Android Keystore-backed EncryptedSharedPreferences to store short-lived API tokens.
 * Never hardcodes or stores broker account passwords in Android.
 */
object GatewaySession {
    private const val PREFS_NAME = "smarthub_secure_session"
    private const val KEY_API_TOKEN = "api_token"
    private const val KEY_GATEWAY_URL = "gateway_url"

    private var volatileToken: String = ""
    private var volatileUrl: String = "https://127.0.0.1:5000"

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
        } catch (e: Exception) {
            // Fallback for non-android unit test environments or keystore initialization issues
            e.printStackTrace()
        }
    }

    fun saveSession(context: Context?, token: String, gatewayUrl: String) {
        volatileToken = token.trim()
        volatileUrl = gatewayUrl.trim().trimEnd('/')

        if (context != null) {
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
                prefs.edit()
                    .putString(KEY_API_TOKEN, volatileToken)
                    .putString(KEY_GATEWAY_URL, volatileUrl)
                    .apply()
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }

    var apiToken: String
        get() = volatileToken
        set(value) { volatileToken = value }

    var gatewayUrl: String
        get() = volatileUrl
        set(value) { volatileUrl = value }

    fun isAuthenticated(): Boolean = volatileToken.isNotBlank() && volatileToken.length >= 32
}
