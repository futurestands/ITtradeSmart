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
        val edtPairingCode = findViewById<EditText>(R.id.edtPairingCode)
        val btnEnrollDevice = findViewById<Button>(R.id.btnEnrollDevice)
        val btnLogout = findViewById<Button>(R.id.btnLogout)

        // Pre-fill stored gateway URL
        edtGatewayIp.setText(GatewaySession.gatewayUrl)

        // Legacy credential inputs remain disabled. Credentials stay on Windows gateway.
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

        // 1. One-Time Pairing Code Device Enrollment
        btnEnrollDevice.setOnClickListener {
            val code = edtPairingCode.text.toString().trim()
            val url = edtGatewayIp.text.toString().trim()

            if (code.isBlank()) {
                Toast.makeText(this, "Enter one-time pairing code from administrator", Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }

            txtAnalysisOutput.text = "Pairing device with gateway..."
            repository.enrollDevice(url, code, "Android " + android.os.Build.MODEL) { result ->
                runOnUiThread {
                    result.fold(
                        onSuccess = { json ->
                            val token = json.optString("device_token")
                            val expiresAt = json.optString("expires_at")
                            if (token.isNotBlank()) {
                                val saved = GatewaySession.saveSession(this, token, url)
                                if (saved) {
                                    txtAnalysisOutput.text = "[Device Pairing Successful]\n" +
                                            "Device ID: ${GatewaySession.deviceId}\n" +
                                            "Status: Paired & Token Saved to Android Keystore\n" +
                                            "Token Expiration: $expiresAt"
                                    Toast.makeText(this, "Device Paired Successfully!", Toast.LENGTH_SHORT).show()
                                } else {
                                    txtAnalysisOutput.text = "⚠️ Keystore Save Failed: Unable to persist token securely."
                                    Toast.makeText(this, "Keystore Storage Failed!", Toast.LENGTH_LONG).show()
                                }
                            } else {
                                txtAnalysisOutput.text = "Pairing failed: No token issued."
                            }
                        },
                        onFailure = { err ->
                            txtAnalysisOutput.text = "Pairing Error: ${err.message}"
                        }
                    )
                }
            }
        }

        // Safe Logout with Server-Side Revocation & Clear Local Keystore Credentials
        btnLogout.setOnClickListener {
            val currentDeviceId = GatewaySession.deviceId
            txtAnalysisOutput.text = "Revoking session with gateway server..."

            repository.revokeSession(currentDeviceId) { result ->
                runOnUiThread {
                    result.fold(
                        onSuccess = {
                            GatewaySession.logout(this)
                            txtAnalysisOutput.text = "✅ Session Revoked Server-Side & Local Credentials Wiped from Keystore."
                            Toast.makeText(this, "Logged out & Server Session Revoked", Toast.LENGTH_SHORT).show()
                        },
                        onFailure = { err ->
                            // Distinguish remote revocation failure while clearing local credentials
                            GatewaySession.logout(this)
                            txtAnalysisOutput.text = "⚠️ Remote Revocation Failed: ${err.message}\nLocal Keystore Session Wiped."
                            Toast.makeText(this, "Remote Revocation Failed. Local Session Cleared.", Toast.LENGTH_LONG).show()
                        }
                    )
                }
            }
        }

        // 2. Process System Logs & Compute Infrastructure Risk Factor
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

        // 3. Sync Read-Only MT5 Diagnostics
        btnSyncMt5.setOnClickListener {
            updateGatewayUrlFromInput(edtGatewayIp)
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

        // 4. V4 Risk Fusion Query
        btnQueryRiskContext.setOnClickListener {
            updateGatewayUrlFromInput(edtGatewayIp)
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

        // 5. V4 Exposure-Aware Alerts Query
        btnQueryAlerts.setOnClickListener {
            updateGatewayUrlFromInput(edtGatewayIp)
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

        // 6. V4 Incident-to-Trade Research
        btnQueryResearch.setOnClickListener {
            updateGatewayUrlFromInput(edtGatewayIp)
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

    private fun updateGatewayUrlFromInput(edtGatewayIp: EditText) {
        val url = edtGatewayIp.text.toString().trim()
        if (url.isNotBlank()) GatewaySession.gatewayUrl = url
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
