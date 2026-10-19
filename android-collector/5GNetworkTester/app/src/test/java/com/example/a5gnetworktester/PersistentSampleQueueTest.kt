package com.example.a5gnetworktester

import com.example.a5gnetworktester.streaming.C7IngestHello
import com.example.a5gnetworktester.streaming.C7Ping
import com.example.a5gnetworktester.streaming.PersistentSampleQueue
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

/**
 * Unit tests for PersistentSampleQueue (T12-003, ADR-017).
 *
 * Verifies:
 * 1. Survives process kill / reload from disk.
 * 2. Drop-oldest counter reported upon overflow and in hello/ping messages.
 * 3. Max in-flight unacked window <= MAX_INFLIGHT_UNACKED.
 */
class PersistentSampleQueueTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    @Test
    fun queue_survivesProcessKillAndRecoversUnackedSamples() {
        val queueDir = File(tempFolder.root, "queue_test_1")

        // 1. Initial process lifetime: enqueue 10 samples
        val queue1 = PersistentSampleQueue(
            storageDir = queueDir,
            maxQueue = 100,
            maxInflight = 50
        )
        for (seq in 1L..10L) {
            queue1.enqueue(seq, """{"seq":$seq,"data":"sample_$seq"}""")
        }
        assertEquals(10, queue1.size)

        // 2. Simulate process kill (queue1 instance discarded)
        // 3. New process lifecycle: reopen queue from same storageDir
        val queue2 = PersistentSampleQueue(
            storageDir = queueDir,
            maxQueue = 100,
            maxInflight = 50
        )

        // Acceptance criteria: Survives process kill
        assertEquals("Queue must recover all unacked items after restart", 10, queue2.size)
        val pending = queue2.getAllPending()
        assertEquals(1L, pending.first().seq)
        assertEquals(10L, pending.last().seq)

        // Acknowledge cumulative seq 6
        val acked = queue2.acknowledge(6L)
        assertEquals(6, acked)
        assertEquals(4, queue2.size)

        // 4. Second process restart
        val queue3 = PersistentSampleQueue(
            storageDir = queueDir,
            maxQueue = 100,
            maxInflight = 50
        )
        assertEquals(4, queue3.size)
        val remaining = queue3.getAllPending()
        assertEquals(listOf(7L, 8L, 9L, 10L), remaining.map { it.seq })
    }

    @Test
    fun queue_dropsOldestWhenFullAndTracksDroppedCountAcrossRestarts() {
        val queueDir = File(tempFolder.root, "queue_test_2")

        // Cap queue at 5 items
        val queue1 = PersistentSampleQueue(
            storageDir = queueDir,
            maxQueue = 5,
            maxInflight = 50
        )

        // Enqueue 8 items (overflow by 3)
        for (seq in 1L..8L) {
            queue1.enqueue(seq, """{"seq":$seq}""")
        }

        // Acceptance criteria: drop-oldest when full
        assertEquals(5, queue1.size)
        assertEquals("Oldest 3 items must be dropped", 3L, queue1.droppedFromQueue)
        val pending = queue1.getAllPending()
        assertEquals(listOf(4L, 5L, 6L, 7L, 8L), pending.map { it.seq })

        // Acceptance criteria: drop-oldest counter reported in hello / ping
        val ping = C7Ping(
            dropped_from_queue = queue1.droppedFromQueue,
            queue_depth = queue1.size.toLong()
        )
        val pingJson = ping.toCanonicalJson()
        assertTrue(pingJson.contains(""""dropped_from_queue":3"""))
        assertTrue(pingJson.contains(""""queue_depth":5"""))
        assertTrue(pingJson.contains(""""type":"ping""""))

        val hello = C7IngestHello(
            client_id = "test-uuid",
            device = "SM-A156E",
            manufacturer = "samsung",
            android = "16",
            operator = "airtel",
            dropped_from_queue = queue1.droppedFromQueue,
            queue_depth = queue1.size.toLong()
        )
        val helloJson = hello.toCanonicalJson()
        assertTrue(helloJson.contains(""""dropped_from_queue":3"""))
        assertTrue(helloJson.contains(""""queue_depth":5"""))

        // Simulate process kill: droppedFromQueue must survive
        val queue2 = PersistentSampleQueue(
            storageDir = queueDir,
            maxQueue = 5,
            maxInflight = 50
        )
        assertEquals(3L, queue2.droppedFromQueue)
        assertEquals(5, queue2.size)
    }

    @Test
    fun maxInflight_strictlyEnforcedBelowOrEqualMaxInflightUnacked() {
        val queueDir = File(tempFolder.root, "queue_test_3")
        val maxInflightLimit = 3

        val queue = PersistentSampleQueue(
            storageDir = queueDir,
            maxQueue = 100,
            maxInflight = maxInflightLimit
        )

        for (seq in 1L..10L) {
            queue.enqueue(seq, """{"seq":$seq}""")
        }

        // Acceptance criteria: Max in-flight unacked <= MAX_INFLIGHT_UNACKED
        val batch1 = queue.pollNextInflightBatch()
        assertEquals(3, batch1.size)
        assertEquals(3, queue.inFlightCount)
        assertTrue(queue.inFlightCount <= maxInflightLimit)

        // Attempting to poll further while window is full yields empty list
        val batch2 = queue.pollNextInflightBatch()
        assertTrue(batch2.isEmpty())
        assertEquals(3, queue.inFlightCount)

        // Acknowledge seq 2 (removes seq 1 and 2 from inflight)
        queue.acknowledge(2L)
        assertEquals(1, queue.inFlightCount) // Only seq 3 remains in-flight

        // Now window has capacity for 2 more items
        val batch3 = queue.pollNextInflightBatch()
        assertEquals(2, batch3.size)
        assertEquals(listOf(4L, 5L), batch3.map { it.seq })
        assertEquals(3, queue.inFlightCount)
        assertTrue(queue.inFlightCount <= maxInflightLimit)

        // Reset in-flight on connection drop
        queue.resetInFlight()
        assertEquals(0, queue.inFlightCount)
    }
}
