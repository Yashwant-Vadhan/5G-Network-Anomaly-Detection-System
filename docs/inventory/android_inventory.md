# Android Collector App Inventory — 5G-NADS

> Documented evidence for the 5G-NADS Android collector app (`5GNetworkTester`), build setup, permissions, layout hierarchy, theme tokens, telemetry sampling path, and network isolation.

---

## 12. Gradle & Project Configuration

- **Project Location:** `android-collector/5GNetworkTester` ([`settings.gradle.kts`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/settings.gradle.kts))
- **Application ID:** `"com.example.a5gnetworktester"` ([`app/build.gradle.kts:L13`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/build.gradle.kts#L13))
- **SDK Versions:**
  - `minSdk = 29` (Android 10) ([`app/build.gradle.kts:L14`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/build.gradle.kts#L14))
  - `targetSdk = 37` ([`app/build.gradle.kts:L15`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/build.gradle.kts#L15))
  - `compileSdk = 37` (`release(37)`) ([`app/build.gradle.kts:L9`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/build.gradle.kts#L9))
- **Languages:** **Kotlin** (`org.jetbrains.kotlin.plugin.compose` 2.2.10, Java 11 compatibility) ([`app/build.gradle.kts:L3-L4,L30-L31`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/build.gradle.kts#L3-L4))
- **UI Toolkit:** **Hybrid / Programmatic View Hierarchy**: `MainActivity` builds UI using programmatic Android Views (`LinearLayout`, `TextView`, `Button`, `ScrollView`) in Kotlin ([`MainActivity.kt:L116-L228`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L116-L228)). Jetpack Compose dependencies and theme files (`Color.kt`, `Theme.kt`, `Type.kt`) are included in Gradle/sources but unused in `MainActivity.kt`.
- **Key Dependencies ([`app/build.gradle.kts:L38-L54`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/build.gradle.kts#L38-L54), [`libs.versions.toml`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/gradle/libs.versions.toml)):**
  - Android Gradle Plugin `9.4.1`
  - Kotlin `2.2.10`
  - `androidx.core:core-ktx:1.10.1`
  - `androidx.lifecycle:lifecycle-runtime-ktx:2.6.1`
  - `androidx.activity:activity-compose:1.8.0`
  - Compose BOM `2026.02.01` (`androidx.compose.material3`, `ui`, `ui-graphics`, `ui-tooling`)

---

## 13. Manifest Inspection

- **File:** [`app/src/main/AndroidManifest.xml`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/AndroidManifest.xml)
- **Permissions Requested:**
  - `android.permission.READ_PHONE_STATE` ([`AndroidManifest.xml:L4`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/AndroidManifest.xml#L4))
  - `android.permission.ACCESS_FINE_LOCATION` ([`AndroidManifest.xml:L5`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/AndroidManifest.xml#L5))
- **Services Registered:** **None** (No foreground or background service registered).
- **Network Security Configuration:** `usesCleartextTraffic` NOT specified; `networkSecurityConfig` NOT specified. Backup rules specified via `@xml/backup_rules` and `@xml/data_extraction_rules`.
- **Exported Components:** `com.example.a5gnetworktester.MainActivity` (`exported="true"`, LAUNCHER intent filter) ([`AndroidManifest.xml:L15-L26`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/AndroidManifest.xml#L15-L26)).

---

## 14. Screens & Activities Inventory

- **Activity Count:** 1 (`com.example.a5gnetworktester.MainActivity`).
- **Screen Layout:** Built programmatically in `createUI()` ([`MainActivity.kt:L116-L228`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L116-L228)):
  - Vertical Root `LinearLayout` (padding: 30px).
  - Title `TextView`: `"5G NETWORK TESTER"` (textSize: 22sp, centered).
  - Status `TextView`: `statusText` (textSize: 16sp).
  - Horizontal `LinearLayout` containing three control buttons:
    - `"START"` (`startButton`): Triggers `startCollection()`.
    - `"STOP"` (`stopButton`): Triggers `stopCollection()`.
    - `"SAVE CSV"` (`saveButton`): Triggers `saveCsv()`.
  - Telephony Output `ScrollView` containing `outputText` `TextView` (textSize: 15sp) displaying real-time single-sample telemetry dump.
- **Navigation:** Single screen app (no multi-activity or Compose navigation).

---

## 14b. UI Theme & Asset Inventory

- **UI Framework:** Programmatic Android Views wrapped in `Theme._5GNetworkTester` ([`themes.xml:L4`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/res/values/themes.xml#L4) parent `android:Theme.Material.Light.NoActionBar`).
- **Resource Strings (`strings.xml`):** Contains only `<string name="app_name">5GNetworkTester</string>` ([`strings.xml:L2`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/res/values/strings.xml#L2)). All UI button text ("START", "STOP", "SAVE CSV"), section headers, and field labels are **hard-coded strings in `MainActivity.kt`**.
- **Colors (`colors.xml`):** Contains standard launcher color definitions (`purple_200`, `purple_500`, `purple_700`, `teal_200`, `teal_700`, `black`, `white`).
- **Dark-Mode Support:** No `values-night` directory exists. View-based UI uses system light theme defaults.
- **Drawables & Vectors:** Standard adaptive launcher icons (`ic_launcher_background.xml`, `ic_launcher_foreground.xml`, `ic_launcher.xml`, `ic_launcher_round.xml`).
- **Hard-Coded Layout Text:**
  - Title: `"5G NETWORK TESTER"` ([`MainActivity.kt:L133`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L133))
  - Buttons: `"START"`, `"STOP"`, `"SAVE CSV"` ([`MainActivity.kt:L163,L173,L183`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L163))
  - Reading Header: `"CURRENT READING\n============================\n\n"` ([`MainActivity.kt:L771`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L771))

---

## 14c. CSV Logging Trigger & UI Decoupling

- **UI Start Trigger:** [`MainActivity.kt:L165`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L165)
  `startButton.setOnClickListener { startCollection() }`
- **Execution Chain:**
  1. `startCollection()` ([`L358`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L358)): Clears `csvRows` list, adds Contract C1 header row, calls `collectSample()`, and schedules `collectionRunnable` every 3000 ms.
  2. `collectSample()` ([`L461`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L461)): Invokes `telephonyManager.requestCellInfoUpdate()`.
  3. `processCellInfo()` ([`L520`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L520)): Filters for `CellInfoNr` (prioritizing registered cell).
  4. `processNrCell()` ([`L605`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L605)): Extracts metrics, joins values into CSV comma-separated string `row`, and calls `csvRows.add(row)`.
  5. UI Display Update: `outputText.text = "CURRENT READING..."` updates the on-screen TextView from the extracted variables independently of `csvRows`.
- **UI Save Trigger:** [`MainActivity.kt:L185`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L185)
  `saveButton.setOnClickListener { saveCsv() }`
  - Writes `csvRows.joinToString("\n")` to `getExternalFilesDir(null)/5G_measurements_yyyyMMdd_HHmmss.csv` ([`L950`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L950)).
- **UI Decoupling Proof:** The CSV row generation logic (`processNrCell()`) and CSV storage list (`csvRows`) operate independently of the View hierarchy layout code (`createUI()`). A complete UI refactor (e.g. converting to Jetpack Compose) will not affect CSV generation as long as `startCollection()` and `saveCsv()` methods remain intact.

---

## 15. Telemetry Collection & File Export

- **Sampling Frequency:** Every 3000 ms (`SAMPLE_INTERVAL = 3000L`, [`MainActivity.kt:L53`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L53)).
- **Android Telephony APIs Used:**
  - `telephonyManager.registerTelephonyCallback` (Android 12+ `DisplayInfoListener`) for `TelephonyDisplayInfo.OVERRIDE_NETWORK_TYPE_NR_NSA` detection ([`L65-L85`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L65-L85)).
  - `telephonyManager.requestCellInfoUpdate()` for asynchronous 5G cell telemetry ([`L472`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L472)).
  - `CellInfoNr`, `CellSignalStrengthNr` (`ssRsrp`, `ssRsrq`, `ssSinr`, `csiRsrp`, `csiRsrq`, `csiSinr`), `CellIdentityNr` (`pci`, `nci`, `nrarfcn`).
- **CSV Header:** `timestamp,device,manufacturer,android,operator,network_type,deployment_mode,display_override,registered,ss_rsrp,ss_rsrq,ss_sinr,csi_rsrp,csi_rsrq,csi_sinr,pci,nci,nrarfcn` ([`L385-L391`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L385-L391)).
- **Timestamp Format:** `SimpleDateFormat("dd-MM-yy HH:mm:ss", Locale.getDefault()).format(Date())` ([`L621-L624`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L621-L624)).
- **Sentinel & Unavailable Value Handling:**
  - Functions `metricValue()`, `intMetricValue()`, `longMetricValue()` convert `Int.MAX_VALUE` (2147483647), `Int.MIN_VALUE`, `Long.MAX_VALUE`, `Long.MIN_VALUE` to `"NA"` ([`L813-L871`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L813-L871)).
- **File Naming & Location:**
  - Name: `5G_measurements_yyyyMMdd_HHmmss.csv` ([`L931-L937`](file:///d:/5G-Network-Anomaly-Detection-System/android-collector/5GNetworkTester/app/src/main/java/com/example/a5gnetworktester/MainActivity.kt#L931-L937)).
  - Location: App external files directory `getExternalFilesDir(null)` (e.g. `/storage/emulated/0/Android/data/com.example.a5gnetworktester/files/`).
- **File Export/Sharing:**
  - Devices are connected via USB MTP / ADB to pull saved files. No in-app Intent share or email export code exists.

---

## 16. Network Code Audit

- **Network Client Libraries:** **none**
  - No HTTP libraries (OkHttp, Ktor, Volley) or WebSocket clients exist in dependencies or source code. The Android collector app is 100% offline and file-based.

---

## 17. Screenshots Status

- **SKIPPED** — `adb` command was not available in PATH and no physical Android device or emulator was attached to the execution environment.
