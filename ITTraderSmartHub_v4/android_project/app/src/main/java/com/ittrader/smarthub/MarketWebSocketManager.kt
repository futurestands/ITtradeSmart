package com.ittrader.smarthub

import okhttp3.*
import org.json.JSONObject
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit
import kotlin.math.min

/**
 * Live Market WebSocket Manager with exponential backoff and staleness monitoring.
 * Connects to Binance BTC/USDT trade stream.
 */
class MarketWebSocketManager(
    private val onPriceReceived: (Double) -> Unit,
    private val onStatusChanged: (String) -> Unit = {}
) {
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()

    private var webSocket: WebSocket? = null
    private var isClosed = false
    private var reconnectAttempt = 0
    private var lastPriceTimeMs: Long = 0
    private val scheduler: ScheduledExecutorService = Executors.newSingleThreadScheduledExecutor()

    fun connect() {
        isClosed = false
        internalConnect()
        scheduleStalenessCheck()
    }

    private fun internalConnect() {
        if (isClosed) return

        onStatusChanged("Connecting to Binance BTC/USDT...")
        val request = Request.Builder()
            .url("wss://stream.binance.com:9443/ws/btcusdt@trade")
            .build()

        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                reconnectAttempt = 0
                onStatusChanged("Connected")
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                try {
                    val json = JSONObject(text)
                    if (json.has("p")) {
                        val currentPrice = json.getString("p").toDouble()
                        lastPriceTimeMs = System.currentTimeMillis()
                        onPriceReceived(currentPrice)
                    }
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                if (!isClosed) {
                    onStatusChanged("Connection Failed. Retrying...")
                    scheduleReconnect()
                }
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                if (!isClosed) {
                    onStatusChanged("Disconnected: $reason")
                    scheduleReconnect()
                }
            }
        })
    }

    private fun scheduleReconnect() {
        if (isClosed) return
        reconnectAttempt++
        val backoffSeconds = min(30, 1 shl (reconnectAttempt - 1))
        scheduler.schedule({
            internalConnect()
        }, backoffSeconds.toLong(), TimeUnit.SECONDS)
    }

    private fun scheduleStalenessCheck() {
        scheduler.scheduleWithFixedDelay({
            if (!isClosed && lastPriceTimeMs > 0) {
                val ageMs = System.currentTimeMillis() - lastPriceTimeMs
                if (ageMs > 15000) {
                    onStatusChanged("⚠️ Stale Market Data (${ageMs / 1000}s ago)")
                }
            }
        }, 5, 5, TimeUnit.SECONDS)
    }

    fun isDataFresh(): Boolean {
        if (lastPriceTimeMs <= 0) return false
        return (System.currentTimeMillis() - lastPriceTimeMs) <= 15000
    }

    fun disconnect() {
        isClosed = true
        webSocket?.close(1000, "App paused")
        scheduler.shutdownNow()
    }
}
