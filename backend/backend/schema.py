"""
member2/schema.py
-----------------
Input schema and validation layer for Member 2 — Incident Investigation Engineer.

Validates anomaly events produced by Member 1 (or mock data) before any
investigation logic is applied.  No correlation, grouping, severity, or
IBM watsonx logic lives here.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, List, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# AnomalyEvent — one detected anomaly from the telemetry pipeline
# ---------------------------------------------------------------------------

class AnomalyEvent(BaseModel):
    """Represents a single anomaly event emitted by Member 1."""

    event_id: Annotated[str, Field(min_length=1)]
    """Unique identifier for this anomaly event (non-empty string)."""

    timestamp: datetime
    """ISO-8601 timestamp of the anomaly; parsed to a timezone-aware datetime."""

    channel: Annotated[str, Field(min_length=1)]
    """Telemetry channel name (non-empty string)."""

    anomaly_score: Annotated[float, Field(ge=0.0, le=1.0)]
    """Anomaly confidence score in [0, 1]."""

    raw_value: float
    """Raw telemetry value at the time of detection (numeric)."""

    expected_range: Tuple[float, float]
    """Two-element [min, max] range that is considered nominal for this channel."""

    deviation_sigma: float
    """How many standard deviations the raw_value is from the expected mean (numeric)."""

    detection_method: Annotated[str, Field(min_length=1)]
    """Name of the algorithm that flagged this anomaly (non-empty string)."""

    # ------------------------------------------------------------------
    # Field-level validators
    # ------------------------------------------------------------------

    @field_validator("event_id", "channel", "detection_method", mode="before")
    @classmethod
    def _strip_and_require_nonempty(cls, v: object) -> str:
        """Strip surrounding whitespace and reject empty strings."""
        if not isinstance(v, str):
            raise ValueError("must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace-only")
        return stripped

    @field_validator("timestamp", mode="before")
    @classmethod
    def _parse_timestamp(cls, v: object) -> datetime:
        """
        Accept either a datetime object or an ISO-8601 string.
        Attaches UTC timezone when the parsed datetime is naive.
        """
        if isinstance(v, datetime):
            dt = v
        elif isinstance(v, str):
            try:
                dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError(
                    f"'{v}' is not a valid ISO-8601 timestamp "
                    "(expected format: YYYY-MM-DDTHH:MM:SSZ or with offset)"
                )
        else:
            raise ValueError("timestamp must be an ISO-8601 string or a datetime object")

        # Make naive datetimes timezone-aware (assume UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    @field_validator("expected_range", mode="before")
    @classmethod
    def _validate_expected_range(cls, v: object) -> Tuple[float, float]:
        """Ensure expected_range is a two-element sequence of numerics."""
        if not isinstance(v, (list, tuple)):
            raise ValueError("expected_range must be a list or tuple with exactly two numeric values")
        if len(v) != 2:
            raise ValueError(
                f"expected_range must contain exactly 2 values, got {len(v)}"
            )
        result = []
        for i, item in enumerate(v):
            try:
                result.append(float(item))
            except (TypeError, ValueError):
                raise ValueError(
                    f"expected_range[{i}] must be numeric, got {type(item).__name__!r}"
                )
        return (result[0], result[1])

    # ------------------------------------------------------------------
    # Cross-field validators
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _validate_expected_range_order(self) -> "AnomalyEvent":
        """Warn if expected_range[0] > expected_range[1] (not a hard error — some
        sensors may have inverted nominal bands, but it is likely a data issue)."""
        lo, hi = self.expected_range
        if lo > hi:
            raise ValueError(
                f"expected_range lower bound ({lo}) must not exceed upper bound ({hi})"
            )
        return self


# ---------------------------------------------------------------------------
# AnomalyEventInput — top-level container matching anomaly_events.json
# ---------------------------------------------------------------------------

class AnomalyEventInput(BaseModel):
    """
    Top-level container that wraps the full anomaly_events.json payload
    produced by Member 1 (or mock data).
    """

    schema_version: str = Field(default="1.0")
    """Version string of the data format (informational, not validated strictly)."""

    generated_at: datetime
    """ISO-8601 timestamp indicating when the file was produced."""

    source_dataset: Annotated[str, Field(min_length=1)]
    """Name of the originating dataset (e.g. 'OPS-SAT-AD')."""

    events: List[AnomalyEvent]
    """Ordered list of anomaly events to be investigated."""

    @field_validator("generated_at", mode="before")
    @classmethod
    def _parse_generated_at(cls, v: object) -> datetime:
        """Reuse the same ISO-8601 parsing logic as AnomalyEvent.timestamp."""
        return AnomalyEvent._parse_timestamp(v)  # type: ignore[attr-defined]

    @field_validator("events", mode="after")
    @classmethod
    def _require_at_least_one_event(cls, v: List[AnomalyEvent]) -> List[AnomalyEvent]:
        """An empty events list is almost certainly a pipeline error."""
        if not v:
            raise ValueError("events list must not be empty")
        return v


# ---------------------------------------------------------------------------
# Convenience loader
# ---------------------------------------------------------------------------

def load_anomaly_events(path: str | Path) -> AnomalyEventInput:
    """
    Load and validate an anomaly_events.json file from *path*.

    Returns a fully validated :class:`AnomalyEventInput` on success.
    Raises :exc:`pydantic.ValidationError` with field-level error messages
    on failure, or :exc:`json.JSONDecodeError` if the file is not valid JSON.

    Example::

        from member2.schema import load_anomaly_events
        data = load_anomaly_events("data/mock/anomaly_events.json")
        for event in data.events:
            print(event.event_id, event.timestamp, event.anomaly_score)
    """
    raw = Path(path).read_text(encoding="utf-8")
    payload = json.loads(raw)
    return AnomalyEventInput.model_validate(payload)
