package com.ittrader.smarthub

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Fast structural checks without starting Android or touching the Gateway. */
class DashboardTabSpecTest {
    @Test fun fiveDestinationsAreOneToOne() {
        val tabs = DashboardTabSpec.tabs
        assertEquals(5, tabs.size)
        assertEquals(5, tabs.map { it.menuId }.toSet().size)
        assertEquals(5, tabs.map { it.pageId }.toSet().size)
        assertEquals(R.id.nav_home, tabs.first().menuId)
        assertEquals(R.id.pageHome, tabs.first().pageId)
    }

    @Test fun accountsAndResearchHaveDedicatedScreens() {
        val tabs = DashboardTabSpec.tabs.associateBy { it.menuId }
        assertEquals(R.id.pageAccounts, tabs[R.id.nav_accounts]?.pageId)
        assertEquals(R.id.pageResearch, tabs[R.id.nav_research]?.pageId)
        assertEquals(R.id.pageRisk, tabs[R.id.nav_risk]?.pageId)
        assertEquals(R.id.pageSettings, tabs[R.id.nav_settings]?.pageId)
        assertTrue(tabs.values.all { it.titleId != 0 && it.subtitleId != 0 })
    }
}
