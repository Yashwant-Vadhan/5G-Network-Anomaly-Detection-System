# 5G Network Anomaly Detection System — Testing & Security Documentation

This document outlines the testing strategy, automated test coverage, and security/privacy checks implemented for the 5G Network Anomaly Detection System (5G-NADS).

---

## 1. Test Suite Summary

The automated test suite in `tests/` covers unit tests, integration tests, contract assertions, data preprocessing, feature engineering, classification rules, agent deterministic renderers, and security/privacy constraints.

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
