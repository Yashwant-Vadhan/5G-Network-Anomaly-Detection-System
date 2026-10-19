package com.example.a5gnetworktester

import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

sealed class PairingResult {
    data class Success(
        val sessionId: String,
        val ingestToken: String,
        val wsUrl: String
    ) : PairingResult()

    object Expired : PairingResult()
    object InvalidCode : PairingResult()
    object AlreadyUsed : PairingResult()
    data class RateLimited(val message: String) : PairingResult()
    object ServerUnreachable : PairingResult()
    data class Error(val message: String) : PairingResult()

    /**
     * Distinct user-facing error message for each failure case (T19-008 acceptance criteria).
     */
    fun userFacingMessage(): String = when (this) {
        is Success -> "Pairing successful! Ready to stream telemetry."
        is Expired -> "The pairing code has expired. Please generate a new code on the dashboard."
        is InvalidCode -> "Pairing code not found. Please verify the 8-character code and try again."
        is AlreadyUsed -> "This pairing code has already been used. Please generate a new code."
        is RateLimited -> "Too many failed pairing attempts. Please wait before retrying."
        is ServerUnreachable -> "Server unreachable. Check your Wi-Fi, mobile network, or adb connection."
        is Error -> "Pairing failed: $message"
    }
}

/**
 * Client for Contract C10 phone pairing endpoint: POST /api/v1/pair (T19-008).
 */
class PairingClient(
    private val serverBaseUrl: String,
    private val clientId: String = "com.example.a5gnetworktester",
    private val connectTimeoutMs: Int = 5000,
    private val readTimeoutMs: Int = 5000
) {

    fun pair(pairingCode: String): PairingResult {
        val cleanCode = pairingCode.trim().uppercase()
        if (cleanCode.length != 8) {
            return PairingResult.InvalidCode
        }

        val endpoint = "${serverBaseUrl.trimEnd('/')}/api/v1/pair"
        var connection: HttpURLConnection? = null

        return try {
            val url = URL(endpoint)
            connection = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                doOutput = true
                connectTimeout = connectTimeoutMs
                readTimeout = readTimeoutMs
                setRequestProperty("Content-Type", "application/json")
                setRequestProperty("Accept", "application/json")
            }

            val requestBody = "{\"pairing_code\":\"$cleanCode\",\"client_id\":\"$clientId\"}"

            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { writer ->
                writer.write(requestBody)
                writer.flush()
            }

            val statusCode = connection.responseCode
            when (statusCode) {
                200 -> {
                    val responseStr = connection.inputStream.bufferedReader().use(BufferedReader::readText)
                    val sessionId = extractJsonField(responseStr, "session_id") ?: ""
                    val ingestToken = extractJsonField(responseStr, "ingest_token") ?: ""
                    val wsUrl = extractJsonField(responseStr, "ws_url") ?: "/api/v1/ingest"
                    PairingResult.Success(sessionId, ingestToken, wsUrl)
                }
                400 -> PairingResult.Expired
                404 -> PairingResult.InvalidCode
                409 -> PairingResult.AlreadyUsed
                429 -> {
                    val errorDetail = extractErrorDetail(connection)
                    PairingResult.RateLimited(errorDetail)
                }
                else -> {
                    val errorDetail = extractErrorDetail(connection)
                    PairingResult.Error("HTTP $statusCode: $errorDetail")
                }
            }
        } catch (_: java.io.IOException) {
            PairingResult.ServerUnreachable
        } catch (e: Exception) {
            PairingResult.Error(e.message ?: "Unknown error")
        } finally {
            connection?.disconnect()
        }
    }

    private fun extractJsonField(json: String, field: String): String? {
        val regex = Regex("\"$field\"\\s*:\\s*\"([^\"]*)\"")
        return regex.find(json)?.groupValues?.get(1)
    }

    private fun extractErrorDetail(connection: HttpURLConnection): String {
        return try {
            val stream = connection.errorStream ?: connection.inputStream
            val text = stream.bufferedReader().use(BufferedReader::readText)
            extractJsonField(text, "detail") ?: text
        } catch (_: Exception) {
            "Request failed with status ${connection.responseCode}"
        }
    }
}
