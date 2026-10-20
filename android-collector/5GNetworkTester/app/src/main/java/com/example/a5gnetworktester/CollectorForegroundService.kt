package com.example.a5gnetworktester

import android.Manifest
import android.annotation.SuppressLint
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.telephony.CellIdentityNr
import android.telephony.CellInfo
import android.telephony.CellInfoNr
import android.telephony.CellSignalStrengthNr
import android.telephony.TelephonyCallback
import android.telephony.TelephonyDisplayInfo
import android.telephony.TelephonyManager
import androidx.annotation.RequiresApi
import androidx.core.app.ActivityCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import com.example.a5gnetworktester.streaming.StreamClient
import com.example.a5gnetworktester.streaming.TelemetryDispatcher
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Foreground service executing continuous 3-second 5G cellular sampling and streaming (T19-009).
 *
 * Implements:
 * 1. Moves the 3 s loop into a foreground service with an ongoing notification stating what is running.
 * 2. Declares service type `dataSync` (FOREGROUND_SERVICE_DATA_SYNC).
 * 3. Handles Android 15+ (targetSdk 37) 6-hour timeout cleanly via Service.onTimeout(int, int).
 * 4. Acquires Partial WakeLock to ensure collection survives screen-off on Redmi & Samsung devices.
 * 5. Uses IncrementalCsvWriter (Guardrail G18, F10) and TelemetryDispatcher for streaming (T19-012).
 */
class CollectorForegroundService : Service() {

    companion object {
        const val ACTION_START = "com.example.a5gnetworktester.action.START"
        const val ACTION_STOP = "com.example.a5gnetworktester.action.STOP"
        const val SAMPLE_INTERVAL_MS = 3000L
        private const val WAKELOCK_TAG = "5GNetworkTester:CollectorWakeLock"

        private val _uiStateFlow = MutableStateFlow(UiState())
        val uiStateFlow: StateFlow<UiState> = _uiStateFlow.asStateFlow()

        private val _isCollectingFlow = MutableStateFlow(false)
        val isCollectingFlow: StateFlow<Boolean> = _isCollectingFlow.asStateFlow()

        val csvRows = mutableListOf<String>()
        var currentSessionWriter: IncrementalCsvWriter? = null
        var activeSessionFile: File? = null
        var streamClient: StreamClient? = null

        /**
         * Starts the foreground service via ContextCompat.startForegroundService.
         */
        fun start(context: Context) {
            val intent = Intent(context, CollectorForegroundService::class.java).apply {
                action = ACTION_START
            }
            ContextCompat.startForegroundService(context, intent)
        }

        /**
         * Stops the foreground service.
         */
        fun stop(context: Context) {
            val intent = Intent(context, CollectorForegroundService::class.java).apply {
                action = ACTION_STOP
            }
            context.startService(intent)
        }

        /**
         * Updates external UI state observable from Activities and Composables.
         */
        fun updateUiState(newState: UiState) {
            _uiStateFlow.value = newState
            _isCollectingFlow.value = newState.isCollecting
        }

        /**
         * Finalizes the current active CSV writer and returns the saved file.
         */
        fun finalizeCsv(directory: File): File? {
            val activeWriter = currentSessionWriter
            val file = if (activeWriter != null && activeWriter.file.exists() && activeWriter.file.length() > 0) {
                activeWriter.close()
                currentSessionWriter = null
                activeSessionFile = activeWriter.file
                activeWriter.file
            } else if (csvRows.size > 1) {
                activeWriter?.close()
                currentSessionWriter = null
                val fallbackFile = IncrementalCsvWriter.createSessionFile(directory)
                fallbackFile.writeText(csvRows.joinToString("\n") + "\n")
                activeSessionFile = fallbackFile
                fallbackFile
            } else {
                activeWriter?.close()
                currentSessionWriter = null
                null
            }
            return file
        }
    }

    private lateinit var telephonyManager: TelephonyManager
    private var powerManager: PowerManager? = null
    private var wakeLock: PowerManager.WakeLock? = null
    private val handler: Handler by lazy { Handler(Looper.getMainLooper()) }
    private var latestDisplayInfo: TelephonyDisplayInfo? = null

    private val dispatcher = TelemetryDispatcher(
        onLogCsv = { row ->
            csvRows.add(row)
            currentSessionWriter?.appendRow(row)
        },
        onStream = { row -> streamClient?.sendCsvRow(row) }
    )

    private val collectionRunnable = object : Runnable {
        override fun run() {
            if (!_isCollectingFlow.value) return
            collectSample()
            handler.postDelayed(this, SAMPLE_INTERVAL_MS)
        }
    }

    private val telephonyCallback = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        object : TelephonyCallback(), TelephonyCallback.DisplayInfoListener {
            override fun onDisplayInfoChanged(telephonyDisplayInfo: TelephonyDisplayInfo) {
                latestDisplayInfo = telephonyDisplayInfo
                updateStatus()
            }
        }
    } else {
        null
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        telephonyManager = getSystemService(TELEPHONY_SERVICE) as TelephonyManager
        powerManager = getSystemService(POWER_SERVICE) as? PowerManager
        registerDisplayCallback()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopCollection()
                stopSelf(startId)
                return START_NOT_STICKY
            }
            ACTION_START, null -> {
                startCollectionForeground()
                return START_STICKY
            }
            else -> {
                return START_STICKY
            }
        }
    }

    /**
     * Starts continuous sampling loop in the foreground with ongoing notification.
     */
    @SuppressLint("WakelockTimeout")
    private fun startCollectionForeground() {
        if (_isCollectingFlow.value) return

        _isCollectingFlow.value = true
        csvRows.clear()
        csvRows.add(CsvBuilder.CSV_HEADER)

        // Initialize incremental session writer (T19-004, Guardrail G18)
        try {
            val directory = getExternalFilesDir(null) ?: filesDir
            currentSessionWriter?.close()
            val sessionFile = IncrementalCsvWriter.createSessionFile(directory)
            currentSessionWriter = IncrementalCsvWriter(sessionFile)
            activeSessionFile = sessionFile
        } catch (_: Exception) {
            currentSessionWriter = null
        }

        // 1. Acquire partial wake lock for continuous screen-off sampling on Redmi & Samsung
        try {
            wakeLock = powerManager?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, WAKELOCK_TAG)?.apply {
                setReferenceCounted(false)
                acquire()
            }
        } catch (_: Exception) {}

        // 2. Start Foreground with DATA_SYNC type
        val notification = CollectorNotificationHelper.buildNotification(
            context = this,
            sampleCount = 0,
            deploymentMode = getDeploymentMode(),
            isStreaming = streamClient != null
        )

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(
                CollectorNotificationHelper.NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            )
        } else {
            startForeground(CollectorNotificationHelper.NOTIFICATION_ID, notification)
        }

        // 3. Update initial state
        updateUiState(
            _uiStateFlow.value.copy(
                isCollecting = true,
                sampleCount = 0,
                deploymentMode = getDeploymentMode(),
                latestReading = null,
                statusMessage = getString(R.string.waiting_measurement)
            )
        )

        // 4. Initial sample and recurring 3s loop
        collectSample()
        handler.postDelayed(collectionRunnable, SAMPLE_INTERVAL_MS)
    }

    /**
     * Stops continuous measurement collection.
     */
    private fun stopCollection() {
        _isCollectingFlow.value = false
        handler.removeCallbacks(collectionRunnable)

        releaseWakeLock()

        updateUiState(
            _uiStateFlow.value.copy(
                isCollecting = false,
                deploymentMode = getDeploymentMode()
            )
        )

        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
    }

    /**
     * Android 15+ (targetSdk 37) Timeout Callback:
     * DataSync foreground services enforce a maximum 6h execution window in 24h.
     * Service.onTimeout(int, int) must cleanly call stopSelf().
     */
    @RequiresApi(Build.VERSION_CODES.VANILLA_ICE_CREAM)
    override fun onTimeout(startId: Int, fgsType: Int) {
        handleTimeout(startId, fgsType)
    }

    var onStopSelfAction: ((startId: Int) -> Unit)? = null

    /**
     * Handles timeout callback cleanly: flushes writer, releases wake lock,
     * updates status message, and invokes stopSelf() (Acceptance Criterion 2).
     */
    fun handleTimeout(startId: Int, fgsType: Int) {
        _isCollectingFlow.value = false
        try {
            handler.removeCallbacks(collectionRunnable)
        } catch (_: Exception) {}

        // Flush and close active CSV writer to protect captured data
        try {
            currentSessionWriter?.close()
        } catch (_: Exception) {}

        releaseWakeLock()

        val timeoutMsg = try {
            getString(R.string.timeout_stopped_message)
        } catch (_: Exception) {
            "Collection stopped: Android 15+ 6-hour dataSync timeout reached."
        }

        updateUiState(
            _uiStateFlow.value.copy(
                isCollecting = false,
                statusMessage = timeoutMsg
            )
        )

        try {
            ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        } catch (_: Exception) {}

        val stopper = onStopSelfAction
        if (stopper != null) {
            stopper(startId)
        } else {
            stopSelf(startId)
        }
    }

    private fun releaseWakeLock() {
        try {
            if (wakeLock?.isHeld == true) {
                wakeLock?.release()
            }
        } catch (_: Exception) {}
        wakeLock = null
    }

    private fun registerDisplayCallback() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            if (ActivityCompat.checkSelfPermission(this, Manifest.permission.READ_PHONE_STATE) != PackageManager.PERMISSION_GRANTED) {
                return
            }
            try {
                telephonyManager.registerTelephonyCallback(mainExecutor, telephonyCallback!!)
            } catch (_: Exception) {}
        }
    }

    private fun unregisterDisplayCallback() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            try {
                telephonyCallback?.let { telephonyManager.unregisterTelephonyCallback(it) }
            } catch (_: Exception) {}
        }
    }

    fun getDeploymentMode(): String {
        val info = latestDisplayInfo ?: return "UNKNOWN"
        return when (info.overrideNetworkType) {
            TelephonyDisplayInfo.OVERRIDE_NETWORK_TYPE_NR_NSA,
            TelephonyDisplayInfo.OVERRIDE_NETWORK_TYPE_NR_NSA_MMWAVE -> "NSA"
            else -> "UNKNOWN"
        }
    }

    private fun getDisplayOverride(): String {
        val info = latestDisplayInfo ?: return "UNKNOWN"
        return when (info.overrideNetworkType) {
            TelephonyDisplayInfo.OVERRIDE_NETWORK_TYPE_NONE -> "NONE"
            TelephonyDisplayInfo.OVERRIDE_NETWORK_TYPE_NR_NSA -> "NR_NSA"
            TelephonyDisplayInfo.OVERRIDE_NETWORK_TYPE_NR_NSA_MMWAVE -> "NR_NSA_MMWAVE"
            else -> info.overrideNetworkType.toString()
        }
    }

    private fun collectSample() {
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            return
        }

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                telephonyManager.requestCellInfoUpdate(
                    mainExecutor,
                    object : TelephonyManager.CellInfoCallback() {
                        override fun onCellInfo(cellInfo: MutableList<CellInfo>) {
                            processCellInfo(cellInfo)
                        }

                        override fun onError(errorCode: Int, detail: Throwable?) {
                            val detailMsg = detail?.message ?: getString(R.string.cell_info_none)
                            updateUiState(
                                _uiStateFlow.value.copy(
                                    statusMessage = getString(R.string.cell_info_error, errorCode, detailMsg)
                                )
                            )
                        }
                    }
                )
            } else {
                @Suppress("DEPRECATION")
                val cellInfo = telephonyManager.allCellInfo
                processCellInfo(cellInfo)
            }
        } catch (e: Exception) {
            updateUiState(
                _uiStateFlow.value.copy(
                    statusMessage = getString(R.string.collection_error, e.message ?: "")
                )
            )
        }
    }

    private fun processCellInfo(cellInfoList: List<CellInfo>?) {
        if (!_isCollectingFlow.value) return

        if (cellInfoList.isNullOrEmpty()) {
            updateUiState(
                _uiStateFlow.value.copy(
                    statusMessage = "No cellular information returned.\n\nRetrying..."
                )
            )
            return
        }

        var bestNrCell: CellInfoNr? = null
        var secondaryNrCell: CellInfoNr? = null
        var anyNrCell: CellInfoNr? = null

        for (cellInfo in cellInfoList) {
            if (cellInfo is CellInfoNr) {
                if (anyNrCell == null) anyNrCell = cellInfo
                if (cellInfo.isRegistered && bestNrCell == null) bestNrCell = cellInfo
                if (cellInfo.cellConnectionStatus == CellInfo.CONNECTION_SECONDARY_SERVING && secondaryNrCell == null) {
                    secondaryNrCell = cellInfo
                }
            }
        }

        val selectedNr = bestNrCell ?: secondaryNrCell ?: anyNrCell
        if (selectedNr != null) {
            processNrCell(selectedNr)
            return
        }

        val deployment = getDeploymentMode()
        val msg = if (deployment == "NSA") {
            "5G NSA DETECTED\n\nNR measurement is currently unavailable.\nLTE anchor information may be available.\n\nRetrying..."
        } else {
            "No NR measurement available.\n\nDeployment: $deployment\n\nRetrying..."
        }
        updateUiState(_uiStateFlow.value.copy(statusMessage = msg))
        updateStatus()
    }

    private fun processNrCell(cellInfo: CellInfoNr) {
        val signal = cellInfo.cellSignalStrength as CellSignalStrengthNr
        val identity = cellInfo.cellIdentity as CellIdentityNr

        val timestamp = SimpleDateFormat("dd-MM-yy HH:mm:ss", Locale.getDefault()).format(Date())
        val device = Build.MODEL
        val manufacturer = Build.MANUFACTURER
        val androidVersion = Build.VERSION.RELEASE

        val operator = try {
            telephonyManager.networkOperatorName
        } catch (_: Exception) {
            "UNKNOWN"
        }

        val networkType = try {
            when (telephonyManager.dataNetworkType) {
                TelephonyManager.NETWORK_TYPE_NR -> "5G NR"
                TelephonyManager.NETWORK_TYPE_LTE -> "LTE"
                else -> telephonyManager.dataNetworkType.toString()
            }
        } catch (_: Exception) {
            "UNKNOWN"
        }

        val deploymentMode = getDeploymentMode()
        val displayOverride = getDisplayOverride()
        val registered = cellInfo.isRegistered.toString().uppercase()

        val ssRsrp = CsvBuilder.metricValue(signal.ssRsrp)
        val ssRsrq = CsvBuilder.metricValue(signal.ssRsrq)
        val ssSinr = CsvBuilder.metricValue(signal.ssSinr)
        val csiRsrp = CsvBuilder.metricValue(signal.csiRsrp)
        val csiRsrq = CsvBuilder.metricValue(signal.csiRsrq)
        val csiSinr = CsvBuilder.metricValue(signal.csiSinr)
        val pci = CsvBuilder.metricValue(identity.pci)
        val nci = CsvBuilder.metricValue(identity.nci)
        val nrarfcn = CsvBuilder.metricValue(identity.nrarfcn)

        val row = CsvBuilder.buildCsvRow(
            timestamp, device, manufacturer, androidVersion, operator,
            networkType, deploymentMode, displayOverride, registered,
            ssRsrp, ssRsrq, ssSinr, csiRsrp, csiRsrq, csiSinr,
            pci, nci, nrarfcn
        )

        dispatcher.dispatch(row)

        val samplesCount = if (csvRows.isEmpty()) 0 else csvRows.size - 1

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
            samplesStored = samplesCount
        )

        updateUiState(
            _uiStateFlow.value.copy(
                isCollecting = _isCollectingFlow.value,
                sampleCount = samplesCount,
                deploymentMode = deploymentMode,
                latestReading = reading,
                statusMessage = null
            )
        )

        // Update ongoing foreground notification with latest state
        updateNotification(samplesCount, deploymentMode)
    }

    private fun updateNotification(sampleCount: Int, deploymentMode: String) {
        val notification = CollectorNotificationHelper.buildNotification(
            context = this,
            sampleCount = sampleCount,
            deploymentMode = deploymentMode,
            isStreaming = streamClient != null
        )
        val manager = getSystemService(NOTIFICATION_SERVICE) as? android.app.NotificationManager
        manager?.notify(CollectorNotificationHelper.NOTIFICATION_ID, notification)
    }

    private fun updateStatus() {
        val sampleCount = if (csvRows.isEmpty()) 0 else csvRows.size - 1
        updateUiState(
            _uiStateFlow.value.copy(
                isCollecting = _isCollectingFlow.value,
                sampleCount = sampleCount,
                deploymentMode = getDeploymentMode()
            )
        )
    }

    override fun onDestroy() {
        stopCollection()
        unregisterDisplayCallback()
        super.onDestroy()
    }
}
