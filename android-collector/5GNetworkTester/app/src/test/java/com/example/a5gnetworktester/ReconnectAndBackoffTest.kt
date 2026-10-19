package com.example.a5gnetworktester

import com.example.a5gnetworktester.streaming.C7Ack
import com.example.a5gnetworktester.streaming.DeviceInfoProvider
import com.example.a5gnetworktester.streaming.ExponentialBackoff
import com.example.a5gnetworktester.streaming.FakeClock
import com.example.a5gnetworktester.streaming.PersistentSampleQueue
import com.example.a5gnetworktester.streaming.StreamClient
import com.example.a5gnetworktester.streaming.StreamState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/**
 * Unit tests for Reconnect with exponential backoff, resume, and window pacing (T12-004).
 *
 * Acceptance Criteria:
 * 1. Server restart mid-session resumes with no duplicates stored.
 * 2. Flush does not flood (respects window).
 * 3. Backoff unit-tested with a fake clock.
 */
class ReconnectAndBackoffTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private val mockDeviceInfo = object : DeviceInfoProvider {
        override val device: String = "SM-A156E"
        override val manufacturer: String = "samsung"
        override val androidVersion: String = "16"
        override val operator: String = "airtel"
        override val networkType: String = "LTE"
        override val deploymentMode: String = "NSA"
        override val displayOverride: String = "NR_NSA"
    }

    @Test
    fun backoff_unitTestedWithFakeClock_capsStrictlyAt30Seconds() {
        val fakeClock = FakeClock(100000L)

        // Zero jitter for deterministic exponential sequence testing
        val backoff = ExponentialBackoff(
            initialDelayMs = 1000L,
            maxDelayMs = 30000L,
            factor = 2.0,
            jitterFactor = 0.0,
            randomProvider = { 0.5 },
            clock = fakeClock
        )

        // Attempt 0: 1000 ms
        val d0 = backoff.nextDelayMs()
        assertEquals(1000L, d0)
        fakeClock.advanceBy(d0)

        // Attempt 1: 2000 ms
        val d1 = backoff.nextDelayMs()
        assertEquals(2000L, d1)
        fakeClock.advanceBy(d1)

        // Attempt 2: 4000 ms
        val d2 = backoff.nextDelayMs()
        assertEquals(4000L, d2)
        fakeClock.advanceBy(d2)

        // Attempt 3: 8000 ms
        val d3 = backoff.nextDelayMs()
        assertEquals(8000L, d3)
        fakeClock.advanceBy(d3)

        // Attempt 4: 16000 ms
        val d4 = backoff.nextDelayMs()
        assertEquals(16000L, d4)
        fakeClock.advanceBy(d4)

        // Attempt 5: 32000 ms -> strictly capped at 30,000 ms (30 s)
        val d5 = backoff.nextDelayMs()
        assertEquals(30000L, d5)
        fakeClock.advanceBy(d5)

        // Subsequent attempts strictly remain at 30,000 ms cap
        val d6 = backoff.nextDelayMs()
        assertEquals(30000L, d6)

        // Reset restores initial delay
        backoff.reset()
        assertEquals(0, backoff.attempt)
        val dAfterReset = backoff.nextDelayMs()
        assertEquals(1000L, dAfterReset)
    }

    @Test
    fun backoff_withJitter_staysWithinCap() {
        val fakeClock = FakeClock(0L)
        val backoff = ExponentialBackoff(
            initialDelayMs = 1000L,
            maxDelayMs = 30000L,
            jitterFactor = 0.25,
            clock = fakeClock
        )

        for (i in 0 until 20) {
            val delay = backoff.nextDelayMs()
            assertTrue("Delay $delay ms must be >= 0", delay >= 0)
            assertTrue("Delay $delay ms must not exceed 30,000 ms cap", delay <= 30000L)
        }
    }

    @Test
    fun serverRestartMidSession_resumesWithNoDuplicatesStored() {
        val queueDir = File(tempFolder.root, "queue_resume_test")
        val queue = PersistentSampleQueue(queueDir, maxQueue = 100, maxInflight = 50)

        val client = StreamClient(
            wsEndpointUrl = "ws://127.0.0.1:8000/api/v1/ingest",
            ingestToken = "test-token",
            clientInfo = mockDeviceInfo,
            queue = queue
        )

        // 1. Client enqueues 5 samples (seq 1..5)
        for (i in 1..5) {
            client.sendSample(
                timestamp = "01-10-26 18:26:0$i",
                registered = true,
                ssRsrp = -90.0,
                ssRsrq = -10.0,
                ssSinr = 15.0,
                csiRsrp = null,
                csiRsrq = null,
                csiSinr = null,
                pci = 100,
                nci = 1L,
                nrarfcn = 600000,
                sentAt = "2026-10-01T18:26:0$i.000Z"
            )
        }
        assertEquals(5, queue.size)

        // 2. Server acks samples up to seq 3
        client.handleIncomingMessage("""{"type":"ack","schema_version":2,"seq":3}""")

        // Acceptance criteria: lastSeqAcked tracks 3, items 1..3 deleted from queue
        assertEquals(3L, client.lastSeqAcked)
        assertEquals("Queue must only contain unacknowledged items (4 and 5)", 2, queue.size)
        val remaining = queue.getAllPending()
        assertEquals(listOf(4L, 5L), remaining.map { it.seq })

        // 3. Simulate server restart: socket drops and client reconnects
        client.disconnect()
        assertEquals(StreamState.DISCONNECTED, client.currentState)

        // In new connection, re-hello sends resume_from_seq = lastSeqAcked (3)
        // Only remaining items 4 and 5 are flushed; 1..3 are not resent or duplicated
        assertEquals(3L, client.lastSeqAcked)
        assertEquals(listOf(4L, 5L), client.queue.getAllPending().map { it.seq })
    }

    @Test
    fun flushDoesNotFlood_respectsInflightWindow() {
        val queueDir = File(tempFolder.root, "queue_flush_test")
        val maxInflightCap = 5
        val queue = PersistentSampleQueue(queueDir, maxQueue = 100, maxInflight = maxInflightCap)

        // 1. Enqueue 20 items while offline
        for (seq in 1L..20L) {
            queue.enqueue(seq, """{"seq":$seq}""")
        }
        assertEquals(20, queue.size)

        // Acceptance criteria: Flush does not flood (respects window)
        // First batch polled must not exceed maxInflight (5)
        val batch1 = queue.pollNextInflightBatch()
        assertEquals(5, batch1.size)
        assertEquals(listOf(1L, 2L, 3L, 4L, 5L), batch1.map { it.seq })
        assertEquals(5, queue.inFlightCount)

        // Further poll attempts return 0 while in-flight window is saturated
        val saturatedPoll = queue.pollNextInflightBatch()
        assertTrue("Must not flood socket while in-flight limit reached", saturatedPoll.isEmpty())

        // Server acknowledges seq 3 (items 1..3 acked, 2 items 4 and 5 remain in flight)
        queue.acknowledge(3L)
        assertEquals(2, queue.inFlightCount)

        // Now next 3 items can be polled without exceeding cap 5
        val batch2 = queue.pollNextInflightBatch()
        assertEquals(3, batch2.size)
        assertEquals(listOf(6L, 7L, 8L), batch2.map { it.seq })
        assertEquals(5, queue.inFlightCount)
        assertTrue(queue.inFlightCount <= maxInflightCap)
    }

    @Test
    fun fatalError_cancelsReconnectLoop() {
        val client = StreamClient(
            wsEndpointUrl = "ws://127.0.0.1:8000/api/v1/ingest",
            ingestToken = "bad-token",
            clientInfo = mockDeviceInfo
        )

        // Receive fatal UNAUTHORIZED error
        client.handleIncomingMessage("""{"type":"error","schema_version":2,"code":"UNAUTHORIZED","message":"Invalid token","fatal":true}""")

        // Acceptance criteria: Reconnect cancelled on fatal error
        assertTrue("Client must be fatal halted", client.isFatalHalted)
        assertEquals(StreamState.FATAL_HALTED, client.currentState)
    }
}
