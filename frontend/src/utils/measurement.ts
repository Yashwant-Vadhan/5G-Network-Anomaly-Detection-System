/**
 * Central measurement validity and formatting utilities.
 * Handles null, undefined, NaN, infinite, and sentinel values (2147483647).
 */

export function isValidMeasurement(val: unknown): boolean {
  if (
    val === null ||
    val === undefined ||
    val === '' ||
    val === 'nan' ||
    val === 'NaN' ||
    val === 'NA' ||
    val === '<NA>' ||
    val === 'None' ||
    val === 2147483647 ||
    val === '2147483647'
  ) {
    return false;
  }
  if (typeof val === 'number') {
    return !Number.isNaN(val) && Number.isFinite(val);
  }
  const num = Number(val);
  return !Number.isNaN(num) && Number.isFinite(num);
}

export function formatVal(
  val: unknown,
  unit: string = '',
  decimals: number = 1
): string {
  if (!isValidMeasurement(val)) {
    return '—';
  }
  const num = Number(val);
  return `${num.toFixed(decimals)} ${unit}`.trim();
}

export function calcDelta(
  curr: unknown,
  prev: unknown,
  decimals: number = 1
): string | null {
  if (!isValidMeasurement(curr) || !isValidMeasurement(prev)) {
    return null;
  }
  const c = Number(curr);
  const p = Number(prev);
  const diff = c - p;
  const sign = diff >= 0 ? '+' : '';
  return `${sign}${diff.toFixed(decimals)}`;
}
