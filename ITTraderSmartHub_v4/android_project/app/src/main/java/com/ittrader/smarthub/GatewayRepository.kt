package com.ittrader.smarthub

import okhttp3.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Repository layer handling HTTP communications with the secure Python gateway.
 */
class GatewayRepository {

    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    fun syncMt5(callback: (Result<JSONObject>) -> Unit) {
        val endpoint = GatewaySession.gatewayUrl
        val token = GatewaySession.apiToken

        if (!endpoint.startsWith("https://") && !endpoint.startsWith("http://127.0.0.1") && !endpoint.startsWith("http://localhost")) {
            callback(Result.failure(IllegalArgumentException("Use an HTTPS or localhost gateway URL. Never transmit unencrypted passwords.")))
            return
        }
        if (!GatewaySession.isAuthenticated()) {
            callback(Result.failure(IllegalStateException("Gateway is not authenticated. Save a valid API token in Keystore.")))
            return
        }

        val url = "$endpoint/analyze"
        val body = "{}".toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())
        val request = Request.Builder()
            .url(url)
            .header("Authorization", "Bearer $token")
            .post(body)
            .build()

        executeRequest(request, callback)
    }

    fun queryRiskContext(baselineRiskPct: Double, symbol: String, callback: (Result<JSONObject>) -> Unit) {
        val endpoint = GatewaySession.gatewayUrl
        val token = GatewaySession.apiToken

        if (!GatewaySession.isAuthenticated()) {
            callback(Result.failure(IllegalStateException("Gateway is not authenticated. Save a valid API token in Keystore.")))
            return
        }

        val payload = V4ApiContracts.riskContext(baselineRiskPct, symbol)
        val body = payload.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())
        val request = Request.Builder()
            .url("$endpoint/api/v4/risk/context")
            .header("Authorization", "Bearer $token")
            .post(body)
            .build()

        executeRequest(request, callback)
    }

    fun queryAlerts(cursor: String? = null, callback: (Result<JSONObject>) -> Unit) {
        val endpoint = GatewaySession.gatewayUrl
        val token = GatewaySession.apiToken

        if (!GatewaySession.isAuthenticated()) {
            callback(Result.failure(IllegalStateException("Gateway is not authenticated. Save a valid API token in Keystore.")))
            return
        }

        val payload = V4ApiContracts.alertQuery(cursor)
        val body = payload.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())
        val request = Request.Builder()
            .url("$endpoint/api/v4/alerts/query")
            .header("Authorization", "Bearer $token")
            .post(body)
            .build()

        executeRequest(request, callback)
    }

    fun queryResearch(startUtc: String, endUtc: String, outcome: String, callback: (Result<JSONObject>) -> Unit) {
        val endpoint = GatewaySession.gatewayUrl
        val token = GatewaySession.apiToken

        if (!GatewaySession.isAuthenticated()) {
            callback(Result.failure(IllegalStateException("Gateway is not authenticated. Save a valid API token in Keystore.")))
            return
        }

        val payload = V4ApiContracts.incidentResearch(startUtc, endUtc, outcome)
        val body = payload.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())
        val request = Request.Builder()
            .url("$endpoint/api/v4/research/incident-impact")
            .header("Authorization", "Bearer $token")
            .post(body)
            .build()

        executeRequest(request, callback)
    }

    private fun executeRequest(request: Request, callback: (Result<JSONObject>) -> Unit) {
        httpClient.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback(Result.failure(e))
            }

            override fun onResponse(call: Call, response: Response) {
                val respStr = response.body?.string() ?: ""
                if (response.isSuccessful) {
                    try {
                        val json = JSONObject(respStr)
                        callback(Result.success(json))
                    } catch (e: Exception) {
                        callback(Result.failure(Exception("Malformed gateway JSON response")))
                    }
                } else {
                    val errMsg = try {
                        JSONObject(respStr).optString("error", "HTTP ${response.code}")
                    } catch (e: Exception) {
                        "HTTP ${response.code} error from gateway"
                    }
                    callback(Result.failure(Exception(errMsg)))
                }
            }
        })
    }
}
