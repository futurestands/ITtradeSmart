package com.ittrader.smarthub

import android.content.SharedPreferences
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.After
import java.security.MessageDigest

/** Preference failure tests only: no real Android keys, files or phone data. */
class GatewayStorageTest {
    @After fun resetSessionFixture() {
        GatewaySession.initStores({ MemoryPrefs() }, { MemoryPrefs() })
    }
    private val origin = "https://ittrader-smarthub-phase3-phone-preview-futurestands.vercel.app"
    private fun session() = JSONObject().put("device_token", "shc_access_" + "a".repeat(43))
        .put("refresh_token", "shc_refresh_" + "r".repeat(43))
        .put("expires_at", System.currentTimeMillis()/1000 + 3600)

    @Test fun brokenLegacyDoesNotBlockCloudAndPairingSurvivesRestart() {
        val cloud = MemoryPrefs()
        val broken = { throw SecurityException("PRIVATE_DIAGNOSTIC_MUST_NOT_APPEAR") }
        GatewaySession.initStores(broken, { cloud })
        assertEquals("CLOUD_READY_LEGACY_UNAVAILABLE", GatewaySession.storageStatus)
        assertTrue(GatewaySession.selectCloud(true))
        assertTrue(GatewaySession.saveCloudSession(session(), origin))
        val id = GatewaySession.deviceId
        GatewaySession.initStores(broken, { cloud })
        assertTrue(GatewaySession.isCloud)
        assertTrue(GatewaySession.isAuthenticated())
        assertEquals(id, GatewaySession.deviceId)
        assertEquals("shc_refresh_" + "r".repeat(43), GatewaySession.refreshToken)
        assertTrue(GatewaySession.logout(null))
        assertFalse(GatewaySession.isAuthenticated())
    }

    @Test fun readableLegacyCloudSessionMigratesWithoutChangingLegacyData() {
        val key = "cloud_" + MessageDigest.getInstance("SHA-256")
            .digest(origin.toByteArray()).joinToString("") { "%02x".format(it) }
        val legacy = MemoryPrefs(mutableMapOf("device_id" to "dev-original", "cloud_mode" to true,
            "cloud_gateway_url" to origin, "api_token" to "LOCAL_ONLY_SECRET".repeat(4),
            key+"_access" to session().getString("device_token"),
            key+"_refresh" to session().getString("refresh_token"),
            key+"_expiry" to session().getLong("expires_at")))
        val before = legacy.data.toMap()
        val cloud = MemoryPrefs()
        GatewaySession.initStores({ legacy }, { cloud })
        assertTrue(GatewaySession.isCloud)
        assertTrue(GatewaySession.isAuthenticated())
        assertEquals(before, legacy.data)
        assertFalse(cloud.data.containsKey("api_token"))
        val migrated = GatewaySession.apiToken
        legacy.data[key+"_access"] = "shc_access_" + "x".repeat(43)
        GatewaySession.initStores({ legacy }, { cloud })
        assertEquals(migrated, GatewaySession.apiToken)
        GatewaySession.gatewayUrl = "https://different.example"
        assertEquals("", GatewaySession.apiToken)
        assertEquals("", GatewaySession.refreshToken)
    }

    @Test fun cloudFailureDoesNotEraseLocalDataOrEnableUnsecuredPairing() {
        val legacy = MemoryPrefs(mutableMapOf("api_token" to "l".repeat(48)))
        val before = legacy.data.toMap()
        GatewaySession.initStores({ legacy }, { throw SecurityException("PRIVATE_STORAGE_DETAIL") })
        assertFalse(GatewaySession.selectCloud(true))
        assertFalse(GatewaySession.isCloud)
        assertEquals("CLOUD_STORAGE_UNAVAILABLE:SecurityException", GatewaySession.storageStatus)
        assertEquals("l".repeat(48), GatewaySession.apiToken)
        assertFalse(GatewaySession.saveCloudSession(session(), origin))
        assertEquals(before, legacy.data)
    }

    @Test fun failedModeCommitLeavesModeUnchanged() {
        val cloud = MemoryPrefs()
        GatewaySession.initStores({ MemoryPrefs() }, { cloud })
        cloud.canCommit = false
        assertFalse(GatewaySession.selectCloud(true))
        assertFalse(GatewaySession.isCloud)
        assertFalse(cloud.getBoolean("cloud_mode", false))
    }

    @Test fun corruptLegacyCloudFieldCannotBlockFreshEncryptedRealm() {
        val key = "cloud_" + MessageDigest.getInstance("SHA-256")
            .digest(origin.toByteArray()).joinToString("") { "%02x".format(it) }
        val legacy = MemoryPrefs(mutableMapOf(key+"_expiry" to "INVALID_OLD_TYPE"))
        val before = legacy.data.toMap()
        GatewaySession.initStores({ legacy }, { MemoryPrefs() })
        assertTrue(GatewaySession.selectCloud(true))
        assertFalse(GatewaySession.isAuthenticated())
        assertEquals(before, legacy.data)
    }

    private class MemoryPrefs(val data: MutableMap<String, Any?> = mutableMapOf()) : SharedPreferences {
        var canCommit = true
        override fun getAll(): MutableMap<String, *> = data.toMutableMap()
        override fun getString(k: String?, d: String?): String? = if(data.containsKey(k)) data[k] as String? else d
        override fun getStringSet(k: String?, d: MutableSet<String>?): MutableSet<String>? = d
        override fun getInt(k: String?, d: Int) = if(data.containsKey(k)) data[k] as Int else d
        override fun getLong(k: String?, d: Long) = if(data.containsKey(k)) data[k] as Long else d
        override fun getFloat(k: String?, d: Float) = if(data.containsKey(k)) data[k] as Float else d
        override fun getBoolean(k: String?, d: Boolean) = if(data.containsKey(k)) data[k] as Boolean else d
        override fun contains(k: String?) = data.containsKey(k)
        override fun registerOnSharedPreferenceChangeListener(l: SharedPreferences.OnSharedPreferenceChangeListener?) = Unit
        override fun unregisterOnSharedPreferenceChangeListener(l: SharedPreferences.OnSharedPreferenceChangeListener?) = Unit
        override fun edit(): SharedPreferences.Editor = object : SharedPreferences.Editor {
            val updates = mutableMapOf<String, Any?>()
            var clear = false
            override fun putString(k: String?, v: String?) = apply { updates[requireNotNull(k)] = v }
            override fun putStringSet(k: String?, v: MutableSet<String>?) = apply { updates[requireNotNull(k)] = v }
            override fun putInt(k: String?, v: Int) = apply { updates[requireNotNull(k)] = v }
            override fun putLong(k: String?, v: Long) = apply { updates[requireNotNull(k)] = v }
            override fun putFloat(k: String?, v: Float) = apply { updates[requireNotNull(k)] = v }
            override fun putBoolean(k: String?, v: Boolean) = apply { updates[requireNotNull(k)] = v }
            override fun remove(k: String?) = apply { updates[requireNotNull(k)] = null }
            override fun clear() = apply { clear = true }
            override fun commit(): Boolean {
                if (!canCommit) return false
                if (clear) data.clear()
                for ((k,v) in updates) if (v == null) data.remove(k) else data[k] = v
                return true
            }
            override fun apply() { commit() }
        }
    }
}
