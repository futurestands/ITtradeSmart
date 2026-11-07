package com.ittrader.smarthub

import okhttp3.*
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

/**
 * Repository layer handling HTTP communications with strict TLS certificate verification, centralized HTTPS validation, V5 Automated Bot Controls, Pipnex calculator, and prop firm drawdown APIs.
 */
class GatewayRepository {

    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .callTimeout(30, TimeUnit.SECONDS)
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .followRedirects(false)
        .followSslRedirects(false)
        .build()

    private val renewalLock = Any()
    private val renewalWaiters = mutableListOf<(Boolean) -> Unit>()
    private var renewing = false

    private fun renewCloud(force: Boolean = false, callback: (Boolean) -> Unit) {
        if (!GatewaySession.isCloud) { callback(false); return }
        if (!force && GatewaySession.isAuthenticated()) { callback(true); return }
        val endpoint = ConnectionPolicy.endpoint(GatewaySession.gatewayUrl, true)
        val refresh = GatewaySession.refreshToken
        if (endpoint == null || refresh.isBlank()) { callback(false); return }
        synchronized(renewalLock) {
            renewalWaiters.add(callback)
            if (renewing) return
            renewing = true
        }
        val body = JSONObject().put("refresh_token", refresh).toString()
            .toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())
        executeRequest(Request.Builder().url("$endpoint/api/v5/device/renew").post(body).build()) { result ->
            val saved = result.getOrNull()?.let { GatewaySession.saveCloudSession(it, endpoint) } == true
            val error = result.exceptionOrNull()
            if (!saved && error is GatewayHttpException && error.status == 401 &&
                GatewaySession.isCloud && GatewaySession.gatewayUrl == endpoint) GatewaySession.logout(null)
            val waiters = synchronized(renewalLock) {
                renewing = false
                renewalWaiters.toList().also { renewalWaiters.clear() }
            }
            waiters.forEach { it(saved) }
        }
    }

    private fun cloudGet(path: String, callback: (Result<JSONObject>) -> Unit) {
        val endpoint = ConnectionPolicy.endpoint(GatewaySession.gatewayUrl, true)
        if (endpoint == null) { callback(Result.failure(IllegalArgumentException("Cloud requires a root HTTPS URL"))); return }
        fun fetch(retried: Boolean) {
            if (!GatewaySession.isCloud || GatewaySession.gatewayUrl != endpoint || !GatewaySession.isAuthenticated()) {
                callback(Result.failure(IllegalStateException("Cloud device enrollment required. NO_TRADE.")))
                return
            }
            val req = CloudRequestFactory.read(endpoint, GatewaySession.apiToken, path)
            executeRequest(req) { result ->
                val err = result.exceptionOrNull()
                if (!retried && err is GatewayHttpException && err.status == 401) {
                    renewCloud(true) { if (it) fetch(true) else callback(Result.failure(IllegalStateException(ConnectionPolicy.failure(401)))) }
                } else callback(result)
            }
        }
        renewCloud { if (it) fetch(false) else callback(Result.failure(IllegalStateException("Cloud enrollment or session renewal required. NO_TRADE."))) }
    }

    fun validateEndpointUrl(urlStr: String): Result<String> {
        val trimmed = urlStr.trim().trimEnd('/')
        val parsed = trimmed.toHttpUrlOrNull()
            ?: return Result.failure(IllegalArgumentException("Invalid gateway URL"))
        if (parsed.username.isNotEmpty() || parsed.password.isNotEmpty() || parsed.query != null || parsed.fragment != null) {
            return Result.failure(IllegalArgumentException("Gateway URL must not contain credentials, query or fragment"))
        }
        if (!parsed.isHttps && parsed.host !in setOf("127.0.0.1", "localhost", "::1")) {
            return Result.failure(IllegalArgumentException("Strict TLS Required: Gateway URL must use an encrypted HTTPS endpoint."))
        }
        return Result.success(trimmed)
    }

    fun queryAIStatus(callback: (Result<JSONObject>) -> Unit) {
        if (GatewaySession.isCloud) { cloudGet("/api/v5/ai/status", callback); return }
        val endpoint = validateEndpointUrl(GatewaySession.gatewayUrl).getOrElse {
            callback(Result.failure(it))
            return
        }
        if (!GatewaySession.isAuthenticated()) {
            callback(Result.failure(IllegalStateException("Enroll device with the gateway first.")))
            return
        }
        // The phone contacts only the authenticated Gateway, never the Lab port/token.
        val request = Request.Builder()
            .url("$endpoint/api/v5/ai/status")
            .header("Authorization", "Bearer ${GatewaySession.apiToken}")
            .get().build()
        executeRequest(request, callback)
    }

    fun queryNAS100ResearchProgress(callback: (Result<JSONObject>) -> Unit) {
        if (GatewaySession.isCloud) { cloudGet("/api/v5/ai/research-progress", callback); return }
        // Read-only synthetic research summary. Never sends a candidate,
        // Lab token, order request, account data, or privileged bot command.
        val endpoint = validateEndpointUrl(GatewaySession.gatewayUrl).getOrElse {
            callback(Result.failure(it))
            return
        }
        if (!GatewaySession.isAuthenticated()) {
            callback(Result.failure(IllegalStateException("Pair this device with the gateway first.")))
            return
        }
        val request = Request.Builder()
            .url("$endpoint/api/v5/ai/research-progress")
            .header("Authorization", "Bearer ${GatewaySession.apiToken}")
            .get()
            .build()
        executeRequest(request, callback)
    }

    fun queryMT5Accounts(callback: (Result<JSONObject>) -> Unit) {
        // Authenticated, read-only aliases. No account credentials or orders.
        val endpoint = validateEndpointUrl(GatewaySession.gatewayUrl).getOrElse {
            callback(Result.failure(it))
            return
        }
        if (!GatewaySession.isAuthenticated()) {
            callback(Result.failure(IllegalStateException("Pair this device with the Gateway first.")))
            return
        }
        val request = Request.Builder()
            .url("$endpoint/api/v5/mt5/accounts")
            .header("Authorization", "Bearer ${GatewaySession.apiToken}")
            .get()
            .build()
        executeRequest(request, callback)
    }

    fun saveMT5Profile(profile: JSONObject, callback: (Result<JSONObject>) -> Unit) {
        // Only five non-sensitive profile fields are allowed; never broker credentials.
        val safeFields = setOf("id", "label", "provider", "account_kind", "symbol")
        if (profile.keys().asSequence().toSet() != safeFields) {
            callback(Result.failure(IllegalArgumentException("Invalid broker profile fields")))
            return
        }
        val endpoint = validateEndpointUrl(GatewaySession.gatewayUrl).getOrElse {
            callback(Result.failure(it))
            return
        }
        if (!GatewaySession.isAuthenticated()) {
            callback(Result.failure(IllegalStateException("Pair device with Gateway first.")))
            return
        }
        val request = Request.Builder()
            .url("$endpoint/api/v5/mt5/accounts")
            .header("Authorization", "Bearer ${GatewaySession.apiToken}")
            .post(profile.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull()))
            .build()
        executeRequest(request, callback)
    }

    fun removeMT5Profile(alias: String, callback: (Result<JSONObject>) -> Unit) {
        if (!Regex("^[a-z][a-z0-9_-]{2,31}$").matches(alias)) {
            callback(Result.failure(IllegalArgumentException("Invalid account profile ID")))
            return
        }
        val endpoint = validateEndpointUrl(GatewaySession.gatewayUrl).getOrElse {
            callback(Result.failure(it))
            return
        }
        if (!GatewaySession.isAuthenticated()) {
            callback(Result.failure(IllegalStateException("Pair device with Gateway first.")))
            return
        }
        val request = Request.Builder()
            .url("$endpoint/api/v5/mt5/accounts/$alias")
            .header("Authorization", "Bearer ${GatewaySession.apiToken}")
            .delete()
            .build()
        executeRequest(request, callback)
    }

    fun queryBotStatus(callback: (Result<JSONObject>) -> Unit) {
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
        val request = Request.Builder()
            .url("$endpoint/api/v5/bot/status")
            .header("Authorization", "Bearer $token")
            .get()
            .build()

        executeRequest(request, callback)
    }

    fun setBotMode(mode: String, adminPasscode: String = "", callback: (Result<JSONObject>) -> Unit) {
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
        val payload = V4ApiContracts.botModeRequest(mode, adminPasscode)
        val body = payload.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

        val request = Request.Builder()
            .url("$endpoint/api/v5/bot/mode")
            .header("Authorization", "Bearer $token")
            .post(body)
            .build()

        executeRequest(request, callback)
    }

    fun triggerBotEmergencyStop(callback: (Result<JSONObject>) -> Unit) {
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
        val body = "{}".toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

        val request = Request.Builder()
            .url("$endpoint/api/v5/bot/emergency-stop")
            .header("Authorization", "Bearer $token")
            .post(body)
            .build()

        executeRequest(request, callback)
    }

    fun runBotBacktest(symbol: String, numBars: Int = 200, callback: (Result<JSONObject>) -> Unit) {
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
        val payload = JSONObject().apply {
            put("symbol", symbol)
            put("num_bars", numBars)
        }
        val body = payload.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

        val request = Request.Builder()
            .url("$endpoint/api/v5/bot/backtest")
            .header("Authorization", "Bearer $token")
            .post(body)
            .build()

        executeRequest(request, callback)
    }

    fun queryPipnexCalculator(balance: Double, riskPct: Double, stopLossPips: Double, symbol: String, callback: (Result<JSONObject>) -> Unit) {
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
        val payload = V4ApiContracts.pipnexCalculator(balance, riskPct, stopLossPips, symbol)
        val body = payload.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

        val request = Request.Builder()
            .url("$endpoint/api/v4/pipnex/calculator")
            .header("Authorization", "Bearer $token")
            .post(body)
            .build()

        executeRequest(request, callback)
    }

    fun queryPipnexPropFirm(currentEquity: Double, initialBalance: Double, dailyStartEquity: Double, callback: (Result<JSONObject>) -> Unit) {
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
        val payload = V4ApiContracts.pipnexPropFirm(currentEquity, initialBalance, dailyStartEquity)
        val body = payload.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

        val request = Request.Builder()
            .url("$endpoint/api/v4/pipnex/prop-firm")
            .header("Authorization", "Bearer $token")
            .post(body)
            .build()

        executeRequest(request, callback)
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

        val route = try {
            EnrollmentPolicy.route(GatewaySession.isCloud, pairingCode)
        } catch (error: IllegalArgumentException) {
            callback(Result.failure(error))
            return
        }

        val deviceId = GatewaySession.deviceId
        val payload = V4ApiContracts.deviceEnroll(deviceId, deviceName, pairingCode)
        val body = payload.toString().toRequestBody("application/json; charset=utf-8".toMediaTypeOrNull())

        if (GatewaySession.isCloud && (ConnectionPolicy.endpoint(endpoint, true) == null ||
            !pairingCode.startsWith("shc_enroll_"))) {
            callback(Result.failure(IllegalArgumentException("Use a separate one-time cloud enrollment code.")))
            return
        }
        val request = Request.Builder()
            .url(endpoint+route)
            .post(body)
            .build()

        executeRequest(request, callback)
    }

    fun revokeSession(deviceId: String, callback: (Result<JSONObject>) -> Unit) {
        if (GatewaySession.isCloud) {
            val endpoint = ConnectionPolicy.endpoint(GatewaySession.gatewayUrl, true)
            if (endpoint == null || GatewaySession.apiToken.isBlank()) {
                callback(Result.failure(IllegalStateException("Cloud device session unavailable"))); return
            }
            executeRequest(Request.Builder().url("$endpoint/api/v5/device/revoke")
                .header("Authorization", "Bearer ${GatewaySession.apiToken}")
                .post("".toRequestBody(null)).build(), callback)
            return
        }
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
        val cloudRequest = GatewaySession.isCloud
        val issuedEndpoint = GatewaySession.gatewayUrl
        httpClient.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                callback(Result.failure(if (cloudRequest) IOException("Cloud connection lost. NO_TRADE.") else e))
            }

            override fun onResponse(call: Call, response: Response) {
                response.use {
                    if (cloudRequest != GatewaySession.isCloud || issuedEndpoint != GatewaySession.gatewayUrl) {
                        callback(Result.failure(IllegalStateException("Connection mode changed; refresh again.")))
                    } else if (!it.isSuccessful) {
                        callback(Result.failure(GatewayHttpException(it.code, cloudRequest)))
                    } else {
                        try {
                            val bytes = it.peekBody(16385).bytes()
                            require(bytes.size <= 16384)
                            callback(Result.success(JSONObject(String(bytes, Charsets.UTF_8))))
                        } catch (_: Exception) {
                            callback(Result.failure(IOException("Malformed or oversized gateway response. NO_TRADE.")))
                        }
                    }
                }
            }
        })
    }
}

class GatewayHttpException(val status: Int, cloud: Boolean) : IOException(
    if (cloud) ConnectionPolicy.failure(status) else "Gateway HTTP $status")
