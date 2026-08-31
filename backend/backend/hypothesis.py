"""
member2/hypothesis.py
---------------------
Evidence-grounded Failure Chain Hypothesis Engine for Member 2.

PURPOSE
-------
Given the output of characteriser.py and scorer.py for one spacecraft incident,
construct a structured failure-chain hypothesis that answers:

    "What sequence of telemetry events is temporally associated with this
     incident, and what evidence supports that hypothesis?"

SCIENTIFIC RULE
---------------
Temporal correlation is NOT physical causality.

Every hypothesis produced by this module EXPLICITLY includes:

    "Temporal correlation observed; physical causality not confirmed."

All language is strictly observational:
    - "Channel A preceded Channel B by X seconds" (OK)
    - "Channel A caused Channel B" (NEVER)

PUBLIC API
----------
build_hypothesis(char_dict, scores_dict)  →  dict

The returned dict contains:

    hypothesis_id            str    unique identifier
    hypothesis_type          str    "single_channel" | "multi_channel" | "insufficient_evidence"
    summary                  str    one human-readable sentence
    chain                    list[dict]   ordered channel links (see below)
    supporting_evidence      list[dict]   per-channel evidence items
    hypothesis_confidence    float  in [0, 1] — derived from temporal evidence only
    scientific_caveat        str    constant mandatory disclaimer
    observed_evidence        list[str]   bullet-point factual observations
    temporal_relationships   list[str]   bullet-point relational observations
    n_corroborating_pairs    int    count of overlapping channel pairs

Chain link dict keys
--------------------
    source_channel      str
    target_channel      str
    gap_seconds         float   (B_start − A_start, always ≥ 0)
    precedence          str     "A_before_B" | "simultaneous"
    windows_overlap     bool
    evidence_ref        str     human-readable reference to the relationship

Supporting evidence item keys
-----------------------------
    channel             str
    first_activation    str     ISO-8601 UTC timestamp
    channel_incident_id str     (if available)
    n_events            int     (if available from char_dict context)
    role                str     "primary" | "secondary" | "concurrent"
    temporal_note       str     human-readable placement note

CONFIDENCE METHODOLOGY
----------------------
Hypothesis confidence is computed deterministically from temporal evidence only:

    1.  chain_completeness   = len(chain) / max(1, n_channels - 1)
        A complete chain connects every consecutive channel pair.

    2.  overlap_fraction     = n_overlapping_pairs / max(1, total_pairs)
        Fraction of all pairs that share overlapping windows.

    3.  gap_penalty          = mean temporal gap normalised by 3600 s (1 hour),
        clipped to [0, 1], inverted: gap_score = 1 - clip(mean_gap/3600, 0, 1)
        Tighter temporal clustering increases confidence.

    4.  channel_count_bonus  = clip((n_channels - 1) / 4, 0, 1)
        More channels = more corroborating evidence available.

    Weighted combination:
        raw = 0.40 * chain_completeness
            + 0.30 * overlap_fraction
            + 0.20 * gap_score
            + 0.10 * channel_count_bonus
        hypothesis_confidence = round(clip(raw, 0.0, 1.0), 4)

    For single-channel incidents: hypothesis_confidence = 0.0
    For insufficient-evidence cases: hypothesis_confidence = 0.0

EDGE CASES
----------
- Single-channel incident   → hypothesis_type = "single_channel"; chain = []
- Empty temporal rels       → hypothesis_type = "insufficient_evidence"
- All simultaneous channels → chain built with gap_seconds = 0.0
- Non-overlapping channels  → windows_overlap = False in each link
"""

from __future__ import annotations

import math
from typing import Any

# Mandatory scientific caveat appended to every hypothesis.
SCIENTIFIC_CAVEAT: str = (
    "Temporal correlation observed; physical causality not confirmed. "
    "All failure-chain descriptions are evidence-supported hypotheses "
    "derived from telemetry patterns only."
)

# Gap normalisation ceiling (seconds).  Gaps larger than this contribute
# the minimum gap_score contribution.
_GAP_CEILING_SEC: float = 3600.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clip(value: float, lo: float, hi: float) -> float:
    """Clip *value* to [lo, hi]."""
    return max(lo, min(hi, value))


def _rel_key(channel_a: str, channel_b: str) -> frozenset:
    """Canonical unordered key for a channel pair."""
    return frozenset({channel_a, channel_b})


def _find_rel(
    rels: list[dict[str, Any]],
    ch_a: str,
    ch_b: str,
) -> dict[str, Any] | None:
    """
    Return the relationship dict for an unordered pair (ch_a, ch_b), or None.
    """
    key = _rel_key(ch_a, ch_b)
    for r in rels:
        if _rel_key(r["channel_a"], r["channel_b"]) == key:
            return r
    return None


def _compute_hypothesis_confidence(
    n_channels: int,
    chain: list[dict[str, Any]],
    rels: list[dict[str, Any]],
) -> float:
    """
    Compute hypothesis confidence in [0, 1] from temporal evidence alone.

    See module docstring for the full methodology.
    """
    if n_channels <= 1 or not rels:
        return 0.0

    total_pairs = len(rels)
    n_chain_links = len(chain)
    expected_links = n_channels - 1

    # 1. Chain completeness
    chain_completeness = n_chain_links / max(1, expected_links)
    chain_completeness = _clip(chain_completeness, 0.0, 1.0)

    # 2. Overlap fraction across all pairs
    n_overlap = sum(1 for r in rels if r.get("windows_overlap", False))
    overlap_fraction = _clip(n_overlap / max(1, total_pairs), 0.0, 1.0)

    # 3. Gap score (tight clustering → higher confidence)
    gaps = [r.get("temporal_gap_sec", 0.0) for r in rels]
    mean_gap = sum(gaps) / len(gaps) if gaps else 0.0
    gap_score = _clip(1.0 - mean_gap / _GAP_CEILING_SEC, 0.0, 1.0)

    # 4. Channel count bonus
    channel_count_bonus = _clip((n_channels - 1) / 4.0, 0.0, 1.0)

    raw = (
        0.40 * chain_completeness
        + 0.30 * overlap_fraction
        + 0.20 * gap_score
        + 0.10 * channel_count_bonus
    )
    return round(_clip(raw, 0.0, 1.0), 4)


def _role_for_channel(channel: str, activation_order: list[str]) -> str:
    """
    Assign a descriptive role based on position in activation order.

        index 0   → "primary"
        index > 0 → "secondary"

    If the channel is not in the activation order (shouldn't happen in
    well-formed input), return "secondary".
    """
    try:
        idx = activation_order.index(channel)
    except ValueError:
        return "secondary"
    return "primary" if idx == 0 else "secondary"


def _temporal_note(channel: str, activation_order: list[str], rels: list[dict[str, Any]]) -> str:
    """
    Build a short human-readable note describing when this channel activated
    relative to the first channel in the activation order.
    """
    if not activation_order:
        return "Activation timing unknown."
    first_ch = activation_order[0]
    if channel == first_ch:
        return "First channel to activate in the observed sequence."
    rel = _find_rel(rels, first_ch, channel)
    if rel is None:
        return f"Activated after {first_ch} (temporal relationship not quantified)."
    gap = rel.get("temporal_gap_sec", 0.0)
    if gap == 0.0:
        return f"Activated simultaneously with {first_ch}."
    return f"Activated {gap:.1f} s after {first_ch}."


# ---------------------------------------------------------------------------
# Public: build_hypothesis
# ---------------------------------------------------------------------------

def build_hypothesis(
    char_dict: dict[str, Any],
    scores_dict: dict[str, Any],
) -> dict[str, Any]:
    """
    Build an evidence-grounded failure-chain hypothesis for one spacecraft incident.

    Parameters
    ----------
    char_dict:
        Dict as returned by ``characteriser.get_incident_characterisation``.
        Required keys:
            spacecraft_incident_id, n_channels_affected, channels_affected,
            channel_activation_order, channel_temporal_relationships,
            channel_incident_ids, start_time, end_time.
    scores_dict:
        Dict as returned by ``scorer.score_incident``.
        Not used for confidence; retained for cross-referencing.

    Returns
    -------
    dict
        See module docstring for full key listing.

    Raises
    ------
    ValueError
        If required keys are missing from char_dict.
    """
    _require_keys(char_dict, [
        "spacecraft_incident_id",
        "n_channels_affected",
        "channels_affected",
        "channel_activation_order",
        "channel_temporal_relationships",
    ], "char_dict")

    sid: int = int(char_dict["spacecraft_incident_id"])
    n_channels: int = int(char_dict["n_channels_affected"])
    activation_order: list[str] = list(char_dict["channel_activation_order"])
    rels: list[dict[str, Any]] = list(char_dict.get("channel_temporal_relationships", []))
    channel_incident_ids: list[str] = list(char_dict.get("channel_incident_ids", []))
    channels_affected: list[str] = list(char_dict.get("channels_affected", []))

    hypothesis_id = f"HYP-{sid}"

    # -----------------------------------------------------------------------
    # SINGLE-CHANNEL CASE
    # -----------------------------------------------------------------------
    if n_channels == 1:
        ch = activation_order[0] if activation_order else (channels_affected[0] if channels_affected else "UNKNOWN")
        inc_id = channel_incident_ids[0] if channel_incident_ids else "N/A"

        # --- Per-incident context extracted from char_dict / scores_dict ---
        n_events      = int(char_dict.get("n_events_total", 0))
        duration_sec  = float(char_dict.get("duration_sec", 0.0))
        peak_score    = float(char_dict.get("peak_anomaly_score", 0.0))
        mean_score    = float(char_dict.get("mean_anomaly_score", 0.0))
        score_std     = float(char_dict.get("score_std", 0.0))
        density       = float(char_dict.get("event_density_per_min", 0.0))
        _raw_persistence = char_dict.get("persistence_class", "SHORT")
        persistence = _raw_persistence.value if hasattr(_raw_persistence, "value") else str(_raw_persistence)
        severity_lbl  = str(scores_dict.get("severity_label", "LOW"))
        segment_span  = int(char_dict.get("segment_span", 1))

        # Descriptive qualifiers derived solely from observed values
        std_qual = (
            "high variability" if score_std >= 0.25
            else "moderate variability" if score_std >= 0.10
            else "low variability"
        )
        density_qual = (
            "very high density" if density >= 100.0
            else "high density" if density >= 20.0
            else "moderate density" if density >= 5.0
            else "low density"
        )
        duration_str = (
            f"{duration_sec:.0f} s ({persistence.lower()} persistence)"
        )

        observed = [
            f"Single channel affected: {ch}.",
            (
                f"Observed {n_events} anomaly event(s) over {duration_str}, "
                f"with peak anomaly score {peak_score:.3f} and mean score {mean_score:.3f}."
            ),
            (
                f"Event density: {density:.1f} events/min ({density_qual}). "
                f"Score standard deviation: {score_std:.3f} ({std_qual})."
            ),
        ]
        if segment_span > 1:
            observed.append(
                f"Anomaly activity spanned {segment_span} telemetry segment(s)."
            )
        observed.append(
            f"Incident severity assessed as {severity_lbl} "
            f"(score: {float(scores_dict.get('severity_score', 0.0)):.4f}/10)."
        )
        observed.append("No multi-channel temporal relationships available.")

        temporal = [
            "Single-channel incident; no inter-channel temporal ordering possible.",
        ]

        supporting_evidence = [
            {
                "channel": ch,
                "first_activation": _isoformat(char_dict.get("start_time")),
                "channel_incident_id": inc_id,
                "role": "primary",
                "temporal_note": "Only channel affected; no relative ordering.",
            }
        ]

        # Low-score-consistency note (Fix 2, single-channel path)
        score_consistency_basis: list[str] = []
        if score_std >= 0.25:
            score_consistency_basis.append(
                f"Investigation confidence is reduced: anomaly score standard deviation "
                f"({score_std:.3f}) is high, indicating substantial score variability across "
                f"the {n_events} event(s) in this incident. This reduces the score-consistency "
                f"component of investigation confidence."
            )

        return {
            "hypothesis_id": hypothesis_id,
            "hypothesis_type": "single_channel",
            "summary": (
                f"Single-channel anomaly observed on {ch} "
                f"({n_events} event(s), {duration_str}, peak score {peak_score:.3f}). "
                "No inter-channel temporal sequence can be established."
            ),
            "chain": [],
            "supporting_evidence": supporting_evidence,
            "hypothesis_confidence": 0.0,
            "scientific_caveat": SCIENTIFIC_CAVEAT,
            "observed_evidence": observed,
            "temporal_relationships": temporal,
            "n_corroborating_pairs": 0,
            "score_consistency_basis": score_consistency_basis,
        }

    # -----------------------------------------------------------------------
    # INSUFFICIENT EVIDENCE CASE (multi-channel but no temporal relationships)
    # -----------------------------------------------------------------------
    if not rels:
        observed = [
            f"{n_channels} channels affected: {', '.join(channels_affected)}.",
            "No temporal relationship data available between channels.",
        ]
        temporal = [
            "Insufficient temporal evidence for a coherent failure-chain hypothesis.",
        ]

        supporting_evidence = _build_supporting_evidence(
            activation_order, channel_incident_ids, char_dict, rels
        )

        return {
            "hypothesis_id": hypothesis_id,
            "hypothesis_type": "insufficient_evidence",
            "summary": (
                "Insufficient temporal evidence for a coherent failure-chain hypothesis."
            ),
            "chain": [],
            "supporting_evidence": supporting_evidence,
            "hypothesis_confidence": 0.0,
            "scientific_caveat": SCIENTIFIC_CAVEAT,
            "observed_evidence": observed,
            "temporal_relationships": temporal,
            "n_corroborating_pairs": 0,
        }

    # -----------------------------------------------------------------------
    # MULTI-CHANNEL CASE
    # -----------------------------------------------------------------------

    # Build chain: walk activation_order, link consecutive channels
    chain: list[dict[str, Any]] = []
    for i in range(len(activation_order) - 1):
        src = activation_order[i]
        tgt = activation_order[i + 1]
        rel = _find_rel(rels, src, tgt)

        if rel is None:
            # Relationship not recorded; create a minimal link with unknown gap
            chain.append({
                "source_channel": src,
                "target_channel": tgt,
                "gap_seconds": None,
                "precedence": "unknown",
                "windows_overlap": False,
                "evidence_ref": (
                    f"No direct temporal relationship recorded between {src} and {tgt}."
                ),
            })
            continue

        # Normalise to source=src, target=tgt ordering
        if rel["channel_a"] == src:
            gap = rel["temporal_gap_sec"]
            prec = rel["temporal_precedence"]
        else:
            # rel has A=tgt, B=src → gap is still B_start - A_start
            # but since src activated before tgt (per activation_order),
            # the characteriser would have assigned the earlier channel as A.
            # If the ordering disagrees, use the gap as-is (it's always ≥ 0).
            gap = rel["temporal_gap_sec"]
            prec = rel["temporal_precedence"]

        overlap = bool(rel.get("windows_overlap", False))

        if prec == "simultaneous":
            evidence_ref = (
                f"{src} and {tgt} activated simultaneously "
                f"(gap = 0.0 s, windows_overlap = {overlap})."
            )
        else:
            evidence_ref = (
                f"{src} preceded {tgt} by {gap:.1f} s "
                f"(windows_overlap = {overlap})."
            )

        chain.append({
            "source_channel": src,
            "target_channel": tgt,
            "gap_seconds": gap,
            "precedence": prec,
            "windows_overlap": overlap,
            "evidence_ref": evidence_ref,
        })

    # Corroborating pairs (all pairs, not just consecutive)
    n_corroborating = sum(1 for r in rels if r.get("windows_overlap", False))

    # Observed evidence bullets (Fix 4: no per-pair redundant gap lines here;
    # those are covered by _build_temporal_bullets via the chain)
    observed = _build_observed_bullets(activation_order, rels, n_channels)

    # Temporal relationship bullets — chain links only (n_channels-1 steps)
    temporal = _build_temporal_bullets(chain)

    # Supporting evidence per channel
    supporting_evidence = _build_supporting_evidence(
        activation_order, channel_incident_ids, char_dict, rels
    )

    # Summary sentence
    first_ch = activation_order[0]
    last_ch = activation_order[-1]
    total_span = _total_span_sec(rels)
    if len(activation_order) == 2:
        pair_rel = _find_rel(rels, first_ch, last_ch)
        gap_text = (
            f"{pair_rel['temporal_gap_sec']:.1f} s apart"
            if pair_rel and pair_rel["temporal_gap_sec"] > 0
            else "simultaneously"
        )
        summary = (
            f"Temporally associated anomaly sequence observed across {n_channels} channels: "
            f"{first_ch} activated first, followed by {last_ch} ({gap_text}). "
            f"{n_corroborating} of {len(rels)} channel pair(s) show temporal overlap."
        )
    else:
        summary = (
            f"Temporally associated anomaly sequence observed across {n_channels} channels "
            f"(spanning {total_span:.0f} s from first to last activation). "
            f"Channel activation order: {' -> '.join(activation_order)}. "
            f"{n_corroborating} of {len(rels)} channel pair(s) show temporal overlap."
        )

    # Confidence
    hypothesis_confidence = _compute_hypothesis_confidence(n_channels, chain, rels)

    # Fix 2: Low-score-consistency note for multi-channel path
    score_std_mc  = float(char_dict.get("score_std", 0.0))
    n_events_mc   = int(char_dict.get("n_events_total", 0))
    score_consistency_basis: list[str] = []
    if score_std_mc >= 0.25:
        score_consistency_basis.append(
            f"Investigation confidence is reduced: anomaly score standard deviation "
            f"({score_std_mc:.3f}) is high, indicating substantial score variability across "
            f"the {n_events_mc} event(s) in this incident. This reduces the score-consistency "
            f"component of investigation confidence."
        )

    return {
        "hypothesis_id": hypothesis_id,
        "hypothesis_type": "multi_channel",
        "summary": summary,
        "chain": chain,
        "supporting_evidence": supporting_evidence,
        "hypothesis_confidence": hypothesis_confidence,
        "scientific_caveat": SCIENTIFIC_CAVEAT,
        "observed_evidence": observed,
        "temporal_relationships": temporal,
        "n_corroborating_pairs": n_corroborating,
        "score_consistency_basis": score_consistency_basis,
    }


# ---------------------------------------------------------------------------
# Private builders
# ---------------------------------------------------------------------------

def _require_keys(d: dict[str, Any], keys: list[str], name: str) -> None:
    """Raise ValueError if any required key is absent."""
    missing = [k for k in keys if k not in d]
    if missing:
        raise ValueError(f"[{name}] Missing required keys: {missing}")


def _isoformat(value: Any) -> str:
    """Convert a datetime (or string) to an ISO-8601 string, or return '' if None."""
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _total_span_sec(rels: list[dict[str, Any]]) -> float:
    """Maximum temporal gap across all pairs (approximation of total sequence span)."""
    if not rels:
        return 0.0
    return max(r.get("temporal_gap_sec") or 0.0 for r in rels)


def _build_observed_bullets(
    activation_order: list[str],
    rels: list[dict[str, Any]],
    n_channels: int,
) -> list[str]:
    """Build factual observation bullet strings.

    Fix 4: per-pair precedence/gap lines are removed from here; they are
    already expressed (non-redundantly) via the activation-chain in
    ``_build_temporal_bullets``.  This avoids repeating the same gap values
    twice in the final hypothesis_statements list.
    """
    bullets: list[str] = [
        f"{n_channels} channels recorded anomalous telemetry.",
        f"Channel activation order (by first anomaly): {' \u2192 '.join(activation_order)}.",
    ]
    n_overlap = sum(1 for r in rels if r.get("windows_overlap", False))
    bullets.append(
        f"{n_overlap} of {len(rels)} channel pair(s) have overlapping or proximate anomaly windows."
    )
    return bullets


def _build_temporal_bullets(chain: list[dict[str, Any]]) -> list[str]:
    """Build temporal relationship bullet strings from the chain."""
    if not chain:
        return ["No temporal chain links established."]
    bullets: list[str] = []
    for link in chain:
        src = link["source_channel"]
        tgt = link["target_channel"]
        gap = link.get("gap_seconds")
        overlap = link.get("windows_overlap", False)
        if gap is None:
            bullets.append(
                f"{src} → {tgt}: temporal relationship not quantified."
            )
        elif gap == 0.0:
            bullets.append(
                f"{src} → {tgt}: simultaneous activation "
                f"(windows_overlap={overlap})."
            )
        else:
            bullets.append(
                f"{src} → {tgt}: {gap:.1f} s gap "
                f"(windows_overlap={overlap})."
            )
    return bullets


def _build_supporting_evidence(
    activation_order: list[str],
    channel_incident_ids: list[str],
    char_dict: dict[str, Any],
    rels: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build one supporting evidence item per channel in activation order."""
    evidence: list[dict[str, Any]] = []
    for idx, ch in enumerate(activation_order):
        inc_id = channel_incident_ids[idx] if idx < len(channel_incident_ids) else "N/A"
        role = _role_for_channel(ch, activation_order)
        note = _temporal_note(ch, activation_order, rels)

        item: dict[str, Any] = {
            "channel": ch,
            "first_activation": _isoformat(char_dict.get("start_time")),
            "channel_incident_id": inc_id,
            "role": role,
            "temporal_note": note,
        }

        # Attach direct relationship to the preceding channel if available
        if idx > 0:
            prev_ch = activation_order[idx - 1]
            rel = _find_rel(rels, prev_ch, ch)
            if rel is not None:
                item["gap_from_previous_sec"] = rel.get("temporal_gap_sec", 0.0)
                item["overlap_with_previous"] = bool(rel.get("windows_overlap", False))

        evidence.append(item)
    return evidence
