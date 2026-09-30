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
import android.view.Gravity
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.core.app.ActivityCompat
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {

    private lateinit var telephonyManager: TelephonyManager
    private lateinit var statusText: TextView
    private lateinit var outputText: TextView

    private val handler = Handler(Looper.getMainLooper())

    private var collecting = false

    /*
     * All collected samples are stored here.
     * The UI shows only the latest sample.
     */
    private val csvRows = mutableListOf<String>()

    /*
     * Latest TelephonyDisplayInfo received from Android.
     */
    private var latestDisplayInfo: TelephonyDisplayInfo? = null

    companion object {

        private const val PERMISSION_REQUEST_CODE = 100

        private const val SAMPLE_INTERVAL = 3000L

        private val REQUIRED_PERMISSIONS = arrayOf(
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.ACCESS_FINE_LOCATION
        )
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

        createUI()

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


    /*
     * Creates the application UI.
     */
    private fun createUI() {

        val root = LinearLayout(this).apply {

            orientation = LinearLayout.VERTICAL

            setPadding(
                30,
                30,
                30,
                30
            )
        }


        val titleText = TextView(this).apply {

            text = "5G NETWORK TESTER"

            textSize = 22f

            gravity = Gravity.CENTER

            setPadding(
                0,
                0,
                0,
                20
            )
        }


        statusText = TextView(this).apply {

            textSize = 16f

            setPadding(
                0,
                0,
                0,
                15
            )
        }


        val startButton = Button(this).apply {

            text = "START"

            setOnClickListener {
                startCollection()
            }
        }


        val stopButton = Button(this).apply {

            text = "STOP"

            setOnClickListener {
                stopCollection()
            }
        }


        val saveButton = Button(this).apply {

            text = "SAVE CSV"

            setOnClickListener {
                saveCsv()
            }
        }


        val buttonLayout = LinearLayout(this).apply {

            orientation = LinearLayout.HORIZONTAL

            gravity = Gravity.CENTER
        }

        buttonLayout.addView(startButton)
        buttonLayout.addView(stopButton)
        buttonLayout.addView(saveButton)


        outputText = TextView(this).apply {

            textSize = 15f

            setPadding(
                0,
                20,
                0,
                20
            )
        }


        val scrollView = ScrollView(this)

        scrollView.addView(outputText)


        root.addView(titleText)
        root.addView(statusText)
        root.addView(buttonLayout)
        root.addView(scrollView)


        setContentView(root)
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

                outputText.text =
                    "Display callback error: ${e.message}"
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
        csvRows.add(
            "timestamp,device,manufacturer,android,operator," +
                    "network_type,deployment_mode,display_override," +
                    "registered,ss_rsrp,ss_rsrq,ss_sinr," +
                    "csi_rsrp,csi_rsrq,csi_sinr," +
                    "pci,nci,nrarfcn"
        )


        /*
         * Clear previous display.
         */
        outputText.text =
            "Waiting for current 5G measurement..."


        updateStatus()


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
                                outputText.text =
                                    "CELL INFO ERROR\n\n" +
                                            "Error code : $errorCode\n" +
                                            "Detail     : ${detail?.message ?: "None"}\n\n" +
                                            "Retrying..."
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

                outputText.text =
                    "Collection error: ${e.message}"
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
                outputText.text =
                    "No cellular information returned.\n\n" +
                            "Retrying..."
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

            outputText.text =
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
            listOf(
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
            ).joinToString(",")


        csvRows.add(row)


        /*
         * IMPORTANT:
         *
         * Replace the previous screen contents.
         * Do NOT append readings vertically.
         */
        runOnUiThread {

            outputText.text =
                "CURRENT READING\n" +
                        "============================\n\n" +

                        "Timestamp       : $timestamp\n" +
                        "Device          : $device\n" +
                        "Manufacturer    : $manufacturer\n" +
                        "Android         : $androidVersion\n" +
                        "Operator        : $operator\n\n" +

                        "Network Type    : $networkType\n" +
                        "Deployment Mode : $deploymentMode\n" +
                        "Display Override: $displayOverride\n" +
                        "Registered      : $registered\n\n" +

                        "SS-RSRP         : $ssRsrp dBm\n" +
                        "SS-RSRQ         : $ssRsrq dB\n" +
                        "SS-SINR         : $ssSinr dB\n\n" +

                        "CSI-RSRP        : $csiRsrp\n" +
                        "CSI-RSRQ        : $csiRsrq\n" +
                        "CSI-SINR        : $csiSinr\n\n" +

                        "PCI             : $pci\n" +
                        "NCI             : $nci\n" +
                        "NRARFCN         : $nrarfcn\n\n" +

                        "============================\n" +
                        "Samples Stored  : ${csvRows.size - 1}\n\n" +
                        "CSV stores ALL samples.\n" +
                        "Screen shows CURRENT sample."
        }


        updateStatus()
    }


    /*
     * Converts unavailable integer measurements to NA.
     *
     * 2147483647 = Int.MAX_VALUE
     */
    private fun metricValue(
        value: Int
    ): String {

        return if (
            value == Int.MAX_VALUE ||
            value == Int.MIN_VALUE
        ) {

            "NA"

        } else {

            value.toString()
        }
    }


    /*
     * Converts unavailable integer identity
     * values to NA.
     */
    private fun intMetricValue(
        value: Int
    ): String {

        return if (
            value == Int.MAX_VALUE ||
            value == Int.MIN_VALUE
        ) {

            "NA"

        } else {

            value.toString()
        }
    }


    /*
     * Converts unavailable Long values to NA.
     */
    private fun longMetricValue(
        value: Long
    ): String {

        return if (
            value == Long.MAX_VALUE ||
            value == Long.MIN_VALUE
        ) {

            "NA"

        } else {

            value.toString()
        }
    }


    /*
     * Updates the small status section.
     */
    private fun updateStatus() {

        if (!::statusText.isInitialized) {
            return
        }


        val sampleCount =
            if (csvRows.isEmpty()) {
                0
            } else {
                csvRows.size - 1
            }


        statusText.text =
            "Collection : ${
                if (collecting) "RUNNING" else "STOPPED"
            }\n" +
                    "Samples    : $sampleCount\n" +
                    "Deployment : ${getDeploymentMode()}\n" +
                    "Anomaly Detection : NOT YET"
    }


    /*
     * Saves all collected measurements to CSV.
     */
    private fun saveCsv() {

        if (csvRows.size <= 1) {

            outputText.text =
                "No measurements available to save."

            return
        }


        try {

            val directory =
                getExternalFilesDir(null)


            if (directory == null) {

                outputText.text =
                    "Unable to access app storage."

                return
            }


            val fileName =
                "5G_measurements_" +
                        SimpleDateFormat(
                            "yyyyMMdd_HHmmss",
                            Locale.getDefault()
                        ).format(Date()) +
                        ".csv"


            val file =
                File(
                    directory,
                    fileName
                )


            /*
             * Write every collected sample.
             */
            file.writeText(
                csvRows.joinToString("\n")
            )


            /*
             * Show the exact saved path.
             */
            outputText.text =
                "CSV SAVED SUCCESSFULLY\n" +
                        "============================\n\n" +
                        "Samples Saved : ${csvRows.size - 1}\n\n" +
                        "File Name:\n" +
                        "$fileName\n\n" +
                        "Path:\n" +
                        "${file.absolutePath}\n\n" +
                        "============================\n" +
                        "All collected samples are stored."


        } catch (e: Exception) {

            outputText.text =
                "CSV SAVE ERROR\n\n" +
                        "${e.message}"
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


    override fun onDestroy() {

        collecting = false

        handler.removeCallbacks(
            collectionRunnable
        )

        unregisterDisplayCallback()

        super.onDestroy()
    }
}