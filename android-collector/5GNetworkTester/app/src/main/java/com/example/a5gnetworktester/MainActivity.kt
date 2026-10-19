package com.example.a5gnetworktester

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.telephony.CellInfo
import android.telephony.CellInfoNr
import android.telephony.CellIdentityNr
import android.telephony.CellSignalStrengthNr
import android.telephony.TelephonyCallback
import android.telephony.TelephonyDisplayInfo
import android.telephony.TelephonyManager
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.activity.ComponentActivity
import androidx.core.app.ActivityCompat
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import com.example.a5gnetworktester.streaming.AlertNotificationManager
import com.example.a5gnetworktester.streaming.C7Alert
import com.example.a5gnetworktester.streaming.C7Error
import com.example.a5gnetworktester.streaming.StreamClient
import com.example.a5gnetworktester.streaming.StreamClientListener
import com.example.a5gnetworktester.streaming.StreamState
import com.example.a5gnetworktester.streaming.TelemetryDispatcher
import com.example.a5gnetworktester.ui.theme._5GNetworkTesterTheme

enum class AppScreen {
    HOME,
    PAIRING,
    CONSENT
}

class MainActivity : ComponentActivity() {

    private lateinit var telephonyManager: TelephonyManager

    private val handler = Handler(Looper.getMainLooper())

    private var collecting = false

    /*
     * All collected samples are stored here.
     * The UI shows only the latest sample.
     */
    private val csvRows = mutableListOf<String>()

    private var streamClient: StreamClient? = null
    private var isStreamingActive by mutableStateOf(false)

    /*
     * Incremental CSV writer persisting measurements as collected (T19-004, Guardrail G18).
     */
    private var currentSessionWriter: IncrementalCsvWriter? = null

    /*
     * Telemetry dispatcher ensuring CSV logging executes independently
     * and prior to any streaming hook (Guardrail G18, T12-007, T19-012).
     */
    private val dispatcher = TelemetryDispatcher(
        onLogCsv = { row ->
            csvRows.add(row)
            currentSessionWriter?.appendRow(row)
        },
        onStream = { row -> streamClient?.sendCsvRow(row) }
    )

    /*
     * Latest TelephonyDisplayInfo received from Android.
     */
    private var latestDisplayInfo: TelephonyDisplayInfo? = null

    private lateinit var alertNotificationManager: AlertNotificationManager

    var currentScreen by mutableStateOf(AppScreen.HOME)

    var uiState: UiState by mutableStateOf(UiState())

    companion object {

        private const val PERMISSION_REQUEST_CODE = 100

        private const val SAMPLE_INTERVAL = 3000L

        private val REQUIRED_PERMISSIONS: Array<String>
            get() = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                arrayOf(
                    Manifest.permission.READ_PHONE_STATE,
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.POST_NOTIFICATIONS
                )
            } else {
                arrayOf(
                    Manifest.permission.READ_PHONE_STATE,
                    Manifest.permission.ACCESS_FINE_LOCATION
                )
            }
    }


    /*
     * Android 12+ callback for TelephonyDisplayInfo.
     */
    private val telephonyCallback =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {

            object : TelephonyCallback(),
                TelephonyCallback.DisplayInfoListener {

                override fun onDisplayInfoChanged(
                    telephonyDisplayInfo: TelephonyDisplayInfo
                ) {

                    latestDisplayInfo = telephonyDisplayInfo

                    runOnUiThread {
                        updateStatus()
                    }
                }
            }

        } else {
            null
        }


    override fun onCreate(savedInstanceState: Bundle?) {

        super.onCreate(savedInstanceState)

        telephonyManager =
            getSystemService(TELEPHONY_SERVICE) as TelephonyManager

        alertNotificationManager = AlertNotificationManager(this)

        setContent {
            _5GNetworkTesterTheme {
                when (currentScreen) {
                    AppScreen.HOME -> HomeScreen(
                        uiState = uiState,
                        isStreaming = isStreamingActive,
                        onStartClick = { startCollection() },
                        onStopClick = { stopCollection() },
                        onSaveCsvClick = { saveCsv() },
                        onNavigatePairing = { currentScreen = AppScreen.PAIRING },
                        onNavigateConsent = { currentScreen = AppScreen.CONSENT }
                    )
                    AppScreen.PAIRING -> PairingScreen(
                        onPairSuccess = { sessionId, ingestToken, serverUrl, wsUrl ->
                            initStreamClient(serverUrl, ingestToken, wsUrl)
                            currentScreen = AppScreen.HOME
                        },
                        onBack = { currentScreen = AppScreen.HOME },
                        tokenStorageSaver = { token ->
                            TokenStorage(this@MainActivity).saveIngestToken(token)
                        }
                    )
                    AppScreen.CONSENT -> ConsentScreen(
                        onAccept = {
                            ConsentManager.setConsent(this@MainActivity, true)
                            currentScreen = AppScreen.HOME
                        },
                        onDecline = { currentScreen = AppScreen.HOME }
                    )
                }
            }
        }

        if (!hasPermissions()) {

            ActivityCompat.requestPermissions(
                this,
                REQUIRED_PERMISSIONS,
                PERMISSION_REQUEST_CODE
            )

        } else {

            registerDisplayCallback()
            updateStatus()
        }
    }


    private fun hasPermissions(): Boolean {

        return REQUIRED_PERMISSIONS.all {

            ActivityCompat.checkSelfPermission(
                this,
                it
            ) == PackageManager.PERMISSION_GRANTED
        }
    }


    /*
     * Registers Android's display information callback.
     */
    private fun registerDisplayCallback() {

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {

            if (
                ActivityCompat.checkSelfPermission(
                    this,
                    Manifest.permission.READ_PHONE_STATE
                ) != PackageManager.PERMISSION_GRANTED
            ) {
                return
            }

            try {

                telephonyManager.registerTelephonyCallback(
                    mainExecutor,
                    telephonyCallback!!
                )

            } catch (e: Exception) {

                uiState = uiState.copy(statusMessage = "Display callback error: ${e.message}")
            }
        }
    }


    private fun unregisterDisplayCallback() {

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {

            try {

                if (telephonyCallback != null) {

                    telephonyManager.unregisterTelephonyCallback(
                        telephonyCallback!!
                    )
                }

            } catch (_: Exception) {
            }
        }
    }


    /*
     * Determines deployment mode.
     *
     * NSA:
     * Android explicitly reports NR-NSA.
     *
     * SA:
     * We do not infer SA from "5G NR".
     *
     * UNKNOWN:
     * Android does not expose enough information.
     */
    private fun getDeploymentMode(): String {

        val info = latestDisplayInfo
            ?: return "UNKNOWN"


        return when (info.overrideNetworkType) {

            TelephonyDisplayInfo.OVERRIDE_NETWORK_TYPE_NR_NSA -> {
                "NSA"
            }

            TelephonyDisplayInfo.OVERRIDE_NETWORK_TYPE_NR_NSA_MMWAVE -> {
                "NSA"
            }

            else -> {
                "UNKNOWN"
            }
        }
    }


    /*
     * Gives the raw Android display override state.
     */
    private fun getDisplayOverride(): String {

        val info = latestDisplayInfo
            ?: return "UNKNOWN"


        return when (info.overrideNetworkType) {

            TelephonyDisplayInfo.OVERRIDE_NETWORK_TYPE_NONE ->
                "NONE"

            TelephonyDisplayInfo.OVERRIDE_NETWORK_TYPE_NR_NSA ->
                "NR_NSA"

            TelephonyDisplayInfo.OVERRIDE_NETWORK_TYPE_NR_NSA_MMWAVE ->
                "NR_NSA_MMWAVE"

            else ->
                info.overrideNetworkType.toString()
        }
    }


    /*
     * Starts continuous measurement collection.
     */
    private fun startCollection() {

        if (!hasPermissions()) {

            ActivityCompat.requestPermissions(
                this,
                REQUIRED_PERMISSIONS,
                PERMISSION_REQUEST_CODE
            )

            return
        }


        if (collecting) {
            return
        }


        collecting = true

        csvRows.clear()


        /*
         * CSV header.
         */
        csvRows.add(CsvBuilder.CSV_HEADER)

        /*
         * Initialize incremental session writer (T19-004, Guardrail G18).
         * Each subsequent sample will be appended and flushed immediately to file.
         */
        try {
            val directory = getExternalFilesDir(null) ?: filesDir
            currentSessionWriter?.close()
            currentSessionWriter = IncrementalCsvWriter(IncrementalCsvWriter.createSessionFile(directory))
        } catch (_: Exception) {
            currentSessionWriter = null
        }


        /*
         * Clear previous display via UiState.
         */
        uiState = uiState.copy(
            isCollecting = true,
            sampleCount = 0,
            deploymentMode = getDeploymentMode(),
            latestReading = null,
            statusMessage = getString(R.string.waiting_measurement)
        )


        /*
         * Collect immediately.
         */
        collectSample()


        /*
         * Continue every 3 seconds.
         */
        handler.postDelayed(
            collectionRunnable,
            SAMPLE_INTERVAL
        )
    }


    /*
     * Repeated measurement task.
     */
    private val collectionRunnable = object : Runnable {

        override fun run() {

            if (!collecting) {
                return
            }


            collectSample()


            handler.postDelayed(
                this,
                SAMPLE_INTERVAL
            )
        }
    }


    /*
     * Stops collection.
     */
    private fun stopCollection() {

        collecting = false

        handler.removeCallbacks(
            collectionRunnable
        )

        updateStatus()
    }


    /*
     * Requests current cellular information.
     */
    private fun collectSample() {

        if (!hasPermissions()) {
            return
        }


        try {

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {

                telephonyManager.requestCellInfoUpdate(
                    mainExecutor,
                    object : TelephonyManager.CellInfoCallback() {

                        override fun onCellInfo(
                            cellInfo: MutableList<CellInfo>
                        ) {

                            processCellInfo(cellInfo)
                        }


                        override fun onError(
                            errorCode: Int,
                            detail: Throwable?
                        ) {
                            runOnUiThread {
                                val detailMsg = detail?.message ?: getString(R.string.cell_info_none)
                                uiState = uiState.copy(statusMessage = getString(R.string.cell_info_error, errorCode, detailMsg))
                            }
                        }
                    }
                )

            } else {

                val cellInfo =
                    telephonyManager.allCellInfo

                processCellInfo(cellInfo)
            }

        } catch (e: Exception) {

            runOnUiThread {
                uiState = uiState.copy(statusMessage = getString(R.string.collection_error, e.message ?: ""))
            }
        }
    }


    /*
     * Searches the returned cell list for NR cells.
     */
    private fun processCellInfo(
        cellInfoList: List<CellInfo>?
    ) {
        if (cellInfoList.isNullOrEmpty()) {
            runOnUiThread {
                uiState = uiState.copy(
                    statusMessage = "No cellular information returned.\n\nRetrying..."
                )
            }
            return
        }

        var bestNrCell: CellInfoNr? = null
        var secondaryNrCell: CellInfoNr? = null
        var anyNrCell: CellInfoNr? = null

        for (cellInfo in cellInfoList) {

            if (cellInfo is CellInfoNr) {

                if (anyNrCell == null) {
                    anyNrCell = cellInfo
                }

                if (cellInfo.isRegistered && bestNrCell == null) {
                    bestNrCell = cellInfo
                }

                if (
                    cellInfo.cellConnectionStatus ==
                    CellInfo.CONNECTION_SECONDARY_SERVING &&
                    secondaryNrCell == null
                ) {
                    secondaryNrCell = cellInfo
                }
            }
        }

        /*
         * Priority:
         * 1. Registered NR
         * 2. Secondary-serving NR (important for NSA)
         * 3. Any available NR cell
         */
        val selectedNr =
            bestNrCell
                ?: secondaryNrCell
                ?: anyNrCell

        if (selectedNr != null) {
            processNrCell(selectedNr)
            return
        }

        /*
         * No NR CellInfo was returned.
         *
         * The phone may still be in NSA with LTE as
         * the primary/anchor cell.
         */
        runOnUiThread {

            val deployment = getDeploymentMode()

            val msg =
                if (deployment == "NSA") {
                    "5G NSA DETECTED\n\n" +
                            "NR measurement is currently unavailable.\n" +
                            "LTE anchor information may be available.\n\n" +
                            "Retrying..."
                } else {
                    "No NR measurement available.\n\n" +
                            "Deployment: $deployment\n\n" +
                            "Retrying..."
                }

            uiState = uiState.copy(statusMessage = msg)
            updateStatus()
        }
    }


    /*
     * Processes one registered NR cell.
     */
    private fun processNrCell(
        cellInfo: CellInfoNr
    ) {

        /*
         * Explicitly cast to the NR-specific classes.
         */
        val signal =
            cellInfo.cellSignalStrength as CellSignalStrengthNr


        val identity =
            cellInfo.cellIdentity as CellIdentityNr


        val timestamp =
            SimpleDateFormat(
                "dd-MM-yy HH:mm:ss",
                Locale.getDefault()
            ).format(Date())


        val device =
            Build.MODEL


        val manufacturer =
            Build.MANUFACTURER


        val androidVersion =
            Build.VERSION.RELEASE


        val operator =
            try {

                telephonyManager.networkOperatorName

            } catch (_: Exception) {

                "UNKNOWN"
            }


        val networkType =
            try {

                when (telephonyManager.dataNetworkType) {

                    TelephonyManager.NETWORK_TYPE_NR ->
                        "5G NR"

                    TelephonyManager.NETWORK_TYPE_LTE ->
                        "LTE"

                    else ->
                        telephonyManager.dataNetworkType.toString()
                }

            } catch (_: Exception) {

                "UNKNOWN"
            }


        val deploymentMode =
            getDeploymentMode()


        val displayOverride =
            getDisplayOverride()


        val registered =
            cellInfo.isRegistered
                .toString()
                .uppercase()


        /*
         * SS measurements.
         *
         * Android may return 2147483647
         * when a measurement is unavailable.
         */
        val ssRsrp =
            metricValue(signal.ssRsrp)


        val ssRsrq =
            metricValue(signal.ssRsrq)


        val ssSinr =
            metricValue(signal.ssSinr)


        /*
         * CSI measurements.
         */
        val csiRsrp =
            metricValue(signal.csiRsrp)


        val csiRsrq =
            metricValue(signal.csiRsrq)


        val csiSinr =
            metricValue(signal.csiSinr)


        /*
         * NR cell identity.
         */
        val pci =
            intMetricValue(identity.pci)


        val nci =
            longMetricValue(identity.nci)


        val nrarfcn =
            intMetricValue(identity.nrarfcn)


        /*
         * Store the complete sample in CSV.
         */
        val row =
            buildCsvRow(
                timestamp,
                device,
                manufacturer,
                androidVersion,
                operator,
                networkType,
                deploymentMode,
                displayOverride,
                registered,
                ssRsrp,
                ssRsrq,
                ssSinr,
                csiRsrp,
                csiRsrq,
                csiSinr,
                pci,
                nci,
                nrarfcn
            )


        dispatcher.dispatch(row)


        /*
         * Decoupled UI state publication (T19-003).
         * Replaces previous screen contents with current sample via UiState.
         */
        val reading = TelemetryReading(
            timestamp = timestamp,
            device = device,
            manufacturer = manufacturer,
            androidVersion = androidVersion,
            operator = operator,
            networkType = networkType,
            deploymentMode = deploymentMode,
            displayOverride = displayOverride,
            registered = registered,
            ssRsrp = ssRsrp,
            ssRsrq = ssRsrq,
            ssSinr = ssSinr,
            csiRsrp = csiRsrp,
            csiRsrq = csiRsrq,
            csiSinr = csiSinr,
            pci = pci,
            nci = nci,
            nrarfcn = nrarfcn,
            samplesStored = csvRows.size - 1
        )

        uiState = uiState.copy(
            isCollecting = collecting,
            sampleCount = csvRows.size - 1,
            deploymentMode = getDeploymentMode(),
            latestReading = reading,
            statusMessage = null
        )
    }


    /*
     * Converts unavailable integer measurements to NA.
     */
    private fun metricValue(
        value: Int
    ): String = CsvBuilder.metricValue(value)


    /*
     * Converts unavailable integer identity
     * values to NA.
     */
    private fun intMetricValue(
        value: Int
    ): String = CsvBuilder.metricValue(value)


    /*
     * Converts unavailable Long values to NA.
     */
    private fun longMetricValue(
        value: Long
    ): String = CsvBuilder.metricValue(value)


    /*
     * Updates the small status section.
     */
    private fun updateStatus() {
        val sampleCount =
            if (csvRows.isEmpty()) {
                0
            } else {
                csvRows.size - 1
            }

        uiState = uiState.copy(
            isCollecting = collecting,
            sampleCount = sampleCount,
            deploymentMode = getDeploymentMode()
        )
    }


    /*
     * Saves all collected measurements to CSV and offers sharing (T19-004, T19-011).
     */
    private fun saveCsv() {

        if (csvRows.size <= 1) {
            uiState = uiState.copy(
                latestReading = null,
                statusMessage = getString(R.string.no_measurements_to_save)
            )
            return
        }


        try {
            val directory =
                getExternalFilesDir(null) ?: filesDir

            val activeWriter = currentSessionWriter
            val file = if (activeWriter != null && activeWriter.file.exists() && activeWriter.file.length() > 0) {
                activeWriter.close()
                currentSessionWriter = null
                activeWriter.file
            } else {
                activeWriter?.close()
                currentSessionWriter = null
                val fallbackFile = IncrementalCsvWriter.createSessionFile(directory)
                fallbackFile.writeText(csvRows.joinToString("\n") + "\n")
                fallbackFile
            }


            /*
             * Show the exact saved path via UiState.
             */
            val msg =
                "CSV SAVED SUCCESSFULLY\n" +
                        "============================\n\n" +
                        "Samples Saved : ${csvRows.size - 1}\n\n" +
                        "File Name:\n" +
                        "${file.name}\n\n" +
                        "Path:\n" +
                        "${file.absolutePath}\n\n" +
                        "============================\n" +
                        "All collected samples are stored."

            uiState = uiState.copy(
                latestReading = null,
                statusMessage = msg
            )

            offerShare(file)

        } catch (e: Exception) {

            val msg =
                "CSV SAVE ERROR\n\n" +
                        "${e.message}"

            uiState = uiState.copy(
                latestReading = null,
                statusMessage = msg
            )
        }
    }

    private fun offerShare(file: File) {
        try {
            val uri = androidx.core.content.FileProvider.getUriForFile(
                this,
                "${packageName}.provider",
                file
            )
            val shareIntent = android.content.Intent(android.content.Intent.ACTION_SEND).apply {
                type = "text/csv"
                putExtra(android.content.Intent.EXTRA_STREAM, uri)
                addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            startActivity(
                android.content.Intent.createChooser(
                    shareIntent,
                    getString(R.string.share_csv_title)
                )
            )
        } catch (_: Exception) {
            // Sharing may not be available on headless/test environments
        }
    }


    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {

        super.onRequestPermissionsResult(
            requestCode,
            permissions,
            grantResults
        )


        if (
            requestCode == PERMISSION_REQUEST_CODE &&
            hasPermissions()
        ) {

            registerDisplayCallback()

            updateStatus()
        }
    }


    private fun initStreamClient(serverUrl: String, ingestToken: String, wsUrlPath: String) {
        val cleanServer = serverUrl.trimEnd('/')
        val wsScheme = if (cleanServer.startsWith("https")) "wss" else "ws"
        val hostPort = cleanServer.substringAfter("://")
        val path = if (wsUrlPath.startsWith('/')) wsUrlPath else "/$wsUrlPath"
        val fullWsUrl = "$wsScheme://$hostPort$path"

        streamClient?.disconnect()
        val client = StreamClient(
            wsEndpointUrl = fullWsUrl,
            ingestToken = ingestToken,
            context = this,
            listener = object : StreamClientListener {
                override fun onConnected() {
                    runOnUiThread {
                        isStreamingActive = true
                    }
                }
                override fun onConnectionStateChanged(state: StreamState) {
                    runOnUiThread {
                        isStreamingActive = (state == StreamState.CONNECTED)
                    }
                }
                override fun onAlert(alert: C7Alert) {
                    runOnUiThread {
                        alertNotificationManager.onAlert(alert)
                    }
                }
            }
        )
        streamClient = client
        client.connect()
    }

    override fun onDestroy() {

        collecting = false

        handler.removeCallbacks(
            collectionRunnable
        )

        unregisterDisplayCallback()
        currentSessionWriter?.close()
        currentSessionWriter = null
        streamClient?.disconnect()
        streamClient = null

        super.onDestroy()
    }
}