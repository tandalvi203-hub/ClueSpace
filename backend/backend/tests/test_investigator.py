"""
member2/tests/test_investigator.py
-----------------------------------
Comprehensive tests for member2/investigator.py.

Covers:
    1.  valid single-channel investigation
    2.  valid multi-channel investigation
    3.  invalid incident ID
    4.  missing columns
    5.  all pipeline stages invoked correctly
    6.  final report structure
    7.  score propagation
    8.  hypothesis propagation
    9.  evidence graph propagation
    10. actions propagation
    11. traceability
    12. deterministic output
    13. scientific caveat preserved
    14. no causal terminology
    15. real-data incident 988 integration

The real-data test (test 15) loads the actual OPS-SAT-AD CSV files from:
    data/spacecraft_incidents.csv
    data/incidents.csv
    data/anomaly_events.csv

Expected values for incident 988:
    n_channels_affected     : 5
    n_temporal_pairs        : 10
    no duplicate pairs
    significance_score      : 98.75
    severity_score          : 9.375
    investigation_confidence: 0.7879
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import call, patch

import pandas as pd
import pytest

from member2.investigator import investigate_incident
from member2.output_schema import (
    SCIENTIFIC_NOTE,
    EvidenceGraph,
    InvestigationReport,
    Investigation,
    MissionImpactLevel,
)

# ---------------------------------------------------------------------------
# Path to real data
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_AE_CSV = _DATA_DIR / "anomaly_events.csv"
_INC_CSV = _DATA_DIR / "incidents.csv"
_SI_CSV = _DATA_DIR / "spacecraft_incidents.csv"


# ---------------------------------------------------------------------------
# Minimal DataFrame factories for unit tests
# ---------------------------------------------------------------------------

def _make_ae_df(
    channel: str = "CH_A",
    segment: int = 1,
    n: int = 5,
    anomaly_score: float = 0.8,
    value: float = 0.5,
) -> pd.DataFrame:
    """Single-channel anomaly events block."""
    base_ts = pd.Timestamp("2022-01-01T00:00:00Z")
    rows = [
        {
            "timestamp": base_ts + pd.Timedelta(seconds=i),
            "channel": channel,
            "segment": segment,
            "value": value,
            "anomaly_score": anomaly_score,
        }
        for i in range(n)
    ]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def _make_multi_ae_df() -> pd.DataFrame:
    """Two-channel anomaly events block."""
    a = _make_ae_df("CH_A", 1, 5, 0.9)
    b = _make_ae_df("CH_B", 2, 3, 0.7)
    # offset channel B times so they differ
    b["timestamp"] = b["timestamp"] + pd.Timedelta(seconds=10)
    return pd.concat([a, b], ignore_index=True)


def _make_inc_df(
    incident_id: str = "INC_1",
    channel: str = "CH_A",
    segment: int = 1,
    spacecraft_incident_id: int = 1,
    duration_sec: float = 100.0,
    n_events: int = 5,
    peak: float = 0.8,
    mean: float = 0.6,
    start_offset_sec: int = 0,
    end_offset_sec: int = 100,
) -> pd.DataFrame:
    base_ts = pd.Timestamp("2022-01-01T00:00:00Z")
    return pd.DataFrame([{
        "incident_id": incident_id,
        "channel": channel,
        "segment": segment,
        "start_time": base_ts + pd.Timedelta(seconds=start_offset_sec),
        "end_time": base_ts + pd.Timedelta(seconds=end_offset_sec),
        "duration_sec": duration_sec,
        "n_events": n_events,
        "peak_anomaly_score": peak,
        "mean_anomaly_score": mean,
        "spacecraft_incident_id": spacecraft_incident_id,
    }])


def _make_multi_inc_df(spacecraft_incident_id: int = 1) -> pd.DataFrame:
    a = _make_inc_df("INC_A", "CH_A", 1, spacecraft_incident_id, 200.0, 5, 0.9, 0.7, 0, 200)
    b = _make_inc_df("INC_B", "CH_B", 2, spacecraft_incident_id, 180.0, 3, 0.7, 0.5, 10, 190)
    return pd.concat([a, b], ignore_index=True)


def _make_si_df(
    spacecraft_incident_id: int = 1,
    channels: list[str] | None = None,
    start_offset_sec: int = 0,
    end_offset_sec: int = 100,
    duration_sec: float = 100.0,
    n_events_total: int = 5,
    peak: float = 0.8,
    mean: float = 0.6,
    n_channels: int = 1,
) -> pd.DataFrame:
    if channels is None:
        channels = ["CH_A"]
    base_ts = pd.Timestamp("2022-01-01T00:00:00Z")
    return pd.DataFrame([{
        "spacecraft_incident_id": spacecraft_incident_id,
        "start_time": base_ts + pd.Timedelta(seconds=start_offset_sec),
        "end_time": base_ts + pd.Timedelta(seconds=end_offset_sec),
        "duration_sec": duration_sec,
        "channels_affected": channels,  # already a list (as loader returns it)
        "n_channels_affected": n_channels,
        "n_events_total": n_events_total,
        "peak_anomaly_score": peak,
        "mean_anomaly_score": mean,
        "segments_affected": [1] * n_channels,
    }])


def _single_channel_fixtures() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ae = _make_ae_df()
    inc = _make_inc_df()
    si = _make_si_df()
    return ae, inc, si


def _multi_channel_fixtures() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ae = _make_multi_ae_df()
    inc = _make_multi_inc_df()
    si = _make_si_df(
        channels=["CH_A", "CH_B"],
        n_channels=2,
        n_events_total=8,
        peak=0.9,
        mean=0.7,
        duration_sec=200.0,
        end_offset_sec=200,
    )
    return ae, inc, si


# ---------------------------------------------------------------------------
# 1. Valid single-channel investigation
# ---------------------------------------------------------------------------

class TestSingleChannelInvestigation:
    def test_returns_investigation_report(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        assert isinstance(report, InvestigationReport)

    def test_report_has_one_investigation(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        assert len(report.investigations) == 1

    def test_investigation_identity(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert inv.spacecraft_incident_id == 1
        # Fix 5: stable ID format is now INV-{sid} without embedded timestamp
        assert inv.investigation_id == "INV-1"

    def test_single_channel_fields(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert inv.n_channels_affected == 1
        assert inv.is_multi_channel is False
        assert inv.channels_affected == ["CH_A"]

    def test_duration_and_temporal_bounds(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert inv.duration_sec == 100.0
        assert inv.start_time is not None
        assert inv.end_time is not None
        assert inv.end_time > inv.start_time

    def test_timeline_not_empty(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert len(inv.timeline) > 0

    def test_event_statistics(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert inv.n_events_total == 5
        assert 0.0 <= inv.peak_anomaly_score <= 1.0
        assert 0.0 <= inv.mean_anomaly_score <= 1.0
        assert inv.score_std >= 0.0


# ---------------------------------------------------------------------------
# 2. Valid multi-channel investigation
# ---------------------------------------------------------------------------

class TestMultiChannelInvestigation:
    def test_returns_investigation_report(self):
        ae, inc, si = _multi_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        assert isinstance(report, InvestigationReport)

    def test_multi_channel_fields(self):
        ae, inc, si = _multi_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert inv.n_channels_affected == 2
        assert inv.is_multi_channel is True
        assert set(inv.channels_affected) == {"CH_A", "CH_B"}

    def test_channel_activation_order_set(self):
        ae, inc, si = _multi_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert len(inv.channel_activation_order) == 2

    def test_temporal_relationships_populated(self):
        ae, inc, si = _multi_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        # 2 channels → 1 pair
        assert len(inv.channel_temporal_relationships) == 1

    def test_temporal_relationship_structure(self):
        ae, inc, si = _multi_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        rel = inv.channel_temporal_relationships[0]
        assert "channel_a" in rel
        assert "channel_b" in rel
        assert "temporal_gap_sec" in rel
        assert "temporal_precedence" in rel
        assert "windows_overlap" in rel


# ---------------------------------------------------------------------------
# 3. Invalid incident ID
# ---------------------------------------------------------------------------

class TestInvalidIncidentId:
    def test_nonexistent_id_raises_value_error(self):
        ae, inc, si = _single_channel_fixtures()
        with pytest.raises(ValueError, match="not found"):
            investigate_incident(99999, ae, inc, si)

    def test_error_message_contains_id(self):
        ae, inc, si = _single_channel_fixtures()
        with pytest.raises(ValueError, match="99999"):
            investigate_incident(99999, ae, inc, si)


# ---------------------------------------------------------------------------
# 4. Missing columns
# ---------------------------------------------------------------------------

class TestMissingColumns:
    def test_missing_ae_column_raises(self):
        ae, inc, si = _single_channel_fixtures()
        ae_bad = ae.drop(columns=["anomaly_score"])
        with pytest.raises(ValueError, match="anomaly_score"):
            investigate_incident(1, ae_bad, inc, si)

    def test_missing_inc_column_raises(self):
        ae, inc, si = _single_channel_fixtures()
        inc_bad = inc.drop(columns=["incident_id"])
        with pytest.raises(ValueError, match="incident_id"):
            investigate_incident(1, ae, inc_bad, si)

    def test_missing_si_column_raises(self):
        ae, inc, si = _single_channel_fixtures()
        si_bad = si.drop(columns=["channels_affected"])
        with pytest.raises(ValueError, match="channels_affected"):
            investigate_incident(1, ae, inc, si_bad)

    def test_non_dataframe_raises_type_error(self):
        ae, inc, si = _single_channel_fixtures()
        with pytest.raises(TypeError, match="anomaly_events_df"):
            investigate_incident(1, {"not": "a df"}, inc, si)

    def test_non_dataframe_inc_raises_type_error(self):
        ae, inc, si = _single_channel_fixtures()
        with pytest.raises(TypeError, match="incidents_df"):
            investigate_incident(1, ae, None, si)

    def test_non_dataframe_si_raises_type_error(self):
        ae, inc, si = _single_channel_fixtures()
        with pytest.raises(TypeError, match="spacecraft_incidents_df"):
            investigate_incident(1, ae, inc, [1, 2, 3])


# ---------------------------------------------------------------------------
# 5. All pipeline stages invoked correctly
# ---------------------------------------------------------------------------

class TestPipelineInvocation:
    def test_characteriser_called(self):
        ae, inc, si = _single_channel_fixtures()
        with patch("member2.investigator.characteriser.get_incident_characterisation",
                   wraps=__import__("member2.characteriser", fromlist=["get_incident_characterisation"]).get_incident_characterisation) as mock_char:
            investigate_incident(1, ae, inc, si)
            mock_char.assert_called_once()
            call_kwargs = mock_char.call_args
            assert call_kwargs[1]["spacecraft_incident_id"] == 1 or call_kwargs[0][0] == 1

    def test_scorer_called(self):
        ae, inc, si = _single_channel_fixtures()
        with patch("member2.investigator.scorer.score_incident",
                   wraps=__import__("member2.scorer", fromlist=["score_incident"]).score_incident) as mock_score:
            investigate_incident(1, ae, inc, si)
            mock_score.assert_called_once()

    def test_hypothesis_called(self):
        ae, inc, si = _single_channel_fixtures()
        with patch("member2.investigator.hypothesis.build_hypothesis",
                   wraps=__import__("member2.hypothesis", fromlist=["build_hypothesis"]).build_hypothesis) as mock_hyp:
            investigate_incident(1, ae, inc, si)
            mock_hyp.assert_called_once()

    def test_evidence_graph_called(self):
        ae, inc, si = _single_channel_fixtures()
        with patch("member2.investigator.evidence_graph.build_evidence_graph",
                   wraps=__import__("member2.evidence_graph", fromlist=["build_evidence_graph"]).build_evidence_graph) as mock_eg:
            investigate_incident(1, ae, inc, si)
            mock_eg.assert_called_once()

    def test_actions_called(self):
        ae, inc, si = _single_channel_fixtures()
        with patch("member2.investigator.actions.generate_actions",
                   wraps=__import__("member2.actions", fromlist=["generate_actions"]).generate_actions) as mock_act:
            investigate_incident(1, ae, inc, si)
            mock_act.assert_called_once()

    def test_pipeline_order_characteriser_before_scorer(self):
        """Verify characteriser runs before scorer by checking scorer receives char_dict output."""
        ae, inc, si = _single_channel_fixtures()
        call_log: list[str] = []

        import member2.characteriser as _char_mod
        import member2.scorer as _score_mod

        orig_char = _char_mod.get_incident_characterisation
        orig_score = _score_mod.score_incident

        def _wrap_char(*a, **kw):
            call_log.append("characteriser")
            return orig_char(*a, **kw)

        def _wrap_score(*a, **kw):
            call_log.append("scorer")
            return orig_score(*a, **kw)

        with patch("member2.investigator.characteriser.get_incident_characterisation", side_effect=_wrap_char), \
             patch("member2.investigator.scorer.score_incident", side_effect=_wrap_score):
            investigate_incident(1, ae, inc, si)

        assert call_log.index("characteriser") < call_log.index("scorer")


# ---------------------------------------------------------------------------
# 6. Final report structure
# ---------------------------------------------------------------------------

class TestFinalReportStructure:
    def setup_method(self):
        ae, inc, si = _single_channel_fixtures()
        self.report = investigate_incident(1, ae, inc, si)
        self.inv = self.report.investigations[0]

    def test_schema_version(self):
        assert self.report.schema_version == "2.0"

    def test_generated_at_utc(self):
        assert self.report.generated_at.tzinfo is not None

    def test_source_files_present(self):
        assert "anomaly_events" in self.report.source_files
        assert "incidents" in self.report.source_files
        assert "spacecraft_incidents" in self.report.source_files

    def test_dataset_stats_present(self):
        ds = self.report.dataset_stats
        assert ds.total_spacecraft_incidents >= 1
        assert ds.total_channel_incidents >= 1
        assert ds.total_anomaly_events >= 1

    def test_investigation_id_format(self):
        # Fix 5: stable ID format is INV-{sid}
        assert self.inv.investigation_id == "INV-1"

    def test_generated_at_on_investigation(self):
        assert self.inv.generated_at.tzinfo is not None

    def test_persistence_class_valid(self):
        assert self.inv.persistence_class.value in {"SHORT", "MEDIUM", "LONG", "EXTENDED"}

    def test_significance_score_range(self):
        assert 0.0 <= self.inv.significance_score <= 100.0

    def test_severity_score_range(self):
        assert 0.0 <= self.inv.severity_score <= 10.0

    def test_investigation_confidence_range(self):
        assert 0.0 <= self.inv.investigation_confidence <= 1.0

    def test_evidence_graph_is_evidence_graph(self):
        assert isinstance(self.inv.evidence_graph, EvidenceGraph)

    def test_mission_impact_level_valid(self):
        assert self.inv.mission_impact_level in list(MissionImpactLevel)

    def test_scientific_note_present(self):
        assert self.inv.scientific_note == SCIENTIFIC_NOTE

    def test_channel_incident_ids_present(self):
        assert isinstance(self.inv.channel_incident_ids, list)
        assert len(self.inv.channel_incident_ids) >= 1


# ---------------------------------------------------------------------------
# 7. Score propagation
# ---------------------------------------------------------------------------

class TestScorePropagation:
    def test_significance_score_propagated(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert math.isfinite(inv.significance_score)
        assert inv.significance_score > 0.0

    def test_severity_score_propagated(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert math.isfinite(inv.severity_score)

    def test_confidence_propagated(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert math.isfinite(inv.investigation_confidence)

    def test_significance_components_propagated(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert isinstance(inv.significance_components, dict)
        assert len(inv.significance_components) > 0

    def test_severity_components_propagated(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert isinstance(inv.severity_components, dict)
        assert len(inv.severity_components) > 0

    def test_confidence_components_propagated(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert isinstance(inv.confidence_components, dict)
        assert len(inv.confidence_components) > 0

    def test_mission_impact_consistent_with_severity(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        # LOW severity should not produce CRITICAL impact
        if inv.severity_score < 3.0:
            assert inv.mission_impact_level == MissionImpactLevel.LOW


# ---------------------------------------------------------------------------
# 8. Hypothesis propagation
# ---------------------------------------------------------------------------

class TestHypothesisPropagation:
    def test_hypothesis_statements_present(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert isinstance(inv.hypothesis_statements, list)
        assert len(inv.hypothesis_statements) > 0

    def test_hypothesis_basis_present(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert isinstance(inv.hypothesis_basis, list)
        assert len(inv.hypothesis_basis) > 0

    def test_single_channel_has_single_channel_hypothesis(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        # single channel → "single_channel" hypothesis type in statements
        combined = " ".join(inv.hypothesis_statements).lower()
        assert "single" in combined or "ch_a" in combined.lower()

    def test_multi_channel_hypothesis_contains_both_channels(self):
        ae, inc, si = _multi_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        combined = " ".join(inv.hypothesis_statements).lower()
        assert "ch_a" in combined or "ch_b" in combined


# ---------------------------------------------------------------------------
# 9. Evidence graph propagation
# ---------------------------------------------------------------------------

class TestEvidenceGraphPropagation:
    def test_evidence_graph_has_nodes(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert len(inv.evidence_graph.nodes) > 0

    def test_evidence_graph_has_edges(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert len(inv.evidence_graph.edges) > 0

    def test_incident_node_present(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        node_ids = [n.node_id for n in inv.evidence_graph.nodes]
        assert "incident:1" in node_ids

    def test_channel_node_present(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        node_ids = [n.node_id for n in inv.evidence_graph.nodes]
        assert "channel:CH_A" in node_ids

    def test_hypothesis_node_present(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        node_types = [n.node_type for n in inv.evidence_graph.nodes]
        assert "hypothesis" in node_types

    def test_no_causal_edge_relations(self):
        ae, inc, si = _multi_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        forbidden = {"causes", "caused_by", "causal", "responsible_for"}
        for edge in inv.evidence_graph.edges:
            assert edge.relation not in forbidden, f"Forbidden relation: {edge.relation}"

    def test_multi_channel_has_temporal_edges(self):
        ae, inc, si = _multi_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        relations = {e.relation for e in inv.evidence_graph.edges}
        assert "temporal_precedence" in relations or "temporal_overlap" in relations


# ---------------------------------------------------------------------------
# 10. Actions propagation
# ---------------------------------------------------------------------------

class TestActionsPropagation:
    def test_recommended_actions_present(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert isinstance(inv.recommended_actions, list)
        assert len(inv.recommended_actions) > 0

    def test_actions_are_strings(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        for action in inv.recommended_actions:
            assert isinstance(action, str)

    def test_action_ids_in_strings(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        # Each action string should contain the action ID prefix "ACT-"
        assert any("ACT-" in a for a in inv.recommended_actions)

    def test_review_initial_channel_always_present(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        combined = " ".join(inv.recommended_actions).lower()
        assert "review initial" in combined or "initial anomaly channel" in combined or "ch_a" in combined

    def test_multi_channel_has_temporal_action(self):
        ae, inc, si = _multi_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        combined = " ".join(inv.recommended_actions).lower()
        assert "temporal" in combined or "sequence" in combined


# ---------------------------------------------------------------------------
# 11. Traceability
# ---------------------------------------------------------------------------

class TestTraceability:
    def test_channel_incident_ids_match_inc_df(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert "INC_1" in inv.channel_incident_ids

    def test_channels_affected_match_si_df(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert inv.channels_affected == ["CH_A"]

    def test_peak_score_traceable_to_events(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        # all events have anomaly_score=0.8 → peak should be 0.8
        assert abs(inv.peak_anomaly_score - 0.8) < 1e-6

    def test_mean_score_traceable_to_events(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert abs(inv.mean_anomaly_score - 0.8) < 1e-6

    def test_mission_impact_basis_not_empty(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert len(inv.mission_impact_basis) > 0

    def test_severity_rules_applied_is_list(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert isinstance(inv.severity_rules_applied, list)


# ---------------------------------------------------------------------------
# 12. Deterministic output
# ---------------------------------------------------------------------------

class TestDeterministicOutput:
    def test_same_input_same_scores(self):
        ae, inc, si = _single_channel_fixtures()
        r1 = investigate_incident(1, ae, inc, si)
        r2 = investigate_incident(1, ae, inc, si)
        inv1 = r1.investigations[0]
        inv2 = r2.investigations[0]
        assert inv1.significance_score == inv2.significance_score
        assert inv1.severity_score == inv2.severity_score
        assert inv1.investigation_confidence == inv2.investigation_confidence

    def test_same_input_same_hypothesis_statements(self):
        ae, inc, si = _single_channel_fixtures()
        r1 = investigate_incident(1, ae, inc, si)
        r2 = investigate_incident(1, ae, inc, si)
        assert r1.investigations[0].hypothesis_statements == r2.investigations[0].hypothesis_statements

    def test_same_input_same_graph_structure(self):
        ae, inc, si = _single_channel_fixtures()
        r1 = investigate_incident(1, ae, inc, si)
        r2 = investigate_incident(1, ae, inc, si)
        ids1 = sorted(n.node_id for n in r1.investigations[0].evidence_graph.nodes)
        ids2 = sorted(n.node_id for n in r2.investigations[0].evidence_graph.nodes)
        assert ids1 == ids2

    def test_same_input_same_channels_affected(self):
        ae, inc, si = _single_channel_fixtures()
        r1 = investigate_incident(1, ae, inc, si)
        r2 = investigate_incident(1, ae, inc, si)
        assert r1.investigations[0].channels_affected == r2.investigations[0].channels_affected

    def test_different_incident_different_report(self):
        ae, inc, si = _single_channel_fixtures()
        # Add a second incident
        ae2 = _make_ae_df("CH_X", 9, 2, 0.4)
        inc2 = _make_inc_df("INC_2", "CH_X", 9, 2, 50.0, 2, 0.4, 0.3)
        si2 = _make_si_df(2, ["CH_X"], duration_sec=50.0, n_events_total=2, peak=0.4, mean=0.3, end_offset_sec=50)
        ae_all = pd.concat([ae, ae2], ignore_index=True)
        inc_all = pd.concat([inc, inc2], ignore_index=True)
        si_all = pd.concat([si, si2], ignore_index=True)
        r1 = investigate_incident(1, ae_all, inc_all, si_all)
        r2 = investigate_incident(2, ae_all, inc_all, si_all)
        assert r1.investigations[0].spacecraft_incident_id == 1
        assert r2.investigations[0].spacecraft_incident_id == 2
        assert r1.investigations[0].significance_score != r2.investigations[0].significance_score


# ---------------------------------------------------------------------------
# 13. Scientific caveat preserved
# ---------------------------------------------------------------------------

class TestScientificCaveat:
    def test_scientific_note_is_constant(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        assert SCIENTIFIC_NOTE in inv.scientific_note

    def test_scientific_caveat_in_hypothesis_basis(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        combined = " ".join(inv.hypothesis_basis).lower()
        assert "causality" in combined or "temporal correlation" in combined

    def test_mission_impact_basis_contains_caveat(self):
        ae, inc, si = _single_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        combined = " ".join(inv.mission_impact_basis).lower()
        assert "telemetry" in combined or "physical" in combined


# ---------------------------------------------------------------------------
# 14. No causal terminology
# ---------------------------------------------------------------------------

class TestNoCausalTerminology:
    _CAUSAL_TERMS = [
        "caused by",
        "root cause",
        "caused the",
        "is responsible for",
        "triggered by",  # allowed in action rationale context
    ]
    # We only check fields that are purely investigator-assembled
    _CAUSAL_STRICT = [
        "caused by",
        "root cause",
    ]

    def _get_all_text(self, inv: Investigation) -> str:
        parts = [
            inv.scientific_note,
            " ".join(inv.hypothesis_statements),
            " ".join(inv.hypothesis_basis),
            " ".join(inv.mission_impact_basis),
        ]
        for rel in inv.channel_temporal_relationships:
            parts.append(str(rel))
        return " ".join(parts).lower()

    def test_no_caused_by_in_core_fields(self):
        ae, inc, si = _multi_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        text = self._get_all_text(inv)
        for term in self._CAUSAL_STRICT:
            assert term not in text, f"Found causal term: '{term}'"

    def test_no_root_cause_in_core_fields(self):
        ae, inc, si = _multi_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        text = self._get_all_text(inv)
        assert "root cause" not in text

    def test_no_causal_edge_labels(self):
        ae, inc, si = _multi_channel_fixtures()
        report = investigate_incident(1, ae, inc, si)
        inv = report.investigations[0]
        for edge in inv.evidence_graph.edges:
            assert "caus" not in edge.relation.lower()
            assert "caus" not in edge.label.lower()


# ---------------------------------------------------------------------------
# 15. Real-data incident 988 integration
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not (_AE_CSV.exists() and _INC_CSV.exists() and _SI_CSV.exists()),
    reason="Real OPS-SAT-AD data files not found in data/",
)
class TestRealDataIncident988:
    """
    Integration test using the actual OPS-SAT spacecraft incident 988.

    Expected values (pre-computed from the full dataset):
        n_channels_affected       : 5
        n_temporal_pairs          : 10   (C(5,2) = 10)
        duplicate pairs           : 0
        significance_score        : 98.75
        severity_score            : 9.375
        investigation_confidence  : 0.7879
    """

    @pytest.fixture()
    def real_report(self) -> InvestigationReport:
        from member2.loaders import (
            load_anomaly_events_csv,
            load_incidents_csv,
            load_spacecraft_incidents_csv,
        )
        ae = load_anomaly_events_csv(_AE_CSV)
        inc = load_incidents_csv(_INC_CSV)
        si = load_spacecraft_incidents_csv(_SI_CSV)
        return investigate_incident(988, ae, inc, si)

    @pytest.fixture()
    def real_inv(self, real_report: InvestigationReport) -> Investigation:
        return real_report.investigations[0]

    def test_real_incident_id(self, real_inv: Investigation):
        assert real_inv.spacecraft_incident_id == 988

    def test_real_n_channels_affected(self, real_inv: Investigation):
        assert real_inv.n_channels_affected == 5

    def test_real_channels_affected(self, real_inv: Investigation):
        expected = {"CADC0872", "CADC0873", "CADC0874", "CADC0888", "CADC0894"}
        assert set(real_inv.channels_affected) == expected

    def test_real_n_temporal_pairs(self, real_inv: Investigation):
        # C(5,2) = 10 unique unordered pairs
        assert len(real_inv.channel_temporal_relationships) == 10

    def test_real_no_duplicate_pairs(self, real_inv: Investigation):
        rels = real_inv.channel_temporal_relationships
        seen: set[frozenset[str]] = set()
        duplicates: list = []
        for r in rels:
            key = frozenset({r["channel_a"], r["channel_b"]})
            if key in seen:
                duplicates.append(r)
            seen.add(key)
        assert len(duplicates) == 0, f"Duplicate pairs found: {duplicates}"

    def test_real_significance_score(self, real_inv: Investigation):
        assert abs(real_inv.significance_score - 98.75) < 0.01, (
            f"Expected ~98.75, got {real_inv.significance_score}"
        )

    def test_real_severity_score(self, real_inv: Investigation):
        assert abs(real_inv.severity_score - 9.375) < 0.01, (
            f"Expected ~9.375, got {real_inv.severity_score}"
        )

    def test_real_investigation_confidence(self, real_inv: Investigation):
        assert abs(real_inv.investigation_confidence - 0.7879) < 0.0001, (
            f"Expected ~0.7879, got {real_inv.investigation_confidence}"
        )

    def test_real_is_multi_channel(self, real_inv: Investigation):
        assert real_inv.is_multi_channel is True

    def test_real_hypothesis_type_multi_channel(self, real_inv: Investigation):
        # Multi-channel incident → hypothesis contains multi-channel summary
        combined = " ".join(real_inv.hypothesis_statements).lower()
        assert len(combined) > 0

    def test_real_evidence_graph_not_empty(self, real_inv: Investigation):
        assert len(real_inv.evidence_graph.nodes) > 0
        assert len(real_inv.evidence_graph.edges) > 0

    def test_real_incident_node_present(self, real_inv: Investigation):
        node_ids = [n.node_id for n in real_inv.evidence_graph.nodes]
        assert "incident:988" in node_ids

    def test_real_all_channel_nodes_present(self, real_inv: Investigation):
        expected_nodes = {
            "channel:CADC0872", "channel:CADC0873", "channel:CADC0874",
            "channel:CADC0888", "channel:CADC0894",
        }
        node_ids = set(n.node_id for n in real_inv.evidence_graph.nodes)
        for expected in expected_nodes:
            assert expected in node_ids, f"Missing node: {expected}"

    def test_real_hypothesis_node_present(self, real_inv: Investigation):
        node_ids = [n.node_id for n in real_inv.evidence_graph.nodes]
        assert any("hypothesis" in nid for nid in node_ids)

    def test_real_recommended_actions_present(self, real_inv: Investigation):
        assert len(real_inv.recommended_actions) > 0

    def test_real_scientific_note_preserved(self, real_inv: Investigation):
        assert real_inv.scientific_note == SCIENTIFIC_NOTE

    def test_real_no_causal_terminology(self, real_inv: Investigation):
        full_text = " ".join([
            real_inv.scientific_note,
            " ".join(real_inv.hypothesis_statements),
            " ".join(real_inv.hypothesis_basis),
        ]).lower()
        assert "root cause" not in full_text
        assert "caused by" not in full_text

    def test_real_report_serialises_to_json(self, real_report: InvestigationReport):
        json_str = real_report.model_dump_json()
        assert len(json_str) > 100
        assert '"spacecraft_incident_id": 988' in json_str or '"spacecraft_incident_id":988' in json_str

    def test_real_deterministic(self):
        """Same data must produce identical scores on two separate calls."""
        from member2.loaders import (
            load_anomaly_events_csv,
            load_incidents_csv,
            load_spacecraft_incidents_csv,
        )
        ae = load_anomaly_events_csv(_AE_CSV)
        inc = load_incidents_csv(_INC_CSV)
        si = load_spacecraft_incidents_csv(_SI_CSV)
        r1 = investigate_incident(988, ae, inc, si)
        r2 = investigate_incident(988, ae, inc, si)
        inv1 = r1.investigations[0]
        inv2 = r2.investigations[0]
        assert inv1.significance_score == inv2.significance_score
        assert inv1.severity_score == inv2.severity_score
        assert inv1.investigation_confidence == inv2.investigation_confidence
        assert inv1.channel_temporal_relationships == inv2.channel_temporal_relationships

    def test_real_hypothesis_propagated_correctly(self, real_inv: Investigation):
        """Hypothesis statements and basis must be non-empty and come from real data."""
        assert len(real_inv.hypothesis_statements) > 0
        assert len(real_inv.hypothesis_basis) > 0
        # The scientific caveat must appear in the basis
        combined = " ".join(real_inv.hypothesis_basis).lower()
        assert "causality" in combined or "temporal correlation" in combined

    def test_real_dataset_stats_correct(self, real_report: InvestigationReport):
        ds = real_report.dataset_stats
        assert ds.total_spacecraft_incidents > 0
        assert ds.total_channel_incidents > 0
        assert ds.total_anomaly_events > 0
        assert ds.multi_channel_count >= 1
        assert len(ds.channels_observed) > 0
