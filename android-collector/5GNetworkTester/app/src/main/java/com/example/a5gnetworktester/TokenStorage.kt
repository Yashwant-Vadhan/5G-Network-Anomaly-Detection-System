package com.example.a5gnetworktester

import android.content.Context
import android.util.Base64
import java.security.SecureRandom
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Secure, encrypted storage abstraction for ephemeral ingest tokens (T19-008).
 * Ensures tokens are encrypted with AES-256-GCM and NEVER stored in plaintext or logged.
 */
class TokenStorage(private val context: Context) {

    companion object {
        private const val PREFS_NAME = "5g_nads_secure_token_prefs"
        private const val KEY_ENCRYPTED_TOKEN = "enc_ingest_token"
        private const val KEY_IV = "token_iv"
        private const val KEY_RAW_KEY = "master_key_enc"
        private const val GCM_TAG_LENGTH_BITS = 128
        private const val GCM_IV_LENGTH_BYTES = 12
        private const val AES_KEY_SIZE_BITS = 256
    }

    private val secureRandom = SecureRandom()

    private fun getOrCreateSecretKey(): SecretKey {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val storedKeyBase64 = prefs.getString(KEY_RAW_KEY, null)
        if (storedKeyBase64 != null) {
            val keyBytes = Base64.decode(storedKeyBase64, Base64.DEFAULT)
            return SecretKeySpec(keyBytes, "AES")
        }

        val keyGen = KeyGenerator.getInstance("AES")
        keyGen.init(AES_KEY_SIZE_BITS, secureRandom)
        val newKey = keyGen.generateKey()
        val encodedKey = Base64.encodeToString(newKey.encoded, Base64.DEFAULT)
        prefs.edit().putString(KEY_RAW_KEY, encodedKey).apply()
        return newKey
    }

    /**
     * Encrypts and stores the ingest token. The token is never logged or exposed.
     */
    fun saveIngestToken(token: String) {
        val key = getOrCreateSecretKey()
        val iv = ByteArray(GCM_IV_LENGTH_BYTES)
        secureRandom.nextBytes(iv)

        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        val spec = GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv)
        cipher.init(Cipher.ENCRYPT_MODE, key, spec)

        val encryptedBytes = cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        val encBase64 = Base64.encodeToString(encryptedBytes, Base64.DEFAULT)
        val ivBase64 = Base64.encodeToString(iv, Base64.DEFAULT)

        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit()
            .putString(KEY_ENCRYPTED_TOKEN, encBase64)
            .putString(KEY_IV, ivBase64)
            .apply()
    }

    /**
     * Decrypts and retrieves the stored ingest token, or null if none exists.
     */
    fun getIngestToken(): String? {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val encBase64 = prefs.getString(KEY_ENCRYPTED_TOKEN, null) ?: return null
        val ivBase64 = prefs.getString(KEY_IV, null) ?: return null

        return try {
            val key = getOrCreateSecretKey()
            val encBytes = Base64.decode(encBase64, Base64.DEFAULT)
            val iv = Base64.decode(ivBase64, Base64.DEFAULT)

            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            val spec = GCMParameterSpec(GCM_TAG_LENGTH_BITS, iv)
            cipher.init(Cipher.DECRYPT_MODE, key, spec)

            val decryptedBytes = cipher.doFinal(encBytes)
            String(decryptedBytes, Charsets.UTF_8)
        } catch (_: Exception) {
            null
        }
    }

    /**
     * Checks if a valid token is present without decrypting into memory.
     */
    fun hasToken(): Boolean {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.contains(KEY_ENCRYPTED_TOKEN) && prefs.contains(KEY_IV)
    }

    /**
     * Securely deletes the token upon session termination.
     */
    fun clearToken() {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit()
            .remove(KEY_ENCRYPTED_TOKEN)
            .remove(KEY_IV)
            .apply()
    }
}
