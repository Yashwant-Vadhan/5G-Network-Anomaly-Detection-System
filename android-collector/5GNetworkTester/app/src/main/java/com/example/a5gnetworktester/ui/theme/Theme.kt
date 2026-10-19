package com.example.a5gnetworktester.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val DarkColorScheme = darkColorScheme(
    primary = DarkPrimary,
    onPrimary = Color.White,
    primaryContainer = DarkSurfaceHover,
    onPrimaryContainer = DarkText,
    secondary = DarkPrimaryHover,
    onSecondary = Color.White,
    background = DarkBg,
    onBackground = DarkText,
    surface = DarkSurface,
    onSurface = DarkText,
    surfaceVariant = DarkSurfaceHover,
    onSurfaceVariant = DarkTextMuted,
    outline = DarkBorder,
    error = StatusAnomalyDark,
    onError = DarkBg
)

val LightColorScheme = lightColorScheme(
    primary = LightPrimary,
    onPrimary = Color.White,
    primaryContainer = LightSurfaceHover,
    onPrimaryContainer = LightText,
    secondary = LightPrimaryHover,
    onSecondary = Color.White,
    background = LightBg,
    onBackground = LightText,
    surface = LightSurface,
    onSurface = LightText,
    surfaceVariant = LightSurfaceHover,
    onSurfaceVariant = LightTextMuted,
    outline = LightBorder,
    error = StatusAnomalyLight,
    onError = Color.White
)

/**
 * 5G-NADS Collector theme composed from DESIGN tokens (T19-005).
 * Follows system dark/light theme setting by default.
 */
@Composable
fun _5GNetworkTesterTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColorScheme else LightColorScheme

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}