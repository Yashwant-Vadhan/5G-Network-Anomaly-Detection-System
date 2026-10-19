package com.example.a5gnetworktester.streaming

import java.util.TreeMap

/**
 * Contract C7 WebSocket message definitions and canonical serialization (T12-002, T10-005).
 */
data class C7SamplePayload(
    val timestamp: String,
    val device: String,
    val manufacturer: String,
    val android: String,
    val operator: String,
    val network_type: String,
    val deployment_mode: String,
    val display_override: String,
    val registered: Boolean,
    val ss_rsrp: Double?,
    val ss_rsrq: Double?,
    val ss_sinr: Double?,
    val csi_rsrp: Double?,
    val csi_rsrq: Double?,
    val csi_sinr: Double?,
    val pci: Int?,
    val nci: Long?,
    val nrarfcn: Int?
) {
    fun toMap(): Map<String, Any?> = sortedMapOf(
        "android" to android,
        "csi_rsrp" to csi_rsrp,
        "csi_rsrq" to csi_rsrq,
        "csi_sinr" to csi_sinr,
        "deployment_mode" to deployment_mode,
        "device" to device,
        "display_override" to display_override,
        "manufacturer" to manufacturer,
        "nci" to nci,
        "network_type" to network_type,
        "nrarfcn" to nrarfcn,
        "operator" to operator,
        "pci" to pci,
        "registered" to registered,
        "ss_rsrp" to ss_rsrp,
        "ss_rsrq" to ss_rsrq,
        "ss_sinr" to ss_sinr,
        "timestamp" to timestamp
    )
}

data class C7IngestSample(
    val type: String = "sample",
    val schema_version: Int = 2,
    val seq: Long,
    val sent_at: String,
    val payload: C7SamplePayload,
    val edge: Map<String, Any?>? = null
) {
    fun toMap(): Map<String, Any?> = sortedMapOf(
        "edge" to edge,
        "payload" to payload.toMap(),
        "schema_version" to schema_version,
        "sent_at" to sent_at,
        "seq" to seq,
        "type" to type
    )

    fun toCanonicalJson(): String = C7Json.canonicalize(toMap())
}

data class C7IngestHello(
    val type: String = "hello",
    val schema_version: Int = 2,
    val client_id: String,
    val app_version: String = "1.3.0",
    val device: String,
    val manufacturer: String,
    val android: String,
    val operator: String,
    val resume_from_seq: Long = 0,
    val dropped_from_queue: Long = 0,
    val queue_depth: Long = 0,
    val session_label: String = "collector",
    val source: String = "phone",
    val edge: Map<String, Any?>? = null
) {
    fun toMap(): Map<String, Any?> = sortedMapOf(
        "android" to android,
        "app_version" to app_version,
        "client_id" to client_id,
        "device" to device,
        "dropped_from_queue" to dropped_from_queue,
        "edge" to edge,
        "manufacturer" to manufacturer,
        "operator" to operator,
        "queue_depth" to queue_depth,
        "resume_from_seq" to resume_from_seq,
        "schema_version" to schema_version,
        "session_label" to session_label,
        "source" to source,
        "type" to type
    )

    fun toCanonicalJson(): String = C7Json.canonicalize(toMap())
}

data class C7Ack(
    val type: String,
    val schema_version: Int,
    val seq: Long
)

data class C7HelloAck(
    val type: String,
    val schema_version: Int,
    val session_id: String?,
    val accepted: Boolean,
    val resumed_at_seq: Long?
)

data class C7Error(
    val type: String,
    val schema_version: Int,
    val seq: Long?,
    val code: String,
    val message: String,
    val fatal: Boolean
)

data class C7Alert(
    val type: String,
    val schema_version: Int,
    val alert_id: String,
    val severity: String,
    val title: String,
    val detail: String?
)

data class C7Ping(
    val type: String = "ping",
    val schema_version: Int = 2,
    val dropped_from_queue: Long = 0,
    val queue_depth: Long = 0
) {
    fun toMap(): Map<String, Any?> = sortedMapOf(
        "dropped_from_queue" to dropped_from_queue,
        "queue_depth" to queue_depth,
        "schema_version" to schema_version,
        "type" to type
    )

    fun toCanonicalJson(): String = C7Json.canonicalize(toMap())
}

/**
 * Lightweight, zero-dependency canonical JSON serializer for Contract C7.
 * Orders keys alphabetically, formats nulls, escapes strings, and strips whitespace.
 */
object C7Json {

    @Suppress("UNCHECKED_CAST")
    fun canonicalize(value: Any?): String = when (value) {
        null -> "null"
        is String -> escapeString(value)
        is Boolean -> if (value) "true" else "false"
        is Number -> formatNumber(value)
        is Map<*, *> -> {
            val sorted = TreeMap<String, Any?>()
            for ((k, v) in value) {
                sorted[k.toString()] = v
            }
            sorted.entries.joinToString(
                prefix = "{",
                separator = ",",
                postfix = "}"
            ) { (k, v) ->
                "${escapeString(k)}:${canonicalize(v)}"
            }
        }
        is Iterable<*> -> {
            value.joinToString(
                prefix = "[",
                separator = ",",
                postfix = "]"
            ) { canonicalize(it) }
        }
        else -> escapeString(value.toString())
    }

    private fun escapeString(s: String): String {
        val sb = java.lang.StringBuilder("\"")
        for (ch in s) {
            when (ch) {
                '\\' -> sb.append("\\\\")
                '"' -> sb.append("\\\"")
                '\b' -> sb.append("\\b")
                '\u000C' -> sb.append("\\f")
                '\n' -> sb.append("\\n")
                '\r' -> sb.append("\\r")
                '\t' -> sb.append("\\t")
                else -> {
                    if (ch.code < 32) {
                        sb.append(String.format("\\u%04x", ch.code))
                    } else {
                        sb.append(ch)
                    }
                }
            }
        }
        sb.append("\"")
        return sb.toString()
    }

    private fun formatNumber(n: Number): String {
        return when (n) {
            is Double -> {
                if (n.isNaN() || n.isInfinite()) "null"
                else if (n == n.toLong().toDouble()) n.toLong().toString() + ".0"
                else n.toString()
            }
            is Float -> {
                if (n.isNaN() || n.isInfinite()) "null"
                else if (n == n.toLong().toFloat()) n.toLong().toString() + ".0"
                else n.toString()
            }
            else -> n.toString()
        }
    }
}
