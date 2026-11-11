package com.ittrader.smarthub

import android.content.Intent
import android.net.Uri
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.Spinner
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import java.util.Locale
import java.util.UUID
import org.json.JSONArray

class ResearchProfilesController(private val activity: AppCompatActivity) {
    fun bind() {
        val prefs = activity.getSharedPreferences("smarthub_research_profiles_v1", 0)
        val selection = activity.findViewById<Spinner>(R.id.spnResearchProfile)
        val firm = activity.findViewById<Spinner>(R.id.spnResearchFirm)
        val feedback = activity.findViewById<TextView>(R.id.txtResearchProfileStatus)
        val save = activity.findViewById<Button>(R.id.btnSaveResearchProfile)
        val fields = listOf(R.id.edtResearchLabel, R.id.edtResearchProgramme, R.id.edtResearchStage,
            R.id.edtResearchCurrency, R.id.edtResearchSize, R.id.edtResearchTerms)
            .map { activity.findViewById<EditText>(it) }
        val firms = ResearchAccountProfile.officialSources.keys.toList()
        firm.adapter = ArrayAdapter(activity, android.R.layout.simple_spinner_dropdown_item, firms)
        val profiles = try {
            ResearchAccountProfile.decode(prefs.getString("profiles", "[]") ?: "[]").toMutableList()
        } catch (_: Exception) {
            save.isEnabled = false
            feedback.setText(R.string.research_profile_storage_error)
            return // Preserve unreadable data; never silently replace it.
        }
        var editingId: String? = null
        fun refresh(active: String?) {
            selection.adapter = ArrayAdapter(activity, android.R.layout.simple_spinner_dropdown_item,
                listOf(activity.getString(R.string.research_profile_new)) + profiles.map { it.label })
            selection.setSelection(profiles.indexOfFirst { it.id == active }.let { if (it < 0) 0 else it + 1 })
        }
        selection.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                val profile = profiles.getOrNull(position - 1)
                editingId = profile?.id
                val values = profile?.let { listOf(it.label, it.programme, it.stage, it.currency, it.originalSize, it.terms) }
                    ?: List(6) { "" }
                fields.zip(values).forEach { (field, value) -> field.setText(value) }
                firm.setSelection(firms.indexOf(profile?.firm).coerceAtLeast(0))
                feedback.setText(R.string.research_profile_unverified)
            }
        }
        refresh(prefs.getString("selected", null))
        save.setOnClickListener {
            try {
                val values = fields.map { it.text.toString().trim() }
                val profile = ResearchAccountProfile(editingId ?: UUID.randomUUID().toString(), values[0],
                    firms[firm.selectedItemPosition], values[1], values[2], values[3].uppercase(Locale.ROOT), values[4], values[5])
                val next = profiles.filter { it.id != profile.id } + profile
                require(next.size <= 20)
                val encoded = JSONArray().also { array -> next.forEach { array.put(it.toJson()) } }.toString()
                if (!prefs.edit().putString("profiles", encoded).putString("selected", profile.id).commit()) {
                    feedback.setText(R.string.research_profile_storage_error)
                } else {
                    profiles.clear(); profiles.addAll(next); editingId = profile.id
                    refresh(profile.id)
                    feedback.setText(R.string.research_profile_saved)
                }
            } catch (_: Exception) { feedback.setText(R.string.research_profile_invalid) }
        }
        activity.findViewById<Button>(R.id.btnOpenResearchRules).setOnClickListener {
            val url = ResearchAccountProfile.officialSources.getValue(firms[firm.selectedItemPosition])
            try {
                activity.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                feedback.setText(R.string.research_profile_browser_note)
            } catch (_: Exception) { feedback.setText(R.string.research_profile_browser_error) }
        }
    }
}
