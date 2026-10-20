package com.example.a5gnetworktester

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import android.view.WindowManager

/**
 * Handles OEM battery restrictions (MIUI / HyperOS, Samsung OneUI) and screen-on fallback (T19-009).
 *
 * Implements:
 * 1. Checks if the app is exempt from aggressive battery optimization.
 * 2. Provides intents to request battery exemption or navigate to device power settings.
 * 3. Provides screen-on fallback flag toggling on the main Window for aggressive OEM devices.
 */
object BatteryOptimizationHelper {

    /**
     * Checks if battery optimizations are ignored for this application.
     */
    fun isIgnoringBatteryOptimizations(context: Context): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val powerManager = context.getSystemService(Context.POWER_SERVICE) as? PowerManager
            return powerManager?.isIgnoringBatteryOptimizations(context.packageName) ?: true
        }
        return true
    }

    /**
     * Creates an intent to request the system ignore battery optimizations for this app.
     */
    @SuppressLint("BatteryLife")
    fun createRequestIgnoreBatteryOptimizationIntent(context: Context): Intent {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                data = Uri.parse("package:${context.packageName}")
            }
        } else {
            Intent(Settings.ACTION_SETTINGS)
        }
    }

    /**
     * Sets or clears FLAG_KEEP_SCREEN_ON as a fallback for devices with aggressive background killers.
     */
    fun setScreenOnFallback(activity: Activity, keepOn: Boolean) {
        if (keepOn) {
            activity.window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            activity.window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }
}
