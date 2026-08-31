<p align="center">
  <img src="frontend/public/assets/images/cluespace-banner.png" alt="ClueSpace Banner" width="750">
</p>

# ClueSpace — IBM Bob August Challenge

*Where telemetry becomes evidence, and anomalies become answers. Turn raw spacecraft telemetry into 3D spatialized root-cause investigations.*

**Challenge theme:** Space Telemetry & Autonomous Mission Intelligence  
**Challenge:** IBM Bob AI Builders Challenge (August)

**Try it here:** https://clue-space.vercel.app/ 




**ClueSpace turns fragmented spacecraft telemetry into an evidence-backed incident investigation.**

When a spacecraft anomaly occurs, detecting the abnormal signal is only the beginning. The harder problem is understanding what happened around it.

ClueSpace connects related telemetry events across **channels and time**, reconstructs how an incident unfolded, organizes the supporting evidence into an **Evidence Graph**, and produces a structured investigation with a **leading hypothesis, severity, confidence, and recommended investigative actions**.

[🎥 Watch the Demo](YOUR_VIDEO_LINK)



## At a Glance

| | |
|---|---|
| **What** | Spacecraft telemetry incident investigation and reconstruction |
| **Core Problem** | Fragmented anomalies make incident reconstruction difficult |
| **Core Insight** | Related anomalies are clues belonging to the same incident |
| **Investigation** | Temporal relationships + channel context + evidence graph |
| **Output** | Structured investigation, hypothesis, supporting evidence, and next actions |
| **Spatial View** | 3D visualization of affected spacecraft subsystems |
| **Primary Development Tool** | IBM Bob |
| **Challenge** | August 2026 — Advance Space Exploration with AI |

---

# 🔎 The Problem

### An anomaly is a signal. An incident is a story.

Spacecraft continuously generate telemetry across many channels and subsystems.

When a signal deviates from its expected behavior, engineers can detect the anomaly. But an incident rarely appears as one isolated signal.

Related events can occur across different channels, at different points in time, and within overlapping anomaly windows.

The evidence is therefore scattered across:

**Channels → Timestamps → Events → Anomaly Windows**

An investigator may know that something went wrong, but still has to manually work out:

- Which events belong to the same incident?
- What happened first?
- What happened next?
- Which signals are related?
- How did the incident unfold?
- What evidence supports the investigation?
- Where should the investigation continue?

### The real challenge isn't finding the anomaly.

### **It's reconstructing the incident from the evidence.**

---

# ✨ The ClueSpace Approach

ClueSpace treats anomalies as **clues**, rather than isolated alerts.

The system brings related telemetry events together and reconstructs their relationships across time and channels.

Instead of:

```text
Telemetry
   ↓
Anomaly Detected
   ↓
Alert
