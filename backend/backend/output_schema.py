"""
member2/output_schema.py
------------------------
Pydantic output models for the Member 2 → Member 3 contract.

These models define the structure of ``investigations.json`` produced by
Member 2's investigation engine and consumed by Member 3 (IBM watsonx +
Streamlit dashboard).

Do NOT import or reference ``member2.schema`` from this module.
``member2.schema`` is a legacy pre-handoff file and is unrelated to the
real Member 1 CSV output.

Models
------
TimelineEvent           one row in the per-incident event timeline
GraphNode               one node in the evidence graph
GraphEdge               one edge in the evidence graph
EvidenceGraph           full graph (nodes + edges lists)
Investigation           one investigated spacecraft incident
DatasetStats            dataset-level statistics (passed in envelope)
InvestigationReport     top-level output file envelope (schema_version "2.0")

Scientific note
---------------
All ``Investigation`` objects carry a constant ``scientific_note`` field:

    "Temporal correlation between anomaly events does not establish physical
     causality. All failure-chain descriptions are evidence-supported hypotheses
     derived from telemetry patterns only. No spacecraft subsystem mapping has
     been applied."

Serialisation
-------------
All ``datetime`` fields are UTC-aware and serialise to ISO-8601 strings.
Enum fields serialise to their string values.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCIENTIFIC_NOTE: str = (
    "Temporal correlation between anomaly events does not establish physical "
    "causality. All failure-chain descriptions are evidence-supported hypotheses "
    "derived from telemetry patterns only. No spacecraft subsystem mapping has "
    "been applied."
)

SCHEMA_VERSION: str = "2.0"


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class PersistenceClass(str, Enum):
    """Duration-based persistence classification for an incident."""
    SHORT = "SHORT"
    MEDIUM = "MEDIUM"
    LONG = "LONG"
    EXTENDED = "EXTENDED"


class MissionImpactLevel(str, Enum):
    """Mission impact level derived from telemetry evidence only."""
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# TimelineEvent
# ---------------------------------------------------------------------------

class TimelineEvent(BaseModel):
    """
    One telemetry sample in the chronological incident timeline.

    Corresponds directly to a row in ``anomaly_events.csv`` that belongs to
    the investigated spacecraft incident.
    """

    model_config = ConfigDict(ser_json_timedelta="iso8601")

    timestamp: datetime
    channel: Annotated[str, Field(min_length=1)]
    segment: int
    anomaly_score: Annotated[float, Field(ge=0.0, le=1.0)]
    value: float

    @field_validator("timestamp", mode="before")
    @classmethod
    def _ensure_utc(cls, v: object) -> datetime:
        """Accept datetime objects or ISO-8601 strings; attach UTC if naive."""
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            return v
        raise ValueError(f"Cannot convert {type(v).__name__} to datetime")


# ---------------------------------------------------------------------------
# GraphNode / GraphEdge / EvidenceGraph
# ---------------------------------------------------------------------------

class GraphNode(BaseModel):
    """One node in the per-incident evidence graph."""

    node_id: Annotated[str, Field(min_length=1)]
    node_type: Annotated[str, Field(min_length=1)]
    attributes: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """One directed edge in the per-incident evidence graph."""

    source: Annotated[str, Field(min_length=1)]
    target: Annotated[str, Field(min_length=1)]
    relation: Annotated[str, Field(min_length=1)]
    weight: float = 0.0
    label: str = ""


class EvidenceGraph(BaseModel):
    """
    Adjacency-list evidence graph for one spacecraft incident.

    Intentionally plain Python dicts / lists so Member 3 can build a
    ``networkx`` graph directly from the JSON without any special parser.
    """

    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Investigation
# ---------------------------------------------------------------------------

class Investigation(BaseModel):
    """
    Fully characterised investigation of one spacecraft-level incident.

    Every field is derived from the three Member 1 CSV files.
    No field references the ground-truth columns ``anomaly``, ``label``,
    or ``train``, nor any field from the legacy ``member2.schema`` module
    (``event_id``, ``expected_range``, ``deviation_sigma``, ``detection_method``).
    """

    model_config = ConfigDict(ser_json_timedelta="iso8601")

    investigation_id: Annotated[str, Field(min_length=1)]
    spacecraft_incident_id: int
    generated_at: datetime
    start_time: datetime
    end_time: datetime
    duration_sec: Annotated[float, Field(ge=0.0)]
    timeline: List[TimelineEvent] = Field(default_factory=list)
    # Fix 3: timeline truncation metadata
    timeline_truncated: bool = Field(default=False)
    timeline_shown_count: int = Field(default=0, ge=0)
    n_channels_affected: Annotated[int, Field(ge=1)]
    channels_affected: List[str]
    channel_activation_order: List[str]
    is_multi_channel: bool
    n_events_total: Annotated[int, Field(ge=0)]
    event_density_per_min: float
    persistence_class: PersistenceClass
    segment_span: int
    significance_score: Annotated[float, Field(ge=0.0, le=100.0)]
    significance_components: Dict[str, float] = Field(default_factory=dict)
    severity_score: Annotated[float, Field(ge=0.0, le=10.0)]
    severity_components: Dict[str, float] = Field(default_factory=dict)
    severity_rules_applied: List[str] = Field(default_factory=list)
    investigation_confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    confidence_components: Dict[str, float] = Field(default_factory=dict)
    peak_anomaly_score: Annotated[float, Field(ge=0.0, le=1.0)]
    mean_anomaly_score: Annotated[float, Field(ge=0.0, le=1.0)]
    score_std: Annotated[float, Field(ge=0.0)]
    hypothesis_statements: List[str] = Field(default_factory=list)
    hypothesis_basis: List[str] = Field(default_factory=list)
    mission_impact_level: MissionImpactLevel
    mission_impact_basis: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    evidence_graph: EvidenceGraph = Field(default_factory=EvidenceGraph)
    channel_incident_ids: List[str] = Field(default_factory=list)
    channel_temporal_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    scientific_note: str = Field(default=SCIENTIFIC_NOTE)

    @field_validator("generated_at", "start_time", "end_time", mode="before")
    @classmethod
    def _ensure_utc(cls, v: object) -> datetime:
        """Accept datetime objects or ISO-8601 strings; attach UTC if naive."""
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            return v
        raise ValueError(f"Cannot convert {type(v).__name__} to datetime")


# ---------------------------------------------------------------------------
# DatasetStats
# ---------------------------------------------------------------------------

class DatasetStats(BaseModel):
    """Dataset-level statistics computed once at load time."""

    total_spacecraft_incidents: Annotated[int, Field(ge=0)]
    total_channel_incidents: Annotated[int, Field(ge=0)]
    total_anomaly_events: Annotated[int, Field(ge=0)]
    multi_channel_count: Annotated[int, Field(ge=0)]
    date_range_start: datetime
    date_range_end: datetime
    channels_observed: List[str]

    @field_validator("date_range_start", "date_range_end", mode="before")
    @classmethod
    def _ensure_utc(cls, v: object) -> datetime:
        """Accept datetime objects or ISO-8601 strings; attach UTC if naive."""
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            return v
        raise ValueError(f"Cannot convert {type(v).__name__} to datetime")


# ---------------------------------------------------------------------------
# InvestigationReport
# ---------------------------------------------------------------------------

class InvestigationReport(BaseModel):
    """
    Top-level output file envelope written to ``investigations.json``.

    Member 3 reads this file directly.  ``schema_version`` is always ``"2.0"``.
    ``investigations`` is sorted by ``significance_score`` descending.
    """

    model_config = ConfigDict(ser_json_timedelta="iso8601")

    schema_version: str = Field(default=SCHEMA_VERSION)
    generated_at: datetime
    source_files: Dict[str, str] = Field(default_factory=dict)
    dataset_stats: DatasetStats
    investigations: List[Investigation]

    @field_validator("generated_at", mode="before")
    @classmethod
    def _ensure_utc(cls, v: object) -> datetime:
        """Accept datetime objects or ISO-8601 strings; attach UTC if naive."""
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime):
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            return v
        raise ValueError(f"Cannot convert {type(v).__name__} to datetime")
