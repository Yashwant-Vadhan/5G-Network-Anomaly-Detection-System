package com.example.a5gnetworktester

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.a5gnetworktester.ui.theme.Spacing

/**
 * Compose Pairing Screen for Contract C10 phone pairing (T19-008).
 * Ensures tokens are never displayed or logged, and provides distinct failure messages.
 */
@Composable
fun PairingScreen(
    onPairSuccess: (sessionId: String) -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
    pairingClientFactory: (url: String) -> PairingClient = { url -> PairingClient(url) },
    tokenStorageSaver: (token: String) -> Unit = {}
) {
    var serverUrl by remember { mutableStateOf("http://localhost:8000") }
    var pairingCode by remember { mutableStateOf("") }
    var isLoading by remember { mutableStateOf(false) }
    var pairingResult by remember { mutableStateOf<PairingResult?>(null) }

    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = MaterialTheme.colorScheme.background
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(Spacing.md),
            verticalArrangement = Arrangement.spacedBy(Spacing.md)
        ) {
            Text(
                text = "Live Stream Pairing",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onBackground,
                fontWeight = FontWeight.Bold
            )

            Text(
                text = "Enter the 8-character pairing code shown on your 5G-NADS web dashboard.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            OutlinedTextField(
                value = serverUrl,
                onValueChange = { serverUrl = it },
                label = { Text("Server Base URL") },
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics { contentDescription = "Server URL input" },
                singleLine = true
            )

            OutlinedTextField(
                value = pairingCode,
                onValueChange = { input ->
                    val filtered = input.filter { it.isLetterOrDigit() }.uppercase()
                    if (filtered.length <= 8) {
                        pairingCode = filtered
                        pairingResult = null
                    }
                },
                label = { Text("Pairing Code (8 Characters)") },
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics { contentDescription = "Pairing code input, 8 alphanumeric characters" },
                singleLine = true,
                textStyle = MaterialTheme.typography.titleMedium.copy(
                    fontFamily = FontFamily.Monospace,
                    letterSpacing = 4.sp,
                    fontWeight = FontWeight.Bold
                ),
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.Characters
                )
            )

            // Result Alert Banner with distinct user-facing message per failure case
            pairingResult?.let { result ->
                val isSuccess = result is PairingResult.Success
                val bannerColor = if (isSuccess) {
                    MaterialTheme.colorScheme.primaryContainer
                } else {
                    MaterialTheme.colorScheme.error.copy(alpha = 0.15f)
                }
                val textColor = if (isSuccess) {
                    MaterialTheme.colorScheme.onPrimaryContainer
                } else {
                    MaterialTheme.colorScheme.error
                }

                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics { contentDescription = "Pairing status message" },
                    colors = CardDefaults.cardColors(containerColor = bannerColor)
                ) {
                    Text(
                        text = result.userFacingMessage(),
                        color = textColor,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.padding(Spacing.md)
                    )
                }
            }

            Spacer(modifier = Modifier.weight(1f))

            Button(
                onClick = {
                    isLoading = true
                    pairingResult = null
                    val client = pairingClientFactory(serverUrl)
                    Thread {
                        val result = client.pair(pairingCode)
                        isLoading = false
                        pairingResult = result

                        if (result is PairingResult.Success) {
                            // Securely store token without logging
                            tokenStorageSaver(result.ingestToken)
                            onPairSuccess(result.sessionId)
                        }
                    }.start()
                },
                enabled = pairingCode.length == 8 && !isLoading,
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 48.dp)
                    .semantics { contentDescription = "Pair mobile device button" },
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    contentColor = MaterialTheme.colorScheme.onPrimary
                )
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        color = MaterialTheme.colorScheme.onPrimary,
                        modifier = Modifier.height(24.dp)
                    )
                } else {
                    Text(text = "Pair Device", style = MaterialTheme.typography.labelLarge)
                }
            }
        }
    }
}
