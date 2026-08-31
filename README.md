<p align="center">
  <img src="frontend/public/assets/images/cluespace-banner.png" alt="ClueSpace Banner" width="750">
</p>

# ClueSpace — IBM Bob August Challenge

*Where telemetry becomes evidence, and anomalies become answers. Turn raw spacecraft telemetry into 3D spatialized root-cause investigations.*

**Challenge theme:** Space Telemetry & Autonomous Mission Intelligence  
**Challenge:** IBM Bob AI Builders Challenge (August)

**Try it here:** https://clue-space.vercel.app/ 



## Motivation

Modern satellites generate hundreds of thousands of multi-channel telemetry data points every second. When complex anomalies occur in orbit, manual incident diagnosis across isolated 2D charts takes hours or even days—wasting critical time when spacecraft assets are on the line.

**ClueSpace** is an autonomous telemetry forensics and root-cause reconstruction engine. It ingests high-frequency spacecraft sensor streams, reconstructs cascade anomalies in interactive 3D/4D space, and correlates multi-channel telemetry into clear, evidence-backed diagnostic playbooks.



## How to Use

1. **Explore Mission Control** — View real-time fleet intelligence, severity distributions, and cross-channel failure classifications across 805+ reconstructed incidents.
2. **Launch the Anomaly Spatializer** — Inspect live telemetry mapped directly onto a 3D satellite model to see physical subsystem stress and channel-level deviations.
3. **Scrub Telemetry Spacetime** — Play the 4D timeline visualizer to watch how anomaly clusters physically propagate across telemetry channels over time.
4. **Select an Incident Investigation** — Filter by severity (Critical / High / Moderate / Low) and load complete forensic cases (e.g., Incident `INV-988`).
5. **Review Evidence Graph & Playbook** — Inspect the millisecond activation sequence, 99% signal pattern similarity links, and execute priority-ranked diagnostic actions.

---

## Demo

**Demo video:** https://youtu.be/your-video-link

| | |
|:---:|:---:|
| <img src="screenshots/anomaly_spatializer.jpg" width="100%" alt="3D Anomaly Spatializer"/> | <img src="screenshots/telemetry_spacetime.jpg" width="100%" alt="Telemetry Spacetime 4D Visualizer"/> |
| <img src="screenshots/mission_control.jpg" width="100%" alt="Mission Control Dashboard"/> | <img src="screenshots/investigation_workspace.jpg" width="100%" alt="Forensic Investigation Workspace"/> |

---

## Tech Stack
## AI Approach and Architecture

### 1. Multi-Channel Anomaly Ingestion & Scoring
Raw telemetry from satellite subsystems is continuously ingested and normalized. Statistical anomaly scores and deviation thresholds are calculated across channels to detect anomalous variance against nominal operational baselines.

### 2. The 5-Stage Forensics Pipeline
The investigation engine processes anomalies through five structured phases:
* **01 Detect:** Continuous sensor stream ingestion and deviation thresholding across active channels.
* **02 Connect:** Uncovering temporal lead-lag relationships across independent telemetry streams.
* **03 Reconstruct:** Mapping telemetry anomalies onto 3D coordinate spacecraft meshes and 4D spacetime trajectories.
* **04 Investigate:** Calculating pairwise activation sequences, duration overlaps, and 99% signal morphology similarities.
* **05 Explain:** Synthesizing statistical evidence into clear natural-language forensic summaries and diagnostic recommendations.

### 3. Spatiotemporal 4D Event Graph & Sequence Consistency
Anomalies are linked into a temporal directed acyclic graph (DAG). The engine measures sequence consistency and channel precedence, verifying that an initiator channel (e.g., `CADC0888`) directly preceded downstream failures across power and thermal subsystems.

### 4. Automated Diagnostic Playbook Generation
The system correlates evidence graph confidence scores with standard flight operating procedures to generate priority-ranked recovery protocols (e.g., transponder high-speed bus inspection, thermal loop shedding, and battery voltage regulation).

---

## How IBM Bob Was Used

This project was built end-to-end using **IBM Bob** as our primary AI development partner:
* **Plan Mode Architecture:** Used IBM Bob's Plan Mode to architect the full 5-stage telemetry forensics pipeline and map Three.js 3D coordinate bindings to sensor IDs.
* **Full-Stack Scaffolding & Prototyping:** Scaffolded the FastAPI backend, telemetry stream parsers, and React 3D spatialization components directly inside the workspace.
* **Debugging & Algorithm Optimization:** Utilized IBM Bob to refine pairwise temporal correlation algorithms, calculate sequence consistency scores, and optimize WebGL rendering performance for high-density spacetime point clouds.
