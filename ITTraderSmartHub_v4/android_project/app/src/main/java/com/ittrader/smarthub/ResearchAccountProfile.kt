package com.ittrader.smarthub

import java.math.BigDecimal
import org.json.JSONArray
import org.json.JSONObject

/** Local research metadata only. Never a broker login or approved risk policy. */
data class ResearchAccountProfile(
    val id: String, val label: String, val firm: String, val programme: String,
    val stage: String, val currency: String, val originalSize: String, val terms: String
) {
    init {
        require(Regex("[a-zA-Z0-9-]{1,40}").matches(id))
        require(firm in officialSources)
        require(listOf(label, programme, stage, terms).all {
            it.isNotBlank() && it.length <= 80 && it.none { c -> c.isISOControl() }
        })
        require(Regex("[A-Z]{3}").matches(currency))
        require(Regex("[0-9]{1,12}(\\.[0-9]{1,2})?").matches(originalSize))
        require(BigDecimal(originalSize) > BigDecimal.ZERO)
    }

    fun toJson() = JSONObject().put("id", id).put("label", label).put("firm", firm)
        .put("programme", programme).put("stage", stage).put("currency", currency)
        .put("original_size", originalSize).put("terms", terms)

    companion object {
        val officialSources = linkedMapOf(
            "FTMO" to "https://ftmo.com/en/trading-objectives/",
            "FundedNext" to "https://help.fundednext.com/en/",
            "GOAT" to "https://help.goatfundedtrader.com/en/collections/11969353-rules",
            "FundingPips" to "https://help.fundingpips.com/hc/en-us/articles/47328410434065-Responsible-Trading-Policy"
        ).toMap()

        fun decode(raw: String): List<ResearchAccountProfile> {
            require(raw.length <= 100_000)
            val array = JSONArray(raw)
            require(array.length() <= 20)
            val result = (0 until array.length()).map {
                val o = array.getJSONObject(it)
                require(o.keys().asSequence().toSet() == setOf("id", "label", "firm", "programme", "stage", "currency", "original_size", "terms"))
                fun text(key: String): String { require(o.get(key) is String); return o.getString(key) }
                ResearchAccountProfile(text("id"), text("label"), text("firm"), text("programme"),
                    text("stage"), text("currency"), text("original_size"), text("terms"))
            }
            require(result.map { it.id }.distinct().size == result.size)
            return result
        }
    }
}
