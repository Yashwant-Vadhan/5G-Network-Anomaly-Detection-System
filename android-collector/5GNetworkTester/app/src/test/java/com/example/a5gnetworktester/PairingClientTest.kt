package com.example.a5gnetworktester

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for PairingClient and Contract C10 error mapping (T19-008).
 */
class PairingClientTest {

    @Test
    fun eachFailureCase_showsItsOwnDistinctMessage() {
        // Acceptance criteria: Each failure case shows its own message
        val expiredMsg = PairingResult.Expired.userFacingMessage()
        val invalidMsg = PairingResult.InvalidCode.userFacingMessage()
        val alreadyUsedMsg = PairingResult.AlreadyUsed.userFacingMessage()
        val rateLimitedMsg = PairingResult.RateLimited("Lockout active").userFacingMessage()
        val unreachableMsg = PairingResult.ServerUnreachable.userFacingMessage()
        val genericErrorMsg = PairingResult.Error("Bad request").userFacingMessage()

        val messages = listOf(
            expiredMsg,
            invalidMsg,
            alreadyUsedMsg,
            rateLimitedMsg,
            unreachableMsg,
            genericErrorMsg
        )

        // All messages must be distinct and non-empty
        val uniqueMessages = messages.toSet()
        assertEquals(
            "Every failure case must have a distinct user-facing message",
            messages.size,
            uniqueMessages.size
        )

        assertTrue(expiredMsg.contains("expired", ignoreCase = true))
        assertTrue(invalidMsg.contains("not found", ignoreCase = true) || invalidMsg.contains("code", ignoreCase = true))
        assertTrue(alreadyUsedMsg.contains("already been used", ignoreCase = true))
        assertTrue(rateLimitedMsg.contains("Too many failed", ignoreCase = true))
        assertTrue(unreachableMsg.contains("unreachable", ignoreCase = true))
    }

    @Test
    fun tokenNeverLogged_tokenNotPresentInUserFacingMessagesOrErrors() {
        // Acceptance criteria: Token never logged
        val secretToken = "secret_ingest_token_xyz_12345_never_log_this"
        val success = PairingResult.Success(
            sessionId = "sess-1234",
            ingestToken = secretToken,
            wsUrl = "/api/v1/ingest"
        )

        val userMsg = success.userFacingMessage()
        assertFalse("Ingest token must NEVER appear in user facing messages", userMsg.contains(secretToken))

        // Check error messages
        val errors = listOf(
            PairingResult.Expired.userFacingMessage(),
            PairingResult.InvalidCode.userFacingMessage(),
            PairingResult.AlreadyUsed.userFacingMessage(),
            PairingResult.RateLimited("Locked").userFacingMessage(),
            PairingResult.ServerUnreachable.userFacingMessage()
        )

        for (err in errors) {
            assertFalse(err.contains(secretToken))
        }
    }

    @Test
    fun invalidCode_shortLength_returnsInvalidCodeDirectly() {
        val client = PairingClient("http://127.0.0.1:8000")
        val result = client.pair("SHORT")
        assertEquals(PairingResult.InvalidCode, result)
    }

    @Test
    fun unreachableServer_returnsServerUnreachable() {
        // Connect to a closed port on loopback
        val client = PairingClient(
            serverBaseUrl = "http://127.0.0.1:59999",
            connectTimeoutMs = 500,
            readTimeoutMs = 500
        )
        val result = client.pair("ABCDEF12")
        assertEquals(PairingResult.ServerUnreachable, result)
    }
}
