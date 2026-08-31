"""
member2/characteriser.py
------------------------
Characterisation engine for Member 2 — Incident Investigation Engineer.

Transforms one spacecraft-level incident (identified by ``spacecraft_incident_id``)
from the three Member 1 CSV DataFrames into a structured description of what
happened: timeline, channel ordering, event statistics, persistence class,
segment span, and inter-channel temporal relationships.

What this module does NOT do
----------------------------
- Anomaly detection or thresholding
- Incident re-grouping (Member 1 already did this)
- Severity scoring, significance scoring, confidence scoring
- Failure-cause claims or hypothesis generation
- Mission impact assessment
- Any reference to the ground-truth ``anomaly``, ``label``, or ``train`` columns

Public API
----------
classify_persistence(duration_sec)      → PersistenceClass
get_channel_temporal_relationships(...)  → list[dict]
get_incident_characterisation(...)       → dict

The returned dict from ``get_incident_characterisation`` is designed to feed
directly into ``output_schema.Investigation`` (all required characterisation
fields are present).  Scoring, hypothesis, impact, and graph fields are NOT
populated here — they are filled by the respective downstream modules.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from member2.output_schema import PersistenceClass, TimelineEvent

# Maximum number of timeline events kept per incident to avoid memory pressure.
_TIMELINE_CAP: int = 1000


# ---------------------------------------------------------------------------
# Public: classify_persistence
# ---------------------------------------------------------------------------

def classify_persistence(duration_sec: float) -> PersistenceClass:
    """
    Classify incident duration into a descriptive persistence class.

    These classes are purely descriptive; they carry no severity implication.

    Parameters
    ----------
    duration_sec:
        Incident duration in seconds.  Must be >= 0.

    Returns
    -------
    PersistenceClass
        - SHORT    : duration_sec < 60
        - MEDIUM   : 60 <= duration_sec < 300
        - LONG     : 300 <= duration_sec < 900
        - EXTENDED : duration_sec >= 900

    Raises
    ------
    ValueError
        If ``duration_sec`` is negative or not finite.
    """
    try:
        d = float(duration_sec)
    except (TypeError, ValueError):
        raise ValueError(f"duration_sec must be a finite number, got {duration_sec!r}")

    if not math.isfinite(d):
        raise ValueError(f"duration_sec must be a finite number, got {duration_sec!r}")
    if d < 0:
        raise ValueError(f"duration_sec must be >= 0, got {duration_sec!r}")

    if d < 60:
        return PersistenceClass.SHORT
    elif d < 300:
        return PersistenceClass.MEDIUM
    elif d < 900:
        return PersistenceClass.LONG
    else:
        return PersistenceClass.EXTENDED


# ---------------------------------------------------------------------------
# Public: get_channel_temporal_relationships
# ---------------------------------------------------------------------------

def get_channel_temporal_relationships(
    channel_incidents: pd.DataFrame,
) -> list[dict]:
    """
    Describe temporal relationships between every pair of affected channels.

    For each ordered pair (channel_A, channel_B) where channel_A activated
    first (or both channels share the same earliest start_time), compute:

    - ``channel_a``              : name of the first-activating channel
    - ``channel_b``              : name of the other channel
    - ``channel_a_start``        : ISO-8601 UTC string, earliest start for A
    - ``channel_b_start``        : ISO-8601 UTC string, earliest start for B
    - ``temporal_gap_sec``       : (B_start − A_start) in seconds (always >= 0)
    - ``temporal_precedence``    : "A_before_B" | "simultaneous"
    - ``windows_overlap``        : bool — do any incident windows for A and B
                                   overlap (or are within 60 s)?

    This function does NOT claim that channel_A caused channel_B.
    All language is strictly observational.

    Parameters
    ----------
    channel_incidents:
        Subset of ``incidents.csv`` rows for one spacecraft incident.
        Must contain columns: ``channel``, ``start_time``, ``end_time``.
        ``start_time`` and ``end_time`` must already be UTC-aware datetimes.

    Returns
    -------
    list[dict]
        One entry per unordered channel pair, sorted deterministically by
        (channel_a, channel_b).  Empty list for single-channel incidents.
    """
    required = ["channel", "start_time", "end_time"]
    missing = [c for c in required if c not in channel_incidents.columns]
    if missing:
        raise ValueError(f"channel_incidents is missing required columns: {missing}")

    # First start time per channel
    channel_first: dict[str, datetime] = {}
    channel_windows: dict[str, list[tuple[datetime, datetime]]] = {}

    for _, row in channel_incidents.iterrows():
        ch = str(row["channel"])
        st = _as_utc(row["start_time"])
        et = _as_utc(row["end_time"])

        if ch not in channel_first or st < channel_first[ch]:
            channel_first[ch] = st

        channel_windows.setdefault(ch, []).append((st, et))

    channels = sorted(channel_first.keys())
    if len(channels) < 2:
        return []

    results = []
    for i, outer_ch in enumerate(channels):
        for inner_ch in channels[i + 1:]:
            t_outer = channel_first[outer_ch]
            t_inner = channel_first[inner_ch]

            # Ensure first is the earlier-activating channel (local vars only)
            if t_inner < t_outer:
                first, second = inner_ch, outer_ch
                t_first, t_second = t_inner, t_outer
            else:
                first, second = outer_ch, inner_ch
                t_first, t_second = t_outer, t_inner

            gap_sec = (t_second - t_first).total_seconds()
            precedence = "simultaneous" if gap_sec == 0.0 else "A_before_B"
            overlap = _windows_overlap_or_proximate(
                channel_windows[first], channel_windows[second]
            )

            results.append({
                "channel_a": first,
                "channel_b": second,
                "channel_a_start": t_first.isoformat(),
                "channel_b_start": t_second.isoformat(),
                "temporal_gap_sec": gap_sec,
                "temporal_precedence": precedence,
                "windows_overlap": overlap,
            })

    results.sort(key=lambda r: (r["channel_a"], r["channel_b"]))
    return results


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _windows_overlap_or_proximate(
    windows_a: list[tuple[datetime, datetime]],
    windows_b: list[tuple[datetime, datetime]],
    proximity_sec: float = 60.0,
) -> bool:
    """
    Return True if any window from A overlaps any window from B, or if the
    gap between any pair is <= proximity_sec (mirroring Member 1's 60-second
    spacecraft-linking rule).
    """
    for a_start, a_end in windows_a:
        for b_start, b_end in windows_b:
            # Overlap: intervals intersect
            if a_start <= b_end and b_start <= a_end:
                return True
            # Proximate: gap is small
            gap = max(
                (b_start - a_end).total_seconds(),
                (a_start - b_end).total_seconds(),
            )
            if gap <= proximity_sec:
                return True
    return False


def _build_timeline(events_df: pd.DataFrame) -> list[TimelineEvent]:
    """
    Build a chronologically sorted, capped list of TimelineEvents.

    If the total event count exceeds ``_TIMELINE_CAP``, the first and last
    events are always preserved and the remainder is evenly sampled.

    Parameters
    ----------
    events_df:
        Filtered anomaly events for this incident (all columns present).

    Returns
    -------
    list[TimelineEvent]
        Sorted by timestamp ascending.
    """
    df = events_df.sort_values("timestamp", kind="stable")
    n = len(df)

    if n == 0:
        return []

    if n <= _TIMELINE_CAP:
        rows = df
    else:
        # Keep first and last; sample interior evenly
        step = (n - 2) / (_TIMELINE_CAP - 2)
        interior_indices = [int(round(1 + i * step)) for i in range(_TIMELINE_CAP - 2)]
        idx = [0] + interior_indices + [n - 1]
        # Deduplicate while preserving order
        seen: set[int] = set()
        unique_interior: list[int] = []
        for i in idx:
            if i not in seen:
                seen.add(i)
                unique_interior.append(i)
        rows = df.iloc[unique_interior]

    timeline: list[TimelineEvent] = []
    for _, row in rows.iterrows():
        timeline.append(TimelineEvent(
            timestamp=_as_utc(row["timestamp"]),
            channel=str(row["channel"]),
            segment=int(row["segment"]),
            anomaly_score=float(row["anomaly_score"]),
            value=float(row["value"]),
        ))
    return timeline


def _as_utc(value: Any) -> datetime:
    """
    Coerce ``value`` to a UTC-aware ``datetime``.

    Accepts:
    - ``datetime`` objects (naive ones get UTC attached)
    - pandas ``Timestamp`` objects
    - ISO-8601 strings (with or without trailing Z)

    Raises
    ------
    ValueError
        If the value cannot be interpreted as a datetime.
    """
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, pd.Timestamp):
        dt = value.to_pydatetime()
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(f"Cannot parse {value!r} as an ISO-8601 datetime")
    else:
        raise ValueError(f"Cannot convert {type(value).__name__} value {value!r} to a datetime")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _require_columns(df: pd.DataFrame, columns: list[str], name: str) -> None:
    """Raise ValueError if any required column is absent from *df*."""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"[{name}] Missing required column(s): {missing}")


# ---------------------------------------------------------------------------
# Public: get_incident_characterisation
# ---------------------------------------------------------------------------

def get_incident_characterisation(
    spacecraft_incident_id: int,
    anomaly_events_df: pd.DataFrame,
    incidents_df: pd.DataFrame,
    spacecraft_incidents_df: pd.DataFrame,
) -> dict:
    """
    Derive a full characterisation for one spacecraft-level incident.

    Parameters
    ----------
    spacecraft_incident_id:
        The ``spacecraft_incident_id`` to investigate.
    anomaly_events_df:
        Loaded ``anomaly_events.csv`` DataFrame (from ``loaders.py``).
    incidents_df:
        Loaded ``incidents.csv`` DataFrame (from ``loaders.py``).
    spacecraft_incidents_df:
        Loaded ``spacecraft_incidents.csv`` DataFrame (from ``loaders.py``).
        ``channels_affected`` and ``segments_affected`` columns must already
        be Python lists (as produced by the loader).

    Returns
    -------
    dict
        Contains the following keys (compatible with the characterisation
        fields of ``output_schema.Investigation``):

        spacecraft_incident_id, start_time, end_time, duration_sec,
        n_channels_affected, channels_affected, channel_activation_order,
        is_multi_channel, n_events_total, event_density_per_min,
        peak_anomaly_score, mean_anomaly_score, score_std,
        persistence_class, segment_span,
        timeline (list[TimelineEvent]),
        channel_incident_ids (list[str]),
        channel_temporal_relationships (list[dict])

        Scoring, hypothesis, mission_impact, evidence_graph, and
        recommended_actions are NOT set here.

    Raises
    ------
    ValueError
        - If ``spacecraft_incident_id`` is not found.
        - If required columns are missing from any input DataFrame.
        - If no channel-level incidents link to this spacecraft incident.
        - If numeric fields are invalid (NaN, Inf, out of range).
    """
    _require_columns(spacecraft_incidents_df, ["spacecraft_incident_id", "start_time", "end_time", "duration_sec", "channels_affected"], "spacecraft_incidents_df")
    _require_columns(incidents_df, ["spacecraft_incident_id", "incident_id", "channel", "segment", "start_time", "end_time"], "incidents_df")
    _require_columns(anomaly_events_df, ["channel", "segment", "timestamp", "anomaly_score", "value"], "anomaly_events_df")

    sid = int(spacecraft_incident_id)

    # --- Locate spacecraft incident row ---
    si_mask = spacecraft_incidents_df["spacecraft_incident_id"].astype(int) == sid
    si_rows = spacecraft_incidents_df[si_mask]
    if si_rows.empty:
        raise ValueError(f"spacecraft_incident_id {sid} not found in spacecraft_incidents_df")

    si_row = si_rows.iloc[0]
    start_time = _as_utc(si_row["start_time"])
    end_time = _as_utc(si_row["end_time"])

    try:
        duration_sec = float(si_row["duration_sec"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"duration_sec for spacecraft_incident_id {sid} is invalid: {exc}")
    if not math.isfinite(duration_sec) or duration_sec < 0:
        raise ValueError(f"duration_sec for spacecraft_incident_id {sid} is invalid: {duration_sec}")

    # --- Channel-level incidents ---
    ch_inc = incidents_df[incidents_df["spacecraft_incident_id"].astype(int) == sid].copy()
    if ch_inc.empty:
        raise ValueError(f"No channel-level incidents found for spacecraft_incident_id {sid} in incidents_df")

    channel_incident_ids = [str(iid) for iid in ch_inc["incident_id"]]

    # --- Channels affected ---
    channels_raw = si_row["channels_affected"]
    if isinstance(channels_raw, list):
        channels_from_si = [str(c) for c in channels_raw]
    else:
        channels_from_si = [str(c).strip() for c in str(channels_raw).split("|")]
    channels_affected = sorted(set(channels_from_si))
    n_channels_affected = len(channels_affected)
    is_multi_channel = n_channels_affected > 1

    # --- Anomaly events for this incident ---
    ae_mask = pd.Series([False] * len(anomaly_events_df), index=anomaly_events_df.index)
    for _, row in ch_inc.iterrows():
        ch = str(row["channel"])
        seg = int(row["segment"])
        ae_mask |= (
            (anomaly_events_df["channel"].astype(str) == ch) &
            (anomaly_events_df["segment"].astype(int) == seg)
        )
    incident_events = anomaly_events_df[ae_mask].copy()

    n_events_total = len(incident_events)
    scores = incident_events["anomaly_score"].astype(float).values

    if len(scores) > 0:
        peak_anomaly_score = float(np.max(scores))
        mean_anomaly_score = float(np.mean(scores))
        score_std_val = float(np.std(scores, ddof=1)) if len(scores) > 1 else 0.0
    else:
        peak_anomaly_score = float(si_row["peak_anomaly_score"])
        mean_anomaly_score = float(si_row["mean_anomaly_score"])
        score_std_val = 0.0

    for label, val in [("peak_anomaly_score", peak_anomaly_score), ("mean_anomaly_score", mean_anomaly_score), ("score_std", score_std_val)]:
        if not math.isfinite(val):
            raise ValueError(f"{label} for spacecraft_incident_id {sid} is not finite: {val}")

    # --- Channel activation order ---
    channel_activation_order: list[str] = sorted(
        channels_affected,
        key=lambda c: (
            ch_inc[ch_inc["channel"].astype(str) == c]["start_time"].apply(_as_utc).min(),
            c,
        )
    )

    # --- Event density ---
    event_density_per_min = (n_events_total / (duration_sec / 60.0)) if duration_sec > 0 else 0.0

    # --- Persistence class ---
    persistence_class = classify_persistence(duration_sec)

    # --- Segment span ---
    all_segments = set(ch_inc["segment"].astype(int).tolist())
    segment_span = len(all_segments)

    # --- Timeline ---
    timeline = _build_timeline(incident_events) if not incident_events.empty else []

    # --- Channel temporal relationships ---
    channel_temporal_relationships = get_channel_temporal_relationships(ch_inc)

    return {
        "spacecraft_incident_id": sid,
        "start_time": start_time,
        "end_time": end_time,
        "duration_sec": duration_sec,
        "n_channels_affected": n_channels_affected,
        "channels_affected": channels_affected,
        "channel_activation_order": channel_activation_order,
        "is_multi_channel": is_multi_channel,
        "n_events_total": n_events_total,
        "event_density_per_min": event_density_per_min,
        "peak_anomaly_score": peak_anomaly_score,
        "mean_anomaly_score": mean_anomaly_score,
        "score_std": score_std_val,
        "persistence_class": persistence_class,
        "segment_span": segment_span,
        "timeline": timeline,
        "channel_incident_ids": channel_incident_ids,
        "channel_temporal_relationships": channel_temporal_relationships,
    }
