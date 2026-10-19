package com.example.a5gnetworktester.streaming

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import com.example.a5gnetworktester.MainActivity

interface NotificationPoster {
    fun postNotification(id: Int, title: String, text: String, pendingIntent: Any?): Boolean
    fun hasPermission(): Boolean
}

/**
 * Handles incoming Contract C7 alert messages by posting standard Android notifications (T12-019).
 *
 * Implements:
 * 1. Notification text matching C9 title and body.
 * 2. Normal importance channel (NotificationManager.IMPORTANCE_DEFAULT) with no custom sounds.
 * 3. Graceful handling of notification permission denial.
 * 4. Deduplication of alerts so duplicate alert_ids notify only once.
 * 5. Tapping opens the main status screen.
 */
class AlertNotificationManager(
    private val context: Context? = null,
    private val poster: NotificationPoster? = null
) {
    companion object {
        const val CHANNEL_ID = "5g_nads_alerts"
        const val CHANNEL_NAME = "5G Anomaly Alerts"
        const val CHANNEL_DESCRIPTION = "Live anomaly notifications from 5G-NADS diagnostic engine"
    }

    private val seenAlertIds = mutableSetOf<String>()
    private var nextNotificationId = 1000

    init {
        createNotificationChannel()
    }

    private fun createNotificationChannel() {
        if (context != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_DEFAULT // Normal importance per T12-019
            ).apply {
                description = CHANNEL_DESCRIPTION
            }
            val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
            notificationManager?.createNotificationChannel(channel)
        }
    }

    /**
     * Handles an incoming Contract C7 alert message.
     * Deduplicates by alert_id and posts a local notification if permissions allow.
     * Returns true if a notification was posted, false otherwise.
     */
    @Synchronized
    fun onAlert(alert: C7Alert): Boolean {
        // Acceptance criterion: Duplicate alert ids notify once
        if (seenAlertIds.contains(alert.alert_id)) {
            return false
        }
        seenAlertIds.add(alert.alert_id)

        // Acceptance criterion: Notification text equals C9 title/body
        val title = alert.title
        val body = alert.detail ?: alert.title

        // If a test or mock poster is provided
        if (poster != null) {
            if (!poster.hasPermission()) {
                // Acceptance criterion: Permission denial handled gracefully
                return false
            }
            return poster.postNotification(nextNotificationId++, title, body, null)
        }

        if (context == null) {
            return false
        }

        // Acceptance criterion: Permission denial handled gracefully
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val granted = ContextCompat.checkSelfPermission(
                context,
                android.Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
            if (!granted) {
                return false
            }
        }

        return try {
            val intent = Intent(context, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
            val pendingIntent = PendingIntent.getActivity(
                context,
                0,
                intent,
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT
            )

            val notification = NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.stat_notify_error)
                .setContentTitle(title)
                .setContentText(body)
                .setPriority(NotificationCompat.PRIORITY_DEFAULT)
                .setContentIntent(pendingIntent)
                .setAutoCancel(true)
                .build()

            val notificationManager = context.getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
            notificationManager?.notify(nextNotificationId++, notification)
            true
        } catch (t: Throwable) {
            // Permission denial or security exception handled gracefully without crashing
            false
        }
    }

    @Synchronized
    fun isAlertSeen(alertId: String): Boolean = seenAlertIds.contains(alertId)

    @Synchronized
    fun clearSeen() {
        seenAlertIds.clear()
    }
}
