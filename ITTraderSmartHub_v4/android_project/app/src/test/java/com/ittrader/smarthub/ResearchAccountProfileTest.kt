package com.ittrader.smarthub

import org.junit.Assert.*
import org.junit.Test

class ResearchAccountProfileTest {
    private fun profile(size: String = "10000") = ResearchAccountProfile("research-test", "Trial",
        "FTMO", "2-Step", "Phase 1", "USD", size, "test-terms-v1")

    @Test fun roundTripKeepsSeparateAccountContexts() {
        val first = profile()
        val second = first.copy(id = "second", firm = "FundedNext", originalSize = "100000")
        val decoded = ResearchAccountProfile.decode("[${first.toJson()},${second.toJson()}]")
        assertEquals(listOf(first, second), decoded)
    }
    @Test fun noPolicyApprovalOrCredentialsSerialized() {
        assertEquals(setOf("id","label","firm","programme","stage","currency","original_size","terms"),
            profile().toJson().keys().asSequence().toSet())
    }
    @Test fun invalidSizesRejected() {
        for (size in listOf("0", "-1", "NaN", "Infinity", "1e5", "true")) {
            assertThrows(IllegalArgumentException::class.java) { profile(size) }
        }
    }
    @Test fun duplicateIdsAndUnexpectedFieldsRejected() {
        val value = profile().toJson()
        assertThrows(IllegalArgumentException::class.java) { ResearchAccountProfile.decode("[$value,$value]") }
        value.put("rules_approved", true)
        assertThrows(IllegalArgumentException::class.java) { ResearchAccountProfile.decode("[$value]") }
    }
    @Test fun noUnknownFirmsOrEmptyTerms() {
        assertThrows(IllegalArgumentException::class.java) { profile().copy(firm = "Unknown") }
        assertThrows(IllegalArgumentException::class.java) { profile().copy(terms = "") }
    }
    @Test fun officialLinksCannotIncludeAccountMetadata() {
        assertEquals(4, ResearchAccountProfile.officialSources.size)
        assertTrue(ResearchAccountProfile.officialSources.values.all { it.startsWith("https://") && !it.contains("?") })
    }
}
