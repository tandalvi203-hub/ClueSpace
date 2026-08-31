"""
member2/actions.py
------------------
Recommended Investigation Action Generator for Member 2 — Incident Investigation Engineer.

PURPOSE
-------
Generate evidence-grounded recommended investigation actions for human operators.
Each action is a suggestion for what a human investigator should review next, based
solely on telemetry evidence contained in the incident characterisation, scores, and
hypothesis outputs.

WHAT THIS MODULE DOES NOT GENERATE
-----------------------------------
- Spacecraft commands
- Autonomous control actions
- Physical remediation instructions
- Causal claims of any kind

SCIENTIFIC RULE
---------------
Temporal correlation is NOT physical causality.
No action description claims that one channel caused another.
All language is strictly observational and investigative in nature.

Action categories
-----------------
REVIEW_INITIAL_CHANNEL
    Recommend examining the first-activating channel in detail.
    Always generated for single- and multi-channel incidents alike.

REVIEW_TEMPORAL_SEQUENCE
    Recommend reviewing the recorded inter-channel temporal ordering.
    Generated only when a multi-channel incident has a confirmed activation order
    with at least one temporal relationship recorded.

REVIEW_OVERLAPPING_CHANNELS
    Recommend reviewing channels that show temporal window overlap.
    Generated only when at least one overlapping channel pair exists.

REVIEW_HIGH_DENSITY_WINDOW
    Recommend examining the high-density event window.
    Generated only when event_density_per_min exceeds the HIGH_DENSITY_THRESHOLD.

REVIEW_LONG_DURATION
    Recommend reviewing persistence characteristics.
    Generated only when persistence_class is LONG or EXTENDED.

PRIORITIZE_OPERATOR_INVESTIGATION
    Flag the incident for elevated operator attention.
    Generated only when severity_score >= SEVERITY_HIGH_THRESHOLD or
    significance_score >= SIGNIFICANCE_HIGH_THRESHOLD.

Determinism guarantee
---------------------
Actions are always generated in the fixed category order listed above.
Within each category exactly zero or one action is produced.
action_id values are stable: "ACT-{incident_id}-{sequence_number}".

Evidence references
-------------------
Each action carries ``evidence_refs``: a list of string identifiers referencing
the specific evidence elements that triggered the recommendation.  These are
taken directly from the input dicts; no evidence is invented.

PUBLIC API
----------
generate_actions(char_dict, scores_dict, hypothesis_dict) → list[dict]

Each returned dict contains:
    action_id       str   stable identifier, e.g. "ACT-988-1"
    category        str   one of the six categories above
    title           str   short human-readable title
    description     str   scientifically cautious, operator-facing description
    priority        int   1 (highest) – 5 (lowest); lower = more urgent
    evidence_refs   list[str]   references to triggering evidence
    rationale       str   one sentence explaining why this action was generated
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Module-level thresholds (calibrated to the OPS-SAT-AD dataset)
# ---------------------------------------------------------------------------

# Event density above which a HIGH_DENSITY review is triggered (ev/min).
# Calibrated to P75 of the observed dataset (median ≈ 13 ev/min; P75 ≈ 25 ev/min).
HIGH_DENSITY_THRESHOLD: float = 25.0

# Severity score (0–10) above which PRIORITIZE_OPERATOR_INVESTIGATION is triggered.
# Corresponds to the HIGH severity boundary used in scorer.py.
SEVERITY_HIGH_THRESHOLD: float = 5.0

# Significance score (0–100) above which PRIORITIZE_OPERATOR_INVESTIGATION is triggered.
# Calibrated to top ~35% of the observed distribution.
SIGNIFICANCE_HIGH_THRESHOLD: float = 60.0

# ---------------------------------------------------------------------------
# Category constants (ordered; determines action generation order)
# ---------------------------------------------------------------------------

CAT_REVIEW_INITIAL_CHANNEL        = "REVIEW_INITIAL_CHANNEL"
CAT_REVIEW_TEMPORAL_SEQUENCE      = "REVIEW_TEMPORAL_SEQUENCE"
CAT_REVIEW_OVERLAPPING_CHANNELS   = "REVIEW_OVERLAPPING_CHANNELS"
CAT_REVIEW_HIGH_DENSITY_WINDOW    = "REVIEW_HIGH_DENSITY_WINDOW"
CAT_REVIEW_LONG_DURATION          = "REVIEW_LONG_DURATION"
CAT_PRIORITIZE_OPERATOR           = "PRIORITIZE_OPERATOR_INVESTIGATION"

# Fixed generation order — determines action_id sequence numbers.
_CATEGORY_ORDER: list[str] = [
    CAT_REVIEW_INITIAL_CHANNEL,
    CAT_REVIEW_TEMPORAL_SEQUENCE,
    CAT_REVIEW_OVERLAPPING_CHANNELS,
    CAT_REVIEW_HIGH_DENSITY_WINDOW,
    CAT_REVIEW_LONG_DURATION,
    CAT_PRIORITIZE_OPERATOR,
]

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _safe_float(val: Any, default: float = 0.0) -> float:
    """Return a finite float or *default*."""
    import math
    try:
        f = float(val)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    """Return an int or *default*."""
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _overlapping_pairs(rels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only the relationship dicts where windows_overlap is True."""
    return [r for r in rels if r.get("windows_overlap", False)]


def _require_keys(d: dict[str, Any], keys: list[str], name: str) -> None:
    """Raise ValueError if any required key is absent."""
    missing = [k for k in keys if k not in d]
    if missing:
        raise ValueError(f"[{name}] Missing required keys: {missing}")


# ---------------------------------------------------------------------------
# Individual action builders (each returns a dict or None)
# ---------------------------------------------------------------------------

def _action_review_initial_channel(
    incident_id: int,
    char_dict: dict[str, Any],
    hypothesis_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    Always generated.  Points the operator to the first-activating channel.
    """
    activation_order: list[str] = list(char_dict.get("channel_activation_order", []))
    channels_affected: list[str] = list(char_dict.get("channels_affected", []))

    initial_channel = (
        activation_order[0]
        if activation_order
        else (channels_affected[0] if channels_affected else "UNKNOWN")
    )

    n_channels: int = _safe_int(char_dict.get("n_channels_affected", 1))
    peak: float = _safe_float(char_dict.get("peak_anomaly_score", 0.0))

    evidence_refs = [f"channel:{initial_channel}"]
    if channel_incident_ids := char_dict.get("channel_incident_ids"):
        if channel_incident_ids:
            evidence_refs.append(f"channel_incident:{channel_incident_ids[0]}")
    evidence_refs.append(f"peak_anomaly_score:{peak:.4f}")

    if n_channels == 1:
        description = (
            f"Review telemetry records for channel '{initial_channel}', "
            f"the sole affected channel in this incident. "
            f"Examine the anomaly pattern, magnitude, and timing."
        )
        rationale = (
            f"'{initial_channel}' is the only affected channel "
            f"(peak anomaly score: {peak:.4f}); initial review should focus here."
        )
    else:
        description = (
            f"Review telemetry records for channel '{initial_channel}', "
            f"the first channel to show anomalous behaviour in this incident. "
            f"Examine the anomaly pattern, magnitude, and timing relative to "
            f"the {n_channels - 1} other affected channel(s)."
        )
        rationale = (
            f"'{initial_channel}' is the earliest-activating channel in the "
            f"recorded activation order; investigation should begin here "
            f"(peak anomaly score: {peak:.4f})."
        )

    return {
        "action_id": "",   # filled by caller
        "category": CAT_REVIEW_INITIAL_CHANNEL,
        "title": f"Review initial anomaly channel: {initial_channel}",
        "description": description,
        "priority": 1,
        "evidence_refs": evidence_refs,
        "rationale": rationale,
    }


def _action_review_temporal_sequence(
    incident_id: int,
    char_dict: dict[str, Any],
    hypothesis_dict: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Generated only for multi-channel incidents with recorded temporal relationships.
    Not generated for single-channel incidents.
    """
    n_channels: int = _safe_int(char_dict.get("n_channels_affected", 1))
    if n_channels < 2:
        return None

    rels: list[dict[str, Any]] = list(char_dict.get("channel_temporal_relationships", []))
    if not rels:
        return None

    activation_order: list[str] = list(char_dict.get("channel_activation_order", []))
    chain: list[dict[str, Any]] = list(hypothesis_dict.get("chain", []))

    # Build evidence refs from temporal relationship data
    evidence_refs: list[str] = []
    for r in rels:
        ch_a = r.get("channel_a", "")
        ch_b = r.get("channel_b", "")
        gap = r.get("temporal_gap_sec", 0.0)
        if ch_a and ch_b:
            evidence_refs.append(f"temporal_rel:{ch_a}->{ch_b}:{gap:.1f}s")

    order_str = " → ".join(activation_order) if activation_order else "unknown order"
    n_rels = len(rels)

    description = (
        f"Review the recorded temporal sequence across {n_channels} affected channels: "
        f"{order_str}. "
        f"Examine whether the {n_rels} recorded inter-channel temporal relationship(s) "
        f"are consistent with known subsystem dependencies. "
        f"Note: temporal ordering is observational only; no physical mechanism is implied."
    )
    rationale = (
        f"A multi-channel incident ({n_channels} channels) with {n_rels} recorded "
        f"temporal relationship(s) warrants review of the activation sequence "
        f"to assess whether the ordering is consistent with nominal spacecraft behaviour."
    )

    return {
        "action_id": "",
        "category": CAT_REVIEW_TEMPORAL_SEQUENCE,
        "title": f"Review inter-channel temporal sequence ({n_channels} channels)",
        "description": description,
        "priority": 2,
        "evidence_refs": evidence_refs,
        "rationale": rationale,
    }


def _action_review_overlapping_channels(
    incident_id: int,
    char_dict: dict[str, Any],
    hypothesis_dict: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Generated only when at least one channel pair shows temporal window overlap.
    Not generated for single-channel incidents.
    """
    n_channels: int = _safe_int(char_dict.get("n_channels_affected", 1))
    if n_channels < 2:
        return None

    rels: list[dict[str, Any]] = list(char_dict.get("channel_temporal_relationships", []))
    overlapping = _overlapping_pairs(rels)
    if not overlapping:
        return None

    n_overlapping = len(overlapping)
    n_total_pairs = len(rels)

    # Build evidence refs from overlapping pairs
    evidence_refs: list[str] = []
    for r in overlapping:
        ch_a = r.get("channel_a", "")
        ch_b = r.get("channel_b", "")
        if ch_a and ch_b:
            evidence_refs.append(f"overlapping_pair:{ch_a}+{ch_b}")
    evidence_refs.append(
        f"n_corroborating_pairs:{hypothesis_dict.get('n_corroborating_pairs', n_overlapping)}"
    )

    pair_word = "pair" if n_overlapping == 1 else "pairs"
    overlap_pair_strs = [
        f"{r.get('channel_a', '')}+{r.get('channel_b', '')}" for r in overlapping
    ]
    description = (
        f"Review the {n_overlapping} channel {pair_word} that show temporal window overlap: "
        f"{', '.join(overlap_pair_strs)}. "
        f"Concurrent anomaly windows across multiple channels may indicate "
        f"a shared environmental condition or simultaneous subsystem stress. "
        f"This is a temporal observation; no physical causality is inferred."
    )
    rationale = (
        f"{n_overlapping} of {n_total_pairs} channel pair(s) exhibit temporally "
        f"overlapping anomaly windows, suggesting concurrent anomalous behaviour "
        f"that warrants cross-channel comparison."
    )

    return {
        "action_id": "",
        "category": CAT_REVIEW_OVERLAPPING_CHANNELS,
        "title": f"Review {n_overlapping} temporally overlapping channel pair(s)",
        "description": description,
        "priority": 2,
        "evidence_refs": evidence_refs,
        "rationale": rationale,
    }


def _action_review_high_density_window(
    incident_id: int,
    char_dict: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Generated only when event_density_per_min > HIGH_DENSITY_THRESHOLD.
    """
    density: float = _safe_float(char_dict.get("event_density_per_min", 0.0))
    if density <= HIGH_DENSITY_THRESHOLD:
        return None

    n_events: int = _safe_int(char_dict.get("n_events_total", 0))
    duration: float = _safe_float(char_dict.get("duration_sec", 0.0))

    evidence_refs = [
        f"event_density_per_min:{density:.2f}",
        f"n_events_total:{n_events}",
    ]
    if duration > 0.0:
        evidence_refs.append(f"duration_sec:{duration:.1f}")

    description = (
        f"Examine the high-density anomaly window for this incident "
        f"(observed rate: {density:.1f} anomaly events/min, {n_events} total events). "
        f"High event density may indicate rapid or sustained telemetry deviation "
        f"during the incident window. Review individual event timestamps and magnitudes "
        f"to characterise the burst pattern."
    )
    rationale = (
        f"Event density of {density:.1f} ev/min exceeds the high-density threshold "
        f"({HIGH_DENSITY_THRESHOLD:.0f} ev/min), indicating an elevated event rate "
        f"that warrants closer temporal examination."
    )

    return {
        "action_id": "",
        "category": CAT_REVIEW_HIGH_DENSITY_WINDOW,
        "title": f"Review high-density anomaly window ({density:.1f} ev/min)",
        "description": description,
        "priority": 3,
        "evidence_refs": evidence_refs,
        "rationale": rationale,
    }


def _action_review_long_duration(
    incident_id: int,
    char_dict: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Generated only when persistence_class is LONG or EXTENDED.
    """
    persistence: str = str(char_dict.get("persistence_class", "SHORT")).upper()
    if persistence not in {"LONG", "EXTENDED"}:
        return None

    duration: float = _safe_float(char_dict.get("duration_sec", 0.0))
    evidence_refs = [
        f"persistence_class:{persistence}",
        f"duration_sec:{duration:.1f}",
    ]

    if persistence == "EXTENDED":
        description = (
            f"Review the extended-duration anomaly pattern for this incident "
            f"(persistence class: EXTENDED, duration: {duration:.0f} s). "
            f"An extended anomaly window (≥ 900 s) may indicate a sustained "
            f"condition that persisted beyond transient effects. "
            f"Examine whether the anomaly magnitude varied over the duration."
        )
        rationale = (
            f"Persistence class EXTENDED (duration {duration:.0f} s ≥ 900 s) indicates "
            f"the anomaly was sustained for a prolonged period, warranting review of "
            f"the full anomaly trajectory."
        )
    else:
        description = (
            f"Review the long-duration anomaly pattern for this incident "
            f"(persistence class: LONG, duration: {duration:.0f} s). "
            f"An anomaly window of 300–900 s duration may indicate a condition "
            f"that outlasted a single transient. "
            f"Examine whether the anomaly magnitude varied over the duration."
        )
        rationale = (
            f"Persistence class LONG (300 s ≤ duration {duration:.0f} s < 900 s) "
            f"indicates the anomaly persisted beyond a brief transient, "
            f"warranting review of the full anomaly trajectory."
        )

    return {
        "action_id": "",
        "category": CAT_REVIEW_LONG_DURATION,
        "title": f"Review long-duration anomaly persistence ({persistence}, {duration:.0f} s)",
        "description": description,
        "priority": 3,
        "evidence_refs": evidence_refs,
        "rationale": rationale,
    }


def _action_prioritize_operator(
    incident_id: int,
    char_dict: dict[str, Any],
    scores_dict: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Generated when severity_score >= SEVERITY_HIGH_THRESHOLD or
    significance_score >= SIGNIFICANCE_HIGH_THRESHOLD.
    """
    severity: float = _safe_float(scores_dict.get("severity_score", 0.0))
    significance: float = _safe_float(scores_dict.get("significance_score", 0.0))
    severity_label: str = str(scores_dict.get("severity_label", "UNKNOWN"))

    triggers: list[str] = []
    evidence_refs: list[str] = []

    if severity >= SEVERITY_HIGH_THRESHOLD:
        triggers.append(
            f"severity score {severity:.4f} ({severity_label})"
        )
        evidence_refs.append(f"severity_score:{severity:.4f}")
        evidence_refs.append(f"severity_label:{severity_label}")

    if significance >= SIGNIFICANCE_HIGH_THRESHOLD:
        triggers.append(f"significance score {significance:.4f}")
        evidence_refs.append(f"significance_score:{significance:.4f}")

    if not triggers:
        return None

    trigger_text = " and ".join(triggers)
    peak: float = _safe_float(char_dict.get("peak_anomaly_score", 0.0))
    evidence_refs.append(f"peak_anomaly_score:{peak:.4f}")

    description = (
        f"This incident has been flagged for prioritised operator investigation "
        f"based on {trigger_text}. "
        f"A human operator should review this incident before lower-priority items. "
        f"All scores are derived from telemetry patterns only; "
        f"no physical origin or mechanism has been confirmed."
    )
    rationale = (
        f"Triggered by {trigger_text}, which exceeds the threshold for "
        f"elevated operator attention "
        f"(severity threshold: {SEVERITY_HIGH_THRESHOLD:.0f}, "
        f"significance threshold: {SIGNIFICANCE_HIGH_THRESHOLD:.0f})."
    )

    return {
        "action_id": "",
        "category": CAT_PRIORITIZE_OPERATOR,
        "title": f"Prioritise operator investigation (severity: {severity_label})",
        "description": description,
        "priority": 1,
        "evidence_refs": evidence_refs,
        "rationale": rationale,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_actions(
    char_dict: dict[str, Any],
    scores_dict: dict[str, Any],
    hypothesis_dict: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Generate evidence-grounded recommended investigation actions for an operator.

    Actions are recommendations for human review only.  No spacecraft commands,
    autonomous control actions, or causal claims are ever generated.

    Parameters
    ----------
    char_dict:
        Dict as returned by ``characteriser.get_incident_characterisation``.
        Required keys: spacecraft_incident_id, n_channels_affected,
        channel_activation_order, channels_affected, channel_temporal_relationships.
    scores_dict:
        Dict as returned by ``scorer.score_incident``.
        Required keys: severity_score, significance_score.
    hypothesis_dict:
        Dict as returned by ``hypothesis.build_hypothesis``.
        Required keys: hypothesis_type, chain, n_corroborating_pairs.

    Returns
    -------
    list[dict]
        Ordered list of action dicts.  May be empty if no conditions are triggered
        (rare in practice — REVIEW_INITIAL_CHANNEL is always generated).
        Each dict has keys: action_id, category, title, description, priority,
        evidence_refs, rationale.

    Raises
    ------
    ValueError
        If required keys are missing from any of the input dicts.
    """
    _require_keys(char_dict, [
        "spacecraft_incident_id",
        "n_channels_affected",
        "channel_activation_order",
        "channels_affected",
        "channel_temporal_relationships",
    ], "char_dict")
    _require_keys(scores_dict, ["severity_score", "significance_score"], "scores_dict")
    _require_keys(hypothesis_dict, [
        "hypothesis_type", "chain", "n_corroborating_pairs",
    ], "hypothesis_dict")

    incident_id: int = _safe_int(char_dict.get("spacecraft_incident_id", 0))

    # Build candidate actions in fixed category order
    candidates: list[dict[str, Any] | None] = [
        _action_review_initial_channel(incident_id, char_dict, hypothesis_dict),
        _action_review_temporal_sequence(incident_id, char_dict, hypothesis_dict),
        _action_review_overlapping_channels(incident_id, char_dict, hypothesis_dict),
        _action_review_high_density_window(incident_id, char_dict),
        _action_review_long_duration(incident_id, char_dict),
        _action_prioritize_operator(incident_id, char_dict, scores_dict),
    ]

    # Assign stable action_ids only to actions that were generated (not None)
    actions: list[dict[str, Any]] = []
    seq = 1
    for action in candidates:
        if action is not None:
            action["action_id"] = f"ACT-{incident_id}-{seq}"
            actions.append(action)
            seq += 1

    return actions
