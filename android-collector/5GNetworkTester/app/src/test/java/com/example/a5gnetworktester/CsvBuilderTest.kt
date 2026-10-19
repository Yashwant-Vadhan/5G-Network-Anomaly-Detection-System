package com.example.a5gnetworktester

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

/**
 * Golden unit tests for CsvBuilder and buildCsvRow (T19-002, Guardrail G32).
 *
 * Verifies byte-level parity of Contract C1 CSV row construction,
 * exact 18 columns, NA conversion, and dd-MM-yy HH:mm:ss timestamp formatting.
 */
class CsvBuilderTest {

    @Test
    fun header_matchesContractC1ExactOrderAnd18Columns() {
        val expectedHeader =
            "timestamp,device,manufacturer,android,operator," +
                    "network_type,deployment_mode,display_override," +
                    "registered,ss_rsrp,ss_rsrq,ss_sinr," +
                    "csi_rsrp,csi_rsrq,csi_sinr," +
                    "pci,nci,nrarfcn"

        assertEquals(expectedHeader, CsvBuilder.CSV_HEADER)

        val columns = CsvBuilder.CSV_HEADER.split(",")
        assertEquals(18, columns.size)
        assertEquals("timestamp", columns[0])
        assertEquals("device", columns[1])
        assertEquals("manufacturer", columns[2])
        assertEquals("android", columns[3])
        assertEquals("operator", columns[4])
        assertEquals("network_type", columns[5])
        assertEquals("deployment_mode", columns[6])
        assertEquals("display_override", columns[7])
        assertEquals("registered", columns[8])
        assertEquals("ss_rsrp", columns[9])
        assertEquals("ss_rsrq", columns[10])
        assertEquals("ss_sinr", columns[11])
        assertEquals("csi_rsrp", columns[12])
        assertEquals("csi_rsrq", columns[13])
        assertEquals("csi_sinr", columns[14])
        assertEquals("pci", columns[15])
        assertEquals("nci", columns[16])
        assertEquals("nrarfcn", columns[17])
    }

    @Test
    fun goldenTest_fullValidSampleMatchesExpectedCsvLine() {
        val sdf = SimpleDateFormat(CsvBuilder.TIMESTAMP_PATTERN, Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val fixedDate = sdf.parse("19-10-26 14:30:00")!!

        val row = buildCsvRow(
            date = fixedDate,
            device = "2406ERN9CI",
            manufacturer = "Xiaomi",
            androidVersion = "14",
            operator = "Jio 5G",
            networkType = "5G NR",
            deploymentMode = "SA",
            displayOverride = "5G",
            isRegistered = true,
            rawSsRsrp = -85,
            rawSsRsrq = -11,
            rawSsSinr = 15,
            rawCsiRsrp = -86,
            rawCsiRsrq = -12,
            rawCsiSinr = 14,
            rawPci = 421,
            rawNci = 13322280247L,
            rawNrarfcn = 632000,
            locale = Locale.US,
            timeZone = TimeZone.getTimeZone("UTC")
        )

        val expected =
            "19-10-26 14:30:00,2406ERN9CI,Xiaomi,14,Jio 5G,5G NR,SA,5G,TRUE," +
                    "-85,-11,15,-86,-12,14,421,13322280247,632000"

        assertEquals(expected, row)
        assertEquals(18, row.split(",").size)
    }

    @Test
    fun goldenTest_unavailableMetricsConvertedToNA() {
        val sdf = SimpleDateFormat(CsvBuilder.TIMESTAMP_PATTERN, Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val fixedDate = sdf.parse("30-09-26 22:51:39")!!

        // Unavailable metrics passed as Android framework sentinel values:
        // Int.MAX_VALUE = 2147483647
        // Int.MIN_VALUE = -2147483648
        // Long.MAX_VALUE = 9223372036854775807L
        val row = buildCsvRow(
            date = fixedDate,
            device = "SM-A156E",
            manufacturer = "Samsung",
            androidVersion = "14",
            operator = "Airtel FastLane",
            networkType = "5G NR",
            deploymentMode = "UNKNOWN",
            displayOverride = "NONE",
            isRegistered = false,
            rawSsRsrp = -97,
            rawSsRsrq = -12,
            rawSsSinr = 6,
            rawCsiRsrp = Int.MAX_VALUE,
            rawCsiRsrq = Int.MAX_VALUE,
            rawCsiSinr = Int.MIN_VALUE,
            rawPci = 336,
            rawNci = Long.MAX_VALUE,
            rawNrarfcn = 629952,
            locale = Locale.US,
            timeZone = TimeZone.getTimeZone("UTC")
        )

        val expected =
            "30-09-26 22:51:39,SM-A156E,Samsung,14,Airtel FastLane,5G NR,UNKNOWN,NONE,FALSE," +
                    "-97,-12,6,NA,NA,NA,336,NA,629952"

        assertEquals(expected, row)
        assertEquals(18, row.split(",").size)
    }

    @Test
    fun buildCsvRow_withStringArgs_preservesExactTokens() {
        val row = buildCsvRow(
            timestamp = "01-01-26 00:00:00",
            device = "Redmi 13 5G",
            manufacturer = "Xiaomi",
            androidVersion = "14",
            operator = "UNKNOWN",
            networkType = "LTE",
            deploymentMode = "NSA",
            displayOverride = "OVERRIDE_NETWORK_TYPE_NR_NSA",
            registered = "TRUE",
            ssRsrp = "-105",
            ssRsrq = "-14",
            ssSinr = "2",
            csiRsrp = "NA",
            csiRsrq = "NA",
            csiSinr = "NA",
            pci = "102",
            nci = "NA",
            nrarfcn = "630000"
        )

        val expected =
            "01-01-26 00:00:00,Redmi 13 5G,Xiaomi,14,UNKNOWN,LTE,NSA,OVERRIDE_NETWORK_TYPE_NR_NSA,TRUE," +
                    "-105,-14,2,NA,NA,NA,102,NA,630000"

        assertEquals(expected, row)
        assertEquals(18, row.split(",").size)
    }

    @Test
    fun metricValue_boundaryConversions() {
        assertEquals("NA", CsvBuilder.metricValue(Int.MAX_VALUE))
        assertEquals("NA", CsvBuilder.metricValue(Int.MIN_VALUE))
        assertEquals("-85", CsvBuilder.metricValue(-85))
        assertEquals("0", CsvBuilder.metricValue(0))
        assertEquals("100", CsvBuilder.metricValue(100))

        assertEquals("NA", CsvBuilder.metricValue(Long.MAX_VALUE))
        assertEquals("NA", CsvBuilder.metricValue(Long.MIN_VALUE))
        assertEquals("12345678901", CsvBuilder.metricValue(12345678901L))
    }

    @Test
    fun formatTimestamp_formatsCorrectPattern() {
        val sdf = SimpleDateFormat(CsvBuilder.TIMESTAMP_PATTERN, Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val date = sdf.parse("15-08-26 12:34:56")!!

        val formatted = CsvBuilder.formatTimestamp(date, Locale.US)
        // Check pattern: 2 digits - 2 digits - 2 digits space 2 digits: 2 digits: 2 digits
        val regex = Regex("^\\d{2}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}$")
        assertTrue(regex.matches(formatted))
    }
}
