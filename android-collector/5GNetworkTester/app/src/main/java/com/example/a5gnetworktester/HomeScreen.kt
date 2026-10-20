package com.example.a5gnetworktester

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.a5gnetworktester.ui.theme.DarkPrimary
import com.example.a5gnetworktester.ui.theme.LightPrimary
import com.example.a5gnetworktester.ui.theme.Spacing
import com.example.a5gnetworktester.ui.theme.StatusNormalDark
import com.example.a5gnetworktester.ui.theme.StatusNormalLight

/**
 * Compose Home Screen for 5G-NADS Collector (T19-006, Guardrail G9).
 *
 * Implements:
 * 1. Logging and Streaming status indicators (icon + word).
 * 2. SS-RSRP, SS-RSRQ, and SS-SINR telemetry cards.
 * 3. Network type / deployment mode chip.
 * 4. Sample counter.
 * 5. Start / Stop collection controls with minimum touch targets >= 48dp.
 * 6. Explicit TalkBack labels on all controls.
 * 7. Strictly NO anomaly verdicts on the phone (Guardrail G9).
 */
@Composable
fun HomeScreen(
    uiState: UiState,
    isStreaming: Boolean,
    onStartClick: () -> Unit,
    onStopClick: () -> Unit,
    onSaveCsvClick: () -> Unit,
    onNavigatePairing: () -> Unit,
    onNavigateConsent: () -> Unit,
    modifier: Modifier = Modifier
) {
    Scaffold(
        modifier = modifier.fillMaxSize(),
        containerColor = MaterialTheme.colorScheme.background
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = Spacing.md, vertical = Spacing.sm),
            verticalArrangement = Arrangement.spacedBy(Spacing.md)
        ) {
            // Header Bar
            HeaderBar(
                onNavigatePairing = onNavigatePairing,
                onNavigateConsent = onNavigateConsent
            )

            // Status Strip: Logging & Streaming (icon + word)
            StatusStrip(
                isCollecting = uiState.isCollecting,
                isStreaming = isStreaming
            )

            // Network Type Chip & Sample Counter Row
            NetworkInfoRow(
                deploymentMode = uiState.deploymentMode,
                sampleCount = uiState.sampleCount
            )

            // SS-RSRP, SS-RSRQ, SS-SINR Metric Cards
            SignalMetricCards(reading = uiState.latestReading)

            // Detailed Identifiers / Current Status
            DetailsSection(
                reading = uiState.latestReading,
                statusMessage = uiState.statusMessage
            )

            Spacer(modifier = Modifier.weight(1f, fill = false))

            // Control Buttons (Start/Stop and Save CSV)
            ControlBar(
                isCollecting = uiState.isCollecting,
                sampleCount = uiState.sampleCount,
                onStartClick = onStartClick,
                onStopClick = onStopClick,
                onSaveCsvClick = onSaveCsvClick
            )
        }
    }
}

@Composable
private fun HeaderBar(
    onNavigatePairing: () -> Unit,
    onNavigateConsent: () -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Column {
            Text(
                text = stringResource(R.string.app_name),
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onBackground,
                fontWeight = FontWeight.Bold
            )
            Text(
                text = "5G Telemetry Engine",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        Row(horizontalArrangement = Arrangement.spacedBy(Spacing.xs)) {
            OutlinedButton(
                onClick = onNavigatePairing,
                modifier = Modifier
                    .heightIn(min = 48.dp)
                    .semantics { contentDescription = "Open pairing screen" },
                shape = RoundedCornerShape(8.dp)
            ) {
                Text(text = stringResource(R.string.btn_pairing), style = MaterialTheme.typography.labelMedium)
            }

            OutlinedButton(
                onClick = onNavigateConsent,
                modifier = Modifier
                    .heightIn(min = 48.dp)
                    .semantics { contentDescription = "Open privacy consent screen" },
                shape = RoundedCornerShape(8.dp)
            ) {
                Text(text = stringResource(R.string.btn_privacy), style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}

@Composable
private fun StatusStrip(
    isCollecting: Boolean,
    isStreaming: Boolean
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(12.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(Spacing.md),
            horizontalArrangement = Arrangement.SpaceAround,
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Logging Status Indicator (Icon + Word)
            val loggingLabel = if (isCollecting) {
                stringResource(R.string.logging_active)
            } else {
                stringResource(R.string.logging_idle)
            }
            val loggingColor = if (isCollecting) StatusNormalLight else Color.Gray

            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.semantics {
                    contentDescription = "Logging status: $loggingLabel"
                }
            ) {
                Box(
                    modifier = Modifier
                        .size(12.dp)
                        .clip(CircleShape)
                        .background(loggingColor)
                )
                Spacer(modifier = Modifier.width(Spacing.xs))
                Text(
                    text = loggingLabel,
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }

            // Divider Dot
            Text("•", color = MaterialTheme.colorScheme.outline)

            // Streaming Status Indicator (Icon + Word)
            val streamingLabel = if (isStreaming) {
                stringResource(R.string.streaming_active)
            } else {
                stringResource(R.string.streaming_idle)
            }
            val streamingColor = if (isStreaming) LightPrimary else Color.Gray

            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.semantics {
                    contentDescription = "Streaming status: $streamingLabel"
                }
            ) {
                Box(
                    modifier = Modifier
                        .size(12.dp)
                        .clip(CircleShape)
                        .background(streamingColor)
                )
                Spacer(modifier = Modifier.width(Spacing.xs))
                Text(
                    text = streamingLabel,
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }
        }
    }
}

@Composable
private fun NetworkInfoRow(
    deploymentMode: String,
    sampleCount: Int
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        // Network Type Chip
        val chipText = when (deploymentMode) {
            "NSA" -> stringResource(R.string.network_nr_nsa)
            "SA" -> stringResource(R.string.network_nr_sa)
            "LTE" -> stringResource(R.string.network_lte)
            else -> deploymentMode.ifEmpty { stringResource(R.string.network_unknown) }
        }

        Surface(
            color = MaterialTheme.colorScheme.primaryContainer,
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier
                .heightIn(min = 36.dp)
                .semantics { contentDescription = "Network deployment mode: $chipText" }
        ) {
            Row(
                modifier = Modifier.padding(horizontal = Spacing.md, vertical = Spacing.xs),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Mode: $chipText",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onPrimaryContainer,
                    fontWeight = FontWeight.Bold
                )
            }
        }

        // Sample Counter
        Surface(
            color = MaterialTheme.colorScheme.surfaceVariant,
            shape = RoundedCornerShape(16.dp),
            modifier = Modifier
                .heightIn(min = 36.dp)
                .semantics { contentDescription = "Total samples collected: $sampleCount" }
        ) {
            Row(
                modifier = Modifier.padding(horizontal = Spacing.md, vertical = Spacing.xs),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = stringResource(R.string.samples_counter, sampleCount),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    fontWeight = FontWeight.Medium
                )
            }
        }
    }
}

@Composable
private fun SignalMetricCards(reading: TelemetryReading?) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(Spacing.sm)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(Spacing.sm)
        ) {
            // SS-RSRP Card
            MetricCard(
                title = stringResource(R.string.metric_rsrp_title),
                subtitle = stringResource(R.string.metric_rsrp_subtitle),
                value = reading?.let { formatValueWithUnit(it.ssRsrp, "dBm") } ?: "NA",
                modifier = Modifier.weight(1f)
            )

            // SS-RSRQ Card
            MetricCard(
                title = stringResource(R.string.metric_rsrq_title),
                subtitle = stringResource(R.string.metric_rsrq_subtitle),
                value = reading?.let { formatValueWithUnit(it.ssRsrq, "dB") } ?: "NA",
                modifier = Modifier.weight(1f)
            )
        }

        // SS-SINR Card
        MetricCard(
            title = stringResource(R.string.metric_sinr_title),
            subtitle = stringResource(R.string.metric_sinr_subtitle),
            value = reading?.let { formatValueWithUnit(it.ssSinr, "dB") } ?: "NA",
            modifier = Modifier.fillMaxWidth()
        )
    }
}

@Composable
private fun MetricCard(
    title: String,
    subtitle: String,
    value: String,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier.semantics {
            contentDescription = "$title: $value ($subtitle)"
        },
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(
            modifier = Modifier.padding(Spacing.md)
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface
            )
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(modifier = Modifier.height(Spacing.xs))
            Text(
                text = value,
                style = MaterialTheme.typography.headlineMedium.copy(
                    fontSize = 24.sp,
                    fontFamily = FontFamily.Monospace
                ),
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.primary
            )
        }
    }
}

@Composable
private fun DetailsSection(
    reading: TelemetryReading?,
    statusMessage: String?
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(
            modifier = Modifier.padding(Spacing.md),
            verticalArrangement = Arrangement.spacedBy(Spacing.xs)
        ) {
            Text(
                text = "Cell Identity & Hardware",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = MaterialTheme.colorScheme.onSurface
            )

            if (reading != null) {
                DetailRow("Operator", reading.operator)
                DetailRow("Device", "${reading.manufacturer} ${reading.device}")
                DetailRow("PCI", reading.pci)
                DetailRow("NCI", reading.nci)
                DetailRow("NR-ARFCN", reading.nrarfcn)
                DetailRow("Timestamp", reading.timestamp)
            } else {
                Text(
                    text = statusMessage ?: stringResource(R.string.waiting_measurement),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
            color = MaterialTheme.colorScheme.onSurface,
            fontWeight = FontWeight.Medium
        )
    }
}

@Composable
private fun ControlBar(
    isCollecting: Boolean,
    sampleCount: Int,
    onStartClick: () -> Unit,
    onStopClick: () -> Unit,
    onSaveCsvClick: () -> Unit
) {
    val cdStart = stringResource(R.string.cd_start_collection)
    val cdStop = stringResource(R.string.cd_stop_collection)
    val cdSave = stringResource(R.string.cd_save_csv)

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(Spacing.sm)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(Spacing.sm)
        ) {
            if (!isCollecting) {
                Button(
                    onClick = onStartClick,
                    modifier = Modifier
                        .then(if (sampleCount > 0) Modifier.weight(1f) else Modifier.fillMaxWidth())
                        .heightIn(min = 48.dp)
                        .semantics { contentDescription = cdStart },
                    colors = ButtonDefaults.buttonColors(containerColor = LightPrimary),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text(
                        text = stringResource(R.string.btn_start),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                }

                if (sampleCount > 0) {
                    OutlinedButton(
                        onClick = onSaveCsvClick,
                        modifier = Modifier
                            .weight(1f)
                            .heightIn(min = 48.dp)
                            .semantics { contentDescription = cdSave },
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text(
                            text = stringResource(R.string.btn_save_csv),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            } else {
                Button(
                    onClick = onStopClick,
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 48.dp)
                        .semantics { contentDescription = cdStop },
                    colors = ButtonDefaults.buttonColors(containerColor = MaterialTheme.colorScheme.error),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text(
                        text = stringResource(R.string.btn_stop),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

/**
 * Helper to format metric value with its unit, preserving "NA".
 */
fun formatValueWithUnit(value: String, unit: String): String {
    return if (value.equals("NA", ignoreCase = true) || value.isBlank()) {
        "NA"
    } else {
        "$value $unit"
    }
}
