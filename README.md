<p align="center">
  <img src="frontend/public/assets/images/cluespace-banner.png" alt="ClueSpace Banner" width="750">
</p>

<h1 align="center">
  <em>ClueSpace</em>
</h1>

<p align="left">
  <strong>Try it here:</strong> -🌐https://clue-space.vercel.app/
  <br>
  <strong>Demo Video</strong> - YOUR_DEMO_VIDEO_LINK
</p>
</p>

<br>

## The Challenge
> **An anomaly is a signal. An incident is a story.**

Spacecraft continuously generate telemetry across numerous channels. Detecting an anomaly tells engineers that something unusual occurred—but not necessarily how the surrounding incident unfolded.

The evidence needed to investigate an incident is distributed across channels, timestamps, event sequences, anomaly windows, and temporal relationships. Events may occur seconds apart, overlap in time, or form patterns that are difficult to recognize when examined individually.

This creates an **investigation gap**: engineers can identify abnormal signals, but still need to determine **what happened, in what sequence, which events belong together, and what evidence supports the reconstruction.**

> **The real challenge isn't finding the anomaly. It's reconstructing the incident from the evidence.**

That is the problem ClueSpace is built to solve.


<br>

## The ClueSpace Approach

ClueSpace moves the investigation process from isolated anomaly detection toward **evidence-based incident reconstruction**.

</p>

Instead of asking only **"What was anomalous?"**, ClueSpace helps answer:

- **What happened?**
- **When did it happen?**
- **Which events are connected?**
- **How did affected channels behave relative to one another?**
- **What evidence supports the reconstruction?**
- **What should an investigator examine next?**

<br>


## Product Walkthrough

<table>
  <tr>
    <td width="50%">
      <img src="./screen-shots/Mission control.png" alt="Mission Control">
    </td>
    <td width="50%">
      <img src="./screen-shots/Incident-explorer.png" alt="Incident Explorer">
    </td>
  </tr>

  <tr>
    <td width="50%">
      <img src="./screen-shots/anomaly-spatializer.png" alt="Anomaly Spatializer">
    </td>
    <td width="50%">
      <img src="./screen-shots/Telemetry-spacetime.png" alt="Telemetry Spacetime">
    </td>
  </tr>
</table>

## Investigation Workflow

<!-- Add Investigation Workflow generated image here -->



## Intelligence & Evidence

### From Anomaly to Explanation

Anomaly detection is the **starting point—not the endpoint.**

```text
ANOMALY
"What changed?"
        ↓
TEMPORAL EVIDENCE
"When did related events occur?"
        ↓
CROSS-CHANNEL CORRELATION
"Which signals behaved together?"
        ↓
PATTERN EVIDENCE
"Do their behaviors match?"
        ↓
INCIDENT RECONSTRUCTION
"Which events belong to the same story?"
        ↓
INVESTIGATION INSIGHT
"What should be examined next?"
# ClueSpace — Space Mission Incident Investigator

*Where telemetry becomes evidence, and anomalies become answers.*

**Challenge theme:** Space Telemetry & Autonomous AI Systems  
**Challenge:** IBM Bob AI Builders Challenge (August)

**Try it here:** https://cluespace-app.railway.app  
*(Replace with your live deployment link)*

---

## Motivation

Modern satellites generate hundreds of thousands of multi-channel telemetry data points every second. When complex anomalies occur in orbit, manual incident diagnosis across isolated 2D charts takes hours or even days—wasting critical time when spacecraft assets are on the line.

**ClueSpace** is an autonomous telemetry forensics and root-cause reconstruction engine. It ingests high-frequency spacecraft sensor streams, reconstructs cascade anomalies in interactive 3D/4D space, and correlates multi-channel telemetry into clear, evidence-backed diagnostic playbooks.

---

## How to Use

1. **Explore Mission Control** — View real-time fleet intelligence, severity distributions, and cross-channel failure classifications across 805+ reconstructed incidents.
2. **Launch the Anomaly Spatializer** — Inspect live telemetry mapped directly onto a 3D satellite model to see physical subsystem stress and channel-level deviations.
3. **Scrub Telemetry Spacetime** — Play the 4D timeline visualizer to watch how anomaly clusters physically propagate across telemetry channels.
4. **Select an Incident Investigation** — Filter by severity (Critical / High / Moderate / Low) and load complete forensic cases (e.g., Incident `INV-988`).
5. **Review Evidence Graph & Playbook** — Inspect the millisecond activation sequence, 99% signal pattern similarity links, and execute priority-ranked diagnostic actions.

---

## Demo

**Demo video:** https://youtu.be/your-video-link

| | |
|:---:|:---:|
| <img src="screenshots/hero_spatializer.png" width="100%" alt="3D Anomaly Spatializer"/> | <img src="screenshots/spacetime_4d.png" width="100%" alt="Telemetry Spacetime 4D"/> |
| <img src="screenshots/mission_control.png" width="100%" alt="Mission Control Dashboard"/> | <img src="screenshots/investigation_workspace.png" width="100%" alt="Forensic Investigation Workspace"/> |

---

## Tech Stack
