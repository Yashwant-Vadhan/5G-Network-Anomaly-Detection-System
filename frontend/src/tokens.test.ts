import { describe, it, expect } from 'vitest';

/**
 * WCAG 2.1 AA Relative Luminance & Contrast Ratio calculation.
 * Formula per W3C specification: https://www.w3.org/TR/WCAG21/#dfn-contrast-ratio
 */
function parseHexColor(hex: string): [number, number, number] {
  const clean = hex.replace('#', '');
  const r = parseInt(clean.substring(0, 2), 16);
  const g = parseInt(clean.substring(2, 4), 16);
  const b = parseInt(clean.substring(4, 6), 16);
  return [r, g, b];
}

function getRelativeLuminance(rgb: [number, number, number]): number {
  const [rs, gs, bs] = rgb.map(val => {
    const s = val / 255;
    return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * rs + 0.7152 * gs + 0.0722 * bs;
}

function getContrastRatio(color1: string, color2: string): number {
  const lum1 = getRelativeLuminance(parseHexColor(color1));
  const lum2 = getRelativeLuminance(parseHexColor(color2));
  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);
  return (lighter + 0.05) / (darker + 0.05);
}

describe('Design Tokens & Accessibility Contrast (T16-007)', () => {
  const TOKENS = {
    light: {
      bg: '#F8FAFC',
      surface: '#FFFFFF',
      text: '#0F172A',
      textMuted: '#475569',
      normal: '#15803D',
      warning: '#B45309',
      anomaly: '#DC2626',
      info: '#0369A1',
      neutral700: '#334155',
    },
    dark: {
      bg: '#0F172A',
      surface: '#1E293B',
      text: '#F8FAFC',
      textMuted: '#94A3B8',
      normal: '#22C55E',
      warning: '#F59E0B',
      anomaly: '#EF4444',
      info: '#38BDF8',
      neutral700: '#CBD5E1',
    },
  };

  it('verifies light theme text on surface contrast >= 4.5:1 (WCAG AA)', () => {
    const ratio = getContrastRatio(TOKENS.light.text, TOKENS.light.surface);
    expect(ratio).toBeGreaterThanOrEqual(4.5);
    expect(ratio).toBeGreaterThan(15.0); // Actual ~17.5:1
  });

  it('verifies light theme text on background contrast >= 4.5:1 (WCAG AA)', () => {
    const ratio = getContrastRatio(TOKENS.light.text, TOKENS.light.bg);
    expect(ratio).toBeGreaterThanOrEqual(4.5);
    expect(ratio).toBeGreaterThan(14.0); // Actual ~16.8:1
  });

  it('verifies light theme muted text on surface contrast >= 4.5:1 (WCAG AA)', () => {
    const ratio = getContrastRatio(TOKENS.light.textMuted, TOKENS.light.surface);
    expect(ratio).toBeGreaterThanOrEqual(4.5);
    expect(ratio).toBeGreaterThan(7.0); // Actual ~7.4:1
  });

  it('verifies light theme muted text on background contrast >= 4.5:1 (WCAG AA)', () => {
    const ratio = getContrastRatio(TOKENS.light.textMuted, TOKENS.light.bg);
    expect(ratio).toBeGreaterThanOrEqual(4.5);
    expect(ratio).toBeGreaterThan(6.5); // Actual ~7.1:1
  });

  it('verifies dark theme text on surface contrast >= 4.5:1 (WCAG AA)', () => {
    const ratio = getContrastRatio(TOKENS.dark.text, TOKENS.dark.surface);
    expect(ratio).toBeGreaterThanOrEqual(4.5);
    expect(ratio).toBeGreaterThan(12.0); // Actual ~13.5:1
  });

  it('verifies dark theme text on background contrast >= 4.5:1 (WCAG AA)', () => {
    const ratio = getContrastRatio(TOKENS.dark.text, TOKENS.dark.bg);
    expect(ratio).toBeGreaterThanOrEqual(4.5);
    expect(ratio).toBeGreaterThan(15.0); // Actual ~18.0:1
  });

  it('verifies dark theme muted text on surface contrast >= 4.5:1 (WCAG AA)', () => {
    const ratio = getContrastRatio(TOKENS.dark.textMuted, TOKENS.dark.surface);
    expect(ratio).toBeGreaterThanOrEqual(4.5);
    expect(ratio).toBeGreaterThan(5.0); // Actual ~5.5:1
  });

  it('verifies dark theme muted text on background contrast >= 4.5:1 (WCAG AA)', () => {
    const ratio = getContrastRatio(TOKENS.dark.textMuted, TOKENS.dark.bg);
    expect(ratio).toBeGreaterThanOrEqual(4.5);
    expect(ratio).toBeGreaterThan(6.0); // Actual ~6.8:1
  });
});
