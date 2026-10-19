package com.example.a5gnetworktester

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Pure row and metric building helpers for Contract C1 CSV export (T19-002, Guardrail G32).
 */
object CsvBuilder {

    /**
     * Exact 18-column header mandated by Contract C1.
     */
    const val CSV_HEADER =
        "timestamp,device,manufacturer,android,operator," +
                "network_type,deployment_mode,display_override," +
                "registered,ss_rsrp,ss_rsrq,ss_sinr," +
                "csi_rsrp,csi_rsrq,csi_sinr," +
                "pci,nci,nrarfcn"

    const val TIMESTAMP_PATTERN = "dd-MM-yy HH:mm:ss"

    /**
     * Format a Date into Contract C1 timestamp string: dd-MM-yy HH:mm:ss.
     */
    fun formatTimestamp(
        date: Date,
        locale: Locale = Locale.US,
        timeZone: TimeZone? = null
    ): String {
        return SimpleDateFormat(TIMESTAMP_PATTERN, locale).apply {
            if (timeZone != null) {
                this.timeZone = timeZone
            }
        }.format(date)
    }

    /**
     * Converts unavailable integer measurements (Int.MAX_VALUE or Int.MIN_VALUE) to "NA".
     */
    fun metricValue(value: Int): String {
        return if (value == Int.MAX_VALUE || value == Int.MIN_VALUE) {
            "NA"
        } else {
            value.toString()
        }
    }

    /**
     * Converts unavailable long measurements (Long.MAX_VALUE or Long.MIN_VALUE) to "NA".
     */
    fun metricValue(value: Long): String {
        return if (value == Long.MAX_VALUE || value == Long.MIN_VALUE) {
            "NA"
        } else {
            value.toString()
        }
    }

    /**
     * Pure function to assemble 18 pre-formatted string columns into a single CSV row.
     */
    fun buildCsvRow(
        timestamp: String,
        device: String,
        manufacturer: String,
        androidVersion: String,
        operator: String,
        networkType: String,
        deploymentMode: String,
        displayOverride: String,
        registered: String,
        ssRsrp: String,
        ssRsrq: String,
        ssSinr: String,
        csiRsrp: String,
        csiRsrq: String,
        csiSinr: String,
        pci: String,
        nci: String,
        nrarfcn: String
    ): String {
        return listOf(
            timestamp,
            device,
            manufacturer,
            androidVersion,
            operator,
            networkType,
            deploymentMode,
            displayOverride,
            registered,
            ssRsrp,
            ssRsrq,
            ssSinr,
            csiRsrp,
            csiRsrq,
            csiSinr,
            pci,
            nci,
            nrarfcn
        ).joinToString(",")
    }

    /**
     * Pure function to build a CSV row from raw telemetry readings,
     * handling timestamp formatting, NA conversion for unavailable metrics,
     * and uppercase boolean representation.
     */
    fun buildCsvRow(
        date: Date,
        device: String,
        manufacturer: String,
        androidVersion: String,
        operator: String,
        networkType: String,
        deploymentMode: String,
        displayOverride: String,
        isRegistered: Boolean,
        rawSsRsrp: Int,
        rawSsRsrq: Int,
        rawSsSinr: Int,
        rawCsiRsrp: Int,
        rawCsiRsrq: Int,
        rawCsiSinr: Int,
        rawPci: Int,
        rawNci: Long,
        rawNrarfcn: Int,
        locale: Locale = Locale.US,
        timeZone: TimeZone? = null
    ): String {
        return buildCsvRow(
            timestamp = formatTimestamp(date, locale, timeZone),
            device = device,
            manufacturer = manufacturer,
            androidVersion = androidVersion,
            operator = operator,
            networkType = networkType,
            deploymentMode = deploymentMode,
            displayOverride = displayOverride,
            registered = isRegistered.toString().uppercase(),
            ssRsrp = metricValue(rawSsRsrp),
            ssRsrq = metricValue(rawSsRsrq),
            ssSinr = metricValue(rawSsSinr),
            csiRsrp = metricValue(rawCsiRsrp),
            csiRsrq = metricValue(rawCsiRsrq),
            csiSinr = metricValue(rawCsiSinr),
            pci = metricValue(rawPci),
            nci = metricValue(rawNci),
            nrarfcn = metricValue(rawNrarfcn)
        )
    }
}

/**
 * Top-level convenience delegator for buildCsvRow with pre-formatted strings.
 */
fun buildCsvRow(
    timestamp: String,
    device: String,
    manufacturer: String,
    androidVersion: String,
    operator: String,
    networkType: String,
    deploymentMode: String,
    displayOverride: String,
    registered: String,
    ssRsrp: String,
    ssRsrq: String,
    ssSinr: String,
    csiRsrp: String,
    csiRsrq: String,
    csiSinr: String,
    pci: String,
    nci: String,
    nrarfcn: String
): String = CsvBuilder.buildCsvRow(
    timestamp,
    device,
    manufacturer,
    androidVersion,
    operator,
    networkType,
    deploymentMode,
    displayOverride,
    registered,
    ssRsrp,
    ssRsrq,
    ssSinr,
    csiRsrp,
    csiRsrq,
    csiSinr,
    pci,
    nci,
    nrarfcn
)

/**
 * Top-level convenience delegator for buildCsvRow with raw measurements and Date.
 */
fun buildCsvRow(
    date: Date,
    device: String,
    manufacturer: String,
    androidVersion: String,
    operator: String,
    networkType: String,
    deploymentMode: String,
    displayOverride: String,
    isRegistered: Boolean,
    rawSsRsrp: Int,
    rawSsRsrq: Int,
    rawSsSinr: Int,
    rawCsiRsrp: Int,
    rawCsiRsrq: Int,
    rawCsiSinr: Int,
    rawPci: Int,
    rawNci: Long,
    rawNrarfcn: Int,
    locale: Locale = Locale.US,
    timeZone: TimeZone? = null
): String = CsvBuilder.buildCsvRow(
    date,
    device,
    manufacturer,
    androidVersion,
    operator,
    networkType,
    deploymentMode,
    displayOverride,
    isRegistered,
    rawSsRsrp,
    rawSsRsrq,
    rawSsSinr,
    rawCsiRsrp,
    rawCsiRsrq,
    rawCsiSinr,
    rawPci,
    rawNci,
    rawNrarfcn,
    locale,
    timeZone
)
