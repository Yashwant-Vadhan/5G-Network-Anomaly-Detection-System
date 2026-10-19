package com.example.a5gnetworktester

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for UiState and TelemetryReading (T19-003).
 */
class UiStateTest {

    @Test
    fun telemetryReading_formatDisplay_producesExpectedMultiLineReport() {
        val reading = TelemetryReading(
            timestamp = "01-10-26 18:26:32",
            device = "SM-A156E",
            manufacturer = "samsung",
            androidVersion = "16",
            operator = "airtel",
            networkType = "LTE",
            deploymentMode = "NSA",
            displayOverride = "NR_NSA",
            registered = "false",
            ssRsrp = "-97.0",
            ssRsrq = "-12.0",
            ssSinr = "3.0",
            csiRsrp = "NA",
            csiRsrq = "NA",
            csiSinr = "NA",
            pci = "861",
            nci = "0",
            nrarfcn = "629952",
            samplesStored = 42
        )

        val display = reading.formatDisplay()
        assertTrue(display.startsWith("CURRENT READING\n============================\n\n"))
        assertTrue(display.contains("Timestamp       : 01-10-26 18:26:32\n"))
        assertTrue(display.contains("Device          : SM-A156E\n"))
        assertTrue(display.contains("Manufacturer    : samsung\n"))
        assertTrue(display.contains("Android         : 16\n"))
        assertTrue(display.contains("Operator        : airtel\n\n"))
        assertTrue(display.contains("Network Type    : LTE\n"))
        assertTrue(display.contains("Deployment Mode : NSA\n"))
        assertTrue(display.contains("Display Override: NR_NSA\n"))
        assertTrue(display.contains("Registered      : false\n\n"))
        assertTrue(display.contains("SS-RSRP         : -97.0 dBm\n"))
        assertTrue(display.contains("SS-RSRQ         : -12.0 dB\n"))
        assertTrue(display.contains("SS-SINR         : 3.0 dB\n\n"))
        assertTrue(display.contains("CSI-RSRP        : NA\n"))
        assertTrue(display.contains("CSI-RSRQ        : NA\n"))
        assertTrue(display.contains("CSI-SINR        : NA\n\n"))
        assertTrue(display.contains("PCI             : 861\n"))
        assertTrue(display.contains("NCI             : 0\n"))
        assertTrue(display.contains("NRARFCN         : 629952\n\n"))
        assertTrue(display.contains("Samples Stored  : 42\n\n"))
        assertTrue(display.endsWith("Screen shows CURRENT sample."))
    }

    @Test
    fun uiState_displayOutput_prefersLatestReadingOverStatusMessage() {
        val reading = TelemetryReading(
            timestamp = "01-10-26 18:26:32",
            device = "Redmi 13 5G",
            manufacturer = "Xiaomi",
            androidVersion = "14",
            operator = "Airtel",
            networkType = "NR",
            deploymentMode = "SA",
            displayOverride = "NONE",
            registered = "true",
            ssRsrp = "-85.0",
            ssRsrq = "-8.0",
            ssSinr = "20.0",
            csiRsrp = "-86.0",
            csiRsrq = "-9.0",
            csiSinr = "19.0",
            pci = "120",
            nci = "5000",
            nrarfcn = "630000",
            samplesStored = 1
        )

        val stateWithReading = UiState(
            isCollecting = true,
            sampleCount = 1,
            deploymentMode = "SA",
            latestReading = reading,
            statusMessage = "Waiting for measurement..."
        )

        assertEquals(reading.formatDisplay(), stateWithReading.displayOutput)

        val stateWithMessageOnly = UiState(
            isCollecting = false,
            sampleCount = 0,
            latestReading = null,
            statusMessage = "Waiting for measurement..."
        )

        assertEquals("Waiting for measurement...", stateWithMessageOnly.displayOutput)

        val stateEmpty = UiState()
        assertEquals("", stateEmpty.displayOutput)
    }
}
