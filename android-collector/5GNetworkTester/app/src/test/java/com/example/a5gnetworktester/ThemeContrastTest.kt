package com.example.a5gnetworktester

import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow

/**
 * WCAG 2.1 AA Contrast Ratio Tests for 5G-NADS Theme Tokens (T19-005).
 * Formula per W3C specification: https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio
 */
class ThemeContrastTest {

    private fun parseHex(hex: String): Triple<Double, Double, Double> {
        val clean = hex.removePrefix("#")
        val r = clean.substring(0, 2).toInt(16) / 255.0
        val g = clean.substring(2, 4).toInt(16) / 255.0
        val b = clean.substring(4, 6).toInt(16) / 255.0
        return Triple(r, g, b)
    }

    private fun relativeLuminance(rgb: Triple<Double, Double, Double>): Double {
        fun channel(c: Double): Double =
            if (c <= 0.04045) c / 12.92 else ((c + 0.055) / 1.055).pow(2.4)

        val r = channel(rgb.first)
        val g = channel(rgb.second)
        val b = channel(rgb.third)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    }

    private fun contrastRatio(hex1: String, hex2: String): Double {
        val lum1 = relativeLuminance(parseHex(hex1))
        val lum2 = relativeLuminance(parseHex(hex2))
        val lighter = max(lum1, lum2)
        val darker = min(lum1, lum2)
        return (lighter + 0.05) / (darker + 0.05)
    }

    @Test
    fun lightTheme_textOnSurface_meetsWcagAA() {
        val ratio = contrastRatio("#0F172A", "#FFFFFF")
        assertTrue("Light text on surface ratio $ratio should be >= 4.5", ratio >= 4.5)
    }

    @Test
    fun lightTheme_textOnBackground_meetsWcagAA() {
        val ratio = contrastRatio("#0F172A", "#F8FAFC")
        assertTrue("Light text on background ratio $ratio should be >= 4.5", ratio >= 4.5)
    }

    @Test
    fun lightTheme_textMutedOnSurface_meetsWcagAA() {
        val ratio = contrastRatio("#475569", "#FFFFFF")
        assertTrue("Light muted text on surface ratio $ratio should be >= 4.5", ratio >= 4.5)
    }

    @Test
    fun lightTheme_textMutedOnBackground_meetsWcagAA() {
        val ratio = contrastRatio("#475569", "#F8FAFC")
        assertTrue("Light muted text on background ratio $ratio should be >= 4.5", ratio >= 4.5)
    }

    @Test
    fun darkTheme_textOnSurface_meetsWcagAA() {
        val ratio = contrastRatio("#F8FAFC", "#1E293B")
        assertTrue("Dark text on surface ratio $ratio should be >= 4.5", ratio >= 4.5)
    }

    @Test
    fun darkTheme_textOnBackground_meetsWcagAA() {
        val ratio = contrastRatio("#F8FAFC", "#0F172A")
        assertTrue("Dark text on background ratio $ratio should be >= 4.5", ratio >= 4.5)
    }

    @Test
    fun darkTheme_textMutedOnSurface_meetsWcagAA() {
        val ratio = contrastRatio("#94A3B8", "#1E293B")
        assertTrue("Dark muted text on surface ratio $ratio should be >= 4.5", ratio >= 4.5)
    }

    @Test
    fun darkTheme_textMutedOnBackground_meetsWcagAA() {
        val ratio = contrastRatio("#94A3B8", "#0F172A")
        assertTrue("Dark muted text on background ratio $ratio should be >= 4.5", ratio >= 4.5)
    }
}
