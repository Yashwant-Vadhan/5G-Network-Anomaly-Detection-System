import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';

/**
 * Rule G30: Frontend source must contain no statistical or ML computational logic.
 * The React application is strictly a presentation and visualization layer.
 */
const FORBIDDEN_PATTERNS = [
  /\bisolation_?forest\b/i,
  /\bcompute_?if_?score\b/i,
  /\bcalculate_?if_?score\b/i,
  /\bdecision_function\b/i,
  /\bpredict_proba\b/i,
  /\bcompute_?z_?score\b/i,
  /\bcalculate_?z_?score\b/i,
  /\bcompute_?rolling\b/i,
  /\bcalculate_?rolling\b/i,
  /\bcalc_?rolling\b/i,
  /\brollingMean\b/i,
  /\brollingStd\b/i,
  /\bdetect_?transitions?\b/i,
  /\bdetectTransitions?\b/i,
  /\bdetect_?handovers?\b/i,
  /\bdetectHandovers?\b/i,
  /\bcompute_?transitions?\b/i,
  /\bcomputeTransitions?\b/i,
  /\bgroup_?events?\b/i,
  /\bgroupEvents?\b/i,
  /\bdetect_?events?\b/i,
  /\bdetectEvents?\b/i,
  /\bclassify_?anomal(?:y|ies)\b/i,
  /\bclassifyAnomal(?:y|ies)\b/i,
  /\bassign_?severity\b/i,
  /\bassignSeverity\b/i,
  /\bdiagnose_?events?\b/i,
  /\bdiagnoseEvents?\b/i,
  /\bgenerate_?diagnosis\b/i,
  /\bgenerateDiagnosis\b/i,
];

function getSourceFiles(dir: string): string[] {
  const results: string[] = [];
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...getSourceFiles(fullPath));
    } else if (
      (entry.name.endsWith('.ts') || entry.name.endsWith('.tsx')) &&
      !entry.name.endsWith('.test.ts') &&
      !entry.name.endsWith('.test.tsx') &&
      entry.name !== 'contracts.ts' &&
      entry.name !== 'setupTests.ts'
    ) {
      results.push(fullPath);
    }
  }
  return results;
}

describe('Rule G30: No-Logic Lint (T16-020)', () => {
  it('ensures frontend/src contains no forbidden computational or ML identifiers', () => {
    const srcDir = path.resolve(__dirname);
    const files = getSourceFiles(srcDir);
    expect(files.length).toBeGreaterThan(0);

    const violations: string[] = [];

    for (const file of files) {
      const content = fs.readFileSync(file, 'utf-8');
      for (const pattern of FORBIDDEN_PATTERNS) {
        const match = content.match(pattern);
        if (match) {
          violations.push(`Violation '${match[0]}' found in ${path.relative(srcDir, file)}`);
        }
      }
    }

    expect(violations).toEqual([]);
  });

  it('detects a forbidden identifier if introduced into a mock code snippet', () => {
    const mockSnippet = `
      export function detectTransitions(pciList: number[]) {
        return pciList.filter((p, i) => i > 0 && p !== pciList[i - 1]);
      }
    `;

    const found = FORBIDDEN_PATTERNS.some(p => p.test(mockSnippet));
    expect(found).toBe(true);
  });
});
