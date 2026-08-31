"""
member2/investigator.py
-----------------------
End-to-end orchestration layer for the Space Mission Incident Investigator.

This module is the ONLY public entry point for Member 2.  It coordinates the
five existing intelligence modules in a fixed, deterministic pipeline:

    1. characteriser.get_incident_characterisation   → char_dict
    2. scorer.score_incident                         → scores_dict
    3. hypothesis.build_hypothesis                   → hypothesis_dict
    4. evidence_graph.build_evidence_graph           → EvidenceGraph
    5. actions.generate_actions                      → list[dict]

All intelligence logic lives in the modules above; this orchestrator only
calls them in order and assembles the final ``InvestigationReport``.

Public API
----------
investigate_incident(spacecraft_incident_id, anomaly_events_df, incidents_df,
                     spacecraft_incidents_df)  →  InvestigationReport

Scientific safety
-----------------
- No causal or root-cause claims are ever introduced here.
- No LLM, ML model, or autonomous command is called.
- All conclusions trace directly to the upstream module outputs.
- The ``scientific_note`` field is inherited from ``output_schema.SCIENTIFIC_NOTE``.

Determinism
-----------
Same input DataFrames and incident ID always produce the same report.

Error handling
--------------
- Invalid spacecraft_incident_id  → ValueError (propagated from characteriser)
- Missing required columns        → ValueError (propagated from characteriser)
- Missing referenced incidents    → ValueError (propagated from characteriser)
- Invalid timestamps / numerics   → ValueError (propagated from characteriser)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from member2 import characteriser, scorer, hypothesis, evidence_graph, actions
from member2.output_schema import (
    SCIENTIFIC_NOTE,
    DatasetStats,
    EvidenceGraph,
    Investigation,
    InvestigationReport,
    MissionImpactLevel,
    TimelineEvent,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _mission_impact_from_severity(severity_label: str) -> MissionImpactLevel:
    """
    Map the severity label produced by scorer.py to a MissionImpactLevel.

    The mapping is one-to-one and based solely on the severity score label;
    no causal claim is made.

        CRITICAL → CRITICAL
        HIGH     → HIGH
        MODERATE → MODERATE
        LOW      → LOW  (default for unknown labels)
    """
    mapping = {
        "CRITICAL": MissionImpactLevel.CRITICAL,
        "HIGH":     MissionImpactLevel.HIGH,
        "MODERATE": MissionImpactLevel.MODERATE,
        "LOW":      MissionImpactLevel.LOW,
    }
    return mapping.get(severity_label.upper(), MissionImpactLevel.LOW)


def _mission_impact_basis(
    severity_label: str,
    severity_score: float,
    significance_score: float,
) -> list[str]:
    """
    Build a list of evidence-grounded basis strings for the mission impact level.
    No causal language is used.
    """
    return [
        f"Severity label: {severity_label} (score: {severity_score:.4f}/10).",
        f"Significance score: {significance_score:.4f}/100.",
        "Mission impact level is derived from telemetry-based severity scoring only. "
        "No physical system mapping has been applied.",
    ]


def _hypothesis_statements(hypothesis_dict: dict[str, Any]) -> list[str]:
    """
    Extract ordered human-readable hypothesis statements from the hypothesis dict.

    Fix 4: Uses ``observed_evidence`` + ``temporal_relationships`` (chain-only,
    not the full all-pairs list) as the source.  The redundant per-pair gap
    bullets were removed from ``observed_evidence`` in hypothesis.py so the
    only gap information here is the activation-chain links from
    ``temporal_relationships``.
    """
    stmts: list[str] = []
    summary = hypothesis_dict.get("summary", "")
    if summary:
        stmts.append(summary)
    stmts.extend(hypothesis_dict.get("observed_evidence", []))
    stmts.extend(hypothesis_dict.get("temporal_relationships", []))
    return stmts


def _hypothesis_basis(hypothesis_dict: dict[str, Any]) -> list[str]:
    """
    Extract evidence-basis items (supporting evidence refs + scientific caveat).

    Fix 2: appends ``score_consistency_basis`` items when score_std is high,
    so the UI reader understands why confidence may be low despite high severity.
    """
    basis: list[str] = []
    for item in hypothesis_dict.get("supporting_evidence", []):
        if isinstance(item, dict):
            note = item.get("temporal_note", "")
            ch = item.get("channel", "")
            role = item.get("role", "")
            if ch:
                basis.append(f"Channel {ch} ({role}): {note}" if note else f"Channel {ch} ({role}).")
        elif isinstance(item, str):
            basis.append(item)
    # Fix 2: score-consistency explanation (added by hypothesis.py when std >= 0.25)
    basis.extend(hypothesis_dict.get("score_consistency_basis", []))
    caveat = hypothesis_dict.get("scientific_caveat", "")
    if caveat:
        basis.append(caveat)
    return basis


def _recommended_action_strings(actions_list: list[dict[str, Any]]) -> list[str]:
    """Convert the structured actions list to plain-text strings for the schema field."""
    result: list[str] = []
    for act in actions_list:
        action_id = act.get("action_id", "")
        title = act.get("title", "")
        description = act.get("description", "")
        result.append(f"[{action_id}] {title}: {description}")
    return result


def _build_dataset_stats(
    anomaly_events_df: pd.DataFrame,
    incidents_df: pd.DataFrame,
    spacecraft_incidents_df: pd.DataFrame,
) -> DatasetStats:
    """Compute dataset-level statistics from the three loaded DataFrames."""
    total_spacecraft = len(spacecraft_incidents_df)
    total_channel = len(incidents_df)
    total_events = len(anomaly_events_df)

    # Multi-channel count: spacecraft incidents with n_channels_affected > 1
    if "n_channels_affected" in spacecraft_incidents_df.columns:
        multi_channel_count = int(
            (spacecraft_incidents_df["n_channels_affected"].astype(int) > 1).sum()
        )
    else:
        multi_channel_count = 0

    # Date range from anomaly events
    timestamps = anomaly_events_df["timestamp"]
    date_range_start = timestamps.min()
    date_range_end = timestamps.max()

    # Convert to UTC-aware datetime
    if isinstance(date_range_start, pd.Timestamp):
        if date_range_start.tzinfo is None:
            date_range_start = date_range_start.tz_localize("UTC")
        date_range_start = date_range_start.to_pydatetime()
    if isinstance(date_range_end, pd.Timestamp):
        if date_range_end.tzinfo is None:
            date_range_end = date_range_end.tz_localize("UTC")
        date_range_end = date_range_end.to_pydatetime()

    # Observed channels
    channels_observed = sorted(anomaly_events_df["channel"].astype(str).unique().tolist())

    return DatasetStats(
        total_spacecraft_incidents=total_spacecraft,
        total_channel_incidents=total_channel,
        total_anomaly_events=total_events,
        multi_channel_count=multi_channel_count,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        channels_observed=channels_observed,
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_AE_REQUIRED = ["timestamp", "channel", "segment", "value", "anomaly_score"]
_INC_REQUIRED = ["incident_id", "channel", "segment", "start_time", "end_time",
                  "duration_sec", "n_events", "peak_anomaly_score", "mean_anomaly_score",
                  "spacecraft_incident_id"]
_SI_REQUIRED = ["spacecraft_incident_id", "start_time", "end_time", "duration_sec",
                 "channels_affected", "n_channels_affected", "n_events_total",
                 "peak_anomaly_score", "mean_anomaly_score", "segments_affected"]


def _validate_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"[{name}] Missing required column(s): {missing}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def investigate_incident(
    spacecraft_incident_id: int,
    anomaly_events_df: pd.DataFrame,
    incidents_df: pd.DataFrame,
    spacecraft_incidents_df: pd.DataFrame,
) -> InvestigationReport:
    """
    Orchestrate a complete investigation for one spacecraft incident.

    Parameters
    ----------
    spacecraft_incident_id:
        The integer ID of the spacecraft incident to investigate.
    anomaly_events_df:
        Loaded ``anomaly_events.csv`` DataFrame (from ``loaders.py``).
    incidents_df:
        Loaded ``incidents.csv`` DataFrame (from ``loaders.py``).
    spacecraft_incidents_df:
        Loaded ``spacecraft_incidents.csv`` DataFrame (from ``loaders.py``).
        ``channels_affected`` column must already be a Python list
        (as produced by ``load_spacecraft_incidents_csv``).

    Returns
    -------
    InvestigationReport
        A fully assembled, Pydantic-validated investigation report containing
        one ``Investigation`` entry for the requested incident.

    Raises
    ------
    ValueError
        - If ``spacecraft_incident_id`` is not found.
        - If required columns are missing from any input DataFrame.
        - If data contains invalid timestamps or non-finite numerics.
    TypeError
        If any input DataFrame is not a pandas DataFrame.
    """
    # --- Input type guard ---
    for df, name in [
        (anomaly_events_df, "anomaly_events_df"),
        (incidents_df, "incidents_df"),
        (spacecraft_incidents_df, "spacecraft_incidents_df"),
    ]:
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"{name} must be a pandas DataFrame, got {type(df).__name__}")

    # --- Column validation ---
    _validate_columns(anomaly_events_df, _AE_REQUIRED, "anomaly_events_df")
    _validate_columns(incidents_df, _INC_REQUIRED, "incidents_df")
    _validate_columns(spacecraft_incidents_df, _SI_REQUIRED, "spacecraft_incidents_df")

    sid = int(spacecraft_incident_id)

    # -----------------------------------------------------------------------
    # Pipeline stage 1: Characterisation
    # -----------------------------------------------------------------------
    char_dict = characteriser.get_incident_characterisation(
        spacecraft_incident_id=sid,
        anomaly_events_df=anomaly_events_df,
        incidents_df=incidents_df,
        spacecraft_incidents_df=spacecraft_incidents_df,
    )

    # -----------------------------------------------------------------------
    # Pipeline stage 2: Scoring
    # -----------------------------------------------------------------------
    scores_dict = scorer.score_incident(char_dict)

    # -----------------------------------------------------------------------
    # Pipeline stage 3: Hypothesis
    # -----------------------------------------------------------------------
    hypothesis_dict = hypothesis.build_hypothesis(char_dict, scores_dict)

    # -----------------------------------------------------------------------
    # Pipeline stage 4: Evidence graph
    # -----------------------------------------------------------------------
    evidence_graph_obj: EvidenceGraph = evidence_graph.build_evidence_graph(
        char_dict, scores_dict, hypothesis_dict
    )

    # -----------------------------------------------------------------------
    # Pipeline stage 5: Actions
    # -----------------------------------------------------------------------
    actions_list = actions.generate_actions(char_dict, scores_dict, hypothesis_dict)

    # -----------------------------------------------------------------------
    # Assemble Investigation
    # -----------------------------------------------------------------------
    severity_label: str = str(scores_dict.get("severity_label", "LOW"))
    severity_score: float = float(scores_dict.get("severity_score", 0.0))
    significance_score: float = float(scores_dict.get("significance_score", 0.0))

    mission_impact = _mission_impact_from_severity(severity_label)
    impact_basis = _mission_impact_basis(severity_label, severity_score, significance_score)

    hyp_statements = _hypothesis_statements(hypothesis_dict)
    hyp_basis = _hypothesis_basis(hypothesis_dict)
    recommended = _recommended_action_strings(actions_list)

    now_utc = datetime.now(tz=timezone.utc)
    # Fix 5: stable investigation ID — no embedded timestamp
    investigation_id = f"INV-{sid}"

    # Fix 3: timeline truncation metadata
    raw_timeline = char_dict["timeline"]
    timeline_shown_count = len(raw_timeline)
    timeline_truncated = char_dict["n_events_total"] > timeline_shown_count

    investigation = Investigation(
        investigation_id=investigation_id,
        spacecraft_incident_id=sid,
        generated_at=now_utc,
        start_time=char_dict["start_time"],
        end_time=char_dict["end_time"],
        duration_sec=char_dict["duration_sec"],
        timeline=raw_timeline,
        timeline_truncated=timeline_truncated,
        timeline_shown_count=timeline_shown_count,
        n_channels_affected=char_dict["n_channels_affected"],
        channels_affected=char_dict["channels_affected"],
        channel_activation_order=char_dict["channel_activation_order"],
        is_multi_channel=char_dict["is_multi_channel"],
        n_events_total=char_dict["n_events_total"],
        event_density_per_min=char_dict["event_density_per_min"],
        persistence_class=char_dict["persistence_class"],
        segment_span=char_dict["segment_span"],
        significance_score=significance_score,
        significance_components=dict(scores_dict.get("significance_components", {})),
        severity_score=severity_score,
        severity_components=dict(scores_dict.get("severity_components", {})),
        severity_rules_applied=[],
        investigation_confidence=float(scores_dict.get("investigation_confidence", 0.0)),
        confidence_components=dict(scores_dict.get("confidence_components", {})),
        peak_anomaly_score=char_dict["peak_anomaly_score"],
        mean_anomaly_score=char_dict["mean_anomaly_score"],
        score_std=char_dict["score_std"],
        hypothesis_statements=hyp_statements,
        hypothesis_basis=hyp_basis,
        mission_impact_level=mission_impact,
        mission_impact_basis=impact_basis,
        recommended_actions=recommended,
        evidence_graph=evidence_graph_obj,
        channel_incident_ids=char_dict["channel_incident_ids"],
        channel_temporal_relationships=char_dict["channel_temporal_relationships"],
        scientific_note=SCIENTIFIC_NOTE,
    )

    # -----------------------------------------------------------------------
    # Assemble dataset stats
    # -----------------------------------------------------------------------
    dataset_stats = _build_dataset_stats(
        anomaly_events_df, incidents_df, spacecraft_incidents_df
    )

    # -----------------------------------------------------------------------
    # Assemble InvestigationReport
    # -----------------------------------------------------------------------
    report = InvestigationReport(
        generated_at=now_utc,
        source_files={
            "anomaly_events": "anomaly_events.csv",
            "incidents": "incidents.csv",
            "spacecraft_incidents": "spacecraft_incidents.csv",
        },
        dataset_stats=dataset_stats,
        investigations=[investigation],
    )

    return report
