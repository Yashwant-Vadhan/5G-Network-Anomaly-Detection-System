package com.example.a5gnetworktester

import android.app.Activity
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.core.content.FileProvider
import java.io.File
import java.io.InputStream

/**
 * Handles exporting and sharing saved CSV telemetry logs via Android share intent (T19-011).
 *
 * Implements:
 * 1. FileProvider content URI generation adhering to current Android security best practices.
 * 2. Intent.ACTION_SEND with MIME type "text/csv", ClipData for granted URI permissions,
 *    and Intent.createChooser supporting Drive, WhatsApp, Gmail, etc.
 * 3. Parity verification confirming the shared file equals the saved file byte-for-byte.
 */
object CsvShareHelper {

    const val MIME_TYPE_CSV = "text/csv"

    /**
     * Builds the standard ACTION_SEND Intent with FileProvider URI, clip data, and permissions.
     */
    fun createShareIntent(
        context: Context,
        file: File,
        subject: String? = null,
        chooserTitle: String = "Share 5G Telemetry CSV"
    ): Intent {
        require(file.exists()) { "Cannot share non-existent file: ${file.absolutePath}" }

        val uri = getFileUri(context, file)
        val shareSubject = subject ?: "5G Network Telemetry - ${file.name}"
        val shareText = "Exported 5G network telemetry CSV log (${file.name})"

        val sendIntent = Intent(Intent.ACTION_SEND).apply {
            type = MIME_TYPE_CSV
            putExtra(Intent.EXTRA_STREAM, uri)
            putExtra(Intent.EXTRA_SUBJECT, shareSubject)
            putExtra(Intent.EXTRA_TEXT, shareText)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            // ClipData ensures URI read permissions propagate properly on Android 10+
            clipData = ClipData.newRawUri("5G Telemetry CSV", uri)
        }

        return Intent.createChooser(sendIntent, chooserTitle).apply {
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
    }

    /**
     * Obtains a secure content URI using androidx.core.content.FileProvider.
     */
    fun getFileUri(context: Context, file: File): Uri {
        return FileProvider.getUriForFile(
            context,
            "${context.packageName}.provider",
            file
        )
    }

    /**
     * Launches the system share chooser for the given CSV file.
     * Returns true if the chooser activity was successfully started, false otherwise.
     */
    fun shareCsvFile(
        activity: Activity,
        file: File,
        subject: String? = null,
        chooserTitle: String = "Share 5G Telemetry CSV"
    ): Boolean {
        return try {
            val chooserIntent = createShareIntent(activity, file, subject, chooserTitle)
            activity.startActivity(chooserIntent)
            true
        } catch (_: Exception) {
            false
        }
    }

    /**
     * Verifies that the shared file contents match the saved file byte-for-byte (Acceptance Criterion 2).
     */
    fun verifySharedFileMatches(savedFile: File, sharedStream: InputStream): Boolean {
        if (!savedFile.exists() || !savedFile.canRead()) return false
        val savedBytes = savedFile.readBytes()
        val sharedBytes = sharedStream.use { it.readBytes() }
        return savedBytes.contentEquals(sharedBytes)
    }

    /**
     * Verifies that the shared byte array matches the saved file byte-for-byte.
     */
    fun verifySharedFileMatches(savedFile: File, sharedBytes: ByteArray): Boolean {
        if (!savedFile.exists() || !savedFile.canRead()) return false
        val savedBytes = savedFile.readBytes()
        return savedBytes.contentEquals(sharedBytes)
    }
}
