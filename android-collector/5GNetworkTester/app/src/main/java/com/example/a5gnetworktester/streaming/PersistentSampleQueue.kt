package com.example.a5gnetworktester.streaming

import java.io.BufferedReader
import java.io.File
import java.io.FileReader
import java.io.FileWriter
import java.io.PrintWriter
import java.util.Properties

data class QueuedItem(
    val seq: Long,
    val sampleJson: String
)

/**
 * Persistent sample queue for Contract C7 telemetry (T12-003, ADR-017).
 *
 * Implements:
 * 1. Persistent append-only sequential storage surviving process death.
 * 2. FIFO drop-oldest upon queue overflow (cap: maxQueue = 5,000 ≈ 4 h).
 * 3. Cumulative acknowledgement deletion (seq <= cumAckSeq).
 * 4. In-flight unacknowledged window control (cap: maxInflight = 50).
 * 5. Tracking and recovery of dropped_from_queue counter for hello/ping reporting.
 */
class PersistentSampleQueue(
    private val storageDir: File,
    val maxQueue: Int = DEFAULT_MAX_QUEUE,
    val maxInflight: Int = DEFAULT_MAX_INFLIGHT_UNACKED
) {

    companion object {
        const val DEFAULT_MAX_QUEUE = 5000
        const val DEFAULT_MAX_INFLIGHT_UNACKED = 50
        private const val LOG_FILE_NAME = "sample_queue.log"
        private const val META_FILE_NAME = "queue_meta.properties"
        private const val KEY_DROPPED_FROM_QUEUE = "dropped_from_queue"
    }

    private val logFile = File(storageDir, LOG_FILE_NAME)
    private val metaFile = File(storageDir, META_FILE_NAME)

    private val pendingItems = LinkedHashMap<Long, QueuedItem>()
    private val inFlightSeqs = mutableSetOf<Long>()

    var droppedFromQueue: Long = 0L
        private set

    val size: Int
        @Synchronized get() = pendingItems.size

    val inFlightCount: Int
        @Synchronized get() = inFlightSeqs.size

    init {
        if (!storageDir.exists()) {
            storageDir.mkdirs()
        }
        loadFromDisk()
    }

    private var uncompactedDrops: Int = 0

    /**
     * Enqueues a sample.
     * If the queue reaches capacity (maxQueue), drops the oldest item and increments droppedFromQueue.
     */
    @Synchronized
    fun enqueue(seq: Long, sampleJson: String): Boolean {
        // Drop oldest if at capacity
        if (pendingItems.size >= maxQueue) {
            val oldestSeq = pendingItems.keys.firstOrNull()
            if (oldestSeq != null) {
                pendingItems.remove(oldestSeq)
                inFlightSeqs.remove(oldestSeq)
                droppedFromQueue++
                uncompactedDrops++
                saveMeta()
            }
        }

        val item = QueuedItem(seq, sampleJson)
        pendingItems[seq] = item

        if (uncompactedDrops >= 2) {
            compactLog()
            uncompactedDrops = 0
        } else {
            appendLog(item)
        }
        saveMeta()
        return true
    }

    /**
     * Acknowledges all items with seq <= cumAckSeq.
     * Returns the count of newly acknowledged items removed.
     */
    @Synchronized
    fun acknowledge(cumAckSeq: Long): Int {
        val toRemove = pendingItems.keys.filter { it <= cumAckSeq }
        if (toRemove.isEmpty()) return 0

        for (seq in toRemove) {
            pendingItems.remove(seq)
            inFlightSeqs.remove(seq)
        }

        // Compact log file to reclaim space
        compactLog()
        saveMeta()
        return toRemove.size
    }

    /**
     * Obtains next un-sent items up to available in-flight window.
     */
    @Synchronized
    fun pollNextInflightBatch(limit: Int = maxInflight): List<QueuedItem> {
        val availableWindow = (maxInflight - inFlightSeqs.size).coerceAtLeast(0)
        val takeCount = limit.coerceAtMost(availableWindow)
        if (takeCount <= 0) return emptyList()

        val batch = mutableListOf<QueuedItem>()
        for (item in pendingItems.values) {
            if (!inFlightSeqs.contains(item.seq)) {
                batch.add(item)
                inFlightSeqs.add(item.seq)
                if (batch.size >= takeCount) break
            }
        }
        return batch
    }

    /**
     * Mark a specific seq as currently in-flight.
     */
    @Synchronized
    fun markInFlight(seq: Long): Boolean {
        if (inFlightSeqs.size >= maxInflight) return false
        if (pendingItems.containsKey(seq)) {
            inFlightSeqs.add(seq)
            return true
        }
        return false
    }

    /**
     * Clears in-flight tracking (e.g. after socket disconnect) so items can be resent.
     */
    @Synchronized
    fun resetInFlight() {
        inFlightSeqs.clear()
    }

    /**
     * Get all currently pending queued items (ordered by sequence).
     */
    @Synchronized
    fun getAllPending(): List<QueuedItem> {
        return pendingItems.values.toList()
    }

    private fun appendLog(item: QueuedItem) {
        PrintWriter(FileWriter(logFile, true)).use { writer ->
            writer.println("${item.seq}\t${item.sampleJson}")
        }
    }

    private fun compactLog() {
        val tempFile = File(storageDir, "$LOG_FILE_NAME.tmp")
        PrintWriter(FileWriter(tempFile, false)).use { writer ->
            for (item in pendingItems.values) {
                writer.println("${item.seq}\t${item.sampleJson}")
            }
        }
        if (tempFile.exists()) {
            if (logFile.exists()) {
                logFile.delete()
            }
            tempFile.renameTo(logFile)
        }
    }

    private fun saveMeta() {
        val props = Properties()
        props.setProperty(KEY_DROPPED_FROM_QUEUE, droppedFromQueue.toString())
        FileWriter(metaFile).use { writer ->
            props.store(writer, "PersistentSampleQueue Metadata")
        }
    }

    private fun loadFromDisk() {
        pendingItems.clear()
        inFlightSeqs.clear()

        // 1. Load metadata
        if (metaFile.exists()) {
            val props = Properties()
            FileReader(metaFile).use { reader ->
                props.load(reader)
            }
            droppedFromQueue = props.getProperty(KEY_DROPPED_FROM_QUEUE, "0").toLongOrNull() ?: 0L
        }

        // 2. Load log
        if (logFile.exists()) {
            BufferedReader(FileReader(logFile)).use { reader ->
                var line: String? = reader.readLine()
                while (line != null) {
                    val parts = line.split("\t", limit = 2)
                    if (parts.size == 2) {
                        val seq = parts[0].toLongOrNull()
                        val json = parts[1]
                        if (seq != null) {
                            pendingItems[seq] = QueuedItem(seq, json)
                        }
                    }
                    line = reader.readLine()
                }
            }
        }

        // 3. Guarantee queue capacity invariant across reloads
        if (pendingItems.size > maxQueue) {
            val overflow = pendingItems.size - maxQueue
            for (i in 0 until overflow) {
                val oldest = pendingItems.keys.firstOrNull() ?: break
                pendingItems.remove(oldest)
            }
            compactLog()
        }
    }
}
