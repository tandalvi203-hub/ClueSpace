<p align="center">
  <img src="frontend/public/assets/images/cluespace-banner.png" alt="ClueSpace Banner" width="750">
</p>

# ClueSpace — IBM Bob August Challenge

*Where telemetry becomes evidence, and anomalies become answers. Turn raw spacecraft telemetry into 3D spatialized root-cause investigations.*

ClueSpace is a spacecraft incident investigation system that turns fragmented telemetry anomalies into a connected incident story. It links related events across channels and time, reconstructs how an incident unfolded, visualizes the evidence through an interactive Evidence Graph and 3D spacecraft view, and generates a structured investigation with a leading hypothesis, confidence, supporting evidence, and recommended next actions.

**Challenge theme:** Space Telemetry & Autonomous Mission Intelligence  
**Challenge:** IBM Bob AI Builders Challenge (August)

**Try it here:** https://clue-space.vercel.app/ 


## At a Glance

| Attribute | Specification |
| :--- | :--- |
| **What** | Autonomous spacecraft telemetry forensics and incident reconstruction platform. |
| **Core Problem** | Fragmented multi-channel anomalies make manual cascade diagnosis slow and prone to error. |
| **Core Insight** | Related anomalies are interconnected clues belonging to a single causal incident. |
| **Investigation Engine** | Temporal lead-lag matrix + 99% signal morphology match + Evidence Graph DAG. |
| **Primary Output** | Reconstructed timelines, causal hypotheses, quantified evidence scores, and next-action playbooks. |
| **Spatial Computing** | 3D satellite subsystem spatializer and 4D spacetime cascade trajectory canvas. |
| **Primary AI Partner** | **IBM Bob** (Plan Mode architecture, algorithmic refinement, backend scaffolding). |
| **Challenge Theme** | August 2026 — *Advance Space Exploration with AI*. |

## 🔎 The Problem

Modern spacecraft continuously stream high-density telemetry across dozens of isolated subsystem channels (thermal, power, RF, and bus logic). When compound orbital incidents occur:

* **High-Dimensional Telemetry Floods:** Critical warning signals are buried under massive streams of sensor noise, overwhelming ground operators during tight orbital contact passes.
* **Manual Forensics Delays:** Flight controllers must manually correlate flat 2D time-series charts across dozens of channels—a process taking hours or days when every second determines mission survival.
* **Cascading Multi-Channel Blindspots:** Over **60.1% of critical orbital failures are multi-channel cascades**, where the root cause (such as a high-speed transponder bus anomaly) is physically and temporally separated from the symptom (such as an RF amplifier thermal shutdown).

> **The real challenge isn't finding the anomaly. It's reconstructing the incident from fragmented evidence.**

---

## ⚡ The Solution

**ClueSpace** is an autonomous incident investigation engine that transforms raw satellite telemetry into spatialized intelligence and actionable recovery protocols.

* **3D Anomaly Spatializer:** Projects live telemetry deviations onto an interactive 3D spacecraft mesh, allowing operators to visually isolate subsystem stress and channel-level deviations instantly.
* **4D Spacetime Trajectory Engine:** Maps multi-channel failure vectors along an interactive spacetime continuum, enabling engineers to scrub across milliseconds and observe failure propagation paths.
* **Autonomous Evidence Graphing:** Reconstructs pairwise activation sequences, calculates lead-lag precedence, and evaluates **99% signal pattern similarities** to confirm causal dependencies.
* **Automated Diagnostic Playbooks:** Synthesizes complex telemetry data into ranked operational directives (e.g., transponder bus isolation, load shedding, thermal loop resets).

---

## 🖥️ System Walkthrough & Visual Proof

### 1. 3D Anomaly Spatializer
Pins telemetry anomalies to physical satellite components with real-time severity inspection.

<p align="center">
  <img src="https://github.com/user-attachments/assets/f23dcddc-dcfa-4498-a86c-434a90f4a4f4" width="95%" alt="3D Anomaly Spatializer Screen"/>
</p>

* **Physical Component Mapping:** Translates abstract sensor IDs (`CADC0888`, `CADC0872`) to physical subsystems (solar arrays, communications dish, bus logic).
* **Channel Inspector:** Displays peak anomaly scores, duration, data verification, and live telemetry deviation snippets.

---

### 2. 4D Telemetry Spacetime Engine
Visualizes multi-channel cascade propagation vectors along an interactive 4D spacetime continuum.

<p align="center">
  <img src="< "https://github.com/user-attachments/assets/ed6e9b99-ab20-420a-b941-2287e1e836c2" width="95%" alt="Telemetry Spacetime 4D Visualizer"/>
</p>

* **Spatiotemporal Event Clusters:** Maps anomaly occurrences across both 3D coordinate space and time simultaneously.
* **Timeline Scrubber:** Allows flight controllers to scrub across milliseconds and visually track cascade propagation vectors.

---

### 3. Mission Control Fleet Intelligence
Fleet-wide operational triage across 805 reconstructed incidents and 163k+ telemetry data points.

<p align="center">
  <img src="<isrc="https://github.com/user-attachments/assets/617f3057-cfd4-4f94-87a7-7c25526cbf2e" " width="95%" alt="Mission Control Dashboard"/>
</p>

* **Fleet Triage:** Classifies anomalies into Multi-Channel (60.1%) vs. Single-Channel (39.9%) incidents.
* **Risk Distribution:** Real-time tracking of incident severity (Critical, High, Moderate, Low) and most vulnerable spacecraft channels.

---

### 4. Forensic Investigation Workspace & Playbooks
Automated incident dossier with activation sequences, 99% pattern match links, and recovery playbooks.

<p align="center">
  <img src="PASTE_INVESTIGATION_URL_HERE" width="95%" alt="Forensic Investigation Workspace"/>
</p>

* **Temporal Activation Sequence:** Reconstructs the exact chain reaction from the initiator (`CADC0888`) across downstream subsystems over a 57-second activation span.
* **Evidence Graph DAG:** Measures sequence consistency, duration overlap, and signal morphology correlations.
* **Automated Diagnostic Actions:** Delivers ranked remediation playbooks directly to flight control teams.

---

## 🛰️ The 5-Stage Forensics Pipeline

1. **Detect (`01`):** Ingests raw telemetry points (OPS-SAT real spacecraft data) and flags abnormal behavioral drift across channels.
2. **Connect (`02`):** Computes pairwise lead-lag dependencies to uncover hidden temporal links between isolated telemetry channels.
3. **Reconstruct (`03`):** Projects sensor anomalies directly onto interactive 3D satellite coordinates and 4D spacetime point clouds.
4. **Investigate (`04`):** Measures sequence consistency, time gaps ($t_{\text{gap}} < 2\text{s}$), and 99% signal pattern similarity across active nodes.
5. **Explain (`05`):** Synthesizes forensic findings into clear root-cause conclusions with prioritized, actionable diagnostic procedures.

---

## ⚡ Why ClueSpace is Different

| Traditional Anomaly Monitoring | ClueSpace Telemetry Forensics |
| :--- | :--- |
| Detects isolated anomalies | Reconstructs multi-channel incidents |
| Focuses on single-channel thresholds | Correlates cross-channel cascade dependencies |
| Signal-centric (flags raw spikes) | Evidence-centric (builds causal chains) |
| Lacks temporal relationship context | Quantifies lead-lag precedence and duration overlap |
| Stops at alerting | Delivers hypotheses and prioritized recovery actions |
| Flat 2D strip-charts | Interactive 3D component spatialization & 4D spacetime trajectories |

---

## 🛠️ How IBM Bob Was Used

**IBM Bob** served as our primary AI systems architect and pair programmer throughout development:

* **Plan Mode Architecture:** Used IBM Bob's Plan Mode to break down the incident reconstruction pipeline into discrete modules: event validation, temporal lead-lag analysis, and evidence graph scoring.
* **Core Forensics Engine Implementation:** Leveraged Bob to build and refine the algorithms responsible for calculating pairwise channel overlap, sequence consistency scores, and signal morphology correlations.
* **WebGL & 3D Optimization:** Utilized Bob to implement 3D coordinate bindings from sensor IDs to satellite meshes and optimize rendering performance for 4D spacetime point clouds.
* **Testing & Robustness:** Iterated with Bob to construct unit test suites for schema validation, temporal graph construction, and edge-case multi-channel cascades.

---


