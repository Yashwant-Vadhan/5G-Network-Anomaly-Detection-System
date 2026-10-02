# 5G Network Anomaly Detection System — Testing & Security Documentation

This document outlines the testing strategy, automated test coverage, and security/privacy checks implemented for the 5G Network Anomaly Detection System (5G-NADS).

---

## 1. Test Suite Summary

The automated test suite in `tests/` covers unit tests, integration tests, contract assertions, data preprocessing, feature engineering, classification rules, agent deterministic renderers, and security/privacy constraints.

For complete mapping of Guardrails G1–G16 to automated test suites, see [`docs/guardrails_checklist.md`](docs/guardrails_checklist.md).

| Test Module | Coverage / Focus | Guardrails Enforced |
|---|---|---|
| [`tests/test_preprocessing.py`](file:///d:/5G-Network-Anomaly-Detection-System/tests/test_preprocessing.py) | Raw CSV sanitisation, sentinel replacement, datetime parsing, idempotency | G7, G8 |
| [`tests/test_features.py`](file:///d:/5G-Network-Anomaly-Detection-System/tests/test_features.py) | Delta calculation, rolling window statistics, signal state flags | G1, G2, G3 |
| [`tests/test_classification.py`](file:///d:/5G-Network-Anomaly-Detection-System/tests/test_classification.py) | Negative case exclusions, 6 rule categories, precedence hierarchy | G5, G6 |
| [`tests/test_agents.py`](file:///d:/5G-Network-Anomaly-Detection-System/tests/test_agents.py) | Agent contract assertions, no sklearn imports in agents, non-causal text | G4, G9, G14 |
| [`tests/test_pipeline_integration.py`](file:///d:/5G-Network-Anomaly-Detection-System/tests/test_pipeline_integration.py) | End-to-end execution, Contract C2–C5 schema validation, offline determinism | G13 |
| [`tests/test_security_privacy.py`](file:///d:/5G-Network-Anomaly-Detection-System/tests/test_security_privacy.py) | PII column rejection, secret patterns, `.gitignore` rules, offline imports | G7, G13 |

---

## 2. Security and Privacy Audit (T7-009)

### 2.1 Automated Checks

1. **PII Column Rejection (Guardrail G49 / PRD §49):**
   - Direct rejection of forbidden columns (`phone`, `imsi`, `imei`, `lat`, `lon`, `msisdn`, `user_id`, `email`, `name`, `address`) via `ml.schema.assert_no_pii_columns`.
   - Verified by unit tests in [`tests/test_security_privacy.py`](file:///d:/5G-Network-Anomaly-Detection-System/tests/test_security_privacy.py).

2. **Zero-Network / Offline Operation (Guardrail G13):**
   - Core ML modules (`ml/`, `pipelines/`) are strictly offline.
   - Test `test_no_network_imports_in_core_pipeline` asserts no usage or imports of `requests`, `urllib`, `httpx`, `aiohttp`, or `socket`.

3. **Data & Artifact Isolation (Guardrail G7):**
   - Raw measurements, processed outputs, model artifacts, and environment files (`.env`, `*.key`, `*.pem`, `*.keystore`, `*.jks`) are strictly excluded via `.gitignore`.
   - Test `test_gitignore_covers_sensitive_files` enforces `.gitignore` rule completeness.

4. **Secret Scanning:**
   - Automated regex search in `test_no_hardcoded_secrets_in_repo` scans codebase for private keys, AWS access keys, GitHub tokens, and hardcoded secrets.

5. **Local Dashboard Isolation:**
   - Streamlit configuration binds to localhost (`127.0.0.1`) by default, preventing unintended network exposition over public IP interfaces (`0.0.0.0`).

---

## 3. Non-Applicable (N/A) Security Items

The following standard web application security items are classified as **Non-Applicable (N/A)** for the current MVP release:

| Security Domain | Status | Reason & Justification |
|---|---|---|
| **User Authentication (AuthN)** | N/A | 5G-NADS is a single-user desktop replay dashboard running locally. No user logins or identity providers are required. |
| **Role-Based Access Control (RBAC)** | N/A | Local file system access permissions dictate artifact availability. |
| **TLS / HTTPS Encryption** | N/A | Application operates locally over loopback (`127.0.0.1`). Transport encryption is not applicable for local IPC. |
| **API Rate Limiting** | N/A | Core pipeline runs as a standalone Python CLI. No public web APIs or webhooks are exposed. |
| **Cross-Origin Resource Sharing (CORS)** | N/A | Frontend (Streamlit) directly loads local CSV/JSON files without cross-origin HTTP API calls. |

---

## 4. Running the Test Suite

To run the complete test suite locally:

```bash
python -m pytest
```

---

## 5. Responsive & Accessibility Audit (T6-012)

A comprehensive responsive layout and accessibility verification was conducted across all six Streamlit dashboard pages (`dashboard/pages/`).

### 5.1 Responsive Breakpoint Verification

| Breakpoint | Target Screen | Audit Findings & Layout Adaptations | Status |
|---|---|---|---|
| **375 px** | Mobile Portrait (e.g. iPhone SE) | Streamlit sidebar collapses into top hamburger navigation; single-column container stacking prevents horizontal scroll blowout; Plotly charts scale down with touch drag/zoom enabled. | **PASS** |
| **768 px** | Tablet (e.g. iPad Portrait) | Metric cards adapt into 2-column flex rows; event detail cards and agent tabs remain legible without text truncation. | **PASS** |
| **1280 px** | Desktop / Laptop | Multi-column metric grid (4:8 Overview ratio, 6:6 Explorer split) renders cleanly at full density with responsive container widths (`use_container_width=True`). | **PASS** |

### 5.2 Accessibility & WCAG Compliance Checklist

1. **Use of Color (WCAG 1.4.1):**
   - Anomaly severity banners combine colored backgrounds with distinct Unicode indicator symbols (⚠️ for WARNING/MEDIUM, 🔴 for HIGH, ✅ for NORMAL).
   - Plotly scatter plots use distinct marker shapes (e.g., `symbol='x'` for anomaly points vs dots/lines for metrics) so colorblind users can distinguish flagged points independently of hue.

2. **Non-text Content Summaries (WCAG 1.1.1):**
   - Every Plotly chart across all pages includes a descriptive `st.caption` chart text summary directly below the figure explaining displayed metrics and marker meaning.

3. **Keyboard Navigation & Focus Visibility (WCAG 2.4.7):**
   - All interactive Streamlit components (replay position slider, device/operator selectboxes, page tabs, event dropdowns, data table expanders) respond to `Tab` focus navigation with high-contrast browser focus outlines.

