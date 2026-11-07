package com.ittrader.smarthub

/** A cloud invitation must never be sent to the legacy local enrollment route. */
object EnrollmentPolicy {
    fun route(cloud: Boolean, code: String): String {
        val cloudCode = code.startsWith("shc_enroll_")
        require(cloud || !cloudCode) {
            "Turn Cloud HTTPS mode ON first, then enter the Preview URL and cloud code again."
        }
        require(!cloud || cloudCode) { "Use a separate one-time cloud enrollment code." }
        return if (cloud) "/api/v5/device/enroll" else "/api/v4/device/enroll"
    }
}
