package com.example.a5gnetworktester

import com.example.a5gnetworktester.streaming.TelemetryDispatcher
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.IOException

/**
 * Regression and invariant tests proving CSV logging is independent of streaming (T12-007, Guardrail G18).
 */
class TelemetryDispatcherTest {

    @Test
    fun exceptionInStreamClient_neverStopsLogging() {
        // Acceptance criteria: Exception in StreamClient never stops logging
        val loggedRows = mutableListOf<String>()

        val failingStreamHook: (String) -> Unit = {
            throw RuntimeException("Simulated WebSocket pipe broken")
        }

        val dispatcher = TelemetryDispatcher(
            onLogCsv = { row -> loggedRows.add(row) },
            onStream = failingStreamHook
        )

        for (i in 1..50) {
            val fakeRow = "row-$i,-85,-11,15,336,13322280247,632000"
            // Dispatch should NOT throw despite failing stream hook
            dispatcher.dispatch(fakeRow)
        }

        assertEquals("All 50 rows must be logged to CSV despite streaming exceptions", 50, loggedRows.size)
        assertEquals(50L, dispatcher.loggedCount)
        assertEquals(0L, dispatcher.streamedCount)
        assertEquals(50L, dispatcher.streamingErrorsCount)
        assertNotNull(dispatcher.lastStreamingError)
    }

    @Test
    fun killingServerMidSession_leavesCompleteCsv() {
        // Acceptance criteria: Killing the server mid-session leaves a complete CSV
        val loggedRows = mutableListOf<String>()
        var serverAlive = true

        val streamingHook: (String) -> Unit = {
            if (!serverAlive) {
                throw IOException("Connection refused: server terminated")
            }
        }

        val dispatcher = TelemetryDispatcher(
            onLogCsv = { row -> loggedRows.add(row) },
            onStream = streamingHook
        )

        // 10 samples while server is alive
        for (i in 1..10) {
            dispatcher.dispatch("sample-$i")
        }
        assertEquals(10, loggedRows.size)
        assertEquals(10L, dispatcher.streamedCount)
        assertEquals(0L, dispatcher.streamingErrorsCount)

        // Server is killed mid-session!
        serverAlive = false

        // Another 15 samples after server was killed
        for (i in 11..25) {
            dispatcher.dispatch("sample-$i")
        }

        assertEquals("CSV must contain all 25 rows despite server being killed mid-session", 25, loggedRows.size)
        assertEquals(25L, dispatcher.loggedCount)
        assertEquals(10L, dispatcher.streamedCount)
        assertEquals(15L, dispatcher.streamingErrorsCount)
    }

    @Test
    fun testFailsIfOrderIsReversed() {
        // Acceptance criteria: Test fails if the order is reversed
        // Verifies the structural invariant: logging happens strictly before streaming.
        val callOrder = mutableListOf<String>()

        val dispatcher = TelemetryDispatcher(
            onLogCsv = { callOrder.add("CSV") },
            onStream = { callOrder.add("STREAM") }
        )

        dispatcher.dispatch("sample-1")
        assertEquals(listOf("CSV", "STREAM"), callOrder)

        // Negative proof: If order is reversed (STREAM before CSV), an exception in STREAM drops CSV
        val badOrderLogged = mutableListOf<String>()
        var badOrderDiedBeforeCsv = false

        try {
            // Simulated reversed order implementation:
            val reversedStream: () -> Unit = { throw IOException("Stream failed early") }
            val reversedCsv: () -> Unit = { badOrderLogged.add("csv-row") }

            // STREAM first:
            reversedStream.invoke()
            // CSV second (unreachable):
            reversedCsv.invoke()
        } catch (_: IOException) {
            badOrderDiedBeforeCsv = true
        }

        assertTrue("Reversing the order drops CSV when stream throws", badOrderDiedBeforeCsv)
        assertTrue("CSV was never recorded under reversed order", badOrderLogged.isEmpty())

        // In contrast, TelemetryDispatcher preserves CSV even when stream throws
        val safeLogged = mutableListOf<String>()
        val safeDispatcher = TelemetryDispatcher(
            onLogCsv = { safeLogged.add("safe-row") },
            onStream = { throw IOException("Stream failed") }
        )
        safeDispatcher.dispatch("sample")
        assertEquals(1, safeLogged.size)
    }
}
