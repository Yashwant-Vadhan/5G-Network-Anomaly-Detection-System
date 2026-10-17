/**
 * Bundle Loader & Validator for Contract C11 (T16-008).
 *
 * Enforces version checks and schema integrity without stack traces.
 * Provides clear human-readable error messages and remediation text.
 */

import { DemoBundle } from '../types/contracts';

export interface BundleValidationResult {
  bundle: DemoBundle | null;
  error: string | null;
}

const REQUIRED_BUNDLE_KEYS = [
  'bundle_version',
  'generated_at',
  'model_version',
  'source',
  'privacy',
  'sessions',
  'samples',
  'transitions',
  'events',
  'quality',
] as const;

export function loadAndValidateBundle(raw: unknown): BundleValidationResult {
  if (raw === null || raw === undefined) {
    return {
      bundle: null,
      error:
        'Demo bundle data is missing or empty. Run `python scripts/build_demo_bundle.py --out frontend/public/data/demo_bundle.json` to generate it.',
    };
  }

  if (typeof raw !== 'object' || Array.isArray(raw)) {
    return {
      bundle: null,
      error:
        'Invalid demo bundle format (expected a JSON object). Please regenerate using `python scripts/build_demo_bundle.py`.',
    };
  }

  const obj = raw as Record<string, unknown>;

  // Check version
  const bundleVersion = obj['bundle_version'];
  if (typeof bundleVersion !== 'number' || bundleVersion < 1) {
    return {
      bundle: null,
      error: `Unsupported bundle version '${bundleVersion}'. Expected bundle_version 1. Please update your bundle using 'python scripts/build_demo_bundle.py'.`,
    };
  }

  // Check required keys
  for (const key of REQUIRED_BUNDLE_KEYS) {
    if (!(key in obj) || obj[key] === undefined || obj[key] === null) {
      return {
        bundle: null,
        error: `Invalid demo bundle: Missing required field '${key}'. Please build the demo bundle using 'python scripts/build_demo_bundle.py --out frontend/public/data/demo_bundle.json'.`,
      };
    }
  }

  // Validate sessions and samples structure
  if (!Array.isArray(obj['sessions'])) {
    return {
      bundle: null,
      error:
        "Invalid demo bundle: 'sessions' must be an array. Please regenerate using 'python scripts/build_demo_bundle.py'.",
    };
  }

  const samples = obj['samples'] as Record<string, unknown>;
  if (
    typeof samples !== 'object' ||
    !Array.isArray(samples['columns']) ||
    !Array.isArray(samples['rows'])
  ) {
    return {
      bundle: null,
      error:
        "Invalid demo bundle: 'samples' must contain 'columns' and 'rows' arrays. Please regenerate using 'python scripts/build_demo_bundle.py'.",
    };
  }

  return {
    bundle: raw as DemoBundle,
    error: null,
  };
}

export async function fetchDemoBundle(
  url = '/data/demo_bundle.json'
): Promise<BundleValidationResult> {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      return {
        bundle: null,
        error: `Could not load demo bundle (HTTP ${response.status} from ${url}). Ensure the bundle exists by running 'python scripts/build_demo_bundle.py --out frontend/public/data/demo_bundle.json'.`,
      };
    }
    const data = await response.json();
    return loadAndValidateBundle(data);
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    return {
      bundle: null,
      error: `Failed to fetch demo bundle from ${url} (${msg}). Run 'python scripts/build_demo_bundle.py --out frontend/public/data/demo_bundle.json'.`,
    };
  }
}
