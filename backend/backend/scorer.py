"""
member2/scorer.py
-----------------
Score computation engine for Member 2 — Incident Investigation Engineer.

Computes three independent, explainable scores for each spacecraft incident:

    A.  significance_score      (0–100)   how noteworthy relative to context
    B.  severity_score          (0–10)    absolute assessment of incident severity
    C.  investigation_confidence (0–1)    how trustworthy the investigation output is

Scoring principles
------------------
- All normalisation is continuous; no hard step-function thresholds.
- Every component is named and its contribution recorded separately.
- No ground-truth label (``anomaly``, ``label``, ``train``) is used.
- No LLM, ML model, or IBM watsonx is called.
- Temporal correlation is evidence of association only; physical causality is
  NEVER claimed.

Component formulas (empirically grounded on the 805-incident OPS-SAT-AD dataset)
----------------------------------------------------------------------------------

ANOMALY STRENGTH (continuous):
    anomaly_strength = clip((peak_anomaly_score - 0.30) / 0.70, 0, 1)
    Rationale: the minimum observed peak_anomaly_score is 0.30; scores are
    normalised over the effective [0.30, 1.00] range.

EVENT DENSITY (continuous):
    event_density_norm = clip(event_density_per_min / 100, 0, 1)
    Rationale: 100 ev/min is a saturation ceiling calibrated to P99 of the
    dataset (observed P99 ≈ 104 ev/min; max ≈ 146 ev/min).  Using 100 as
    the ceiling avoids distorting high-density outliers.

CHANNEL BREADTH (continuous):
    channel_breadth = clip((n_channels_affected - 1) / 4, 0, 1)
    Rationale: channel count ranges from 1 to 5 in the dataset.
    (n - 1) / 4 maps [1,5] → [0.0, 1.0] with equal step size per channel.

EVENT QUANTITY (log-normalised):
    event_qty = clip(log(n_events_total + 1) / log(1325), 0, 1)
    Rationale: n_events ranges from 2 to 1324.  log(2+1)/log(1325) ≈ 0.15;
    log(105+1)/log(1325) ≈ 0.64 (median).  Logarithmic scaling prevents
    the extreme upper tail (max 1324) from dominating mid-range incidents.
    The constant 1325 = max_observed + 1 ensures the observed maximum maps
    to ≈ 1.0 without hard-clipping.

PERSISTENCE (monotonic ordinal):
    SHORT    → 0.25
    MEDIUM   → 0.50
    LONG     → 0.75
    EXTENDED → 1.00
    Rationale: four equally-spaced steps across the four descriptive classes.
    No severity implication is embedded; the mapping is purely ordinal.

SCORE CONSISTENCY (confidence component):
    consistency = 1 - clip(score_std / 0.25, 0, 1)
    Rationale: P95 of score_std is 0.25 in the dataset.  High consistency
    (low variance in anomaly scores across events) supports confident investigation.
    This does NOT imply physical causality.

CROSS-CHANNEL CORROBORATION (from characteriser):
    corroboration = clip(n_overlapping_pairs / max(1, n_pairs), 0, 1)
    where n_overlapping_pairs = count of channel pairs with windows_overlap==True.
    Rationale: temporal overlap between channels is evidence of temporal
    association; it is NOT treated as causal evidence.

SIGNIFICANCE score (0–100)
--------------------------
Weighted combination emphasising anomaly strength and breadth:

    sig_raw = (
        0.30 * anomaly_strength
      + 0.20 * event_density_norm
      + 0.25 * event_qty
      + 0.15 * channel_breadth
      + 0.05 * persistence_norm
      + 0.05 * corroboration
    )
    significance_score = round(clip(sig_raw, 0, 1) * 100, 4)

SEVERITY score (0–10)
---------------------
Weighted combination emphasising anomaly strength and persistence:

    sev_raw = (
        0.35 * anomaly_strength
      + 0.25 * persistence_norm
      + 0.25 * event_density_norm
      + 0.15 * channel_breadth
    )
    severity_score = round(clip(sev_raw, 0, 1) * 10, 4)

CONFIDENCE score (0–1)
-----------------------
Emphasises evidence quantity, consistency, and corroboration:

    conf_raw = (
        0.40 * event_qty
      + 0.30 * consistency
      + 0.20 * corroboration
      + 0.10 * channel_breadth
    )
    investigation_confidence = round(clip(conf_raw, 0, 1), 4)

Severity labels (applied AFTER score computation):
---------------------------------------------------
Label boundaries are calibrated to the observed score distribution of the
805-incident dataset to avoid label collapse:

    score >= 7.0  → CRITICAL   (≈ top 10%)
    score >= 5.0  → HIGH       (≈ top 35%)
    score >= 3.0  → MODERATE   (≈ top 68%)
    score <  3.0  → LOW        (≈ bottom 32%)

These boundaries were set by inspecting the severity_score distribution
(see distribution report in AGENTS.md), ensuring no single label captures
an overwhelming majority of incidents.

Scientific compliance
---------------------
- No component uses ``anomaly``, ``label``, or ``train`` columns.
- ``channel_temporal_relationships`` is used as evidence of temporal
  association only; no physical causality is inferred.
- ``deviation_sigma`` is not available in CSV inputs and is not used.
"""

from __future__ import annotations

import math
from typing import Any

from member2.output_schema import PersistenceClass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Saturating ceiling for event density (ev/min).
# P99 of the observed dataset is ≈ 104 ev/min; max ≈ 146 ev/min.
_DENSITY_SATURATION: float = 100.0

# Normalising constant for event quantity (log scale).
# = log(max_observed_n_events + 1) = log(1324 + 1) = log(1325)
_EVENT_QTY_DENOM: float = math.log(1325)

# Peak score lower bound (below this, anomaly_strength = 0).
_PEAK_FLOOR: float = 0.30

# Persistence ordinal mapping: SHORT < MEDIUM < LONG < EXTENDED
_PERSISTENCE_ORDINAL: dict[str, float] = {
    PersistenceClass.SHORT.value:    0.25,
    PersistenceClass.MEDIUM.value:   0.50,
    PersistenceClass.LONG.value:     0.75,
    PersistenceClass.EXTENDED.value: 1.00,
}

# Score std normalising constant (P95 of dataset score_std ≈ 0.25)
_SCORE_STD_SATURATION: float = 0.25

# Significance component weights (must sum to 1.0)
_SIG_W_ANOMALY:     float = 0.30
_SIG_W_DENSITY:     float = 0.20
_SIG_W_EVENT_QTY:   float = 0.25
_SIG_W_BREADTH:     float = 0.15
_SIG_W_PERSISTENCE: float = 0.05
_SIG_W_CORROBORATION: float = 0.05

# Severity component weights (must sum to 1.0)
_SEV_W_ANOMALY:     float = 0.35
_SEV_W_PERSISTENCE: float = 0.25
_SEV_W_DENSITY:     float = 0.25
_SEV_W_BREADTH:     float = 0.15

# Confidence component weights (must sum to 1.0)
_CONF_W_EVENT_QTY:     float = 0.40
_CONF_W_CONSISTENCY:   float = 0.30
_CONF_W_CORROBORATION: float = 0.20
_CONF_W_BREADTH:       float = 0.10

# Severity label boundaries (calibrated to observed distribution)
# Applied to severity_score (0–10)
_SEV_CRITICAL: float = 7.0
_SEV_HIGH:     float = 5.0
_SEV_MODERATE: float = 3.0
# below _SEV_MODERATE → LOW


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clip(value: float, lo: float, hi: float) -> float:
    """Clip *value* to the closed interval [lo, hi]."""
    return max(lo, min(hi, value))


def _anomaly_strength(peak_anomaly_score: float) -> float:
    """
    Continuous anomaly strength normalised over [0.30, 1.00].

    Formula: clip((peak_anomaly_score - 0.30) / 0.70, 0, 1)
    """
    return _clip((peak_anomaly_score - _PEAK_FLOOR) / (1.0 - _PEAK_FLOOR), 0.0, 1.0)


def _event_density_norm(event_density_per_min: float) -> float:
    """
    Continuous density normalisation with saturation ceiling at 100 ev/min.

    Formula: clip(event_density_per_min / 100, 0, 1)
    """
    return _clip(event_density_per_min / _DENSITY_SATURATION, 0.0, 1.0)


def _channel_breadth(n_channels_affected: int) -> float:
    """
    Continuous channel breadth normalised over [1, 5].

    Formula: clip((n_channels_affected - 1) / 4, 0, 1)
    """
    return _clip((n_channels_affected - 1) / 4.0, 0.0, 1.0)


def _event_qty_norm(n_events_total: int) -> float:
    """
    Log-normalised event quantity.

    Formula: clip(log(n_events_total + 1) / log(1325), 0, 1)

    Calibration: log(1325) ≈ 7.189 so that the observed maximum
    (n_events=1324) maps to ≈ 1.0.  Median (n_events=105) maps to ≈ 0.65.
    """
    if n_events_total < 0:
        return 0.0
    return _clip(math.log(n_events_total + 1) / _EVENT_QTY_DENOM, 0.0, 1.0)


def _persistence_norm(persistence_class: str | PersistenceClass) -> float:
    """
    Monotonic ordinal mapping of persistence class to [0.25, 1.00].

    SHORT=0.25, MEDIUM=0.50, LONG=0.75, EXTENDED=1.00.
    Returns 0.25 for unknown values (fail-safe).
    """
    if isinstance(persistence_class, PersistenceClass):
        key = persistence_class.value
    else:
        key = str(persistence_class)
    return _PERSISTENCE_ORDINAL.get(key, 0.25)


def _score_consistency(score_std: float) -> float:
    """
    Evidence-quality component based on score standard deviation.

    Formula: 1 - clip(score_std / 0.25, 0, 1)

    High consistency (low variance) → higher confidence.
    Does NOT imply physical causality.
    """
    return 1.0 - _clip(score_std / _SCORE_STD_SATURATION, 0.0, 1.0)


def _cross_channel_corroboration(channel_temporal_relationships: list[dict[str, Any]]) -> float:
    """
    Fraction of channel pairs that show temporal overlap or proximity.

    Uses the ``windows_overlap`` boolean from each relationship dict
    (produced by characteriser.get_channel_temporal_relationships).

    Returns 0.0 for single-channel incidents (empty list).

    This is evidence of temporal association ONLY; no physical causality
    is inferred.
    """
    if not channel_temporal_relationships:
        return 0.0
    n_pairs = len(channel_temporal_relationships)
    n_overlap = sum(
        1 for rel in channel_temporal_relationships if rel.get("windows_overlap", False)
    )
    return _clip(n_overlap / n_pairs, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Public: compute_significance
# ---------------------------------------------------------------------------

def compute_significance(
    peak_anomaly_score: float,
    event_density_per_min: float,
    n_events_total: int,
    n_channels_affected: int,
    persistence_class: str | PersistenceClass,
    channel_temporal_relationships: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compute the significance score (0–100) for one spacecraft incident.

    Significance measures how noteworthy an incident is across its context.

    Parameters
    ----------
    peak_anomaly_score:
        Highest anomaly confidence score in [0, 1].
    event_density_per_min:
        Anomaly events per minute during the incident.
    n_events_total:
        Total number of anomaly events linked to this incident.
    n_channels_affected:
        Count of distinct telemetry channels involved.
    persistence_class:
        Descriptive persistence class string or enum value.
    channel_temporal_relationships:
        List of per-pair dicts from characteriser (may be empty for
        single-channel incidents).

    Returns
    -------
    dict with keys:
        ``significance_score``   : float in [0, 100]
        ``significance_components`` : dict[str, float] — named contributions
    """
    a_s  = _anomaly_strength(peak_anomaly_score)
    dn   = _event_density_norm(event_density_per_min)
    eq   = _event_qty_norm(n_events_total)
    cb   = _channel_breadth(n_channels_affected)
    pn   = _persistence_norm(persistence_class)
    corr = _cross_channel_corroboration(channel_temporal_relationships)

    raw = (
        _SIG_W_ANOMALY      * a_s
        + _SIG_W_DENSITY    * dn
        + _SIG_W_EVENT_QTY  * eq
        + _SIG_W_BREADTH    * cb
        + _SIG_W_PERSISTENCE * pn
        + _SIG_W_CORROBORATION * corr
    )

    score = round(_clip(raw, 0.0, 1.0) * 100.0, 4)

    components: dict[str, float] = {
        "anomaly_strength":   round(a_s,  6),
        "event_density":      round(dn,   6),
        "event_quantity":     round(eq,   6),
        "channel_breadth":    round(cb,   6),
        "persistence":        round(pn,   6),
        "cross_channel":      round(corr, 6),
    }

    return {
        "significance_score":      score,
        "significance_components": components,
    }


# ---------------------------------------------------------------------------
# Public: compute_severity
# ---------------------------------------------------------------------------

def compute_severity(
    peak_anomaly_score: float,
    persistence_class: str | PersistenceClass,
    event_density_per_min: float,
    n_channels_affected: int,
) -> dict[str, Any]:
    """
    Compute the severity score (0–10) for one spacecraft incident.

    Severity is an absolute assessment independent of the rest of the
    dataset.  It emphasises anomaly strength and persistence.

    Parameters
    ----------
    peak_anomaly_score:
        Highest anomaly confidence score in [0, 1].
    persistence_class:
        Descriptive persistence class string or enum value.
    event_density_per_min:
        Anomaly events per minute during the incident.
    n_channels_affected:
        Count of distinct telemetry channels involved.

    Returns
    -------
    dict with keys:
        ``severity_score``         : float in [0, 10]
        ``severity_components``    : dict[str, float] — named contributions
        ``severity_label``         : str — LOW | MODERATE | HIGH | CRITICAL
    """
    a_s = _anomaly_strength(peak_anomaly_score)
    pn  = _persistence_norm(persistence_class)
    dn  = _event_density_norm(event_density_per_min)
    cb  = _channel_breadth(n_channels_affected)

    raw = (
        _SEV_W_ANOMALY      * a_s
        + _SEV_W_PERSISTENCE * pn
        + _SEV_W_DENSITY    * dn
        + _SEV_W_BREADTH    * cb
    )

    score = round(_clip(raw, 0.0, 1.0) * 10.0, 4)

    label = _severity_label(score)

    components: dict[str, float] = {
        "anomaly_strength": round(a_s, 6),
        "persistence":      round(pn,  6),
        "event_density":    round(dn,  6),
        "channel_breadth":  round(cb,  6),
    }

    return {
        "severity_score":      score,
        "severity_components": components,
        "severity_label":      label,
    }


def _severity_label(severity_score: float) -> str:
    """
    Map a severity_score (0–10) to a descriptive label.

    Boundaries calibrated to the observed 805-incident score distribution:
        CRITICAL : score >= 7.0  (≈ top 10%)
        HIGH     : score >= 5.0  (≈ top 35%)
        MODERATE : score >= 3.0  (≈ top 68%)
        LOW      : score <  3.0  (≈ bottom 32%)
    """
    if severity_score >= _SEV_CRITICAL:
        return "CRITICAL"
    elif severity_score >= _SEV_HIGH:
        return "HIGH"
    elif severity_score >= _SEV_MODERATE:
        return "MODERATE"
    else:
        return "LOW"


# ---------------------------------------------------------------------------
# Public: compute_confidence
# ---------------------------------------------------------------------------

def compute_confidence(
    n_events_total: int,
    score_std: float,
    channel_temporal_relationships: list[dict[str, Any]],
    n_channels_affected: int,
) -> dict[str, Any]:
    """
    Compute the investigation confidence (0–1) for one spacecraft incident.

    Confidence measures how trustworthy the investigation output is given
    the quantity and consistency of available evidence.  It is NOT simply
    another severity score.

    Parameters
    ----------
    n_events_total:
        Total number of anomaly events linked to this incident.
    score_std:
        Standard deviation of anomaly scores across events in this incident.
    channel_temporal_relationships:
        List of per-pair dicts from characteriser (may be empty).
    n_channels_affected:
        Count of distinct telemetry channels involved.

    Returns
    -------
    dict with keys:
        ``investigation_confidence``  : float in [0, 1]
        ``confidence_components``     : dict[str, float] — named contributions
    """
    eq   = _event_qty_norm(n_events_total)
    cons = _score_consistency(score_std)
    corr = _cross_channel_corroboration(channel_temporal_relationships)
    cb   = _channel_breadth(n_channels_affected)

    raw = (
        _CONF_W_EVENT_QTY     * eq
        + _CONF_W_CONSISTENCY  * cons
        + _CONF_W_CORROBORATION * corr
        + _CONF_W_BREADTH      * cb
    )

    confidence = round(_clip(raw, 0.0, 1.0), 4)

    components: dict[str, float] = {
        "evidence_quantity":       round(eq,   6),
        "score_consistency":       round(cons, 6),
        "temporal_corroboration":  round(corr, 6),
        "channel_breadth":         round(cb,   6),
    }

    return {
        "investigation_confidence": confidence,
        "confidence_components":    components,
    }


# ---------------------------------------------------------------------------
# Public: score_incident  (convenience wrapper)
# ---------------------------------------------------------------------------

def score_incident(char_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Compute all three scores from a characterisation dict.

    This is a convenience wrapper around :func:`compute_significance`,
    :func:`compute_severity`, and :func:`compute_confidence`.

    Parameters
    ----------
    char_dict:
        Dict as returned by ``characteriser.get_incident_characterisation``.

    Returns
    -------
    dict with merged keys from all three score functions plus
    ``severity_label``.
    """
    rels: list[dict[str, Any]] = char_dict.get("channel_temporal_relationships", [])

    sig = compute_significance(
        peak_anomaly_score=float(char_dict["peak_anomaly_score"]),
        event_density_per_min=float(char_dict["event_density_per_min"]),
        n_events_total=int(char_dict["n_events_total"]),
        n_channels_affected=int(char_dict["n_channels_affected"]),
        persistence_class=char_dict["persistence_class"],
        channel_temporal_relationships=rels,
    )

    sev = compute_severity(
        peak_anomaly_score=float(char_dict["peak_anomaly_score"]),
        persistence_class=char_dict["persistence_class"],
        event_density_per_min=float(char_dict["event_density_per_min"]),
        n_channels_affected=int(char_dict["n_channels_affected"]),
    )

    conf = compute_confidence(
        n_events_total=int(char_dict["n_events_total"]),
        score_std=float(char_dict.get("score_std", 0.0)),
        channel_temporal_relationships=rels,
        n_channels_affected=int(char_dict["n_channels_affected"]),
    )

    return {**sig, **sev, **conf}
