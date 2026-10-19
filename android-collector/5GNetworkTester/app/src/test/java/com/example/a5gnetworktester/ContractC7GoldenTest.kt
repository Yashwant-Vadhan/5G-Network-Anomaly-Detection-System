package com.example.a5gnetworktester

import com.example.a5gnetworktester.streaming.C7IngestHello
import com.example.a5gnetworktester.streaming.C7IngestSample
import com.example.a5gnetworktester.streaming.C7Json
import com.example.a5gnetworktester.streaming.C7Ping
import com.example.a5gnetworktester.streaming.C7SamplePayload
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Android JVM unit tests for Contract C7 golden serialization (T12-008).
 *
 * Verifies:
 * 1. Tests run via Gradle without a device (pure JVM).
 * 2. Golden files directly shared with Python tests from tests/fixtures/stream/.
 * 3. Null and sentinel handling in compliance with Contract C7.
 */
class ContractC7GoldenTest {

    private fun findRepoRoot(): File {
        var dir: File? = File(".").canonicalFile
        while (dir != null && !File(dir, "tests/fixtures/stream").exists()) {
            dir = dir.parentFile
        }
        return dir ?: error("Could not locate repository root with tests/fixtures/stream/")
    }

    private fun readGoldenFixture(filename: String): String {
        val root = findRepoRoot()
        val file = File(root, "tests/fixtures/stream/$filename")
        assertTrue("Golden fixture must exist at: ${file.absolutePath}", file.exists())
        return file.readText().trim()
    }

    private fun normalizeJson(json: String): String {
        val sb = StringBuilder()
        var inQuotes = false
        var escape = false
        for (ch in json) {
            if (escape) {
                sb.append(ch)
                escape = false
            } else if (ch == '\\') {
                sb.append(ch)
                escape = true
            } else if (ch == '"') {
                inQuotes = !inQuotes
                sb.append(ch)
            } else if (inQuotes || !ch.isWhitespace()) {
                sb.append(ch)
            }
        }
        return sb.toString()
    }

    @Test
    fun goldenC7IngestSample_matchesPythonSharedFixtureByteForByte() {
        val goldenRaw = readGoldenFixture("c7_ingest_sample.example.json")
        val goldenCanonical = normalizeJson(goldenRaw)

        val payload = C7SamplePayload(
            timestamp = "01-10-26 18:26:32",
            device = "SM-A156E",
            manufacturer = "samsung",
            android = "16",
            operator = "airtel",
            network_type = "LTE",
            deployment_mode = "NSA",
            display_override = "NR_NSA",
            registered = false,
            ss_rsrp = -97.0,
            ss_rsrq = -12.0,
            ss_sinr = 3.0,
            csi_rsrp = null,
            csi_rsrq = null,
            csi_sinr = null,
            pci = 861,
            nci = 0L,
            nrarfcn = 629952
        )

        val sample = C7IngestSample(
            seq = 119L,
            sent_at = "2026-10-01T18:26:32.412+05:30",
            payload = payload,
            edge = null
        )

        val generatedCanonical = sample.toCanonicalJson()
        assertEquals(goldenCanonical, generatedCanonical)
    }

    @Test
    fun goldenC7IngestHello_matchesPythonSharedFixtureByteForByte() {
        val goldenRaw = readGoldenFixture("c7_ingest_hello.example.json")
        val goldenCanonical = normalizeJson(goldenRaw)

        val hello = C7IngestHello(
            client_id = "b1e2c3d4-test-uuid",
            app_version = "1.3.0",
            device = "Redmi 13 5G",
            manufacturer = "Xiaomi",
            android = "14",
            operator = "Airtel",
            resume_from_seq = 0L,
            dropped_from_queue = 0L,
            queue_depth = 0L,
            session_label = "walk-01",
            source = "phone",
            edge = null
        )

        val generatedCanonical = hello.toCanonicalJson()
        assertEquals(goldenCanonical, generatedCanonical)
    }

    @Test
    fun goldenC7IngestPing_matchesPythonSharedFixtureByteForByte() {
        val goldenRaw = readGoldenFixture("c7_ingest_ping.example.json")
        val goldenCanonical = normalizeJson(goldenRaw)

        val ping = C7Ping(
            dropped_from_queue = 0L,
            queue_depth = 5L
        )

        val generatedCanonical = ping.toCanonicalJson()
        assertEquals(goldenCanonical, generatedCanonical)
    }

    @Test
    fun nullAndSentinelHandling_serializesNullsExplicitly() {
        val payload = C7SamplePayload(
            timestamp = "01-10-26 18:26:32",
            device = "SM-A156E",
            manufacturer = "samsung",
            android = "16",
            operator = "airtel",
            network_type = "LTE",
            deployment_mode = "NSA",
            display_override = "NR_NSA",
            registered = true,
            ss_rsrp = -95.0,
            ss_rsrq = null,
            ss_sinr = null,
            csi_rsrp = null,
            csi_rsrq = null,
            csi_sinr = null,
            pci = null,
            nci = null,
            nrarfcn = null
        )

        val sample = C7IngestSample(
            seq = 1L,
            sent_at = "2026-10-01T18:26:32.000Z",
            payload = payload
        )

        val json = sample.toCanonicalJson()
        assertTrue("Null metrics must serialize as literal null", json.contains(""""csi_rsrp":null"""))
        assertTrue("Null metrics must serialize as literal null", json.contains(""""csi_rsrq":null"""))
        assertTrue("Null metrics must serialize as literal null", json.contains(""""csi_sinr":null"""))
        assertTrue("Null metrics must serialize as literal null", json.contains(""""pci":null"""))
        assertTrue("Null metrics must serialize as literal null", json.contains(""""nci":null"""))
        assertTrue("Null metrics must serialize as literal null", json.contains(""""nrarfcn":null"""))
    }

    @Test
    fun prohibitedIdentifiers_neverPresentInPayload() {
        val payload = C7SamplePayload(
            timestamp = "01-10-26 18:26:32",
            device = "SM-A156E",
            manufacturer = "samsung",
            android = "16",
            operator = "airtel",
            network_type = "LTE",
            deployment_mode = "NSA",
            display_override = "NR_NSA",
            registered = true,
            ss_rsrp = -95.0,
            ss_rsrq = -10.0,
            ss_sinr = 10.0,
            csi_rsrp = null,
            csi_rsrq = null,
            csi_sinr = null,
            pci = 100,
            nci = 1000L,
            nrarfcn = 600000
        )

        val json = payload.toMap().let { C7Json.canonicalize(it) }

        // Guardrails G28, G29 & Contract C7 prohibited PII/hardware fields
        val prohibited = listOf("imei", "imsi", "mac_address", "serial", "latitude", "longitude", "phone_number")
        for (field in prohibited) {
            assertFalse("Prohibited identifier '$field' must not be in payload JSON", json.contains(""""$field""""))
        }
    }
}
