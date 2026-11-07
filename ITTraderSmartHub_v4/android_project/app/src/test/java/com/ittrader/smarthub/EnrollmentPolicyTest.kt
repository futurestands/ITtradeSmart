package com.ittrader.smarthub

import org.junit.Assert.*
import org.junit.Test

class EnrollmentPolicyTest {
    @Test fun cloudInvitationUsesCloudRoute() {
        assertEquals("/api/v5/device/enroll", EnrollmentPolicy.route(true, "shc_enroll_SYNTHETIC"))
    }
    @Test fun localInvitationKeepsLegacyRoute() {
        assertEquals("/api/v4/device/enroll", EnrollmentPolicy.route(false, "PAIR-SYNTHETIC"))
    }
    @Test fun cloudInvitationInLocalModeExplainsRequiredSwitch() {
        try {
            EnrollmentPolicy.route(false, "shc_enroll_SYNTHETIC")
            fail("Cloud code must not leave through the legacy route")
        } catch (error: IllegalArgumentException) {
            assertTrue(error.message!!.contains("Cloud HTTPS mode ON"))
        }
    }
    @Test fun localInvitationCannotEnrollIntoCloud() {
        try {
            EnrollmentPolicy.route(true, "PAIR-SYNTHETIC")
            fail("Local invitation must not enter cloud enrollment")
        } catch (_: IllegalArgumentException) { }
    }
}
