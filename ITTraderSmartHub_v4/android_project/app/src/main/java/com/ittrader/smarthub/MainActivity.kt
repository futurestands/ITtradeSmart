package com.ittrader.smarthub

import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.activity.OnBackPressedCallback
import kotlin.math.abs

class MainActivity : AppCompatActivity() {

    private lateinit var webSocketManager: MarketWebSocketManager
    private val repository = GatewayRepository()
    private lateinit var dashboardNavigation: DashboardNavigation

    private var liveMarketPrice: Double = 0.0
    private var internalOperationalRisk: Int = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        dashboardNavigation = DashboardNavigation(this)
        dashboardNavigation.initialize(savedInstanceState)
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (dashboardNavigation.currentPage != R.id.nav_home) {
                    dashboardNavigation.navigateTo(R.id.nav_home)
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })

        GatewaySession.init(this)

        val txtLivePrice = findViewById<TextView>(R.id.txtLivePrice)
        val edtLogs = findViewById<EditText>(R.id.edtLogs)
        val btnProcess = findViewById<Button>(R.id.btnProcess)
        val txtAnalysisOutput = findViewById<TextView>(R.id.txtAnalysisOutput)

        // A compact activity strip makes output from hidden screens discoverable
        // without turning the app into one giant chat-style console.
        val txtGlobalFeedback = findViewById<TextView>(R.id.txtGlobalFeedback)
        fun updateCompactStatus(value: CharSequence?) {
            val summary = value?.toString()?.replace(Regex("\\s+"), " ")?.trim().orEmpty()
            txtGlobalFeedback.text = summary.ifBlank { getString(R.string.nav_status_default) }
        }
        txtAnalysisOutput.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) =
                updateCompactStatus(s)
            override fun afterTextChanged(s: Editable?) = Unit
        })
        updateCompactStatus(txtAnalysisOutput.text)
        txtGlobalFeedback.setOnClickListener {
            dashboardNavigation.navigateTo(R.id.nav_home)
            val home = findViewById<ScrollView>(R.id.pageHome)
            home.post { home.fullScroll(View.FOCUS_DOWN) }
        }
        findViewById<Button>(R.id.btnOpenAccounts).setOnClickListener {
            dashboardNavigation.navigateTo(R.id.nav_accounts)
        }
        findViewById<Button>(R.id.btnOpenResearch).setOnClickListener {
            dashboardNavigation.navigateTo(R.id.nav_research)
        }
        findViewById<Button>(R.id.btnOpenRisk).setOnClickListener {
            dashboardNavigation.navigateTo(R.id.nav_risk)
        }

        val edtAccountBalance = findViewById<EditText>(R.id.edtAccountBalance)
        val edtRiskPercentage = findViewById<EditText>(R.id.edtRiskPercentage)
        val edtStopLossPrice = findViewById<EditText>(R.id.edtStopLossPrice)
        val edtStopLossPips = findViewById<EditText>(R.id.edtStopLossPips)
        val edtDailyStartEquity = findViewById<EditText>(R.id.edtDailyStartEquity)

        val edtGatewayIp = findViewById<EditText>(R.id.edtGatewayIp)
        val edtPairingCode = findViewById<EditText>(R.id.edtPairingCode)
        val btnEnrollDevice = findViewById<Button>(R.id.btnEnrollDevice)
        val btnLogout = findViewById<Button>(R.id.btnLogout)
        val cloudMode = findViewById<androidx.appcompat.widget.SwitchCompat>(R.id.switchCloudMode)
        val connectionState = findViewById<TextView>(R.id.txtConnectionState)
        val pairingStatus = findViewById<TextView>(R.id.txtPairingStatus)
        fun showPairingStatus(message: String) {
            pairingStatus.text = message
            connectionState.text = message
            txtAnalysisOutput.text = message
        }
        cloudMode.isChecked = GatewaySession.isCloud
        connectionState.text = if (GatewaySession.isCloud) "Cloud mode. Refresh to authenticate. NO_TRADE." else getString(R.string.cloud_mode_initial)

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
            connectionState.text = if (GatewaySession.isCloud) "Checking authenticated cloud connection..." else "Checking local gateway..."
            btnRefreshAI.isEnabled = false
            repository.queryAIStatus { result ->
                runOnUiThread {
                    btnRefreshAI.isEnabled = true
                    txtAIIntelligence.text = result.fold(
                        onSuccess = {
                            val text = AIIntelligencePresenter.summary(it)
                            val trusted = !text.contains("Response rejected")
                            connectionState.text = if (GatewaySession.isCloud && trusted)
                                "Cloud API: authenticated, fresh response. Model: NOT READY. NO_TRADE."
                                else if (!trusted) "Response rejected. NO_TRADE." else "Local gateway response received."
                            (if (GatewaySession.isCloud) connectionState.text.toString()+"\n" else "") + text
                        },
                        onFailure = {
                            connectionState.text = "Connection unavailable. No fresh result. NO_TRADE."
                            AIIntelligencePresenter.unavailable()+"\n"+(it.message ?: "Unavailable")
                        }
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
            txtNAS100Research.text = "Cached synthetic snapshot — refresh for current status. NO_TRADE.\n" + if (showNAS100Details) {
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
            txtNAS100Research.text = "Checking ${if (GatewaySession.isCloud) "cloud" else "local"} NAS100 research status..."
            repository.queryNAS100ResearchProgress { result ->
                runOnUiThread {
                    btnRefreshNAS100Research.isEnabled = true
                    txtNAS100Research.text = result.fold(
                        onSuccess = { response ->
                            if (NAS100ResearchPresenter.hasVerifiedSyntheticReport(response)) {
                                latestNAS100Response = response
                                btnNAS100ResearchDetails.visibility = View.VISIBLE
                            }
                            (if (GatewaySession.isCloud) "Fresh authenticated cloud response. NO_TRADE.\n" else "") + NAS100ResearchPresenter.overview(response)
                        },
                        onFailure = { NAS100ResearchPresenter.unavailable() }
                    )
                }
            }
        }

        // All broker profile edits occur in the APK and persist only to the
        // Windows Gateway's ignored, credential-free local registry file.
        // Registering a profile never connects MT5 or authorizes trades.
        MT5ProfilesEditor(this, repository) {
            updateGatewayUrlFromInput(edtGatewayIp)
        }

        // Pre-fill stored gateway URL
        edtGatewayIp.setText(GatewaySession.gatewayUrl)
        cloudMode.setOnCheckedChangeListener { _, enabled ->
            if (enabled != GatewaySession.isCloud) {
                updateGatewayUrlFromInput(edtGatewayIp)
                if (!GatewaySession.selectCloud(enabled)) {
                    cloudMode.isChecked = GatewaySession.isCloud
                    connectionState.text = "Secure mode storage failed. Connection unchanged."
                } else {
                    edtGatewayIp.setText(GatewaySession.gatewayUrl)
                    edtPairingCode.setText("")
                    latestNAS100Response = null
                    btnNAS100ResearchDetails.visibility = View.GONE
                    txtNAS100Research.text = NAS100ResearchPresenter.unavailable()+"\nNO_TRADE."
                    txtAIIntelligence.text = AIIntelligencePresenter.unavailable()
                    connectionState.text = if (enabled) "Cloud mode selected. Separate cloud enrollment required. NO_TRADE." else "Local gateway mode restored."
                    for (button in listOf(btnBotOff, btnBotBacktest, btnBotPaper, btnBotEmergencyStop)) button.isEnabled = !enabled
                }
            }
        }
        if (GatewaySession.isCloud) for (button in listOf(btnBotOff, btnBotBacktest, btnBotPaper, btnBotEmergencyStop)) button.isEnabled = false

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
            updateGatewayUrlFromInput(edtGatewayIp)
            val enrollingCloud = GatewaySession.isCloud

            if (code.isBlank()) {
                showPairingStatus("Enter a fresh one-time pairing code, then tap Pair Device.")
                Toast.makeText(this, "Enter one-time pairing code from administrator", Toast.LENGTH_LONG).show()
                return@setOnClickListener
            }

            showPairingStatus("Pairing device with gateway… Please wait up to 30 seconds.")
            btnEnrollDevice.isEnabled = false
            btnEnrollDevice.setText(R.string.pairing_in_progress)
            edtGatewayIp.isEnabled = false
            edtPairingCode.isEnabled = false
            cloudMode.isEnabled = false
            btnLogout.isEnabled = false
            repository.enrollDevice(url, code, "Android " + android.os.Build.MODEL) { result ->
                runOnUiThread {
                    btnEnrollDevice.isEnabled = true
                    btnEnrollDevice.setText(R.string.pair_device)
                    edtGatewayIp.isEnabled = true
                    edtPairingCode.isEnabled = true
                    cloudMode.isEnabled = true
                    btnLogout.isEnabled = true
                    result.fold(
                        onSuccess = { json ->
                            val token = json.optString("device_token")
                            val expiresAt = json.optString("expires_at")
                            if (token.isNotBlank()) {
                                val saved = if (enrollingCloud) GatewaySession.saveCloudSession(json, url)
                                    else if (!GatewaySession.isCloud) GatewaySession.saveSession(this, token, url) else false
                                if (saved) {
                                    showPairingStatus("[Device Pairing Successful]\n" +
                                            "Device ID: ${if (enrollingCloud) json.optString("device_id") else GatewaySession.deviceId}\n" +
                                            "Status: Paired & Token Saved to Android Keystore\n" +
                                            "Token Expiration: $expiresAt")
                                    edtPairingCode.setText("")
                                    Toast.makeText(this, "Device Paired Successfully!", Toast.LENGTH_SHORT).show()
                                } else {
                                    showPairingStatus("⚠️ Keystore Save Failed: Unable to persist token securely.")
                                    Toast.makeText(this, "Keystore Storage Failed!", Toast.LENGTH_LONG).show()
                                }
                            } else {
                                showPairingStatus("Pairing failed: No token issued.")
                            }
                        },
                        onFailure = { err ->
                            showPairingStatus("Pairing Error: ${err.message}")
                            Toast.makeText(this, "Pairing failed. See the status below Pair Device.", Toast.LENGTH_LONG).show()
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

    override fun onSaveInstanceState(outState: Bundle) {
        dashboardNavigation.saveState(outState)
        super.onSaveInstanceState(outState)
    }

    override fun onDestroy() {
        super.onDestroy()
        webSocketManager.disconnect()
    }
}

data class LogReport(val severityIndex: Int)
