package com.example.a5gnetworktester

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.util.Date

/**
 * Unit tests for IncrementalCsvWriter (T19-004, Guardrail G18).
 *
 * Verifies:
 * 1. Immediate file and Contract C1 header creation upon instantiation.
 * 2. Incremental flush: force-stop mid-session leaves a fully valid CSV with all flushed rows.
 * 3. Final content equals the legacy in-memory output for the same rows.
 * 4. File name matches 5G_measurements_yyyyMMdd_HHmmss.csv pattern.
 */
class IncrementalCsvWriterTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    @Test
    fun testFileNamePattern() {
        val fileName = IncrementalCsvWriter.generateSessionFileName()
        val regex = Regex("""^5G_measurements_\d{8}_\d{6}\.csv$""")
        assertTrue("Filename '$fileName' should match pattern 5G_measurements_yyyyMMdd_HHmmss.csv", regex.matches(fileName))
    }

    @Test
    fun testCreatesHeaderImmediatelyUponSessionStart() {
        val sessionFile = IncrementalCsvWriter.createSessionFile(tempFolder.root)
        val writer = IncrementalCsvWriter(sessionFile)

        // Even before any samples are appended, file exists and contains Contract C1 header
        assertTrue("Session file should exist immediately", sessionFile.exists())
        val lines = sessionFile.readLines()
        assertEquals(1, lines.size)
        assertEquals(CsvBuilder.CSV_HEADER, lines[0])

        writer.close()
    }

    @Test
    fun testForceStopMidSessionLeavesValidCsv() {
        val sessionFile = IncrementalCsvWriter.createSessionFile(tempFolder.root)
        val writer = IncrementalCsvWriter(sessionFile)

        val row1 = "19-10-26 14:00:00,2406ERN9CI,Xiaomi,14,Jio,NR,NSA,NR_NSA,YES,-85,-10,15,NA,NA,NA,123,456,12345"
        val row2 = "19-10-26 14:00:03,2406ERN9CI,Xiaomi,14,Jio,NR,NSA,NR_NSA,YES,-86,-11,14,NA,NA,NA,123,456,12345"

        writer.appendRow(row1)
        writer.appendRow(row2)

        // SIMULATE FORCE-STOP / CRASH: We do NOT call writer.close()
        // Instead, a separate file reader reads the file directly from disk
        val contentImmediatelyOnDisk = sessionFile.readLines()
        assertEquals("Header + 2 rows must be present on disk without close()", 3, contentImmediatelyOnDisk.size)
        assertEquals(CsvBuilder.CSV_HEADER, contentImmediatelyOnDisk[0])
        assertEquals(row1, contentImmediatelyOnDisk[1])
        assertEquals(row2, contentImmediatelyOnDisk[2])

        // Verify CSV structure has identical column counts
        val headerColCount = contentImmediatelyOnDisk[0].split(",").size
        assertEquals(18, headerColCount)
        assertEquals(headerColCount, contentImmediatelyOnDisk[1].split(",").size)
        assertEquals(headerColCount, contentImmediatelyOnDisk[2].split(",").size)

        writer.close()
    }

    @Test
    fun testFinalContentEqualsLegacyInMemoryOutput() {
        val sessionFile = IncrementalCsvWriter.createSessionFile(tempFolder.root)
        val writer = IncrementalCsvWriter(sessionFile)

        val mockRows = mutableListOf<String>()
        mockRows.add(CsvBuilder.CSV_HEADER)

        for (i in 1..5) {
            val row = "19-10-26 14:00:0$i,2406ERN9CI,Xiaomi,14,Jio,NR,NSA,NR_NSA,YES,-8$i,-1$i,1$i,NA,NA,NA,123,456,12345"
            mockRows.add(row)
            writer.appendRow(row)
        }

        writer.close()

        val incrementalContent = sessionFile.readText()
        val legacyInMemoryContent = mockRows.joinToString("\n") + "\n"

        assertEquals(
            "Final incremental CSV content must equal legacy in-memory output",
            legacyInMemoryContent,
            incrementalContent
        )
        assertEquals(5, writer.rowCount)
    }
}
