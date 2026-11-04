package com.ittrader.smarthub

import android.os.Bundle
import android.view.View
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.bottomnavigation.BottomNavigationView

/**
 * Five real screens. All original controls remain in one activity, but only
 * one independent scrollable page is visible at a time.
 * Page switches never call broker endpoints or alter bot modes.
 */
object DashboardTabSpec {
    data class Tab(val menuId: Int, val pageId: Int, val titleId: Int, val subtitleId: Int)

    val tabs: List<Tab> = listOf(
        Tab(R.id.nav_home, R.id.pageHome, R.string.nav_home_title, R.string.nav_home_subtitle),
        Tab(R.id.nav_accounts, R.id.pageAccounts, R.string.nav_accounts_title, R.string.nav_accounts_subtitle),
        Tab(R.id.nav_research, R.id.pageResearch, R.string.nav_research_title, R.string.nav_research_subtitle),
        Tab(R.id.nav_risk, R.id.pageRisk, R.string.nav_risk_title, R.string.nav_risk_subtitle),
        Tab(R.id.nav_settings, R.id.pageSettings, R.string.nav_settings_title, R.string.nav_settings_subtitle),
    )
}

class DashboardNavigation(private val activity: AppCompatActivity) {
    private val bar = activity.findViewById<BottomNavigationView>(R.id.bottomNavigation)
    private val heading = activity.findViewById<TextView>(R.id.txtPageHeading)
    private val subtitle = activity.findViewById<TextView>(R.id.txtPageSubtitle)

    companion object {
        private const val KEY = "smarthub.navigation.selected_page"
    }

    val currentPage: Int get() = bar.selectedItemId

    fun initialize(savedState: Bundle?) {
        val requested = savedState?.getInt(KEY) ?: R.id.nav_home
        val initial = if (DashboardTabSpec.tabs.any { it.menuId == requested }) requested else R.id.nav_home
        bar.setOnItemSelectedListener { item -> show(item.itemId) }
        bar.selectedItemId = initial
        show(initial)
    }

    fun navigateTo(menuId: Int) {
        if (DashboardTabSpec.tabs.none { it.menuId == menuId }) return
        bar.selectedItemId = menuId
        show(menuId)
    }

    private fun show(menuId: Int): Boolean {
        val selected = DashboardTabSpec.tabs.firstOrNull { it.menuId == menuId } ?: return false
        DashboardTabSpec.tabs.forEach { tab ->
            activity.findViewById<View>(tab.pageId).visibility =
                if (tab.menuId == menuId) View.VISIBLE else View.GONE
        }
        heading.setText(selected.titleId)
        subtitle.setText(selected.subtitleId)
        return true
    }

    fun saveState(out: Bundle) {
        out.putInt(KEY, bar.selectedItemId)
    }
}
