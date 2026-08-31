<p align="center">
  <img src="frontend/public/assets/images/cluespace-banner.png" alt="ClueSpace Banner" width="750">
</p>

<h1 align="center">
  <em>ClueSpace</em>
</h1>

# 🚀 ClueSpace

### Don't just detect the anomaly. Reconstruct the incident.

> **ClueSpace turns fragmented spacecraft telemetry into an evidence-backed incident investigation.**

Spacecraft continuously generate telemetry across many channels and subsystems. When something behaves unexpectedly, detecting the anomaly is only the beginning.

The harder question is:

> **What happened, how did it unfold, which events are connected, and what evidence supports the investigation?**

ClueSpace is built around this investigation gap.

Instead of treating anomalies as isolated alerts, ClueSpace connects related events across **channels and time**, reconstructs the incident sequence, organizes the supporting evidence, and produces a structured investigation with a leading hypothesis and recommended investigative actions.

---

## 🔎 The Issue

### An anomaly is a signal. An incident is a story.

A spacecraft incident rarely appears as one isolated telemetry value.

Related anomalies can occur across different channels and at different points in time. Some events may precede others, some may follow them, and some may overlap within the same anomaly window.

The evidence needed to understand the incident therefore becomes fragmented across:

**Telemetry → Channels → Timestamps → Events → Anomaly Windows**

An engineer may know that something went wrong, but still has to manually determine:

- Which events belong to the same incident?
- What happened first?
- What happened next?
- Which signals are related?
- How did the incident unfold over time?
- What evidence supports a possible explanation?
- What should be investigated next?

### The real challenge isn't detecting the anomaly.

### It's reconstructing the incident from the evidence.

---

# ✨ Our Magic Solution

ClueSpace treats spacecraft anomalies as **clues belonging to a larger incident**.

It brings related telemetry events together, reconstructs their temporal relationships, connects the evidence through an interactive graph, and transforms that evidence into a structured investigation.

The workflow is:

**Telemetry → Anomaly → Incident → Evidence → Investigation → Action**

ClueSpace helps investigators move from an isolated abnormal signal to a connected understanding of the incident.

The system is designed to support engineering judgment, not replace it. Instead of presenting an unexplained conclusion, ClueSpace makes the investigation trail visible so that the evidence behind a hypothesis can be inspected.

---

# 🛰️ How ClueSpace Works

```text
                SPACECRAFT TELEMETRY
                         │
                         ▼
                 ┌───────────────┐
                 │ Anomaly Events│
                 └───────┬───────┘
                         │
                         ▼
                ┌─────────────────┐
                │    Incident     │
                │  Reconstruction │
                └────────┬────────┘
                         │
             ┌───────────┼───────────┐
             ▼           ▼           ▼
          CHANNELS      TIME       EVENTS
             │           │           │
             └───────────┼───────────┘
                         ▼
                ┌─────────────────┐
                │  Evidence Graph │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │  Investigation  │
                │    Hypothesis   │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ Recommended     │
                │ Investigations  │
                └─────────────────┘
