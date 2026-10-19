# O-RAN Feasibility Note & Operator-Side Integration Analysis

> **Task Reference:** `T15-004` (Phase 15: Should-Have Extras & Research Notes)  
> **Status:** Research Note Only — **NOT IMPLEMENTED**  
> **Author:** M A Sushil Kumar  
> **Audit Date:** 2026-10-19  

---

## 1. Executive Summary & Explicit Scope Boundary

This document evaluates the architectural feasibility of interfacing User Equipment (UE)
telemetry from 5G-NADS with an Open RAN (O-RAN) architecture.

> [!IMPORTANT]
> **Explicit Non-Claim (Guardrail G31):** O-RAN and Near-RT RIC integration is **NOT IMPLEMENTED**
> in the 5G-NADS codebase. 5G-NADS is an exploratory academic prototype collecting passive
> smartphone telemetry; it possesses no direct connection, interface, or control over any
> commercial or private operator Radio Access Network.

---

## 2. O-RAN Architecture Overview & Interfaces

The O-RAN Alliance architecture disaggregates cellular base stations into modular components
managed by software-defined controllers:

1. **Non-Real-Time RAN Intelligent Controller (Non-RT RIC):**
   - Operates on control loops $> 1,000$ ms within Service Management & Orchestration (SMO).
   - Hosts **rApps** for policy guidance, long-term model training, and network configuration.
2. **Near-Real-Time RAN Intelligent Controller (Near-RT RIC):**
   - Operates on control loops between $10$ ms and $1,000$ ms.
   - Hosts **xApps** executing microsecond/millisecond radio resource management and mobility.
3. **E2 Nodes (O-CU-CP, O-CU-UP, O-DU):**
   - Cellular base station elements communicating with the Near-RT RIC via the standardized
     **E2 interface** (O-RAN.WG3.E2GAP).
4. **Service Models (E2SM):**
   - Standards including **E2SM-KPM** (Key Performance Measurements) and **E2SM-RC** (RAN Control)
     defining telemetry and action primitives between E2 Nodes and the RIC.

---

## 3. What UE-Side Telemetry Could Inform in an Operator RIC

If ingested into an operator-side RIC platform, passive client-side telemetry of the type
collected by 5G-NADS (`RSRP`, `RSRQ`, `SINR`, `PCI`, `NCI`, `NRARFCN`) could theoretically inform
several control workflows:

### 3.1 Downlink Coverage Hole & Weak Signal Detection (MDT Proxy)
- **Mechanism:** Standard 3GPP Minimization of Drive Tests (MDT, 3GPP TS 37.320) aggregates
  UE measurement reports to build spatial coverage maps.
- **Feasibility:** Client telemetry provides terminal-perceived layer-1 RF quality. An rApp in
  the Non-RT RIC could correlate geolocated signal dips to adjust remote electrical tilt (RET)
  or gNodeB transmit power via O1.

### 3.2 Handover Flapping & Ping-Pong Detection
- **Mechanism:** Rapid PCI alternations with transient SINR degradation (Contract C5 events).
- **Feasibility:** A traffic-steering xApp in the Near-RT RIC could utilize client-reported
  handover failure intervals to tune Cell Individual Offsets (CIO) and Time-to-Trigger (TTT)
  parameters via E2SM-RC.

### 3.3 Passive Dual-Connectivity Degradation
- **Mechanism:** Tracking Secondary Cell Group (SCG) failure or LTE fallback in NSA deployments.
- **Feasibility:** Terminal-side notifications of abrupt NSA $\to$ LTE downshifts inform
  admission control policies on congested anchoring gNodeBs.

---

## 4. What UE-Side Telemetry CANNOT Inform (Hard Boundaries)

Passive client-side telemetry cannot substitute for infrastructure telemetry. The following
network aspects are completely invisible to 5G-NADS:

1. **Uplink Channel Quality & Sounding:**
   - UE telemetry measures downlink signals broadcast by the tower. The client cannot measure
     gNodeB uplink reception quality, uplink interference, or beamforming reciprocal errors.
2. **Physical Resource Block (PRB) Utilization:**
   - Client APIs cannot inspect the gNodeB MAC scheduler queue, instantaneous multi-user PRB
     allocation, or backhaul capacity constraints.
3. **Fronthaul & Hardware Faults:**
   - Subsystem degradation on the O-RAN 7.2x split (eCPRI packet jitter, PTP synchronization
     drift, or O-RU power amplifier saturation) is undetectable from terminal-layer metrics.
4. **Multi-User Context:**
   - A single terminal cannot distinguish whether a signal drop is caused by spatial fading
     specific to its location or cell-wide congestion affecting all connected subscribers.

---

## 5. Architectural Barriers to Implementation in 5G-NADS

Implementing an O-RAN integration in 5G-NADS is prohibited by the following foundational barriers:

### 5.1 Absence of Standardized Client-to-RIC Interfaces
- O-RAN E2 interfaces connect base stations (O-CU/O-DU) to the RIC; no O-RAN interface connects
  consumer mobile applications directly to a RIC.
- Telemetry from commercial smartphones is ingested into carrier infrastructure solely through
  standardized 3GPP RRC Measurement Reports handled inside the proprietary radio modem firmware,
  not via TCP/WebSocket application streams.

### 5.2 Carrier Closed-Network Perimeter
- Commercial cellular operators (e.g., Bharti Airtel, Reliance Jio) operate strictly isolated
  core and management networks.
- No public API, VPN tunnel, or carrier gateway is provided for third-party mobile applications
  to inject telemetry into carrier RIC deployments.

### 5.3 Licensing & Hardware Prerequisites
- Establishing an end-to-end O-RAN research testbed requires:
  - Private 5G spectrum authorization or RF-shielded anechoic enclosures.
  - Software-Defined Radio (SDR) hardware (e.g., USRP N310 / X310).
  - Open-source full-stack software (e.g., OpenAirInterface, srsRAN, OSC Near-RT RIC).
- These prerequisites lie outside the scope of the 5G-NADS zero-cost laptop/phone environment.

---

## 6. Sourced Statements & Primary Citations

Every technical assertion in this document is verified against current standards or marked:

1. **O-RAN Architecture:**
   - O-RAN Alliance, "O-RAN Architecture Description," O-RAN.WG1.O-RAN-Architecture-Description.
   - *Status:* Verified against O-RAN WG1 specifications.
2. **Near-RT RIC & E2 Interface:**
   - O-RAN Alliance, "Near-Real-time RAN Intelligent Controller Architecture & E2 General Aspects,"
     O-RAN.WG3.E2GAP.
   - *Status:* Verified against O-RAN WG3 specifications.
3. **Minimization of Drive Tests (MDT):**
   - 3GPP, "Universal Terrestrial Radio Access (UTRA) and Evolved UTRA (E-UTRA); Radio measurement
     collection for Minimization of Drive Tests (MDT); Overall description; Stage 2,"
     3GPP TS 37.320.
   - *Status:* Verified against 3GPP Release 16/17 specifications.
4. **Commercial Carrier RIC Ingestion Policies:**
   - Assertion that commercial Indian carriers (Airtel, Jio) do not expose public RIC endpoints.
   - *Status:* Marked **UNVERIFIED BY PRIMARY CARRIER SPECIFICATION** (inferred from standard
     telecom security architecture and absence of public carrier API documentation).

---

## 7. Conclusion

While joint terminal-and-network telemetry represents a promising direction for future 6G and
O-RAN research, direct integration with a live operator RIC is technically, legally, and
architecturally impossible within an academic client-side prototype.

**5G-NADS deliberately and honestly retains O-RAN integration as NOT IMPLEMENTED.**
