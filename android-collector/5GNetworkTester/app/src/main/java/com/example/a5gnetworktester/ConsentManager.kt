package com.example.a5gnetworktester

import android.content.Context

/**
 * Manages user telemetry consent, persistence, and versioning (T19-007, Guardrail G28).
 */
object ConsentManager {

    const val CURRENT_CONSENT_VERSION = "2.0.0"
    const val PREFS_NAME = "5g_nads_consent_prefs"
    const val KEY_CONSENT_ACCEPTED = "consent_accepted"
    const val KEY_CONSENT_VERSION = "consent_version"

    val CONSENT_TEXT = """
5G-NADS Privacy Notice & Telemetry Consent
Version: 2.0.0
Reviewed and Approved by Authors: Yashwant Vadhan & Sushil Kumar

1. What Telemetry Is Collected:
When you pair your device and start streaming, the 5G-NADS mobile collector transmits the following 18 radio and device metrics (Contract C1/C7) to the server:
- Timestamp: Collection time formatted as dd-MM-yy HH:mm:ss (timestamp)
- Device Information: Device model (device), hardware manufacturer (manufacturer), and Android OS version (android)
- Network Information: Operator name (operator), radio access technology (network_type), 5G deployment mode (deployment_mode: SA or NSA), 5G display override (display_override), and cellular registration status (registered)
- Radio Signal Metrics: SS-RSRP (ss_rsrp), SS-RSRQ (ss_rsrq), SS-SINR (ss_sinr), CSI-RSRP (csi_rsrp), CSI-RSRQ (csi_rsrq), CSI-SINR (csi_sinr)
- Cell Identifiers: Physical Cell ID (pci), NR Cell Identity (nci), and NR-ARFCN (nrarfcn)

2. What Is NOT Collected:
- NO GPS or GNSS precise latitude/longitude coordinates
- NO phone number (MSISDN) or subscriber SIM identifiers (IMSI, ICCID)
- NO device hardware serial numbers or IMEI
- NO user accounts, names, email addresses, contacts, call logs, SMS, or app traffic
- NO persistent cross-session tracking identifiers

3. Approximate Location Disclosure:
Cellular base stations broadcast fixed identifiers (pci, nci). While we do NOT collect GPS coordinates, cellular tower IDs correspond to physical locations. Anyone with access to cell tower databases could estimate the approximate area (typically within 500m - 2km) where the telemetry was recorded.

4. Retention Policy:
Live sessions are EPHEMERAL. All telemetry is stored purely in volatile server memory and is purged immediately upon session teardown, disconnect, or after 15 minutes of inactivity. Nothing is persisted to disk on public servers (Guardrail G29).
You may download your raw session data as a CSV in your browser before ending the session.

5. Platform Logs:
The 5G-NADS application strictly redacts cell IDs, pairing codes, and tokens from application logs. However, platform-level network ingress logs (e.g. reverse proxy, hosting provider) record client IP addresses and connection timestamps outside of our application control.

6. Ending Streaming:
You can stop streaming at any time by tapping 'Stop Streaming' in the mobile app, clicking 'End Session' in the browser dashboard, or closing the connection.
""".trimIndent()

    /**
     * Pure function to determine whether consent is valid given stored state.
     * Guardrail G28: streaming cannot start until accepted, and version bumps require re-consent.
     */
    fun isConsentValid(
        accepted: Boolean,
        storedVersion: String?,
        currentVersion: String = CURRENT_CONSENT_VERSION
    ): Boolean {
        return accepted && storedVersion == currentVersion
    }

    /**
     * Checks if current valid consent exists in SharedPreferences.
     */
    fun hasConsent(context: Context): Boolean {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val accepted = prefs.getBoolean(KEY_CONSENT_ACCEPTED, false)
        val version = prefs.getString(KEY_CONSENT_VERSION, null)
        return isConsentValid(accepted, version)
    }

    /**
     * Persists consent acceptance and version to SharedPreferences.
     */
    fun setConsent(
        context: Context,
        accepted: Boolean,
        version: String = CURRENT_CONSENT_VERSION
    ) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit()
            .putBoolean(KEY_CONSENT_ACCEPTED, accepted)
            .putString(KEY_CONSENT_VERSION, if (accepted) version else null)
            .apply()
    }

    /**
     * Guardrail G28 check: Ensures NO network streaming call can proceed without valid consent.
     * Throws SecurityException if consent is missing or version is stale.
     */
    fun assertCanStartStreaming(context: Context) {
        if (!hasConsent(context)) {
            throw SecurityException("Consent not granted or version bump requires re-consent (Guardrail G28)")
        }
    }
}
