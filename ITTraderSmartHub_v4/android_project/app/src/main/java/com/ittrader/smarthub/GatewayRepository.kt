package com.ittrader.smarthub

import okhttp3.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Repository layer handling HTTP communications with strict TLS certificate verification and centralized HTTPS validation.
 */
class GatewayRepository {

    // Strict system TLS configuration with 10s connect / 15s read timeouts
    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()

    fun validateEndpointUrl(urlStr: String): Result<String> {
        val trimmed = urlStr.trim().trimEnd('/')
        if (trimmed.startsWith("http://127.0.0.1") || trimmed.startsWith("http://localhost")) {
            return Result.success(trimmed)
        }
        if (!trimmed.startsWith("https://")) {
            return Result.failure(IllegalArgumentException("Strict TLS Required: Gateway URL must use an encrypted HTTPS endpoint."))
        }
        return Result.success(trimmed)
    }

    fun enrollDevice(gatewayUrl: String, pairingCode: String, deviceName: String, callback: (Result<JSONObject>) -> Unit) {
        val valRes = validateEndpointUrl(gatewayUrl)
        val endpoint = valRes.getOrElse {
            callback(Result.failure(it))
            return
        }

        if (pairingCode.isBlank()) {
            callback(Result.failure(IllegalArgumentException("Pairing code is required")))
            return
        }

        val deviceId = GatewaySession.deviceId
        val payload = V4ApiContracts.deviceEnroll(deviceId, deviceName, pairingCode)
        val body = payload.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

        val request = Request.Builder()
            .url("$endpoint/api/v4/device/enroll")
            .post(body)
            .build()

        executeRequest(request, callback)
    }

    fun revokeSession(deviceId: String, callback: (Result<JSONObject>) -> Unit) {
        val valRes = validateEndpointUrl(GatewaySession.gatewayUrl)
        val endpoint = valRes.getOrElse {
            callback(Result.failure(it))
            return
        }

        if (!GatewaySession.isAuthenticated()) {
            callback(Result.failure(IllegalStateException("No active authenticated session")))
            return
        }

        val token = GatewaySession.apiToken
        val payload = V4ApiContracts.deviceRevoke(deviceId)
        val body = payload.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

        val request = Request.Builder()
            .url("$endpoint/api/v4/device/revoke")
            .header("Authorization", "Bearer $token")
            .post(body)
            .build()

        executeRequest(request, callback)
    }

    fun syncMt5(callback: (Result<JSONObject>) -> Unit) {
        val valRes = validateEndpointUrl(GatewaySession.gatewayUrl)
        val endpoint = valRes.getOrElse {
            callback(Result.failure(it))
            return
        }

        if (!GatewaySession.isAuthenticated()) {
            callback(Result.failure(IllegalStateException("Gateway is not authenticated. Enroll device with a pairing code.")))
            return
        }

        val token = GatewaySession.apiToken
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
        val valRes = validateEndpointUrl(GatewaySession.gatewayUrl)
        val endpoint = valRes.getOrElse {
            callback(Result.failure(it))
            return
        }

        if (!GatewaySession.isAuthenticated()) {
            callback(Result.failure(IllegalStateException("Gateway is not authenticated. Enroll device with a pairing code.")))
            return
        }

        val token = GatewaySession.apiToken
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
        val valRes = validateEndpointUrl(GatewaySession.gatewayUrl)
        val endpoint = valRes.getOrElse {
            callback(Result.failure(it))
            return
        }

        if (!GatewaySession.isAuthenticated()) {
            callback(Result.failure(IllegalStateException("Gateway is not authenticated. Enroll device with a pairing code.")))
            return
        }

        val token = GatewaySession.apiToken
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
        val valRes = validateEndpointUrl(GatewaySession.gatewayUrl)
        val endpoint = valRes.getOrElse {
            callback(Result.failure(it))
            return
        }

        if (!GatewaySession.isAuthenticated()) {
            callback(Result.failure(IllegalStateException("Gateway is not authenticated. Enroll device with a pairing code.")))
            return
        }

        val token = GatewaySession.apiToken
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
