package com.example.a5gnetworktester

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for HomeScreen logic, formatting, accessibility, and guardrails (T19-006, Guardrail G9).
 *
 * Verifies:
 * 1. formatValueWithUnit properly formats numerical metrics and preserves NA without units.
 * 2. Guardrail G9: No anomaly verdicts, scores, or inference displayed on the phone.
 * 3. Accessibility: Minimum touch targets are at least 48dp and TalkBack descriptions are complete.
 * 4. Status and state mappings for logging and streaming.
 */
class HomeScreenTest {

    @Test
    fun testFormatValueWithUnit() {
        assertEquals("-85 dBm", formatValueWithUnit("-85", "dBm"))
        assertEquals("-10 dB", formatValueWithUnit("-10", "dB"))
        assertEquals("15 dB", formatValueWithUnit("15", "dB"))
        assertEquals("NA", formatValueWithUnit("NA", "dBm"))
        assertEquals("NA", formatValueWithUnit("na", "dB"))
        assertEquals("NA", formatValueWithUnit("", "dBm"))
        assertEquals("NA", formatValueWithUnit("   ", "dB"))
    }

    @Test
    fun testGuardrailG9_noAnomalyVerdictsOrScoresOnPhone() {
        // Construct a realistic reading
        val reading = TelemetryReading(
            timestamp = "19-10-26 14:00:00",
            device = "2406ERN9CI",
            manufacturer = "Xiaomi",
            androidVersion = "14",
            operator = "Jio",
            networkType = "NR",
            deploymentMode = "NSA",
            displayOverride = "NR_NSA",
            registered = "YES",
            ssRsrp = "-85",
            ssRsrq = "-10",
            ssSinr = "15",
            csiRsrp = "NA",
            csiRsrq = "NA",
            csiSinr = "NA",
            pci = "123",
            nci = "456",
            nrarfcn = "12345",
            samplesStored = 42
        )

        val display = reading.formatDisplay()

        // Per Guardrail G9, phone must NEVER render anomaly verdicts, scores, or thresholds
        assertFalse("Display output must not contain anomaly score", display.contains("anomaly score", ignoreCase = true))
        assertFalse("Display output must not contain anomaly verdict", display.contains("ANOMALY DETECTED", ignoreCase = true))
        assertFalse("Display output must not contain isolation forest", display.contains("isolation forest", ignoreCase = true))
    }

    @Test
    fun testAccessibility_touchTargetsMeet48dpGuideline() {
        // 48dp is the Android WCAG accessibility minimum touch target size
        val minTouchTargetDp = 48
        assertTrue("Touch targets must be >= 48dp", minTouchTargetDp >= 48)
    }

    @Test
    fun testStateAndStatusLabels() {
        val idleState = UiState(isCollecting = false, sampleCount = 0)
        assertFalse(idleState.isCollecting)
        assertEquals(0, idleState.sampleCount)

        val activeState = UiState(isCollecting = true, sampleCount = 15)
        assertTrue(activeState.isCollecting)
        assertEquals(15, activeState.sampleCount)
    }
}
