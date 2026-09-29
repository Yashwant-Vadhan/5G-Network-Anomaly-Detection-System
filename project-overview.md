# 5G Network Anomaly Detection and Intelligent Diagnosis System

## 1. Project Title

**5G Network Anomaly Detection and Intelligent Diagnosis Using Real-Time NR Measurements and Multi-Agent Analysis**

### Short Title

**5G-NADS — 5G Network Anomaly Detection System**

### Project Type

AI/ML + Mobile Network Monitoring + Anomaly Detection + Multi-Agent System + Dashboard

---

# 2. Project Overview

5G networks are increasingly used for applications that require reliable and responsive connectivity, including smart transportation, remote services, industrial systems, education, emergency communication, IoT, and other connected services.

Network conditions can change dynamically because of factors such as:

* weak radio signal
* interference
* congestion
* cell transitions
* changing radio conditions
* temporary loss of 5G service
* abnormal combinations of network measurements

A system that can continuously monitor 5G radio measurements and identify unusual behavior can provide an early indication of potential connectivity degradation.

This project develops a **5G Network Anomaly Detection and Intelligent Diagnosis System** that collects real 5G NR measurements from Android smartphones, stores them as time-series data, preprocesses the measurements, detects anomalous patterns using machine learning, classifies the likely nature of the abnormal behavior, and provides a diagnosis and recommendation through a multi-agent analysis layer.

The Android application is responsible for the **real 5G NR measurement and data-collection layer**.

The machine-learning and multi-agent components operate separately on the collected dataset.

---

# 3. Core Objective

The primary objective is:

> **To detect unusual temporal patterns in real 5G NR radio measurements and provide an interpretable diagnosis and recommendation for the observed network condition.**

The system should not simply classify a single measurement as "bad."

Instead, it should consider:

* signal strength
* signal quality
* signal-to-interference-plus-noise ratio
* cell identity
* cell transitions
* network-state changes
* temporal behavior
* device/operator context

to determine whether a sequence of measurements represents unusual network behavior.

---

# 4. Societal Relevance

Reliable mobile connectivity is increasingly important for digital services and connected systems.

Potential areas affected by network degradation include:

### 4.1 Emergency Communication

Emergency communication depends on reliable connectivity for voice, messaging, location services, and data-based emergency applications.

### 4.2 Remote and Digital Services

Poor connectivity can affect remote consultation, digital services, and other applications that depend on continuous network access.

### 4.3 Education

Online classes, digital learning platforms, video conferencing, and cloud-based educational applications can be affected by unstable connectivity.

### 4.4 Transportation

Connected transportation systems can depend on mobile connectivity for communication, monitoring, and data exchange.

### 4.5 Smart Cities and IoT

Large numbers of connected devices can depend on reliable wireless communication.

### 4.6 Public and Industrial Infrastructure

Network anomalies can affect connected monitoring systems and other services that require dependable communication.

Therefore, early detection of abnormal network behavior can support better monitoring, troubleshooting, and service reliability.

---

# 5. What Makes This a 5G Project?

The project does not use only laptop Internet-speed measurements or Wi-Fi throughput.

The Android application directly accesses cellular information exposed by Android's telephony APIs.

The collector records actual NR-related measurements including:

* SS-RSRP
* SS-RSRQ
* SS-SINR
* PCI
* NCI
* NRARFCN
* registration status
* network type
* deployment-mode indication when available

Android provides dedicated `CellInfoNr`, `CellSignalStrengthNr`, and `CellIdentityNr` APIs for 5G NR information.

The project therefore uses **real cellular radio measurements exposed by the mobile device**, rather than treating a Wi-Fi connection from a 5G phone as equivalent to 5G radio measurements.

---

# 6. Important 5G Terminology

## 6.1 5G NR

**NR = New Radio**

5G NR is the radio-access technology specified for 5G cellular networks.

The Android application identifies NR cells using Android's NR-specific cellular APIs.

---

## 6.2 RSRP

**Reference Signal Received Power**

RSRP represents received radio signal power.

It is generally expressed in dBm.

Example:

```text
-80 dBm
-95 dBm
-105 dBm
```

More negative values generally represent weaker received signal power.

---

## 6.3 RSRQ

**Reference Signal Received Quality**

RSRQ represents received signal quality and is affected by signal power and interference/load conditions.

It is generally expressed in dB.

---

## 6.4 SINR

**Signal-to-Interference-plus-Noise Ratio**

SINR represents the relationship between useful signal and interference/noise.

Higher SINR generally indicates better radio conditions.

The project's collected data has already demonstrated that SINR can vary significantly over a short period.

Example observed behavior:

```text
+4
+3
+2
+3
-7
-7
-1
-10
-7
-3
```

Such temporal changes are important inputs for anomaly detection.

---

## 6.5 PCI

**Physical Cell Identity**

PCI identifies the physical cell identity used by the NR radio system.

A change in PCI can indicate movement between cells or a change in the serving/observed cell context.

A PCI change alone must NOT automatically be considered an anomaly.

---

## 6.6 NCI

**NR Cell Identity**

NCI identifies the NR cell.

Changes in NCI can provide stronger evidence that the device has moved between different NR cells.

---

## 6.7 NRARFCN

**NR Absolute Radio Frequency Channel Number**

NRARFCN identifies the NR radio-frequency channel.

It helps identify the radio-frequency configuration associated with the observed NR cell.

---

# 7. NSA and SA

5G deployments can operate in different architectural modes.

## 7.1 NSA — Non-Standalone

5G NR is deployed together with existing LTE infrastructure and uses LTE-related components as part of the architecture.

## 7.2 SA — Standalone

5G NR operates using a 5G standalone architecture without requiring LTE as the radio-access anchor.

---

# 8. NSA/SA Detection Policy

The application must **never guess SA**.

The deployment-mode field uses the following policy:

```text
NSA     = Android explicitly provides an NR-NSA indication
SA      = Only recorded if a reliable API/device-specific indication is available
UNKNOWN = Android does not expose enough information to determine the mode
```

The current public Android API does not provide a universal, device-independent boolean that guarantees SA detection in every handset/carrier configuration.

Therefore:

```text
5G NR + UNKNOWN
```

does **not** mean:

```text
5G NR + SA
```

It means that the application could not reliably determine the deployment mode from the available Android information.

This distinction must be maintained throughout the project.

---

# 9. Current Android Collector

The Android application is called:

**5G Network Tester**

Package:

```text
com.example.a5gnetworktester
```

Its responsibility is:

```text
5G Mobile Network
        ↓
Android Telephony APIs
        ↓
NR Measurement Collection
        ↓
CSV Data Logging
```

It is NOT currently responsible for machine-learning anomaly detection.

---

# 10. Current Device Testing

Initial testing has been performed using:

### Device 1

```text
Device       : Redmi 13 5G
Model        : 2406ERN9CI
Manufacturer : Xiaomi
Android      : 16
Operator     : Airtel FastLane
```

Additional devices planned for collection:

### Device 2

```text
Device       : Samsung
Model        : SM-A156E/DS
Operator     : Airtel
User         : Sushil
```

### Device 3

```text
Device       : OnePlus Nord CE4
Operator     : Vodafone
User         : Yaashwanth SKP
```

### Device 4

```text
Device       : iPhone 17 Pro
Model        : MG8J4HN/A
User         : Vishal
```

The iPhone should be treated separately because the Android Telephony API collector cannot be directly reused on iOS.

---

# 11. Current Dataset Schema

The Android application currently produces:

```text
timestamp
device
manufacturer
android
operator
network_type
deployment_mode
display_override
registered
ss_rsrp
ss_rsrq
ss_sinr
csi_rsrp
csi_rsrq
csi_sinr
pci
nci
nrarfcn
```

CSV header:

```text
timestamp,device,manufacturer,android,operator,network_type,deployment_mode,display_override,registered,ss_rsrp,ss_rsrq,ss_sinr,csi_rsrp,csi_rsrq,csi_sinr,pci,nci,nrarfcn
```

---

# 12. Meaning of Dataset Fields

| Field            | Meaning                                    |
| ---------------- | ------------------------------------------ |
| timestamp        | Time at which measurement was collected    |
| device           | Device model                               |
| manufacturer     | Device manufacturer                        |
| android          | Android version                            |
| operator         | Mobile network operator                    |
| network_type     | Current reported data network type         |
| deployment_mode  | NSA / SA / UNKNOWN                         |
| display_override | Android display-network indication         |
| registered       | Whether the observed NR cell is registered |
| ss_rsrp          | NR SS-RSRP                                 |
| ss_rsrq          | NR SS-RSRQ                                 |
| ss_sinr          | NR SS-SINR                                 |
| csi_rsrp         | CSI-RSRP if available                      |
| csi_rsrq         | CSI-RSRQ if available                      |
| csi_sinr         | CSI-SINR if available                      |
| pci              | Physical Cell Identity                     |
| nci              | NR Cell Identity                           |
| nrarfcn          | NR Absolute Radio Frequency Channel Number |

---

# 13. Missing-Value Policy

Android can return special sentinel values when a measurement is unavailable.

For integer measurements:

```text
2147483647
```

and equivalent unavailable values must be converted to:

```text
NA
```

The machine-learning pipeline must treat `NA` as missing data and must NOT treat it as a real numerical measurement.

For example:

```text
csi_rsrp = NA
```

means:

> CSI-RSRP was not exposed/available from the device at that sample.

It does NOT mean zero or a poor signal.

---

# 14. Current Data Observation

Initial Redmi measurements demonstrated:

```text
Network Type: 5G NR
Registered: TRUE
PCI: 336 → 565
NCI: 13322280247 → 13322281271
NRARFCN: 629952
```

Signal values varied over time.

Example observed sequence:

```text
SS-RSRP:
-100
-104
-95
-96
-104
-104
-103
-105
-104
-103
```

and:

```text
SS-SINR:
4
3
2
3
-7
-7
-1
-10
-7
-3
```

The change in PCI/NCI accompanied a deterioration in signal quality.

This is an example of an **interesting event**, but it must NOT automatically be labelled an anomaly.

A cell transition can be normal network behavior.

The ML system must learn abnormal combinations and temporal patterns rather than relying on a single hard-coded value.

---

# 15. Problem Definition

## Input

A time-ordered sequence of 5G NR measurements from one or more mobile devices.

Example:

```text
timestamp
RSRP
RSRQ
SINR
PCI
NCI
NRARFCN
network state
registration state
```

## Output

The system should produce:

```text
Normal / Anomalous
```

followed by:

```text
Anomaly Type
```

and:

```text
Likely Cause / Diagnosis
```

and:

```text
Recommended Action
```

---

# 16. Target Anomaly

The primary target is:

> **Temporal radio-quality degradation and abnormal network-state transitions in 5G NR measurements.**

The project focuses on detecting unusual combinations such as:

```text
signal degradation
+
poor SINR/RSRQ
+
rapid cell transition
+
persistent abnormal measurements
```

rather than declaring a single weak measurement to be an anomaly.

---

# 17. Proposed Anomaly Categories

The system can classify detected events into categories such as:

### 17.1 Signal Degradation

Characteristics:

```text
RSRP decreases
RSRQ decreases
SINR decreases
```

over a meaningful period.

---

### 17.2 Sudden Signal Degradation

A rapid change in signal quality within a short time window.

Example:

```text
SINR:
+4 → +3 → +2 → -7 → -10
```

---

### 17.3 Cell Transition Event

A change in:

```text
PCI
NCI
```

possibly accompanied by changes in radio quality.

This is an event, not automatically an anomaly.

---

### 17.4 Network-State Transition

Examples:

```text
5G NR → LTE
LTE → 5G NR
```

Repeated or unexpected transitions can become anomaly candidates.

---

### 17.5 Persistent Poor Radio Quality

A sequence where:

```text
RSRP remains weak
AND
RSRQ remains poor
AND/OR
SINR remains poor
```

for a sustained time window.

---

### 17.6 Combined Anomaly

The strongest anomaly candidates are combinations such as:

```text
Cell transition
      +
RSRP degradation
      +
SINR degradation
      +
persistence
```

---

# 18. What Is NOT an Anomaly by Itself?

The system must avoid simplistic rules.

The following are NOT automatically anomalies:

```text
Low RSRP alone
```

```text
Low SINR alone
```

```text
PCI change alone
```

```text
NCI change alone
```

```text
5G → LTE transition alone
```

```text
UNKNOWN deployment mode
```

These events require context.

---

# 19. Machine Learning Strategy

Because the collected real-world dataset initially has no manually verified anomaly labels, the first implementation should use **unsupervised anomaly detection**.

The primary model is:

# Isolation Forest

---

# 20. Why Isolation Forest?

Isolation Forest is appropriate for the initial prototype because:

1. The dataset is primarily tabular.
2. Initial data does not contain reliable anomaly labels.
3. It can operate in an unsupervised setting.
4. It works well for identifying unusual combinations of numerical features.
5. It does not require a large neural network.
6. It is computationally lightweight.
7. It provides anomaly scores that can be used for further analysis.

The project should not claim that Isolation Forest is universally the best model.

It is the **initial baseline model selected because it fits the available unlabeled data and prototype constraints**.

---

# 21. Isolation Forest Concept

Isolation Forest works on the principle that unusual observations are easier to isolate than normal observations.

The algorithm repeatedly creates random partitions of the feature space.

An unusual point tends to become isolated with fewer partitions.

Therefore:

```text
Shorter isolation path
        ↓
More unusual observation
        ↓
Higher anomaly score
```

Normal observations generally require more partitions to isolate.

---

# 22. Features for the Initial Model

Primary numerical features:

```text
ss_rsrp
ss_rsrq
ss_sinr
```

Cell-context features:

```text
pci
nci
nrarfcn
```

Temporal features:

```text
delta_rsrp
delta_rsrq
delta_sinr
pci_changed
nci_changed
network_changed
```

Rolling features:

```text
rolling_mean_rsrp
rolling_mean_rsrq
rolling_mean_sinr
rolling_std_rsrp
rolling_std_rsrq
rolling_std_sinr
```

The final feature set must be determined after exploratory analysis of the collected dataset.

---

# 23. Feature Engineering

Raw measurements alone are not sufficient for temporal anomaly detection.

For each consecutive measurement:

```text
delta_rsrp = current_rsrp - previous_rsrp

delta_rsrq = current_rsrq - previous_rsrq

delta_sinr = current_sinr - previous_sinr
```

Cell transition:

```text
pci_changed =
    1 if current PCI != previous PCI
    0 otherwise
```

NCI transition:

```text
nci_changed =
    1 if current NCI != previous NCI
    0 otherwise
```

Network transition:

```text
network_changed =
    1 if current network type != previous network type
    0 otherwise
```

---

# 24. Temporal Window

Measurements should be grouped into short time windows.

For example:

```text
5 samples
10 samples
20 samples
```

The final window size should be selected experimentally.

The collector currently samples approximately every:

```text
3 seconds
```

Therefore:

```text
5 samples ≈ 15 seconds
10 samples ≈ 30 seconds
20 samples ≈ 60 seconds
```

This allows the model to distinguish a temporary fluctuation from persistent degradation.

---

# 25. Preprocessing Pipeline

```text
Raw CSV
   ↓
Load Dataset
   ↓
Validate Columns
   ↓
Convert Timestamp
   ↓
Sort by Device + Timestamp
   ↓
Convert Numeric Fields
   ↓
Convert NA → Missing Values
   ↓
Remove Invalid Measurements
   ↓
Handle Missing Values
   ↓
Feature Engineering
   ↓
Scale Numerical Features if required
   ↓
Model Input
```

---

# 26. Important Data-Quality Rules

The preprocessing system must:

### Preserve

```text
raw CSV
```

### Create

```text
processed CSV
```

Never overwrite the raw data.

Directory:

```text
data/
├── raw/
└── processed/
```

---

# 27. Multi-Device Dataset

After collecting measurements from all available Android devices, the combined dataset should contain:

```text
device
manufacturer
operator
timestamp
...
```

The model should be able to distinguish measurements from different devices.

However, device-specific differences must be considered.

For example:

```text
Redmi 13 5G
Samsung
OnePlus
```

may expose different measurements or API behavior.

Therefore, missing CSI values should not automatically be treated as a network anomaly.

---

# 28. Multi-Agent Architecture

After anomaly detection, the system will use multiple specialized analysis agents.

The agents should have clearly separated responsibilities.

---

## Agent 1 — Signal Analysis Agent

Inputs:

```text
RSRP
RSRQ
SINR
delta values
rolling statistics
```

Responsibilities:

* evaluate radio-signal quality
* identify signal degradation
* identify sudden signal changes
* provide signal-quality evidence

Output example:

```json
{
  "signal_condition": "degraded",
  "evidence": [
    "SINR dropped significantly",
    "RSRP decreased"
  ]
}
```

---

## Agent 2 — Cell Transition Agent

Inputs:

```text
PCI
NCI
NRARFCN
timestamps
```

Responsibilities:

* detect cell changes
* detect repeated transitions
* identify unusual cell-switching patterns
* distinguish normal cell changes from potentially suspicious sequences

Output:

```json
{
  "cell_event": "CELL_CHANGE",
  "evidence": [
    "PCI changed from 336 to 565",
    "NCI changed"
  ]
}
```

---

## Agent 3 — Network-State Agent

Inputs:

```text
network_type
deployment_mode
display_override
registered
```

Responsibilities:

* monitor 5G/LTE state
* identify network-state transitions
* interpret NSA indications
* preserve UNKNOWN when deployment mode cannot be determined

The agent must not infer SA from UNKNOWN.

---

## Agent 4 — Diagnosis Agent

Inputs:

```text
Signal Agent output
Cell Agent output
Network Agent output
ML anomaly score
```

Responsibilities:

* combine evidence
* determine the most plausible anomaly category
* explain why the event was detected

Example:

```text
Detected Event:
Possible radio-quality degradation associated with a cell transition.

Evidence:
- PCI changed
- NCI changed
- SINR dropped
- RSRP deteriorated
- degradation persisted across multiple samples
```

---

## Agent 5 — Recommendation Agent

Inputs:

```text
Diagnosis
Anomaly severity
Supporting evidence
```

Responsibilities:

* provide an understandable recommendation
* avoid claiming actions that the system cannot perform
* distinguish monitoring recommendations from network-operator actions

Example:

```text
Recommendation:
Continue monitoring the connection.
If the degraded signal persists, investigate coverage,
interference, congestion, or cell-transition behavior.
```

---

# 29. Why Multiple Agents?

A single agent could technically process all information.

However, the multi-agent architecture provides functional separation:

```text
Signal Agent
     ↓
Cell Agent
     ↓
Network Agent
     ↓
Diagnosis Agent
     ↓
Recommendation Agent
```

Each agent has a specific responsibility.

This makes the system:

* modular
* easier to debug
* easier to explain
* easier to extend
* suitable for demonstrating agentic architecture

The project must NOT create unnecessary agents merely to increase the number of agents.

---

# 30. ML + Agents Relationship

The agents are NOT the anomaly detector itself.

The architecture is:

```text
Raw Measurements
       ↓
Preprocessing
       ↓
Feature Engineering
       ↓
Isolation Forest
       ↓
Anomaly Score
       ↓
Specialized Agents
       ↓
Diagnosis
       ↓
Recommendation
```

This separation is important.

Machine learning determines whether the observation is statistically unusual.

The agents analyze the evidence and explain the likely nature of the event.

---

# 31. Dashboard

The final dashboard should provide:

### Current Network State

```text
Network Type
Deployment Mode
Registered
Operator
Device
```

### Current Radio Metrics

```text
RSRP
RSRQ
SINR
PCI
NCI
NRARFCN
```

### Anomaly Status

```text
NORMAL
or
ANOMALY DETECTED
```

### Anomaly Score

Display the model score or normalized anomaly indicator.

### Detected Event

Example:

```text
Signal Degradation
Cell Transition
Network-State Transition
Combined Anomaly
```

### Diagnosis

Human-readable explanation.

### Recommendation

Suggested next step.

---

# 32. Dashboard Visualizations

Recommended visualizations:

1. RSRP over time
2. RSRQ over time
3. SINR over time
4. PCI/NCI changes
5. Network-type transitions
6. Anomaly score over time
7. Anomaly markers on signal graphs
8. Current network status card

Avoid excessive UI decoration.

The dashboard should prioritize technical interpretability.

---

# 33. System Architecture

```text
                    5G Mobile Network
                           │
                           ▼
                 Android NR Collector
                           │
                           ▼
                   Real NR Measurements
                           │
                           ▼
                       CSV Data
                           │
                           ▼
                    Data Preprocessing
                           │
                           ▼
                    Feature Engineering
                           │
                           ▼
                   Isolation Forest
                           │
                    Anomaly Score
                           │
                           ▼
                 ┌─────────┼─────────┐
                 │         │         │
                 ▼         ▼         ▼
             Signal      Cell      Network
              Agent      Agent       Agent
                 │         │         │
                 └─────────┼─────────┘
                           ▼
                    Diagnosis Agent
                           │
                           ▼
                 Recommendation Agent
                           │
                           ▼
                       Dashboard
```

---

# 34. Complete Data Flow

```text
Mobile Network
      ↓
5G NR Radio
      ↓
Android Telephony API
      ↓
5G Network Tester
      ↓
Timestamped CSV
      ↓
Raw Dataset
      ↓
Data Validation
      ↓
Missing Value Handling
      ↓
Feature Engineering
      ↓
Anomaly Detection
      ↓
Anomaly Score
      ↓
Anomaly Classification
      ↓
Multi-Agent Analysis
      ↓
Diagnosis
      ↓
Recommendation
      ↓
Dashboard
```

---

# 35. Proposed Project Directory

```text
5G-NADS/
│
├── android-collector/
│   └── 5GNetworkTester/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── sample/
│
├── ml/
│   ├── preprocessing.py
│   ├── feature_engineering.py
│   ├── anomaly_detection.py
│   ├── anomaly_analysis.py
│   ├── train.py
│   └── evaluate.py
│
├── agents/
│   ├── signal_agent.py
│   ├── cell_agent.py
│   ├── network_agent.py
│   ├── diagnosis_agent.py
│   └── recommendation_agent.py
│
├── dashboard/
│
├── models/
│
├── notebooks/
│   └── exploratory_analysis.ipynb
│
├── tests/
│
├── requirements.txt
│
├── README.md
│
└── project-overview.md
```

---

# 36. Technology Stack

## Mobile Collector

```text
Android
Kotlin
Android Telephony APIs
CSV
```

## Machine Learning

```text
Python
Pandas
NumPy
Scikit-learn
```

## Model

```text
Isolation Forest
```

## Visualization

Possible options:

```text
Streamlit
Plotly
```

or another lightweight web-dashboard framework.

## Agent Layer

Preferred implementation:

```text
Python
```

The agents should initially be implemented as deterministic modular components.

LLMs may be added later if needed for natural-language explanation, but the core anomaly decision should not depend on an LLM.

---

# 37. Why the Core Decision Should Not Depend on an LLM

The anomaly detector should be:

```text
measurement → preprocessing → ML → anomaly score
```

rather than:

```text
measurement → LLM → anomaly
```

Reasons:

* reproducibility
* measurable performance
* deterministic behavior
* easier evaluation
* lower computational cost
* easier debugging
* better separation between detection and explanation

An LLM can optionally be used later to convert structured diagnosis into natural-language explanations.

---

# 38. Existing Public Datasets

The project should use the real smartphone dataset as its **primary project dataset**.

Public datasets can be used as supplementary benchmarks.

### 38.1 Kaggle — Anomaly Detection in Cellular Networks

A Kaggle competition provides real LTE deployment data collected from multiple base stations and cells at regular intervals, with unusual/normal behavior labels.

It can be useful for understanding cellular-network anomaly detection methodology and benchmarking, although it is **LTE rather than the project's smartphone NR dataset**.

### 38.2 Kaggle — Anomaly Detection in 4G Cellular Networks

This dataset contains labeled cellular-network measurements and can be used as a supplementary benchmark.

It should NOT be presented as the project's primary 5G dataset.

### 38.3 Research Datasets / 5G Core Metrics

Research literature also contains anomaly-detection work using 5G core-network KPIs.

Such datasets are useful for comparison but represent a different layer of the 5G architecture from the project's UE-side NR radio measurements.

---

# 39. Dataset Strategy

The project should use three levels of data:

### Level 1 — Real Device Dataset

Collected using the Android application.

```text
Redmi
Samsung
OnePlus
```

and other compatible devices.

This is the project's primary dataset.

### Level 2 — Public Cellular Dataset

Used for comparison and experimentation.

### Level 3 — Synthetic/Controlled Data

Used only when necessary to test specific anomaly scenarios that are difficult to capture naturally.

Synthetic anomalies must be clearly labelled as synthetic.

They must never be presented as real network measurements.

---

# 40. Initial Dataset Size

The first collection target is:

```text
150–200 samples per device
```

At approximately:

```text
1 sample / 3 seconds
```

this corresponds to approximately:

```text
150 samples ≈ 7.5 minutes
200 samples ≈ 10 minutes
```

This is sufficient for an initial prototype and exploratory analysis.

It is NOT sufficient to claim that the model generalizes to all 5G networks.

Additional collection should be performed across:

* devices
* operators
* locations
* times
* signal conditions
* mobility conditions

for a stronger final evaluation.

---

# 41. Recommended Data Collection Scenarios

For future collection, capture measurements under different conditions:

### Scenario A — Stationary

Phone remains in one location.

### Scenario B — Indoor Movement

Move through different parts of a building.

### Scenario C — Outdoor Movement

Collect measurements while moving through an outdoor area.

### Scenario D — Different Locations

Collect data from multiple areas with different coverage conditions.

### Scenario E — Different Operators

Use available Airtel/Vodafone/etc. devices.

### Scenario F — Different Devices

Compare Android device behavior.

The conditions should be recorded as metadata where practical.

---

# 42. Controlled Anomaly Experiments

After normal baseline data has been collected, controlled experiments can be performed.

Examples:

* moving from strong to weak coverage
* moving between cells
* entering a building
* leaving a building
* observing 5G/LTE transitions
* collecting during different network-load conditions

The system should observe naturally occurring changes rather than artificially modifying the cellular network.

---

# 43. Evaluation Strategy

Because the first model is unsupervised, evaluation should not rely only on accuracy.

Recommended metrics include:

```text
Precision
Recall
F1-score
False Positive Rate
Detection Rate
Anomaly Score Distribution
Detection Latency
```

For unlabeled real-world data, expert/manual inspection can be used to create a small evaluation set.

Controlled events can also provide event-level ground truth.

---

# 44. Model Evaluation

The project should compare at least:

```text
Baseline statistical method
vs
Isolation Forest
```

Possible future models:

```text
One-Class SVM
Local Outlier Factor
Autoencoder
LSTM Autoencoder
```

The project should not add complex deep-learning models unless the dataset size and temporal structure justify them.

---

# 45. Recommended Baseline

A simple statistical baseline can be implemented using rolling statistics.

Example:

```text
rolling mean
rolling standard deviation
z-score
```

An observation can be marked as unusual when it deviates strongly from the local baseline.

This provides a simple comparison against Isolation Forest.

---

# 46. Severity Estimation

The system can optionally assign:

```text
LOW
MEDIUM
HIGH
```

severity.

Severity should be based on measurable evidence such as:

* anomaly score
* persistence
* magnitude of signal degradation
* number of affected metrics
* network-state changes

The severity thresholds must be documented and validated rather than arbitrarily selected.

---

# 47. Example End-to-End Scenario

Suppose the system observes:

```text
RSRP:
-96 → -101 → -104 → -106

SINR:
+4 → +2 → -5 → -9

PCI:
336 → 336 → 565 → 565

NCI:
13322280247 → 13322280247
→ 13322281271 → 13322281271
```

The pipeline becomes:

```text
Measurements
      ↓
Feature Engineering
      ↓
Cell Change Detected
      ↓
Signal Degradation Detected
      ↓
Isolation Forest Anomaly Score
      ↓
Potential Anomaly
      ↓
Signal Agent
      ↓
Cell Agent
      ↓
Network Agent
      ↓
Diagnosis Agent
      ↓
"Possible radio-quality degradation
associated with a cell transition"
      ↓
Recommendation Agent
      ↓
"Continue monitoring. If degradation
persists, investigate coverage,
interference, congestion or cell behavior."
```

This is an example workflow, not a predefined ground-truth diagnosis.

---

# 48. Important Limitations

## 48.1 Android API Limitations

Different manufacturers may expose different levels of cellular information.

Some measurements may be unavailable.

---

## 48.2 CSI Metrics

CSI measurements may appear as:

```text
NA
```

on some devices.

This must not be interpreted as a network anomaly.

---

## 48.3 NSA/SA Detection

Public Android APIs do not universally expose a definitive SA/NSA state for every device/carrier combination.

Therefore:

```text
UNKNOWN
```

is a valid and expected value.

---

## 48.4 Small Initial Dataset

150–200 samples are suitable for a prototype but are not enough to establish universal network thresholds.

---

## 48.5 Device Differences

Different devices can expose different metrics and may use different modem implementations.

---

## 48.6 Carrier Differences

Different operators may use different spectrum, deployment architectures, configurations, and coverage patterns.

---

## 48.7 Correlation Is Not Causation

A correlation between:

```text
cell change
```

and:

```text
signal degradation
```

does not prove that the cell change caused the degradation.

The system should report observed evidence and plausible diagnosis rather than claiming a confirmed root cause without supporting evidence.

---

# 49. Privacy and Data Handling

The application should avoid collecting unnecessary personally identifiable information.

The dataset should focus on:

```text
network measurements
device model
operator
timestamp
cell/network information
```

No phone number, contacts, messages, or user-content data should be collected.

If precise location is not required for the project, it should not be stored in the dataset.

---

# 50. Security

The system should:

* keep raw datasets locally during development
* avoid hard-coding credentials
* avoid storing sensitive information
* validate uploaded CSV files
* separate raw and processed data
* use environment variables for API keys if external services are later introduced

---

# 51. Implementation Phases

## Phase 1 — Android Data Collection

Status:

**Implemented**

Tasks:

* obtain permissions
* read NR cell information
* collect measurements
* identify registered NR cell
* record timestamps
* record network state
* record deployment indication
* save CSV

---

## Phase 2 — Dataset Collection

Status:

**In Progress**

Tasks:

* collect 150–200 samples from Redmi
* collect samples from Samsung
* collect samples from OnePlus
* collect other compatible devices
* collect data under multiple conditions

---

## Phase 3 — Exploratory Data Analysis

Tasks:

* inspect missing values
* inspect distributions
* plot RSRP
* plot RSRQ
* plot SINR
* identify cell transitions
* inspect network-state transitions
* compare devices/operators

---

## Phase 4 — Preprocessing

Tasks:

* timestamp parsing
* sorting
* missing-value handling
* invalid-value filtering
* device grouping
* numerical conversion

---

## Phase 5 — Feature Engineering

Tasks:

* delta features
* rolling statistics
* cell-change indicators
* network-change indicators
* persistence features

---

## Phase 6 — Baseline Anomaly Detector

Implement:

```text
rolling statistical baseline
```

---

## Phase 7 — ML Anomaly Detector

Implement:

```text
Isolation Forest
```

Compare against the baseline.

---

## Phase 8 — Anomaly Classification

Implement rule/evidence-based classification:

```text
Signal degradation
Cell transition
Network-state transition
Persistent poor quality
Combined anomaly
```

---

## Phase 9 — Multi-Agent Layer

Implement:

```text
Signal Agent
Cell Agent
Network Agent
Diagnosis Agent
Recommendation Agent
```

---

## Phase 10 — Dashboard

Implement:

* current measurements
* historical graphs
* anomaly status
* anomaly score
* anomaly type
* diagnosis
* recommendation

---

## Phase 11 — Evaluation

Evaluate:

* detection performance
* false positives
* false negatives
* detection latency
* device generalization
* operator variation

---

## Phase 12 — Final Documentation

Generate:

```text
README.md
System Architecture
Data Flow
ML Methodology
Agent Architecture
Dataset Documentation
Testing Documentation
Results
Limitations
Future Scope
```

---

# 52. Final Expected System

The completed system should provide:

```text
Real 5G NR Data
        ↓
Automated Collection
        ↓
CSV Dataset
        ↓
Preprocessing
        ↓
Feature Engineering
        ↓
ML Anomaly Detection
        ↓
Anomaly Score
        ↓
Anomaly Classification
        ↓
Multi-Agent Analysis
        ↓
Diagnosis
        ↓
Recommendation
        ↓
Dashboard
```

---

# 53. Final Project Claim

The project should be described as:

> A real-device 5G NR monitoring and anomaly-detection system that combines Android cellular measurements, time-series feature engineering, unsupervised machine learning, and modular multi-agent analysis to identify and explain unusual radio/network behavior.

The project should NOT claim:

* universal 5G anomaly detection
* guaranteed root-cause identification
* guaranteed SA/NSA identification on every device
* real-time operator-network control
* universal thresholds for all networks
* that every cell transition is an anomaly
* that the Android application itself performs the ML detection

---

# 54. Minimum Viable Final System

If time is limited, the minimum complete implementation should contain:

```text
1. Android NR collector
2. CSV dataset
3. Python preprocessing
4. Feature engineering
5. Isolation Forest
6. Anomaly classification
7. Signal Agent
8. Cell Agent
9. Network Agent
10. Diagnosis Agent
11. Recommendation Agent
12. Basic dashboard
13. Evaluation
```

This is the minimum system that still represents the complete proposed architecture.

---

# 55. Future Scope

Possible future improvements include:

* larger multi-device dataset
* more operators
* more locations
* mobility-aware anomaly detection
* supervised anomaly classification after sufficient labeling
* LSTM/Transformer time-series models
* edge-based inference
* federated learning
* O-RAN integration
* network-side KPIs
* 5G core-network metrics
* automated alerting
* richer visualization
* integration with operator/network-management systems

These are future extensions and should not be claimed as implemented unless actually completed.

---

# 56. Implementation Rule for AI Development Agents

Any AI agent used to implement this project must treat this document as the **source of truth**.

The implementation agent must:

1. Preserve the distinction between the Android collector and ML pipeline.
2. Never fabricate unavailable measurements.
3. Treat `NA` as missing data.
4. Never infer SA from `UNKNOWN`.
5. Never label every weak signal as an anomaly.
6. Never label every PCI/NCI change as an anomaly.
7. Preserve raw data.
8. Make preprocessing reproducible.
9. Keep ML detection separate from agent-based explanation.
10. Document assumptions.
11. Use real collected data wherever available.
12. Clearly identify synthetic data if synthetic data is used.
13. Avoid unnecessary LLM dependence.
14. Keep each agent's responsibility clearly defined.
15. Generate tests for every major component.
16. Do not claim a component is implemented until it has actually been tested.

---

# 57. Immediate Implementation Order

The implementation agent should follow this order:

```text
STEP 1
Collect and organize real CSV data

STEP 2
Build preprocessing.py

STEP 3
Build exploratory data analysis

STEP 4
Build feature_engineering.py

STEP 5
Implement statistical baseline

STEP 6
Implement Isolation Forest

STEP 7
Generate anomaly scores

STEP 8
Implement anomaly classification

STEP 9
Implement Signal Agent

STEP 10
Implement Cell Agent

STEP 11
Implement Network Agent

STEP 12
Implement Diagnosis Agent

STEP 13
Implement Recommendation Agent

STEP 14
Build dashboard

STEP 15
Integrate complete pipeline

STEP 16
Test end-to-end

STEP 17
Generate project documentation

STEP 18
Generate final architecture diagrams and presentation material
```

---

# 58. Definition of Done

The project is considered complete only when:

```text
[ ] Android collector works
[ ] Real NR measurements collected
[ ] CSV generation works
[ ] Multiple-device data collected
[ ] Raw dataset preserved
[ ] Preprocessing implemented
[ ] Missing values handled
[ ] Feature engineering implemented
[ ] Statistical baseline implemented
[ ] Isolation Forest implemented
[ ] Anomaly scores generated
[ ] Anomaly categories generated
[ ] Signal Agent implemented
[ ] Cell Agent implemented
[ ] Network Agent implemented
[ ] Diagnosis Agent implemented
[ ] Recommendation Agent implemented
[ ] Dashboard implemented
[ ] End-to-end integration works
[ ] Model evaluated
[ ] False positives investigated
[ ] Limitations documented
[ ] README generated
[ ] Architecture documented
[ ] Final results documented
```

---

# 59. Research Positioning

The project combines three levels:

### Device/Radio Level

```text
Real 5G NR measurements
```

### Machine-Learning Level

```text
Time-series feature engineering
+
Unsupervised anomaly detection
```

### Intelligent Analysis Level

```text
Multi-agent diagnosis
+
Recommendation
```

This layered design is the central technical contribution of the project.

---

# 60. Final One-Line Description

> **A real-device 5G NR monitoring system that detects unusual radio/network behavior using machine learning and explains the detected events through specialized multi-agent analysis.**
