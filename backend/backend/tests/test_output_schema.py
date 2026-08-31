"""
member2/tests/test_output_schema.py
------------------------------------
Unit tests for member2/output_schema.py.

Covers all models: TimelineEvent, GraphNode, GraphEdge, EvidenceGraph,
Investigation, DatasetStats, InvestigationReport, and all enumerations.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from member2.output_schema import (
    SCHEMA_VERSION,
    SCIENTIFIC_NOTE,
    DatasetStats,
    EvidenceGraph,
    GraphEdge,
    GraphNode,
    Investigation,
    InvestigationReport,
    MissionImpactLevel,
    PersistenceClass,
    TimelineEvent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(s: str = "2024-01-01T00:00:00Z") -> str:
    return s


def _dt(s: str = "2024-01-01T00:00:00Z") -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _timeline_event(**kwargs) -> dict:
    base = {
        "timestamp": "2024-01-01T00:00:00Z",
        "channel": "CH_A",
        "segment": 1,
        "anomaly_score": 0.5,
        "value": 1.0,
    }
    base.update(kwargs)
    return base


def _graph_node(**kwargs) -> dict:
    base = {"node_id": "INC-1", "node_type": "incident"}
    base.update(kwargs)
    return base


def _graph_edge(**kwargs) -> dict:
    base = {"source": "INC-1", "target": "CH-A", "relation": "incident_involves_channel"}
    base.update(kwargs)
    return base


def _evidence_graph(**kwargs) -> dict:
    base = {"nodes": [], "edges": []}
    base.update(kwargs)
    return base


def _investigation(**kwargs) -> dict:
    base = {
        "investigation_id": "INV-001",
        "spacecraft_incident_id": 1,
        "generated_at": "2024-01-01T00:00:00Z",
        "start_time": "2024-01-01T00:00:00Z",
        "end_time": "2024-01-01T00:05:00Z",
        "duration_sec": 300.0,
        "timeline": [],
        "timeline_truncated": False,
        "timeline_shown_count": 0,
        "n_channels_affected": 1,
        "channels_affected": ["CH_A"],
        "channel_activation_order": ["CH_A"],
        "is_multi_channel": False,
        "n_events_total": 10,
        "event_density_per_min": 2.0,
        "persistence_class": "MEDIUM",
        "segment_span": 1,
        "significance_score": 50.0,
        "significance_components": {"anomaly_strength": 0.5},
        "severity_score": 5.0,
        "severity_components": {"anomaly_strength": 0.5},
        "severity_rules_applied": [],
        "investigation_confidence": 0.7,
        "confidence_components": {"evidence_quantity": 0.5},
        "peak_anomaly_score": 0.8,
        "mean_anomaly_score": 0.5,
        "score_std": 0.1,
        "hypothesis_statements": [],
        "hypothesis_basis": [],
        "mission_impact_level": "LOW",
        "mission_impact_basis": [],
        "recommended_actions": [],
        "evidence_graph": _evidence_graph(),
        "channel_incident_ids": ["1"],
        "channel_temporal_relationships": [],
    }
    base.update(kwargs)
    return base


def _dataset_stats(**kwargs) -> dict:
    base = {
        "total_spacecraft_incidents": 805,
        "total_channel_incidents": 1875,
        "total_anomaly_events": 158726,
        "multi_channel_count": 484,
        "date_range_start": "2024-01-01T00:00:00Z",
        "date_range_end": "2024-12-31T00:00:00Z",
        "channels_observed": ["CH_A", "CH_B"],
    }
    base.update(kwargs)
    return base


def _report(**kwargs) -> dict:
    base = {
        "generated_at": "2024-01-01T00:00:00Z",
        "source_files": {"spacecraft_incidents": "spacecraft_incidents.csv"},
        "dataset_stats": _dataset_stats(),
        "investigations": [_investigation()],
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# TestTimelineEvent
# ---------------------------------------------------------------------------

class TestTimelineEvent:
    def test_valid_construction(self):
        e = TimelineEvent(**_timeline_event())
        assert e.channel == "CH_A"
        assert e.segment == 1
        assert e.anomaly_score == 0.5
        assert e.value == 1.0

    def test_timestamp_utc_aware(self):
        e = TimelineEvent(**_timeline_event())
        assert e.timestamp.tzinfo is not None

    def test_naive_datetime_gets_utc(self):
        naive = datetime(2024, 1, 1, 0, 0, 0)
        e = TimelineEvent(**_timeline_event(timestamp=naive))
        assert e.timestamp.tzinfo is not None

    def test_datetime_object_accepted(self):
        dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        e = TimelineEvent(**_timeline_event(timestamp=dt))
        assert e.timestamp == dt

    def test_anomaly_score_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            TimelineEvent(**_timeline_event(anomaly_score=-0.01))

    def test_anomaly_score_above_one_rejected(self):
        with pytest.raises(ValidationError):
            TimelineEvent(**_timeline_event(anomaly_score=1.01))

    def test_anomaly_score_boundaries_accepted(self):
        TimelineEvent(**_timeline_event(anomaly_score=0.0))
        TimelineEvent(**_timeline_event(anomaly_score=1.0))

    def test_empty_channel_rejected(self):
        with pytest.raises(ValidationError):
            TimelineEvent(**_timeline_event(channel=""))

    def test_negative_value_accepted(self):
        e = TimelineEvent(**_timeline_event(value=-999.9))
        assert e.value == -999.9


# ---------------------------------------------------------------------------
# TestGraphNode
# ---------------------------------------------------------------------------

class TestGraphNode:
    def test_valid_construction(self):
        n = GraphNode(**_graph_node())
        assert n.node_id == "INC-1"
        assert n.node_type == "incident"

    def test_empty_node_id_rejected(self):
        with pytest.raises(ValidationError):
            GraphNode(**_graph_node(node_id=""))

    def test_empty_node_type_rejected(self):
        with pytest.raises(ValidationError):
            GraphNode(**_graph_node(node_type=""))

    def test_attributes_defaults_to_empty_dict(self):
        n = GraphNode(**_graph_node())
        assert n.attributes == {}

    def test_attributes_accepts_nested_data(self):
        n = GraphNode(**_graph_node(attributes={"n_events": 10, "nested": {"a": 1}}))
        assert n.attributes["n_events"] == 10

    def test_node_types_channel_and_cluster(self):
        GraphNode(node_id="CH-A", node_type="channel")
        GraphNode(node_id="CLU-1", node_type="event_cluster")


# ---------------------------------------------------------------------------
# TestGraphEdge
# ---------------------------------------------------------------------------

class TestGraphEdge:
    def test_valid_construction(self):
        e = GraphEdge(**_graph_edge())
        assert e.source == "INC-1"
        assert e.target == "CH-A"
        assert e.relation == "incident_involves_channel"

    def test_empty_source_rejected(self):
        with pytest.raises(ValidationError):
            GraphEdge(**_graph_edge(source=""))

    def test_empty_target_rejected(self):
        with pytest.raises(ValidationError):
            GraphEdge(**_graph_edge(target=""))

    def test_empty_relation_rejected(self):
        with pytest.raises(ValidationError):
            GraphEdge(**_graph_edge(relation=""))

    def test_weight_defaults_to_zero(self):
        e = GraphEdge(**_graph_edge())
        assert e.weight == 0.0

    def test_label_defaults_to_empty_string(self):
        e = GraphEdge(**_graph_edge())
        assert e.label == ""

    def test_co_active_label_stored(self):
        e = GraphEdge(**_graph_edge(label="temporal co-occurrence, not causal"))
        assert "temporal" in e.label


# ---------------------------------------------------------------------------
# TestEvidenceGraph
# ---------------------------------------------------------------------------

class TestEvidenceGraph:
    def test_valid_construction(self):
        g = EvidenceGraph(**_evidence_graph())
        assert g.nodes == []
        assert g.edges == []

    def test_empty_graph_valid(self):
        g = EvidenceGraph()
        assert g.nodes == []
        assert g.edges == []

    def test_nodes_are_graph_node_instances(self):
        g = EvidenceGraph(nodes=[GraphNode(node_id="INC-1", node_type="incident")])
        assert isinstance(g.nodes[0], GraphNode)

    def test_edges_are_graph_edge_instances(self):
        g = EvidenceGraph(edges=[GraphEdge(source="INC-1", target="CH-A", relation="r")])
        assert isinstance(g.edges[0], GraphEdge)

    def test_multiple_nodes_and_edges(self):
        g = EvidenceGraph(
            nodes=[
                GraphNode(node_id="INC-1", node_type="incident"),
                GraphNode(node_id="CH-A", node_type="channel"),
            ],
            edges=[
                GraphEdge(source="INC-1", target="CH-A", relation="incident_involves_channel")
            ],
        )
        assert len(g.nodes) == 2
        assert len(g.edges) == 1


# ---------------------------------------------------------------------------
# TestInvestigation
# ---------------------------------------------------------------------------

class TestInvestigation:
    def test_valid_construction(self):
        inv = Investigation(**_investigation())
        assert inv.investigation_id == "INV-001"
        assert inv.spacecraft_incident_id == 1

    def test_scientific_note_is_constant(self):
        inv = Investigation(**_investigation())
        assert inv.scientific_note == SCIENTIFIC_NOTE

    def test_scientific_note_cannot_be_overridden(self):
        # scientific_note has a default; it can be set but the default is the constant
        inv = Investigation(**_investigation())
        assert "Temporal correlation" in inv.scientific_note
        assert "physical causality" in inv.scientific_note

    def test_significance_score_bounds(self):
        with pytest.raises(ValidationError):
            Investigation(**_investigation(significance_score=-0.1))
        with pytest.raises(ValidationError):
            Investigation(**_investigation(significance_score=100.1))

    def test_severity_score_bounds(self):
        with pytest.raises(ValidationError):
            Investigation(**_investigation(severity_score=-0.1))
        with pytest.raises(ValidationError):
            Investigation(**_investigation(severity_score=10.1))

    def test_investigation_confidence_bounds(self):
        with pytest.raises(ValidationError):
            Investigation(**_investigation(investigation_confidence=-0.01))
        with pytest.raises(ValidationError):
            Investigation(**_investigation(investigation_confidence=1.01))

    def test_peak_anomaly_score_bounds(self):
        with pytest.raises(ValidationError):
            Investigation(**_investigation(peak_anomaly_score=-0.01))
        with pytest.raises(ValidationError):
            Investigation(**_investigation(peak_anomaly_score=1.01))

    def test_mean_anomaly_score_bounds(self):
        with pytest.raises(ValidationError):
            Investigation(**_investigation(mean_anomaly_score=-0.01))
        with pytest.raises(ValidationError):
            Investigation(**_investigation(mean_anomaly_score=1.01))

    def test_duration_sec_non_negative(self):
        with pytest.raises(ValidationError):
            Investigation(**_investigation(duration_sec=-1.0))

    def test_n_channels_affected_minimum_one(self):
        with pytest.raises(ValidationError):
            Investigation(**_investigation(n_channels_affected=0))

    def test_n_events_total_non_negative(self):
        with pytest.raises(ValidationError):
            Investigation(**_investigation(n_events_total=-1))

    def test_persistence_class_valid_values(self):
        for cls in ["SHORT", "MEDIUM", "LONG", "EXTENDED"]:
            inv = Investigation(**_investigation(persistence_class=cls))
            assert inv.persistence_class.value == cls

    def test_persistence_class_invalid_rejected(self):
        with pytest.raises(ValidationError):
            Investigation(**_investigation(persistence_class="VERY_LONG"))

    def test_mission_impact_valid_values(self):
        for level in ["LOW", "MODERATE", "HIGH", "CRITICAL"]:
            inv = Investigation(**_investigation(mission_impact_level=level))
            assert inv.mission_impact_level.value == level

    def test_mission_impact_invalid_rejected(self):
        with pytest.raises(ValidationError):
            Investigation(**_investigation(mission_impact_level="EXTREME"))

    def test_timestamps_utc_aware(self):
        inv = Investigation(**_investigation())
        assert inv.generated_at.tzinfo is not None
        assert inv.start_time.tzinfo is not None
        assert inv.end_time.tzinfo is not None

    def test_naive_timestamps_get_utc(self):
        naive = datetime(2024, 1, 1)
        inv = Investigation(**_investigation(generated_at=naive, start_time=naive, end_time=naive))
        assert inv.generated_at.tzinfo is not None

    def test_timeline_is_list_of_timeline_events(self):
        te = TimelineEvent(**_timeline_event())
        inv = Investigation(**_investigation(timeline=[te]))
        assert isinstance(inv.timeline[0], TimelineEvent)

    def test_evidence_graph_is_evidence_graph_instance(self):
        inv = Investigation(**_investigation())
        assert isinstance(inv.evidence_graph, EvidenceGraph)

    def test_score_std_non_negative(self):
        with pytest.raises(ValidationError):
            Investigation(**_investigation(score_std=-0.01))

    def test_significance_components_dict(self):
        inv = Investigation(**_investigation(significance_components={"anomaly_strength": 0.8}))
        assert inv.significance_components["anomaly_strength"] == 0.8

    def test_severity_components_dict(self):
        inv = Investigation(**_investigation(severity_components={"persistence": 0.5}))
        assert inv.severity_components["persistence"] == 0.5

    def test_empty_timeline_accepted(self):
        inv = Investigation(**_investigation(timeline=[]))
        assert inv.timeline == []

    def test_multi_channel_flag(self):
        inv = Investigation(**_investigation(is_multi_channel=True, n_channels_affected=2))
        assert inv.is_multi_channel is True


# ---------------------------------------------------------------------------
# TestDatasetStats
# ---------------------------------------------------------------------------

class TestDatasetStats:
    def test_valid_construction(self):
        ds = DatasetStats(**_dataset_stats())
        assert ds.total_spacecraft_incidents == 805

    def test_timestamps_utc_aware(self):
        ds = DatasetStats(**_dataset_stats())
        assert ds.date_range_start.tzinfo is not None
        assert ds.date_range_end.tzinfo is not None

    def test_channels_observed_is_list(self):
        ds = DatasetStats(**_dataset_stats())
        assert isinstance(ds.channels_observed, list)

    def test_zero_counts_rejected(self):
        with pytest.raises(ValidationError):
            DatasetStats(**_dataset_stats(total_spacecraft_incidents=-1))

    def test_zero_multi_channel_accepted(self):
        ds = DatasetStats(**_dataset_stats(multi_channel_count=0))
        assert ds.multi_channel_count == 0


# ---------------------------------------------------------------------------
# TestInvestigationReport
# ---------------------------------------------------------------------------

class TestInvestigationReport:
    def test_valid_construction(self):
        r = InvestigationReport(**_report())
        assert r.schema_version == SCHEMA_VERSION

    def test_schema_version_default(self):
        r = InvestigationReport(**_report())
        assert r.schema_version == "2.0"

    def test_source_files_dict(self):
        r = InvestigationReport(**_report())
        assert isinstance(r.source_files, dict)

    def test_dataset_stats_is_dataset_stats_instance(self):
        r = InvestigationReport(**_report())
        assert isinstance(r.dataset_stats, DatasetStats)

    def test_investigations_list_of_investigation(self):
        r = InvestigationReport(**_report())
        assert isinstance(r.investigations[0], Investigation)

    def test_generated_at_utc(self):
        r = InvestigationReport(**_report())
        assert r.generated_at.tzinfo is not None

    def test_multiple_investigations(self):
        r = InvestigationReport(**_report(investigations=[_investigation(), _investigation()]))
        assert len(r.investigations) == 2

    def test_empty_source_files_accepted(self):
        r = InvestigationReport(**_report(source_files={}))
        assert r.source_files == {}


# ---------------------------------------------------------------------------
# TestEnums
# ---------------------------------------------------------------------------

class TestEnums:
    def test_persistence_class_values(self):
        assert set(e.value for e in PersistenceClass) == {"SHORT", "MEDIUM", "LONG", "EXTENDED"}

    def test_mission_impact_values(self):
        assert set(e.value for e in MissionImpactLevel) == {"LOW", "MODERATE", "HIGH", "CRITICAL"}

    def test_persistence_class_is_str_subclass(self):
        assert isinstance(PersistenceClass.SHORT, str)

    def test_mission_impact_is_str_subclass(self):
        assert isinstance(MissionImpactLevel.LOW, str)


# ---------------------------------------------------------------------------
# TestJsonSerialisation
# ---------------------------------------------------------------------------

class TestJsonSerialisation:
    def test_investigation_serialises_to_json(self):
        inv = Investigation(**_investigation())
        j = json.loads(inv.model_dump_json())
        assert "investigation_id" in j

    def test_persistence_class_serialises_as_string(self):
        inv = Investigation(**_investigation(persistence_class="LONG"))
        j = json.loads(inv.model_dump_json())
        assert j["persistence_class"] == "LONG"

    def test_mission_impact_serialises_as_string(self):
        inv = Investigation(**_investigation(mission_impact_level="HIGH"))
        j = json.loads(inv.model_dump_json())
        assert j["mission_impact_level"] == "HIGH"

    def test_report_serialises_to_json(self):
        r = InvestigationReport(**_report())
        j = json.loads(r.model_dump_json())
        assert "schema_version" in j

    def test_nested_graph_serialises(self):
        g = EvidenceGraph(nodes=[GraphNode(node_id="INC-1", node_type="incident")])
        inv = Investigation(**_investigation(evidence_graph=g))
        j = json.loads(inv.model_dump_json())
        assert len(j["evidence_graph"]["nodes"]) == 1

    def test_timeline_serialises(self):
        te = TimelineEvent(**_timeline_event())
        inv = Investigation(**_investigation(timeline=[te]))
        j = json.loads(inv.model_dump_json())
        assert len(j["timeline"]) == 1

    def test_dataset_stats_serialises(self):
        ds = DatasetStats(**_dataset_stats())
        j = json.loads(ds.model_dump_json())
        assert j["total_spacecraft_incidents"] == 805

    def test_round_trip_investigation(self):
        inv = Investigation(**_investigation())
        j = json.loads(inv.model_dump_json())
        inv2 = Investigation.model_validate(j)
        assert inv2.investigation_id == inv.investigation_id

    def test_round_trip_report(self):
        r = InvestigationReport(**_report())
        j = json.loads(r.model_dump_json())
        r2 = InvestigationReport.model_validate(j)
        assert r2.schema_version == r.schema_version

    def test_source_files_serialises(self):
        r = InvestigationReport(**_report(source_files={"a": "path/a.csv", "b": "path/b.csv"}))
        j = json.loads(r.model_dump_json())
        assert j["source_files"]["a"] == "path/a.csv"


# ---------------------------------------------------------------------------
# TestConstants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_scientific_note_text(self):
        assert "Temporal correlation" in SCIENTIFIC_NOTE
        assert "physical causality" in SCIENTIFIC_NOTE
        assert "hypotheses" in SCIENTIFIC_NOTE
        assert "subsystem mapping" in SCIENTIFIC_NOTE

    def test_schema_version_value(self):
        assert SCHEMA_VERSION == "2.0"

    def test_investigation_default_note_matches_constant(self):
        inv = Investigation(**_investigation())
        assert inv.scientific_note == SCIENTIFIC_NOTE

    def test_report_default_schema_version_matches_constant(self):
        r = InvestigationReport(**_report())
        assert r.schema_version == SCHEMA_VERSION
