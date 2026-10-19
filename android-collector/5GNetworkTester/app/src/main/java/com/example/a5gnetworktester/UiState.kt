package com.example.a5gnetworktester

/**
 * Representation of the latest cellular telemetry sample formatted for UI display (T19-003).
 */
data class TelemetryReading(
    val timestamp: String,
    val device: String,
    val manufacturer: String,
    val androidVersion: String,
    val operator: String,
    val networkType: String,
    val deploymentMode: String,
    val displayOverride: String,
    val registered: String,
    val ssRsrp: String,
    val ssRsrq: String,
    val ssSinr: String,
    val csiRsrp: String,
    val csiRsrq: String,
    val csiSinr: String,
    val pci: String,
    val nci: String,
    val nrarfcn: String,
    val samplesStored: Int
) {
    /**
     * Formats the reading matching the established UI output format.
     */
    fun formatDisplay(): String {
        return "CURRENT READING\n" +
                "============================\n\n" +
                "Timestamp       : $timestamp\n" +
                "Device          : $device\n" +
                "Manufacturer    : $manufacturer\n" +
                "Android         : $androidVersion\n" +
                "Operator        : $operator\n\n" +
                "Network Type    : $networkType\n" +
                "Deployment Mode : $deploymentMode\n" +
                "Display Override: $displayOverride\n" +
                "Registered      : $registered\n\n" +
                "SS-RSRP         : $ssRsrp dBm\n" +
                "SS-RSRQ         : $ssRsrq dB\n" +
                "SS-SINR         : $ssSinr dB\n\n" +
                "CSI-RSRP        : $csiRsrp\n" +
                "CSI-RSRQ        : $csiRsrq\n" +
                "CSI-SINR        : $csiSinr\n\n" +
                "PCI             : $pci\n" +
                "NCI             : $nci\n" +
                "NRARFCN         : $nrarfcn\n\n" +
                "============================\n" +
                "Samples Stored  : $samplesStored\n\n" +
                "CSV stores ALL samples.\n" +
                "Screen shows CURRENT sample."
    }
}

/**
 * Unidirectional UI state decoupling background measurement collection from view rendering (T19-003).
 */
data class UiState(
    val isCollecting: Boolean = false,
    val sampleCount: Int = 0,
    val deploymentMode: String = "NOT_RESTRICTED",
    val latestReading: TelemetryReading? = null,
    val statusMessage: String? = null
) {
    val displayOutput: String
        get() = latestReading?.formatDisplay() ?: statusMessage ?: ""
}
