package com.ittrader.smarthub

import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.Spinner
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

/**
 * Edits broker DISPLAY PROFILES only on the enrolled phone.
 * Never collects or sends MT5 account numbers, passwords or terminal paths.
 * A saved profile is always unconnected, never approved for trading.
 */
class MT5ProfilesEditor(
    private val activity: AppCompatActivity,
    private val repository: GatewayRepository,
    private val beforeRequest: () -> Unit,
) {
    private val text = activity.findViewById<TextView>(R.id.txtMT5Accounts)
    private val feedback = activity.findViewById<TextView>(R.id.txtMT5ProfileFeedback)
    private val refreshButton = activity.findViewById<Button>(R.id.btnRefreshMT5Accounts)
    private val saveButton = activity.findViewById<Button>(R.id.btnSaveMT5Account)
    private val removeButton = activity.findViewById<Button>(R.id.btnRemoveMT5Account)
    private val selector = activity.findViewById<Spinner>(R.id.spnMT5SelectAccount)
    private val alias = activity.findViewById<EditText>(R.id.edtMT5AccountAlias)
    private val label = activity.findViewById<EditText>(R.id.edtMT5AccountLabel)
    private val symbol = activity.findViewById<EditText>(R.id.edtMT5AccountSymbol)
    private val broker = activity.findViewById<EditText>(R.id.edtMT5BrokerName)
    private val kind = activity.findViewById<Spinner>(R.id.spnMT5AccountKind)

    private val kinds = listOf("FREE_TRIAL", "DEMO", "EVALUATION", "FUNDED", "LIVE")
    private var known = listOf<JSONObject>()

    init {
        prepareSelector(kind, kinds)
        selector.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onNothingSelected(parent: AdapterView<*>?) {}
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                if (position == 0 || position > known.size) {
                    setNewProfile()
                } else {
                    val item = known[position - 1]
                    alias.setText(item.optString("id"))
                    alias.isEnabled = false // immutable stable profile ID
                    label.setText(item.optString("label"))
                    symbol.setText(item.optString("symbol"))
                    broker.setText(item.optString("provider"))
                    kind.setSelection(kinds.indexOf(item.optString("account_kind")).coerceAtLeast(0))
                    removeButton.isEnabled = true
                }
            }
        }
        resetSelector()
        refreshButton.setOnClickListener { refresh() }
        saveButton.setOnClickListener { save() }
        removeButton.setOnClickListener {
            val id = alias.text.toString().trim()
            if (id.isEmpty() || !known.any { it.optString("id") == id }) return@setOnClickListener
            AlertDialog.Builder(activity)
                .setTitle("Remove broker profile?")
                .setMessage("Remove the saved label '$id' from the monitor? This cannot close broker trades or terminals.")
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Remove") { _, _ -> delete(id) }
                .show()
        }
    }

    private fun prepareSelector(spinner: Spinner, items: List<String>) {
        val adapter = ArrayAdapter(activity, android.R.layout.simple_spinner_item, items)
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item)
        spinner.adapter = adapter
    }

    private fun resetSelector(selected: String? = null) {
        val names = mutableListOf("＋ Add new broker profile")
        names.addAll(known.map { "${it.optString("label")} (${it.optString("id")})" })
        prepareSelector(selector, names)
        val index = if (selected == null) 0
            else known.indexOfFirst { it.optString("id") == selected }.let { if (it < 0) 0 else it + 1 }
        selector.setSelection(index)
        if (index == 0) setNewProfile()
    }

    private fun setNewProfile() {
        alias.isEnabled = true
        alias.setText("")
        label.setText("")
        symbol.setText("")
        broker.setText("")
        kind.setSelection(0)
        removeButton.isEnabled = false
    }

    private fun applyRegistry(result: JSONObject, select: String?) {
        val overview = MT5AccountsPresenter.summary(result)
        text.text = overview
        if (!overview.startsWith("MULTI-ACCOUNT MONITOR")) {
            feedback.text = "Registry response rejected. No changes assumed."
            return
        }
        val array = result.optJSONArray("accounts") ?: JSONArray()
        val next = mutableListOf<JSONObject>()
        for (i in 0 until array.length()) {
            val item = array.optJSONObject(i) ?: return
            next.add(item)
        }
        known = next
        resetSelector(select)
    }

    fun refresh() {
        beforeRequest()
        refreshButton.isEnabled = false
        feedback.text = "Loading account profiles from Windows Gateway..."
        repository.queryMT5Accounts { result ->
            activity.runOnUiThread {
                refreshButton.isEnabled = true
                result.fold(
                    onSuccess = {
                        applyRegistry(it, null)
                        feedback.text = "Choose an account to edit, or Add new broker profile."
                    },
                    onFailure = {
                        text.text = MT5AccountsPresenter.unavailable()
                        feedback.text = "Could not load profiles: ${it.message ?: "Gateway unavailable"}"
                    }
                )
            }
        }
    }

    private fun save() {
        val id = alias.text.toString().trim().lowercase(Locale.ROOT)
        val name = label.text.toString().trim()
        val ticker = symbol.text.toString().trim()
        val brokerName = broker.text.toString().trim().uppercase(Locale.ROOT)
        if (!Regex("^[a-z][a-z0-9_-]{2,31}$").matches(id) ||
            name.isEmpty() || name.length > 40 ||
            name.any { it.code < 32 || it.code > 126 } ||
            !Regex("^[A-Z][A-Z0-9 ._-]{1,39}$").matches(brokerName) ||
            !Regex("^[A-Za-z0-9._-]{2,32}$").matches(ticker) ||
            ticker == "VERIFY_IN_MT5"
        ) {
            feedback.text = "Enter a unique lowercase alias, broker name, display name and confirmed MT5 symbol (such as US100)."
            return
        }
        beforeRequest()
        val payload = JSONObject().apply {
            put("id", id)
            put("label", name)
            put("provider", brokerName)
            put("account_kind", kinds[kind.selectedItemPosition])
            put("symbol", ticker)
        }
        saveButton.isEnabled = false
        feedback.text = "Saving broker profile to Windows Gateway..."
        repository.saveMT5Profile(payload) { result ->
            activity.runOnUiThread {
                saveButton.isEnabled = true
                result.fold(
                    onSuccess = {
                        applyRegistry(it, id)
                        feedback.text = "Profile saved on Windows. MT5: NOT CONNECTED. Trading: DISABLED."
                    },
                    onFailure = {
                        feedback.text = "Profile not saved: ${it.message ?: "Gateway unavailable"}"
                    }
                )
            }
        }
    }

    private fun delete(id: String) {
        beforeRequest()
        removeButton.isEnabled = false
        feedback.text = "Removing broker profile label..."
        repository.removeMT5Profile(id) { result ->
            activity.runOnUiThread {
                result.fold(
                    onSuccess = {
                        applyRegistry(it, null)
                        feedback.text = "Profile removed from monitor. No MT5 orders or accounts were touched."
                    },
                    onFailure = {
                        removeButton.isEnabled = true
                        feedback.text = "Profile not removed: ${it.message ?: "Gateway unavailable"}"
                    }
                )
            }
        }
    }
}
