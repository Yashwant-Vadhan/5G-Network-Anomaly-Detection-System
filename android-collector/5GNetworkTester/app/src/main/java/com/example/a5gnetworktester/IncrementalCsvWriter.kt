package com.example.a5gnetworktester

import java.io.BufferedWriter
import java.io.File
import java.io.FileWriter
import java.io.PrintWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Incremental CSV session writer guaranteeing crash-resilient persistence (T19-004, Guardrail G18).
 *
 * Implements:
 * 1. Immediate file and Contract C1 header creation upon session start.
 * 2. Incremental append and flush of each row as collected (survives force-stop/kill).
 * 3. Exact filename pattern: 5G_measurements_yyyyMMdd_HHmmss.csv.
 * 4. Content equality with the legacy in-memory output for identical rows.
 */
class IncrementalCsvWriter(
    val file: File,
    writeHeaderOnCreate: Boolean = true
) {
    companion object {
        const val FILE_PREFIX = "5G_measurements_"
        const val FILE_SUFFIX = ".csv"
        const val DATE_PATTERN = "yyyyMMdd_HHmmss"

        fun generateSessionFileName(date: Date = Date(), locale: Locale = Locale.getDefault()): String {
            val dateStr = SimpleDateFormat(DATE_PATTERN, locale).format(date)
            return "$FILE_PREFIX$dateStr$FILE_SUFFIX"
        }

        fun createSessionFile(directory: File, date: Date = Date(), locale: Locale = Locale.getDefault()): File {
            if (!directory.exists()) {
                directory.mkdirs()
            }
            return File(directory, generateSessionFileName(date, locale))
        }
    }

    private var writer: PrintWriter? = null
    var rowCount: Int = 0
        private set

    init {
        val isNew = !file.exists() || file.length() == 0L
        file.parentFile?.mkdirs()
        writer = PrintWriter(BufferedWriter(FileWriter(file, true)), true)
        if (isNew && writeHeaderOnCreate) {
            writer?.print(CsvBuilder.CSV_HEADER + "\n")
            writer?.flush()
        }
    }

    @Synchronized
    fun appendRow(row: String) {
        writer?.print(row + "\n")
        writer?.flush()
        rowCount++
    }

    @Synchronized
    fun close() {
        writer?.flush()
        writer?.close()
        writer = null
    }
}
