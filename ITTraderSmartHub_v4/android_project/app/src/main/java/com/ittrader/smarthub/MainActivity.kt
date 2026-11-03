package com.ittrader.smarthub

import android.os.Bundle
import android.view.View
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
        val edtStopLossPips = findViewById<EditText>(R.id.edtStopLossPips)
        val edtDailyStartEquity = findViewById<EditText>(R.id.edtDailyStartEquity)

        val edtGatewayIp = findViewById<EditText>(R.id.edtGatewayIp)
        val edtPairingCode = findViewById<EditText>(R.id.edtPairingCode)
        val btnEnrollDevice = findViewById<Button>(R.id.btnEnrollDevice)
        val btnLogout = findViewById<Button>(R.id.btnLogout)

        // V5 Bot Control Buttons
        val btnBotOff = findViewById<Button>(R.id.btnBotOff)
        val btnBotBacktest = findViewById<Button>(R.id.btnBotBacktest)
        val btnBotPaper = findViewById<Button>(R.id.btnBotPaper)
        val btnBotEmergencyStop = findViewById<Button>(R.id.btnBotEmergencyStop)

        // Advisory-only AI status; no candidate, order, size or bot mode is sent.
        val txtAIIntelligence = findViewById<TextView>(R.id.txtAIIntelligence)
        val btnRefreshAI = findViewById<Button>(R.id.btnRefreshAI)
        btnRefreshAI.setOnClickListener {
            updateGatewayUrlFromInput(edtGatewayIp)
            btnRefreshAI.isEnabled = false
            repository.queryAIStatus { result ->
                runOnUiThread {
                    btnRefreshAI.isEnabled = true
                    txtAIIntelligence.text = result.fold(
                        onSuccess = { AIIntelligencePresenter.summary(it) },
                        onFailure = { AIIntelligencePresenter.unavailable() }
                    )
                }
            }
        }

        // NAS100 research: read-only status from the authenticated Gateway.
        // No model inference, trade candidate submission, or bot controls.
        val txtNAS100Research = findViewById<TextView>(R.id.txtNAS100Research)
        val btnRefreshNAS100Research = findViewById<Button>(R.id.btnRefreshNAS100Research)
        val btnNAS100ResearchDetails = findViewById<Button>(R.id.btnNAS100ResearchDetails)
        var latestNAS100Response: org.json.JSONObject? = null
        var showNAS100Details = false
        btnNAS100ResearchDetails.visibility = View.GONE

        btnNAS100ResearchDetails.setOnClickListener {
            val snapshot = latestNAS100Response ?: return@setOnClickListener
            showNAS100Details = !showNAS100Details
            txtNAS100Research.text = if (showNAS100Details) {
                NAS100ResearchPresenter.summary(snapshot)
            } else {
                NAS100ResearchPresenter.overview(snapshot)
            }
            btnNAS100ResearchDetails.setText(
                if (showNAS100Details) R.string.nas100_research_details_hide
                else R.string.nas100_research_details_show
            )
        }
        btnRefreshNAS100Research.setOnClickListener {
            updateGatewayUrlFromInput(edtGatewayIp)
            btnRefreshNAS100Research.isEnabled = false
            btnNAS100ResearchDetails.visibility = View.GONE
            latestNAS100Response = null
            showNAS100Details = false
            btnNAS100ResearchDetails.setText(R.string.nas100_research_details_show)
            txtNAS100Research.text = "Checking local NAS100 research report..."
            repository.queryNAS100ResearchProgress { result ->
                runOnUiThread {
                    btnRefreshNAS100Research.isEnabled = true
                    txtNAS100Research.text = result.fold(
                        onSuccess = { response ->
                            if (NAS100ResearchPresenter.hasVerifiedSyntheticReport(response)) {
                                latestNAS100Response = response
                                btnNAS100ResearchDetails.visibility = View.VISIBLE
                            }
                            NAS100ResearchPresenter.overview(response)
                        },
                        onFailure = { NAS100ResearchPresenter.unavailable() }
                    )
                }
            }
        }

        // Multiple accounts are *registered aliases* until separate MT5
        // terminal sessions are independently verified on Windows.
        val txtMT5Accounts = findViewById<TextView>(R.id.txtMT5Accounts)
        val btnRefreshMT5Accounts = findViewById<Button>(R.id.btnRefreshMT5Accounts)
        btnRefreshMT5Accounts.setOnClickListener {
            updateGatewayUrlFromInput(edtGatewayIp)
            btnRefreshMT5Accounts.isEnabled = false
            txtMT5Accounts.text = "Reading Windows broker account registry..."
            repository.queryMT5Accounts { result ->
                runOnUiThread {
                    btnRefreshMT5Accounts.isEnabled = true
                    txtMT5Accounts.text = result.fold(
                        onSuccess = { MT5AccountsPresenter.summary(it) },
                        onFailure = { MT5AccountsPresenter.unavailable() }
                    )
                }
            }
        }

        // Pre-fill stored gateway URL
        edtGatewayIp.setText(GatewaySession.gatewayUrl)

        // Legacy credential inputs remain disabled. Credentials stay on Windows gateway.
        findViewById<EditText>(R.id.edtMt5Login).apply { isEnabled = false; hint = "Configured on gateway"; setText("") }
        findViewById<EditText>(R.id.edtMt5Password).apply { isEnabled = false; hint = "Never enter MT5 password here"; setText("") }
        findViewById<EditText>(R.id.edtMt5Server).apply { isEnabled = false; hint = "Configured on gateway"; setText("") }

        val btnPipnexCalc = findViewById<Button>(R.id.btnPipnexCalc)
        val btnPipnexPropFirm = findViewById<Button>(R.id.btnPipnexPropFirm)
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
                            GatewaySession.logout(this)
                            txtAnalysisOutput.text = "⚠️ Remote Revocation Failed: ${err.message}\nLocal Keystore Session Wiped."
                            Toast.makeText(this, "Remote Revocation Failed. Local Session Cleared.", Toast.LENGTH_LONG).show()
                        }
                    )
                }
            }
        }

        // 2. V5 AUTOMATED TRADING BOT CONTROLS
        btnBotOff.setOnClickListener {
            updateGatewayUrlFromInput(edtGatewayIp)
            txtAnalysisOutput.text = "Setting bot mode to OFF..."
            repository.setBotMode("OFF") { result ->
                runOnUiThread {
                    result.fold(
                        onSuccess = { json ->
                            txtAnalysisOutput.text = V4ApiContracts.botStatusSummary(json)
                        },
                        onFailure = { err ->
                            txtAnalysisOutput.text = "Bot Mode Error: ${err.message}"
                        }
                    )
                }
            }
        }

        btnBotBacktest.setOnClickListener {
            updateGatewayUrlFromInput(edtGatewayIp)
            val symbol = edtSymbol.text.toString().trim().ifBlank { "BTCUSD" }
            txtAnalysisOutput.text = "Running V5 Strategy Backtest Lab for $symbol..."
            repository.runBotBacktest(symbol, 200) { result ->
                runOnUiThread {
                    result.fold(
                        onSuccess = { json ->
                            txtAnalysisOutput.text = V4ApiContracts.botBacktestSummary(json)
                        },
                        onFailure = { err ->
                            txtAnalysisOutput.text = "Backtest Error: ${err.message}"
                        }
                    )
                }
            }
        }

        btnBotPaper.setOnClickListener {
            updateGatewayUrlFromInput(edtGatewayIp)
            txtAnalysisOutput.text = "Switching bot mode to PAPER TRADING..."
            repository.setBotMode("PAPER") { result ->
                runOnUiThread {
                    result.fold(
                        onSuccess = { json ->
                            txtAnalysisOutput.text = V4ApiContracts.botStatusSummary(json)
                        },
                        onFailure = { err ->
                            txtAnalysisOutput.text = "Bot Paper Mode Error: ${err.message}"
                        }
                    )
                }
            }
        }

        btnBotEmergencyStop.setOnClickListener {
            updateGatewayUrlFromInput(edtGatewayIp)
            txtAnalysisOutput.text = "🛑 TRIGGERING EMERGENCY BOT STOP..."
            repository.triggerBotEmergencyStop { result ->
                runOnUiThread {
                    result.fold(
                        onSuccess = { json ->
                            txtAnalysisOutput.text = "🛑 EMERGENCY STOP ENGAGED!\n\n" + V4ApiContracts.botStatusSummary(json)
                            Toast.makeText(this, "EMERGENCY STOP ENGAGED!", Toast.LENGTH_LONG).show()
                        },
                        onFailure = { err ->
                            txtAnalysisOutput.text = "Emergency Stop Error: ${err.message}"
                        }
                    )
                }
            }
        }

        // 3. PIPNEX Smart Lot Size & Pip Value Calculator
        btnPipnexCalc.setOnClickListener {
            updateGatewayUrlFromInput(edtGatewayIp)
            val balance = edtAccountBalance.text.toString().toDoubleOrNull() ?: 10000.0
            val riskPct = edtRiskPercentage.text.toString().toDoubleOrNull() ?: 1.0
            val slPips = edtStopLossPips.text.toString().toDoubleOrNull() ?: 20.0
            val symbol = edtSymbol.text.toString().trim().ifBlank { "BTCUSD" }

            txtAnalysisOutput.text = "Calculating Pipnex Smart Lot Size for $symbol..."
            repository.queryPipnexCalculator(balance, riskPct, slPips, symbol) { result ->
                runOnUiThread {
                    result.fold(
                        onSuccess = { json ->
                            txtAnalysisOutput.text = V4ApiContracts.pipnexCalculatorSummary(json)
                        },
                        onFailure = { err ->
                            txtAnalysisOutput.text = "Pipnex Calculator Error: ${err.message}"
                        }
                    )
                }
            }
        }

        // 4. PIPNEX Prop Firm Drawdown Shield
        btnPipnexPropFirm.setOnClickListener {
            updateGatewayUrlFromInput(edtGatewayIp)
            val equity = edtAccountBalance.text.toString().toDoubleOrNull() ?: 10000.0
            val initialBalance = 10000.0
            val dailyStart = edtDailyStartEquity.text.toString().toDoubleOrNull() ?: 10000.0

            txtAnalysisOutput.text = "Checking Pipnex Prop Firm Drawdown Shield..."
            repository.queryPipnexPropFirm(equity, initialBalance, dailyStart) { result ->
                runOnUiThread {
                    result.fold(
                        onSuccess = { json ->
                            txtAnalysisOutput.text = V4ApiContracts.pipnexPropFirmSummary(json)
                        },
                        onFailure = { err ->
                            txtAnalysisOutput.text = "Pipnex Prop Firm Shield Error: ${err.message}"
                        }
                    )
                }
            }
        }

        // 5. Process System Logs & Compute Infrastructure Risk Factor
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

        // 6. Sync Read-Only MT5 Diagnostics
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

        // 7. V4 Risk Fusion Query
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

        // 8. V4 Exposure-Aware Alerts Query
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

        // 9. V4 Incident-to-Trade Research
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
