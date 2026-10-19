package com.example.a5gnetworktester

import com.example.a5gnetworktester.streaming.AlertNotificationManager
import com.example.a5gnetworktester.streaming.C7Alert
import com.example.a5gnetworktester.streaming.NotificationPoster
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for AlertNotificationManager (T12-019).
 *
 * Verifies:
 * 1. Notification text equals C9 title/body.
 * 2. Permission denial handled gracefully without crashing.
 * 3. Duplicate alert ids notify once.
 */
class AlertNotificationManagerTest {

    private class TestNotificationPoster(var permissionGranted: Boolean = true) : NotificationPoster {
        val posted = mutableListOf<Triple<Int, String, String>>()

        override fun postNotification(id: Int, title: String, text: String, pendingIntent: Any?): Boolean {
            posted.add(Triple(id, title, text))
            return true
        }

        override fun hasPermission(): Boolean = permissionGranted
    }

    @Test
    fun notificationText_equalsC9TitleAndBody() {
        val poster = TestNotificationPoster(permissionGranted = true)
        val manager = AlertNotificationManager(poster = poster)

        val alertWithDetail = C7Alert(
            type = "alert",
            schema_version = 2,
            alert_id = "alert-101",
            severity = "HIGH",
            title = "Severe RSRP Degradation",
            detail = "SS-RSRP dropped 24 dB to -118 dBm on PCI 861"
        )

        val handled = manager.onAlert(alertWithDetail)
        assertTrue(handled)
        assertEquals(1, poster.posted.size)

        // Acceptance criterion: Notification text equals C9 title/body
        val (_, title, text) = poster.posted.first()
        assertEquals("Severe RSRP Degradation", title)
        assertEquals("SS-RSRP dropped 24 dB to -118 dBm on PCI 861", text)

        // Test fallback when detail is null
        val alertWithoutDetail = C7Alert(
            type = "alert",
            schema_version = 2,
            alert_id = "alert-102",
            severity = "MEDIUM",
            title = "Secondary Cell Transition Anomaly",
            detail = null
        )
        val handled2 = manager.onAlert(alertWithoutDetail)
        assertTrue(handled2)
        assertEquals(2, poster.posted.size)
        val (_, title2, text2) = poster.posted[1]
        assertEquals("Secondary Cell Transition Anomaly", title2)
        assertEquals("Secondary Cell Transition Anomaly", text2)
    }

    @Test
    fun permissionDenial_handledGracefullyWithoutCrashing() {
        // Acceptance criterion: Permission denial handled gracefully
        val posterDenied = TestNotificationPoster(permissionGranted = false)
        val manager = AlertNotificationManager(poster = posterDenied)

        val alert = C7Alert(
            type = "alert",
            schema_version = 2,
            alert_id = "alert-denied-1",
            severity = "HIGH",
            title = "Radio Link Failure",
            detail = "Out of service"
        )

        // Must return false without throwing any SecurityException or crash
        val handled = manager.onAlert(alert)
        assertFalse("Notification must not be posted if permission denied", handled)
        assertTrue("Poster must have received zero notifications", posterDenied.posted.isEmpty())
    }

    @Test
    fun duplicateAlertIds_notifyOnce() {
        val poster = TestNotificationPoster(permissionGranted = true)
        val manager = AlertNotificationManager(poster = poster)

        val alertA1 = C7Alert(
            type = "alert",
            schema_version = 2,
            alert_id = "duplicate-test-id",
            severity = "HIGH",
            title = "Coverage Hole Encountered",
            detail = "SINR < -3.0 dB"
        )

        val alertA2 = C7Alert(
            type = "alert",
            schema_version = 2,
            alert_id = "duplicate-test-id",
            severity = "HIGH",
            title = "Coverage Hole Encountered",
            detail = "SINR < -3.0 dB"
        )

        val alertB = C7Alert(
            type = "alert",
            schema_version = 2,
            alert_id = "unique-test-id-2",
            severity = "INFO",
            title = "Handover Started",
            detail = "Target PCI 310"
        )

        // 1. First alert notifies
        val firstResult = manager.onAlert(alertA1)
        assertTrue(firstResult)
        assertEquals(1, poster.posted.size)

        // 2. Acceptance criterion: Duplicate alert ids notify once
        val duplicateResult = manager.onAlert(alertA2)
        assertFalse("Duplicate alert must be dropped and return false", duplicateResult)
        assertEquals("Poster count must not increase on duplicate", 1, poster.posted.size)

        // 3. Different alert id notifies
        val thirdResult = manager.onAlert(alertB)
        assertTrue(thirdResult)
        assertEquals(2, poster.posted.size)
    }
}
