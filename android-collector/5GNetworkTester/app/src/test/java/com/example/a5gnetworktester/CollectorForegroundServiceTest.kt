package com.example.a5gnetworktester

import android.content.pm.ServiceInfo
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Unit tests for CollectorForegroundService, Notification, and Android 15+ Timeout rules (T19-009).
 *
 * Verifies:
 * 1. Notification content explicitly states what is running (sample count, deployment mode, streaming).
 * 2. Service cleanly handles Android 15+ timeout callback (Service.onTimeout / handleTimeout), stops collection,
 *    flushes data, and halts the service without leaks.
 * 3. AndroidManifest declares FOREGROUND_SERVICE, FOREGROUND_SERVICE_DATA_SYNC, WAKE_LOCK permissions,
 *    and registers CollectorForegroundService with foregroundServiceType="dataSync".
 */
class CollectorForegroundServiceTest {

    private fun findRepoRoot(): File {
        var dir: File? = File(".").canonicalFile
        while (dir != null && !File(dir, "android-collector").exists()) {
            dir = dir.parentFile
        }
        return dir ?: error("Could not locate repository root with android-collector/")
    }

    @Test
    fun notificationContent_statesWhatIsRunning_initialState() {
        // Acceptance criterion: Notification states what is running (initial state)
        val (title, content) = CollectorNotificationHelper.buildNotificationContent(
            sampleCount = 0,
            deploymentMode = "UNKNOWN",
            isStreaming = false
        )

        assertEquals("NADS Collector Running", title)
        assertTrue("Notification must state waiting state", content.contains("Waiting for measurement"))
        assertTrue("Notification must show deployment mode", content.contains("UNKNOWN"))
        assertFalse("Notification must not show streaming if inactive", content.contains("Streaming"))
    }

    @Test
    fun notificationContent_statesWhatIsRunning_activeCollectionAndStreaming() {
        // Acceptance criterion: Notification states what is running (active collection + streaming)
        val (title, content) = CollectorNotificationHelper.buildNotificationContent(
            sampleCount = 42,
            deploymentMode = "5G NSA",
            isStreaming = true
        )

        assertEquals("NADS Collector Running", title)
        assertTrue("Notification must state sample count", content.contains("42 samples"))
        assertTrue("Notification must state deployment mode", content.contains("5G NSA"))
        assertTrue("Notification must indicate streaming", content.contains("Streaming"))
    }

    @Test
    fun serviceManifest_declaresForegroundServiceTypeDataSyncAndPermissions() {
        val root = findRepoRoot()
        val manifestFile = File(root, "android-collector/5GNetworkTester/app/src/main/AndroidManifest.xml")
        assertTrue("Manifest must exist", manifestFile.exists())
        val manifestXml = manifestFile.readText()

        // Verify Android 14/15 foreground service permissions
        assertTrue(
            "Manifest must declare FOREGROUND_SERVICE permission",
            manifestXml.contains("android.permission.FOREGROUND_SERVICE\"")
        )
        assertTrue(
            "Manifest must declare FOREGROUND_SERVICE_DATA_SYNC permission",
            manifestXml.contains("android.permission.FOREGROUND_SERVICE_DATA_SYNC\"")
        )
        assertTrue(
            "Manifest must declare WAKE_LOCK for screen-off execution",
            manifestXml.contains("android.permission.WAKE_LOCK\"")
        )

        // Verify service declaration with foregroundServiceType="dataSync"
        assertTrue(
            "Manifest must declare CollectorForegroundService",
            manifestXml.contains("android:name=\".CollectorForegroundService\"")
        )
        assertTrue(
            "Manifest must declare foregroundServiceType=\"dataSync\"",
            manifestXml.contains("android:foregroundServiceType=\"dataSync\"")
        )
    }

    @Test
    fun service_handlesAndroid15TimeoutCallbackCleanly() {
        var stopSelfCalledWithStartId: Int? = null

        val service = CollectorForegroundService().apply {
            onStopSelfAction = { startId ->
                stopSelfCalledWithStartId = startId
            }
        }

        // Set initial running state
        CollectorForegroundService.updateUiState(
            UiState(isCollecting = true, sampleCount = 10, deploymentMode = "NSA")
        )
        assertTrue(CollectorForegroundService.isCollectingFlow.value)

        // Acceptance criterion: Service handles Android 15+ timeout callback cleanly
        val testStartId = 42
        val testFgsType = ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
        service.handleTimeout(testStartId, testFgsType)

        // 1. isCollecting must become false
        assertFalse("Collection must stop on timeout", CollectorForegroundService.isCollectingFlow.value)

        // 2. Status message must communicate timeout
        val finalState = CollectorForegroundService.uiStateFlow.value
        assertNotNull("Status message must be present", finalState.statusMessage)
        assertTrue("Status message must mention timeout", finalState.statusMessage?.contains("timeout") == true)

        // 3. stopSelf must have been called cleanly with startId
        assertEquals(Integer.valueOf(testStartId), stopSelfCalledWithStartId)
    }
}
