package com.example.a5gnetworktester

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for ConsentManager and G28 privacy guardrails (T19-007).
 */
class ConsentManagerTest {

    @Test
    fun isConsentValid_returnsTrueWhenAcceptedAndVersionMatches() {
        val valid = ConsentManager.isConsentValid(
            accepted = true,
            storedVersion = "2.0.0",
            currentVersion = "2.0.0"
        )
        assertTrue("Consent should be valid when accepted with matching version", valid)
    }

    @Test
    fun isConsentValid_returnsFalseWhenDeclined() {
        val valid = ConsentManager.isConsentValid(
            accepted = false,
            storedVersion = "2.0.0",
            currentVersion = "2.0.0"
        )
        assertFalse("Consent must be false when declined", valid)
    }

    @Test
    fun isConsentValid_versionBumpRePrompts_returnsFalse() {
        // Acceptance criteria: version bump re-prompts
        val valid = ConsentManager.isConsentValid(
            accepted = true,
            storedVersion = "1.0.0", // Stale version
            currentVersion = "2.0.0"
        )
        assertFalse("Stale consent version must require re-consent", valid)
    }

    @Test
    fun isConsentValid_returnsFalseWhenVersionNull() {
        val valid = ConsentManager.isConsentValid(
            accepted = true,
            storedVersion = null,
            currentVersion = "2.0.0"
        )
        assertFalse("Null version must be invalid", valid)
    }

    @Test
    fun consentText_containsMandatedPrivacySections() {
        // Acceptance criteria: text matches docs/privacy.md / docs/consent_text.txt
        val text = ConsentManager.CONSENT_TEXT

        assertTrue(text.contains("5G-NADS Privacy Notice & Telemetry Consent"))
        assertTrue(text.contains("Version: 2.0.0"))
        assertTrue(text.contains("1. What Telemetry Is Collected:"))
        assertTrue(text.contains("Contract C1/C7"))
        assertTrue(text.contains("2. What Is NOT Collected:"))
        assertTrue(text.contains("NO GPS or GNSS precise latitude/longitude coordinates"))
        assertTrue(text.contains("NO phone number (MSISDN) or subscriber SIM identifiers"))
        assertTrue(text.contains("3. Approximate Location Disclosure:"))
        assertTrue(text.contains("4. Retention Policy:"))
        assertTrue(text.contains("Live sessions are EPHEMERAL"))
        assertTrue(text.contains("Guardrail G29"))
        assertTrue(text.contains("5. Platform Logs:"))
        assertTrue(text.contains("6. Ending Streaming:"))
    }
}
