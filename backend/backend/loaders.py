"""
member2/loaders.py
------------------
CSV loaders for the three Member 1 output files consumed by Member 2.

Functions
---------
load_anomaly_events_csv(path)       → pd.DataFrame
load_incidents_csv(path)            → pd.DataFrame
load_spacecraft_incidents_csv(path) → pd.DataFrame

All functions:
- Validate that required columns are present.
- Parse timestamp columns as UTC-aware datetimes.
- Convert declared numeric columns to float / int as appropriate.
- Split pipe-delimited fields (channels_affected, segments_affected) into lists.
- Reject null values in required fields.
- Reject NaN / Inf in numeric fields.

The columns `anomaly`, `label`, and `train` are passed through unchanged when
present; they are NOT used for any investigation logic in this module.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

import pandas as pd


# ---------------------------------------------------------------------------
# Column specifications
# ---------------------------------------------------------------------------

# anomaly_events.csv
_AE_REQUIRED: list[str] = [
    "timestamp",
    "channel",
    "segment",
    "value",
    "anomaly_score",
]
_AE_NUMERIC_FLOAT: list[str] = ["value", "anomaly_score"]
_AE_NUMERIC_INT: list[str] = ["segment"]
_AE_TIMESTAMPS: list[str] = ["timestamp"]

# incidents.csv
_INC_REQUIRED: list[str] = [
    "incident_id",
    "channel",
    "segment",
    "start_time",
    "end_time",
    "duration_sec",
    "n_events",
    "peak_anomaly_score",
    "mean_anomaly_score",
    "spacecraft_incident_id",
]
_INC_NUMERIC_FLOAT: list[str] = ["duration_sec", "peak_anomaly_score", "mean_anomaly_score"]
_INC_NUMERIC_INT: list[str] = ["segment", "n_events", "spacecraft_incident_id"]
_INC_TIMESTAMPS: list[str] = ["start_time", "end_time"]

# spacecraft_incidents.csv
_SI_REQUIRED: list[str] = [
    "spacecraft_incident_id",
    "start_time",
    "end_time",
    "duration_sec",
    "channels_affected",
    "n_channels_affected",
    "n_events_total",
    "peak_anomaly_score",
    "mean_anomaly_score",
    "segments_affected",
]
_SI_NUMERIC_FLOAT: list[str] = ["duration_sec", "peak_anomaly_score", "mean_anomaly_score"]
_SI_NUMERIC_INT: list[str] = [
    "spacecraft_incident_id",
    "n_channels_affected",
    "n_events_total",
]
_SI_TIMESTAMPS: list[str] = ["start_time", "end_time"]
_SI_PIPE_FIELDS: list[str] = ["channels_affected", "segments_affected"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_required_columns(df: pd.DataFrame, required: Sequence[str], source: str) -> None:
    """Raise ValueError if any required column is absent from *df*."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"[{source}] Missing required column(s): {missing}"
        )


def _validate_no_nulls(df: pd.DataFrame, columns: Sequence[str], source: str) -> None:
    """Raise ValueError if any required column contains null values."""
    for col in columns:
        if col not in df.columns:
            continue
        null_count = df[col].isna().sum()
        if null_count > 0:
            raise ValueError(
                f"[{source}] Column '{col}' contains {null_count} null value(s). "
                "Required fields must not be null."
            )


def _parse_timestamps(df: pd.DataFrame, columns: Sequence[str], source: str) -> pd.DataFrame:
    """
    Parse *columns* in *df* as UTC-aware datetimes (ISO-8601 with Z suffix).
    Raises ValueError with a clear message on parse failure.
    """
    for col in columns:
        if col not in df.columns:
            continue
        try:
            parsed = pd.to_datetime(df[col], utc=True, format="mixed")
        except Exception as exc:
            raise ValueError(
                f"[{source}] Could not parse column '{col}' as a UTC datetime: {exc}"
            ) from exc

        # Confirm timezone-awareness
        if parsed.dt.tz is None:
            parsed = parsed.dt.tz_localize("UTC")

        df = df.copy()
        df[col] = parsed
    return df


def _convert_numeric_float(df: pd.DataFrame, columns: Sequence[str], source: str) -> pd.DataFrame:
    """Cast *columns* to float64 and reject NaN / Inf values."""
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            continue
        try:
            df[col] = pd.to_numeric(df[col], errors="raise").astype("float64")
        except Exception as exc:
            raise ValueError(
                f"[{source}] Column '{col}' contains non-numeric value(s): {exc}"
            ) from exc
        _check_finite(df, col, source)
    return df


def _convert_numeric_int(df: pd.DataFrame, columns: Sequence[str], source: str) -> pd.DataFrame:
    """Cast *columns* to Int64 (nullable integer) and reject NaN values."""
    df = df.copy()
    for col in columns:
        if col not in df.columns:
            continue
        try:
            df[col] = pd.to_numeric(df[col], errors="raise").astype("Int64")
        except Exception as exc:
            raise ValueError(
                f"[{source}] Column '{col}' contains non-integer value(s): {exc}"
            ) from exc
    return df


def _check_finite(df: pd.DataFrame, col: str, source: str) -> None:
    """Raise ValueError if *col* contains NaN or Inf after numeric conversion."""
    series = df[col]
    if series.isna().any():
        raise ValueError(
            f"[{source}] Column '{col}' contains NaN value(s) after numeric conversion."
        )
    if series.apply(lambda x: math.isinf(x) if isinstance(x, float) else False).any():
        raise ValueError(
            f"[{source}] Column '{col}' contains Inf value(s)."
        )


def _split_pipe_field(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """
    Split a pipe-delimited string column into a Python list column.
    Single-value strings become one-element lists.
    Each element is stripped of surrounding whitespace.
    """
    df = df.copy()
    df[col] = df[col].apply(
        lambda v: [item.strip() for item in str(v).split("|")] if pd.notna(v) else []
    )
    return df


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------

def load_anomaly_events_csv(path: str | Path) -> pd.DataFrame:
    """
    Load ``anomaly_events.csv`` produced by Member 1.

    Columns retained as-is (not used for investigation logic):
    ``anomaly``, ``label``, ``train``, ``predicted_anomaly``.

    Returns
    -------
    pd.DataFrame
        Validated DataFrame with UTC-aware timestamps and typed numeric columns.

    Raises
    ------
    ValueError
        On missing required columns, null values in required fields,
        or non-finite numeric values.
    FileNotFoundError
        If *path* does not exist.
    """
    source = "anomaly_events.csv"
    df = pd.read_csv(path, dtype_backend="numpy_nullable")

    _validate_required_columns(df, _AE_REQUIRED, source)
    _validate_no_nulls(df, _AE_REQUIRED, source)

    df = _parse_timestamps(df, _AE_TIMESTAMPS, source)
    df = _convert_numeric_float(df, _AE_NUMERIC_FLOAT, source)
    df = _convert_numeric_int(df, _AE_NUMERIC_INT, source)

    return df


def load_incidents_csv(path: str | Path) -> pd.DataFrame:
    """
    Load ``incidents.csv`` produced by Member 1.

    Returns
    -------
    pd.DataFrame
        Validated DataFrame with UTC-aware timestamps and typed numeric columns.

    Raises
    ------
    ValueError
        On missing required columns, null values in required fields,
        or non-finite numeric values.
    FileNotFoundError
        If *path* does not exist.
    """
    source = "incidents.csv"
    df = pd.read_csv(path, dtype_backend="numpy_nullable")

    _validate_required_columns(df, _INC_REQUIRED, source)
    _validate_no_nulls(df, _INC_REQUIRED, source)

    df = _parse_timestamps(df, _INC_TIMESTAMPS, source)
    df = _convert_numeric_float(df, _INC_NUMERIC_FLOAT, source)
    df = _convert_numeric_int(df, _INC_NUMERIC_INT, source)

    return df


def load_spacecraft_incidents_csv(
    path: str | Path,
    incidents_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    Load ``spacecraft_incidents.csv`` produced by Member 1.

    Parameters
    ----------
    path:
        Path to ``spacecraft_incidents.csv``.
    incidents_df:
        Optional already-loaded incidents DataFrame (from
        :func:`load_incidents_csv`).  When supplied, referential integrity is
        checked: every ``spacecraft_incident_id`` in *incidents_df* must appear
        in the loaded spacecraft_incidents table.

    Returns
    -------
    pd.DataFrame
        Validated DataFrame with:
        - UTC-aware timestamps
        - Typed numeric columns
        - ``channels_affected`` and ``segments_affected`` as Python lists

    Raises
    ------
    ValueError
        On missing required columns, null values in required fields,
        non-finite numeric values, or referential integrity violations.
    FileNotFoundError
        If *path* does not exist.
    """
    source = "spacecraft_incidents.csv"
    df = pd.read_csv(path, dtype_backend="numpy_nullable")

    _validate_required_columns(df, _SI_REQUIRED, source)
    _validate_no_nulls(df, _SI_REQUIRED, source)

    df = _parse_timestamps(df, _SI_TIMESTAMPS, source)
    df = _convert_numeric_float(df, _SI_NUMERIC_FLOAT, source)
    df = _convert_numeric_int(df, _SI_NUMERIC_INT, source)

    for col in _SI_PIPE_FIELDS:
        df = _split_pipe_field(df, col)

    # Referential integrity: incidents.spacecraft_incident_id ⊆ spacecraft_incidents.spacecraft_incident_id
    if incidents_df is not None:
        known_ids = set(df["spacecraft_incident_id"].astype(int))
        if "spacecraft_incident_id" in incidents_df.columns:
            incident_ids = set(incidents_df["spacecraft_incident_id"].dropna().astype(int))
            orphaned = incident_ids - known_ids
            if orphaned:
                raise ValueError(
                    f"[{source}] Referential integrity violation: "
                    f"{len(orphaned)} spacecraft_incident_id(s) in incidents.csv "
                    f"have no match in spacecraft_incidents.csv: "
                    f"{sorted(orphaned)[:10]}"
                )

    return df
