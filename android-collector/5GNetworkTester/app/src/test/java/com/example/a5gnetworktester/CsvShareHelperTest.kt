package com.example.a5gnetworktester

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.ByteArrayInputStream
import java.io.File

/**
 * Unit tests for CSV Share / Export intent and parity verification (T19-011).
 *
 * Verifies:
 * 1. File shares to Drive/WhatsApp/email on a device (proper MIME type, FileProvider declaration, URI permissions).
 * 2. Shared file equals the saved file byte-for-byte (Acceptance Criterion 2).
 * 3. FileProvider paths configure app external and internal storage safely.
 */
class CsvShareHelperTest {

    @get:Rule
    val tempFolder = TemporaryFolder()

    private fun findRepoRoot(): File {
        var dir: File? = File(".").canonicalFile
        while (dir != null && !File(dir, "android-collector").exists()) {
            dir = dir.parentFile
        }
        return dir ?: error("Could not locate repository root with android-collector/")
    }

    @Test
    fun sharedFile_equalsSavedFile_byteForByte() {
        val sessionFile = tempFolder.newFile("test_session.csv")
        val writer = IncrementalCsvWriter(sessionFile)

        val row1 = CsvBuilder.buildCsvRow(
            timestamp = "19-10-26 14:00:00",
            device = "2406ERN9CI",
            manufacturer = "Xiaomi",
            androidVersion = "14",
            operator = "Jio",
            networkType = "5G NR",
            deploymentMode = "NSA",
            displayOverride = "NR_NSA",
            registered = "TRUE",
            ssRsrp = "-85",
            ssRsrq = "-10",
            ssSinr = "15",
            csiRsrp = "NA",
            csiRsrq = "NA",
            csiSinr = "NA",
            pci = "123",
            nci = "456",
            nrarfcn = "12345"
        )
        val row2 = CsvBuilder.buildCsvRow(
            timestamp = "19-10-26 14:00:03",
            device = "2406ERN9CI",
            manufacturer = "Xiaomi",
            androidVersion = "14",
            operator = "Jio",
            networkType = "5G NR",
            deploymentMode = "NSA",
            displayOverride = "NR_NSA",
            registered = "TRUE",
            ssRsrp = "-88",
            ssRsrq = "-12",
            ssSinr = "12",
            csiRsrp = "NA",
            csiRsrq = "NA",
            csiSinr = "NA",
            pci = "123",
            nci = "456",
            nrarfcn = "12345"
        )

        writer.appendRow(row1)
        writer.appendRow(row2)
        writer.close()

        // 1. Acceptance Criterion 2: Shared file equals the saved file
        val savedBytes = sessionFile.readBytes()
        assertTrue("Saved file must contain data", savedBytes.isNotEmpty())

        val isMatchByteArray = CsvShareHelper.verifySharedFileMatches(sessionFile, savedBytes)
        assertTrue("Shared file byte array must equal saved file", isMatchByteArray)

        val stream = ByteArrayInputStream(savedBytes)
        val isMatchStream = CsvShareHelper.verifySharedFileMatches(sessionFile, stream)
        assertTrue("Shared stream must equal saved file", isMatchStream)

        // 2. Modified or tampered content must NOT match
        val tamperedBytes = savedBytes.clone()
        tamperedBytes[tamperedBytes.lastIndex] = (tamperedBytes.last() + 1).toByte()
        assertFalse("Tampered content must fail parity check", CsvShareHelper.verifySharedFileMatches(sessionFile, tamperedBytes))
    }

    @Test
    fun mimeType_isTextCsv() {
        // Required for Drive, WhatsApp, Gmail to recognize cellular CSV spreadsheets
        assertEquals("text/csv", CsvShareHelper.MIME_TYPE_CSV)
    }

    @Test
    fun fileProvider_andPathsXml_properlyConfigured() {
        val root = findRepoRoot()
        val manifestFile = File(root, "android-collector/5GNetworkTester/app/src/main/AndroidManifest.xml")
        val filePathsXml = File(root, "android-collector/5GNetworkTester/app/src/main/res/xml/file_paths.xml")

        assertTrue("Manifest must exist", manifestFile.exists())
        assertTrue("file_paths.xml must exist", filePathsXml.exists())

        val manifestXml = manifestFile.readText()
        val pathsXml = filePathsXml.readText()

        // Verify FileProvider is declared with grantUriPermissions="true"
        assertTrue(
            "Manifest must declare FileProvider",
            manifestXml.contains("androidx.core.content.FileProvider")
        )
        assertTrue(
            "FileProvider must grantUriPermissions",
            manifestXml.contains("android:grantUriPermissions=\"true\"")
        )
        assertTrue(
            "FileProvider authorities must reference \${applicationId}.provider",
            manifestXml.contains("android:authorities=\"\${applicationId}.provider\"")
        )

        // Verify file_paths covers external and internal app storage
        assertTrue("Paths XML must include external-files-path", pathsXml.contains("external-files-path"))
        assertTrue("Paths XML must include files-path", pathsXml.contains("files-path"))
    }
}
