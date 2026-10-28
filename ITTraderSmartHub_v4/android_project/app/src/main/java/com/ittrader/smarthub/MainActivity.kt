package com.ittrader.smarthub

import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import kotlin.math.abs

class MainActivity : AppCompatActivity() {

    private lateinit var webSocketManager: MarketWebSocketManager
    private val repository = GatewayRepository()

    private var liveMarketPrice: Double = 0.0
    private var internalOperationalRisk: Int = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        GatewaySession.init(this)

        val txtLivePrice = findViewById<TextView>(R.id.txtLivePrice)
        val edtLogs = findViewById<EditText>(R.id.edtLogs)
        val btnProcess = findViewById<Button>(R.id.btnProcess)
        val txtAnalysisOutput = findViewById<TextView>(R.id.txtAnalysisOutput)

        val edtAccountBalance = findViewById<EditText>(R.id.edtAccountBalance)
        val edtRiskPercentage = findViewById<EditText>(R.id.edtRiskPercentage)
        val edtStopLossPrice = findViewById<EditText>(R.id.edtStopLossPrice)

        val edtGatewayIp = findViewById<EditText>(R.id.edtGatewayIp)
        val edtApiToken = findViewById<EditText>(R.id.edtApiToken)
        val btnSaveToken = findViewById<Button>(R.id.btnSaveToken)

        // Pre-fill existing stored token/gateway URL if available
        edtGatewayIp.setText(GatewaySession.gatewayUrl)
        if (GatewaySession.isAuthenticated()) {
            edtApiToken.setText(GatewaySession.apiToken)
        }

        // Legacy credential inputs are disabled. Credentials remain on Windows gateway.
        findViewById<EditText>(R.id.edtMt5Login).apply { isEnabled = false; hint = "Configured on gateway"; setText("") }
        findViewById<EditText>(R.id.edtMt5Password).apply { isEnabled = false; hint = "Never enter MT5 password here"; setText("") }
        findViewById<EditText>(R.id.edtMt5Server).apply { isEnabled = false; hint = "Configured on gateway"; setText("") }

        val btnSyncMt5 = findViewById<Button>(R.id.btnSyncMt5)
        val edtSymbol = findViewById<EditText>(R.id.edtSymbol)
        val btnQueryRiskContext = findViewById<Button>(R.id.btnQueryRiskContext)
        val btnQueryAlerts = findViewById<Button>(R.id.btnQueryAlerts)
        val btnQueryResearch = findViewById<Button>(R.id.btnQueryResearch)

        // Initialize Live Binance Market Stream
        webSocketManager = MarketWebSocketManager(
            onPriceReceived = { price ->
                runOnUiThread {
                    liveMarketPrice = price
                    txtLivePrice.text = String.format("Live BTC/USDT: $%.2f", liveMarketPrice)
                }
            },
            onStatusChanged = { status ->
                runOnUiThread {
                    if (liveMarketPrice <= 0.0) {
                        txtLivePrice.text = "Binance Feed: $status"
                    }
                }
            }
        )
        webSocketManager.connect()

        // 1. Process System Logs & Compute Infrastructure Risk Factor
        btnProcess.setOnClickListener {
            val rawLogs = edtLogs.text.toString()
            val report = analyzeSystemLogs(rawLogs)
            internalOperationalRisk = report.severityIndex

            val balance = edtAccountBalance.text.toString().toDoubleOrNull()
            val baseRiskPct = edtRiskPercentage.text.toString().toDoubleOrNull()
            val stopLoss = edtStopLossPrice.text.toString().toDoubleOrNull()

            if (balance == null || !balance.isFinite() || balance <= 0 ||
                baseRiskPct == null || !baseRiskPct.isFinite() || baseRiskPct <= 0 || baseRiskPct > 100 ||
                stopLoss == null || !stopLoss.isFinite() || stopLoss <= 0 ||
                liveMarketPrice <= 0) {
                txtAnalysisOutput.text = "Enter a positive balance, risk percentage (0–100), valid stop price, and wait for live market quote."
                return@setOnClickListener
            }

            val riskMitigationFactor = 1.0 - 0.5 * internalOperationalRisk / 100.0
            val adjustedRiskPct = (baseRiskPct * riskMitigationFactor) / 100.0

            val totalCashAtRisk = balance * adjustedRiskPct
            val priceDistance = abs(liveMarketPrice - stopLoss)
            val optimizedPositionSize = if (priceDistance > 0) totalCashAtRisk / priceDistance else 0.0

            val systemStatus = if (internalOperationalRisk > 40) "⚠️ SYSTEMS UNDER STRESS" else "✅ SYSTEMS NOMINAL"
            txtAnalysisOutput.text = "[IT Infrastructure Audit]\n" +
                    "Status: $systemStatus\n" +
                    "Stress Index: $internalOperationalRisk%\n\n" +
                    "[Algorithmic Risk Adjustment]\n" +
                    "Active Entry: $$liveMarketPrice\n" +
                    "Risk Ceiling: ${String.format("%.2f", adjustedRiskPct * 100)}% (Base: $baseRiskPct%)\n" +
                    "Max Allocation: $$totalCashAtRisk\n" +
                    "Illustrative Spot Units (NOT MT5 lots): ${String.format("%.4f", optimizedPositionSize)}"
        }

        // Save Token Securely to Keystore
        btnSaveToken.setOnClickListener {
            val token = edtApiToken.text.toString().trim()
            val url = edtGatewayIp.text.toString().trim()
            if (token.length < 32) {
                Toast.makeText(this, "Bearer token must be at least 32 characters long", Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }
            GatewaySession.saveSession(this, token, url)
            Toast.makeText(this, "Credentials saved to Android Keystore!", Toast.LENGTH_SHORT).show()
        }

        // 2. Sync Read-Only MT5 Diagnostics
        btnSyncMt5.setOnClickListener {
            updateGatewaySessionFromInput(edtGatewayIp, edtApiToken)
            txtAnalysisOutput.text = "Requesting MT5 diagnostic analysis from gateway..."

            repository.syncMt5 { result ->
                runOnUiThread {
                    result.fold(
                        onSuccess = { json ->
                            txtAnalysisOutput.text = V4ApiContracts.mt5AnalysisSummary(json)
                        },
                        onFailure = { err ->
                            txtAnalysisOutput.text = "MT5 Sync Error: ${err.message}"
                        }
                    )
                }
            }
        }

        // 3. V4 Risk Fusion Query
        btnQueryRiskContext.setOnClickListener {
            updateGatewaySessionFromInput(edtGatewayIp, edtApiToken)
            val baseRisk = edtRiskPercentage.text.toString().toDoubleOrNull() ?: 1.0
            val symbol = edtSymbol.text.toString().trim().ifBlank { "BTCUSD" }

            txtAnalysisOutput.text = "Querying V4 Risk Fusion Engine for $symbol..."

            repository.queryRiskContext(baseRisk, symbol) { result ->
                runOnUiThread {
                    result.fold(
                        onSuccess = { json ->
                            txtAnalysisOutput.text = V4ApiContracts.riskResultSummary(json)
                        },
                        onFailure = { err ->
                            txtAnalysisOutput.text = "V4 Risk Fusion Error: ${err.message}"
                        }
                    )
                }
            }
        }

        // 4. V4 Exposure-Aware Alerts Query
        btnQueryAlerts.setOnClickListener {
            updateGatewaySessionFromInput(edtGatewayIp, edtApiToken)
            txtAnalysisOutput.text = "Querying V4 Alert Center..."

            repository.queryAlerts { result ->
                runOnUiThread {
                    result.fold(
                        onSuccess = { json ->
                            txtAnalysisOutput.text = V4ApiContracts.alertsSummary(json)
                        },
                        onFailure = { err ->
                            txtAnalysisOutput.text = "Alert Query Error: ${err.message}"
                        }
                    )
                }
            }
        }

        // 5. V4 Incident-to-Trade Research
        btnQueryResearch.setOnClickListener {
            updateGatewaySessionFromInput(edtGatewayIp, edtApiToken)
            txtAnalysisOutput.text = "Querying V4 Incident Research API..."

            val now = System.currentTimeMillis()
            val thirtyDaysAgo = now - (30L * 24 * 3600 * 1000)
            val startUtc = java.time.Instant.ofEpochMilli(thirtyDaysAgo).toString()
            val endUtc = java.time.Instant.ofEpochMilli(now).toString()

            repository.queryResearch(startUtc, endUtc, "rule_violation") { result ->
                runOnUiThread {
                    result.fold(
                        onSuccess = { json ->
                            txtAnalysisOutput.text = V4ApiContracts.researchSummary(json)
                        },
                        onFailure = { err ->
                            txtAnalysisOutput.text = "Research API Error: ${err.message}"
                        }
                    )
                }
            }
        }
    }

    private fun updateGatewaySessionFromInput(edtGatewayIp: EditText, edtApiToken: EditText) {
        val url = edtGatewayIp.text.toString().trim()
        val token = edtApiToken.text.toString().trim()
        if (url.isNotBlank()) GatewaySession.gatewayUrl = url
        if (token.isNotBlank()) GatewaySession.apiToken = token
    }

    private fun analyzeSystemLogs(rawLogs: String): LogReport {
        val lines = rawLogs.lines()
        var criticalCount = 0
        var warningCount = 0
        for (line in lines) {
            val lowerLine = line.lowercase()
            if (lowerLine.contains("fatal") || lowerLine.contains("critical") || lowerLine.contains("out of memory")) criticalCount += 2
            else if (lowerLine.contains("error") || lowerLine.contains("failed")) criticalCount++
            else if (lowerLine.contains("warn")) warningCount++
        }
        val score = (criticalCount * 25) + (warningCount * 10)
        return LogReport(score.coerceAtMost(100))
    }

    override fun onDestroy() {
        super.onDestroy()
        webSocketManager.disconnect()
    }
}

data class LogReport(val severityIndex: Int)
