<p align="center">
  <img src="frontend/public/assets/images/cluespace-banner.png" alt="ClueSpace Banner" width="750">
</p>

<h1 align="center">
  <em>ClueSpace</em>
</h1>

<div align="center">

# 🛰️ ClueSpace
### Autonomous Spacecraft Telemetry Forensics & Root-Cause Reconstruction

**Transforming chaotic multi-sensor telemetry into spatialized evidence and automated recovery actions.**

[![Challenge](https://img.shields.io/badge/IBM%20SkillsBuild-AI%20Builders%20Challenge-blue?style=for-the-badge&logo=IBM)](https://skillsbuild.org/)
[![Stack](https://img.shields.io/badge/Three.js-WebGL%203D-black?style=for-the-badge&logo=three.js)](https://threejs.org/)
[![Backend](https://img.shields.io/badge/Python-FastAPI-green?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)

[Live Application](#) • [Demo Video](#) • [Architecture](#system-architecture)

---

</div>

## 🌌 The Mission Problem

During an orbital anomaly, spacecraft flight controllers receive high-dimensional telemetry streams containing hundreds of thousands of sensor readings. 

* **The Sifting Dilemma:** Identifying the root cause across overlapping thermal, power, and RF channels is like finding a needle in a digital haystack.
* **Cascade Blindspots:** Over **60.1% of critical mission anomalies are multi-channel cascades**, where the true initiator channel triggers chained failures across detached subsystems.
* **Cost of Delay:** Manual 2D telemetry analysis takes hours—costing irreplaceable mission time during critical orbital passes.

---

## ⚡ Solution: ClueSpace

**ClueSpace** is an autonomous incident investigation engine that ingests raw telemetry, reconstructs cross-sensor anomalies in **3D coordinate space and 4D spacetime**, generates statistical evidence graphs, and produces automated diagnostic playbooks for flight control teams.

---

## 🖥️ System Walkthrough & Key Capabilities

| **3D Anomaly Spatializer** | **4D Telemetry Spacetime** |
| :---: | :---: |
| <img src="screenshots/anomaly_spatializer.png" width="100%" alt="3D Anomaly Spatializer"/> | <img src="screenshots/telemetry_spacetime.png" width="100%" alt="4D Telemetry Spacetime Visualizer"/> |
| *Pins telemetry anomalies to physical satellite components with real-time severity filters.* | *Maps sensor events along a 4D spacetime continuum to track failure propagation vectors.* |

| **Mission Control Intelligence** | **Forensic Investigation Workspace** |
| :---: | :---: |
| <img src="screenshots/mission_control.png" width="100%" alt="Mission Control Dashboard"/> | <img src="screenshots/investigation_workspace.png" width="100%" alt="Investigation Workspace"/> |
| *Fleet-level triage tracking 805 incidents, severity distributions, and vulnerable channels.* | *Reconstructs millisecond activation sequences, 99% pattern matches, and diagnostic playbooks.* |

---

## 🔄 The 5-Stage Forensics Pipeline
