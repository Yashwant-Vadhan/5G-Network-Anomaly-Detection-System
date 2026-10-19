package com.example.a5gnetworktester

import com.example.a5gnetworktester.streaming.C7Ack
import com.example.a5gnetworktester.streaming.C7Alert
import com.example.a5gnetworktester.streaming.C7Error
import com.example.a5gnetworktester.streaming.C7HelloAck
import com.example.a5gnetworktester.streaming.C7IngestHello
import com.example.a5gnetworktester.streaming.C7IngestSample
import com.example.a5gnetworktester.streaming.C7Json
import com.example.a5gnetworktester.streaming.C7SamplePayload
import com.example.a5gnetworktester.streaming.DeviceInfoProvider
import com.example.a5gnetworktester.streaming.StreamClient
import com.example.a5gnetworktester.streaming.StreamClientListener
import com.example.a5gnetworktester.streaming.StreamState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.UUID

/**
 * Unit tests for Contract C7 serialization, privacy, and StreamClient lifecycle (T12-002).
 */
class StreamClientTest {

    private val mockDeviceInfo = object : DeviceInfoProvider {
        override val device: String = "SM-A156E"
        override val manufacturer: String = "samsung"
        override val androidVersion: String = "16"
        override val operator: String = "airtel"
        override val networkType: String = "LTE"
        override val deploymentMode: String = "NSA"
        override val displayOverride: String = "NR_NSA"
    }

    @Test
    fun serialization_equalsGoldenC7ExampleByteForByteAfterCanonicalisation() {
        // Acceptance criteria: Serialisation equals the golden C7 example byte-for-byte after canonicalisation
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
            type = "sample",
            schema_version = 2,
            seq = 119L,
            sent_at = "2026-10-01T18:26:32.412+05:30",
            payload = payload,
            edge = null
        )

        val expectedCanonical =
            "{\"edge\":null,\"payload\":{\"android\":\"16\",\"csi_rsrp\":null,\"csi_rsrq\":null,\"csi_sinr\":null," +
                    "\"deployment_mode\":\"NSA\",\"device\":\"SM-A156E\",\"display_override\":\"NR_NSA\"," +
                    "\"manufacturer\":\"samsung\",\"nci\":0,\"network_type\":\"LTE\",\"nrarfcn\":629952," +
                    "\"operator\":\"airtel\",\"pci\":861,\"registered\":false,\"ss_rsrp\":-97.0,\"ss_rsrq\":-12.0," +
                    "\"ss_sinr\":3.0,\"timestamp\":\"01-10-26 18:26:32\"},\"schema_version\":2," +
                    "\"sent_at\":\"2026-10-01T18:26:32.412+05:30\",\"seq\":119,\"type\":\"sample\"}"

        assertEquals(expectedCanonical, sample.toCanonicalJson())
    }

    @Test
    fun noHardwareIdentifiers_inAnyMessage() {
        // Acceptance criteria: No hardware identifiers in any message
        val randomUuid = UUID.randomUUID().toString()
        val hello = C7IngestHello(
            client_id = randomUuid,
            device = "Redmi 13 5G",
            manufacturer = "Xiaomi",
            android = "14",
            operator = "Airtel"
        )
        val helloJson = hello.toCanonicalJson().lowercase()

        val sample = C7IngestSample(
            seq = 1,
            sent_at = "2026-10-19T10:00:00.000Z",
            payload = C7SamplePayload(
                timestamp = "19-10-26 10:00:00",
                device = "Redmi 13 5G",
                manufacturer = "Xiaomi",
                android = "14",
                operator = "Airtel",
                network_type = "5G NR",
                deployment_mode = "SA",
                display_override = "5G",
                registered = true,
                ss_rsrp = -85.0,
                ss_rsrq = -11.0,
                ss_sinr = 15.0,
                csi_rsrp = null,
                csi_rsrq = null,
                csi_sinr = null,
                pci = 421,
                nci = 13322280247L,
                nrarfcn = 632000
            )
        )
        val sampleJson = sample.toCanonicalJson().lowercase()

        val forbiddenIdentifiers = listOf(
            "imei",
            "imsi",
            "iccid",
            "serial",
            "mac_address",
            "phone_number",
            "msisdn"
        )

        for (id in forbiddenIdentifiers) {
            assertFalse("Hello message must not contain $id", helloJson.contains(id))
            assertFalse("Sample message must not contain $id", sampleJson.contains(id))
        }

        assertTrue("client_id must be a valid UUID", UUID.fromString(randomUuid).toString() == randomUuid)
    }

    @Test
    fun fatalErrorCodes_stopReconnectLoops() {
        // Acceptance criteria: Fatal error codes stop reconnect loops
        var receivedError: C7Error? = null
        var lastState: StreamState = StreamState.DISCONNECTED

        val listener = object : StreamClientListener {
            override fun onError(error: C7Error) {
                receivedError = error
            }

            override fun onConnectionStateChanged(state: StreamState) {
                lastState = state
            }
        }

        val client = StreamClient(
            wsEndpointUrl = "ws://127.0.0.1:8000/api/v1/ingest",
            ingestToken = "test-token",
            clientInfo = mockDeviceInfo,
            listener = listener
        )

        assertFalse(client.isFatalHalted)

        // Simulate incoming fatal error from server
        val fatalJson = """
            {"type":"error","schema_version":2,"seq":101,"code":"SESSION_CLOSED","message":"Session was terminated","fatal":true}
        """.trimIndent()

        client.handleIncomingMessage(fatalJson)

        assertNotNull(receivedError)
        assertEquals("SESSION_CLOSED", receivedError?.code)
        assertTrue(receivedError?.fatal == true)
        assertTrue("Client must be marked as fatal-halted", client.isFatalHalted)
        assertEquals(StreamState.FATAL_HALTED, client.currentState)

        // Attempting to connect when fatal-halted must be a no-op (stops reconnect loop)
        client.connect()
        assertEquals(StreamState.FATAL_HALTED, client.currentState)
    }

    @Test
    fun nonFatalError_doesNotHaltClient() {
        var receivedError: C7Error? = null
        val listener = object : StreamClientListener {
            override fun onError(error: C7Error) {
                receivedError = error
            }
        }

        val client = StreamClient(
            wsEndpointUrl = "ws://127.0.0.1:8000/api/v1/ingest",
            ingestToken = "test-token",
            clientInfo = mockDeviceInfo,
            listener = listener
        )

        val nonFatalJson = """
            {"type":"error","schema_version":2,"seq":102,"code":"RATE_LIMIT_WARNING","message":"Slow down","fatal":false}
        """.trimIndent()

        client.handleIncomingMessage(nonFatalJson)

        assertEquals("RATE_LIMIT_WARNING", receivedError?.code)
        assertFalse(receivedError?.fatal ?: true)
        assertFalse("Non-fatal error must not halt client", client.isFatalHalted)
    }

    @Test
    fun incomingAckAndAlert_triggerListeners() {
        var receivedAck: C7Ack? = null
        var receivedAlert: C7Alert? = null
        var receivedHelloAck: C7HelloAck? = null

        val listener = object : StreamClientListener {
            override fun onAck(ack: C7Ack) {
                receivedAck = ack
            }
            override fun onAlert(alert: C7Alert) {
                receivedAlert = alert
            }
            override fun onHelloAck(helloAck: C7HelloAck) {
                receivedHelloAck = helloAck
            }
        }

        val client = StreamClient(
            wsEndpointUrl = "ws://127.0.0.1:8000/api/v1/ingest",
            ingestToken = "test-token",
            clientInfo = mockDeviceInfo,
            listener = listener
        )

        // 1. HelloAck
        client.handleIncomingMessage("""{"type":"hello_ack","schema_version":2,"session_id":"sess-99","accepted":true,"resumed_at_seq":0}""")
        assertEquals("sess-99", receivedHelloAck?.session_id)
        assertTrue(receivedHelloAck?.accepted == true)

        // 2. Ack
        client.handleIncomingMessage("""{"type":"ack","schema_version":2,"seq":119}""")
        assertEquals(119L, receivedAck?.seq)

        // 3. Alert
        client.handleIncomingMessage("""{"type":"alert","schema_version":2,"alert_id":"alt-1","severity":"HIGH","title":"Signal degraded","detail":"SINR negative"}""")
        assertEquals("alt-1", receivedAlert?.alert_id)
        assertEquals("HIGH", receivedAlert?.severity)
    }
}
