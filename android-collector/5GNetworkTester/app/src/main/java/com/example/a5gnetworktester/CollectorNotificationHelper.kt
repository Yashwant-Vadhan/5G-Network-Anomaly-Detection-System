package com.example.a5gnetworktester

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
import androidx.core.app.NotificationCompat

/**
 * Helper to build and manage ongoing notifications for CollectorForegroundService (T19-009).
 *
 * Implements:
 * 1. Low-importance notification channel for silent background persistence.
 * 2. Notification content stating what is running (sample count, deployment mode, streaming state).
 * 3. Quick-action Stop button and tap-to-open intent to MainActivity.
 */
object CollectorNotificationHelper {

    const val CHANNEL_ID = "nads_collector_service_channel"
    const val CHANNEL_NAME = "5G Telemetry Collection"
    const val CHANNEL_DESC = "Ongoing collection of 5G cellular telemetry"
    const val NOTIFICATION_ID = 2001

    /**
     * Pure function returning (title, contentText) describing what is running.
     * Easily verifiable in pure JVM unit tests without Android Context.
     */
    fun buildNotificationContent(
        sampleCount: Int,
        deploymentMode: String,
        isStreaming: Boolean
    ): Pair<String, String> {
        val title = "NADS Collector Running"
        val streamTag = if (isStreaming) " • Streaming" else ""
        val normalizedMode = if (deploymentMode.isBlank()) "UNKNOWN" else deploymentMode
        val content = if (sampleCount <= 0) {
            "Waiting for measurement • $normalizedMode$streamTag"
        } else {
            "Collecting 5G telemetry • $sampleCount samples • $normalizedMode$streamTag"
        }
        return Pair(title, content)
    }

    /**
     * Creates the notification channel on Android O (API 26) and above.
     */
    fun createNotificationChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
            if (manager != null && manager.getNotificationChannel(CHANNEL_ID) == null) {
                val channel = NotificationChannel(
                    CHANNEL_ID,
                    CHANNEL_NAME,
                    NotificationManager.IMPORTANCE_LOW
                ).apply {
                    description = CHANNEL_DESC
                    setShowBadge(false)
                }
                manager.createNotificationChannel(channel)
            }
        }
    }

    /**
     * Builds an ongoing NotificationCompat instance reflecting current collection state.
     */
    fun buildNotification(
        context: Context,
        sampleCount: Int,
        deploymentMode: String,
        isStreaming: Boolean
    ): Notification {
        createNotificationChannel(context)

        val (title, contentText) = buildNotificationContent(sampleCount, deploymentMode, isStreaming)

        // Tapping opens MainActivity
        val openIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openPendingIntent = PendingIntent.getActivity(
            context,
            0,
            openIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        // Stop button directly terminates the foreground service
        val stopIntent = Intent(context, CollectorForegroundService::class.java).apply {
            action = CollectorForegroundService.ACTION_STOP
        }
        val stopPendingIntent = PendingIntent.getService(
            context,
            1,
            stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(context, CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(contentText)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setContentIntent(openPendingIntent)
            .addAction(
                android.R.drawable.ic_media_pause,
                context.getString(R.string.notification_action_stop),
                stopPendingIntent
            )
            .build()
    }
}
