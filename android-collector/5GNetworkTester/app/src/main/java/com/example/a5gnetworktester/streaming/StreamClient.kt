package com.example.a5gnetworktester.streaming

import android.content.Context
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import java.util.UUID
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit

interface StreamClientListener {
    fun onConnected() {}
    fun onHelloAck(helloAck: C7HelloAck) {}
    fun onAck(ack: C7Ack) {}
    fun onAlert(alert: C7Alert) {}
    fun onError(error: C7Error) {}
    fun onConnectionStateChanged(state: StreamState) {}
}

enum class StreamState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    FATAL_HALTED
}

/**
 * Android WebSocket client for Contract C7 telemetry streaming (T12-002).
 * Runs all I/O off the main thread.
 */
class StreamClient(
    private val wsEndpointUrl: String,
    private val ingestToken: String?,
    private val context: Context? = null,
    private val clientInfo: DeviceInfoProvider = DefaultDeviceInfoProvider(context),
    private val listener: StreamClientListener? = null,
    private val okHttpClient: OkHttpClient = OkHttpClient.Builder()
        .readTimeout(10, TimeUnit.SECONDS)
        .build()
) {

    companion object {
        private const val PREFS_NAME = "5g_nads_stream_prefs"
        private const val KEY_CLIENT_ID = "client_uuid"
    }

    private val executor: ScheduledExecutorService = Executors.newSingleThreadScheduledExecutor()
    private var webSocket: WebSocket? = null
    var currentState: StreamState = StreamState.DISCONNECTED
        private set

    var isFatalHalted: Boolean = false
        private set

    val clientId: String by lazy {
        getOrCreateClientId()
    }

    private var currentSeq: Long = 0

    private fun getOrCreateClientId(): String {
        if (context == null) {
            return UUID.randomUUID().toString()
        }
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val existing = prefs.getString(KEY_CLIENT_ID, null)
        if (existing != null) {
            return existing
        }
        val newId = UUID.randomUUID().toString()
        prefs.edit().putString(KEY_CLIENT_ID, newId).apply()
        return newId
    }

    fun connect() {
        if (isFatalHalted) {
            return
        }

        executor.execute {
            if (currentState == StreamState.CONNECTING || currentState == StreamState.CONNECTED) {
                return@execute
            }

            updateState(StreamState.CONNECTING)

            val requestBuilder = Request.Builder().url(wsEndpointUrl)
            if (!ingestToken.isNullOrBlank()) {
                requestBuilder.addHeader("Authorization", "Bearer $ingestToken")
            }

            webSocket = okHttpClient.newWebSocket(requestBuilder.build(), object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    executor.execute {
                        updateState(StreamState.CONNECTED)
                        listener?.onConnected()
                        sendHello(resumeFromSeq = currentSeq)
                    }
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    executor.execute {
                        handleIncomingMessage(text)
                    }
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    executor.execute {
                        this@StreamClient.webSocket = null
                        if (!isFatalHalted) {
                            updateState(StreamState.DISCONNECTED)
                        }
                    }
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    executor.execute {
                        this@StreamClient.webSocket = null
                        if (!isFatalHalted) {
                            updateState(StreamState.DISCONNECTED)
                        }
                    }
                }
            })
        }
    }

    fun disconnect() {
        executor.execute {
            webSocket?.close(1000, "Client disconnected")
            webSocket = null
            if (!isFatalHalted) {
                updateState(StreamState.DISCONNECTED)
            }
        }
    }

    fun sendHello(resumeFromSeq: Long = 0, droppedCount: Long = 0, queueDepth: Long = 0) {
        val hello = C7IngestHello(
            client_id = clientId,
            app_version = "1.3.0",
            device = clientInfo.device,
            manufacturer = clientInfo.manufacturer,
            android = clientInfo.androidVersion,
            operator = clientInfo.operator,
            resume_from_seq = resumeFromSeq,
            dropped_from_queue = droppedCount,
            queue_depth = queueDepth
        )
        webSocket?.send(hello.toCanonicalJson())
    }

    fun sendSample(
        timestamp: String,
        registered: Boolean,
        ssRsrp: Double?,
        ssRsrq: Double?,
        ssSinr: Double?,
        csiRsrp: Double?,
        csiRsrq: Double?,
        csiSinr: Double?,
        pci: Int?,
        nci: Long?,
        nrarfcn: Int?,
        networkType: String = clientInfo.networkType,
        deploymentMode: String = clientInfo.deploymentMode,
        displayOverride: String = clientInfo.displayOverride,
        sentAt: String,
        edge: Map<String, Any?>? = null
    ): Long {
        currentSeq++
        val seqToSend = currentSeq

        val payload = C7SamplePayload(
            timestamp = timestamp,
            device = clientInfo.device,
            manufacturer = clientInfo.manufacturer,
            android = clientInfo.androidVersion,
            operator = clientInfo.operator,
            network_type = networkType,
            deployment_mode = deploymentMode,
            display_override = displayOverride,
            registered = registered,
            ss_rsrp = ssRsrp,
            ss_rsrq = ssRsrq,
            ss_sinr = ssSinr,
            csi_rsrp = csiRsrp,
            csi_rsrq = csiRsrq,
            csi_sinr = csiSinr,
            pci = pci,
            nci = nci,
            nrarfcn = nrarfcn
        )

        val sample = C7IngestSample(
            seq = seqToSend,
            sent_at = sentAt,
            payload = payload,
            edge = edge
        )

        executor.execute {
            webSocket?.send(sample.toCanonicalJson())
        }

        return seqToSend
    }

    fun handleIncomingMessage(text: String) {
        val type = extractField(text, "type") ?: return

        when (type) {
            "hello_ack" -> {
                val schemaVer = extractIntField(text, "schema_version") ?: 2
                val sessionId = extractField(text, "session_id")
                val accepted = extractBooleanField(text, "accepted") ?: true
                val resumedAt = extractLongField(text, "resumed_at_seq")
                val helloAck = C7HelloAck(type, schemaVer, sessionId, accepted, resumedAt)
                listener?.onHelloAck(helloAck)
            }
            "ack" -> {
                val schemaVer = extractIntField(text, "schema_version") ?: 2
                val seq = extractLongField(text, "seq") ?: 0
                val ack = C7Ack(type, schemaVer, seq)
                listener?.onAck(ack)
            }
            "error" -> {
                val schemaVer = extractIntField(text, "schema_version") ?: 2
                val seq = extractLongField(text, "seq")
                val code = extractField(text, "code") ?: "UNKNOWN"
                val message = extractField(text, "message") ?: ""
                val fatal = extractBooleanField(text, "fatal") ?: false

                val error = C7Error(type, schemaVer, seq, code, message, fatal)
                listener?.onError(error)

                // Acceptance criteria: Fatal error codes stop reconnect loops
                if (fatal) {
                    isFatalHalted = true
                    webSocket?.close(1008, "Fatal server error: $code")
                    webSocket = null
                    updateState(StreamState.FATAL_HALTED)
                }
            }
            "alert" -> {
                val schemaVer = extractIntField(text, "schema_version") ?: 2
                val alertId = extractField(text, "alert_id") ?: ""
                val severity = extractField(text, "severity") ?: "INFO"
                val title = extractField(text, "title") ?: ""
                val detail = extractField(text, "detail")
                val alert = C7Alert(type, schemaVer, alertId, severity, title, detail)
                listener?.onAlert(alert)
            }
        }
    }

    private fun updateState(newState: StreamState) {
        currentState = newState
        listener?.onConnectionStateChanged(newState)
    }

    private fun extractField(json: String, field: String): String? {
        val regex = Regex("\"$field\"\\s*:\\s*\"([^\"]*)\"")
        return regex.find(json)?.groupValues?.get(1)
    }

    private fun extractLongField(json: String, field: String): Long? {
        val regex = Regex("\"$field\"\\s*:\\s*(\\d+)")
        return regex.find(json)?.groupValues?.get(1)?.toLongOrNull()
    }

    private fun extractIntField(json: String, field: String): Int? {
        val regex = Regex("\"$field\"\\s*:\\s*(\\d+)")
        return regex.find(json)?.groupValues?.get(1)?.toIntOrNull()
    }

    private fun extractBooleanField(json: String, field: String): Boolean? {
        val regex = Regex("\"$field\"\\s*:\\s*(true|false)")
        return regex.find(json)?.groupValues?.get(1)?.toBooleanStrictOrNull()
    }
}

interface DeviceInfoProvider {
    val device: String
    val manufacturer: String
    val androidVersion: String
    val operator: String
    val networkType: String
    val deploymentMode: String
    val displayOverride: String
}

class DefaultDeviceInfoProvider(
    private val context: Context?
) : DeviceInfoProvider {
    override val device: String get() = android.os.Build.MODEL ?: "UNKNOWN"
    override val manufacturer: String get() = android.os.Build.MANUFACTURER ?: "UNKNOWN"
    override val androidVersion: String get() = android.os.Build.VERSION.RELEASE ?: "UNKNOWN"
    override val operator: String get() = "UNKNOWN"
    override val networkType: String get() = "5G NR"
    override val deploymentMode: String get() = "SA"
    override val displayOverride: String get() = "NONE"
}
