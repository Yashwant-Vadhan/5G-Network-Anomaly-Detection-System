package com.example.a5gnetworktester.streaming

/**
 * Dispatches cellular measurements to both local CSV logging and optional streaming (T12-007, Guardrail G18).
 *
 * Invariant (G18): CSV logging MUST ALWAYS execute before and independently of streaming.
 * Any exception in the streaming path is caught, counted, and surfaced without affecting CSV logging.
 */
class TelemetryDispatcher(
    private val onLogCsv: (row: String) -> Unit,
    private val onStream: ((row: String) -> Unit)? = null
) {
    var loggedCount: Long = 0
        private set

    var streamedCount: Long = 0
        private set

    var streamingErrorsCount: Long = 0
        private set

    var lastStreamingError: Throwable? = null
        private set

    /**
     * Dispatches a row.
     * Guarantees that local CSV logging executes first. If the streaming client throws an exception,
     * it is caught, counted, and loggedCount is fully preserved.
     */
    fun dispatch(row: String) {
        // 1. Mandatory local CSV logging (always first, Guardrail G18)
        onLogCsv(row)
        loggedCount++

        // 2. Best-effort streaming hook
        if (onStream != null) {
            try {
                onStream.invoke(row)
                streamedCount++
            } catch (t: Throwable) {
                streamingErrorsCount++
                lastStreamingError = t
                // Exceptions in stream client MUST NEVER propagate to caller or harm logging
            }
        }
    }
}
