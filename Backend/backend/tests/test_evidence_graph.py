"""
member2/tests/test_evidence_graph.py
-------------------------------------
Unit tests for member2/evidence_graph.py.

Covers:
  1.  Single-channel incident — correct node/edge counts
  2.  Two-channel incident — correct node/edge counts
  3.  Five-channel incident — correct node/edge counts, all 10 relationships
  4.  No temporal relationships — graph still has all channel nodes
  5.  Overlapping relationships — temporal_overlap edges present
  6.  Non-overlapping relationships — no temporal_overlap edges
  7.  Duplicate prevention — identical nodes/edges not added twice
  8.  Deterministic output — same input → same graph twice
  9.  Hypothesis node — present, correct type, confidence preserved
 10.  Invalid input — missing required keys raise ValueError
 11.  No causal terminology — forbidden labels never appear in any edge
 12.  Correct node counts — incident(1) + channel(N) + hypothesis(1)
 13.  Correct edge counts — incident→channel(N) + temporal + channel→hyp(N) + incident→hyp(1)
 14.  Temporal edge attributes — gap_seconds, windows_overlap, precedence in label
 15.  Real incident 988 — end-to-end integration test reporting full statistics
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from member2.evidence_graph import (
    _FORBIDDEN_RELATIONS,
    build_evidence_graph,
)
from member2.output_schema import EvidenceGraph

# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

_EPOCH = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _ts(offset_sec: int = 0) -> str:
    return (_EPOCH + timedelta(seconds=offset_sec)).isoformat()


def _rel(ch_a: str, t_a: int, ch_b: str, t_b: int, overlap: bool = True) -> dict[str, Any]:
    """Build a temporal relationship dict matching characteriser output."""
    if t_b < t_a:
        ch_a, t_a, ch_b, t_b = ch_b, t_b, ch_a, t_a
    gap = float(t_b - t_a)
    return {
        "channel_a": ch_a,
        "channel_b": ch_b,
        "channel_a_start": _ts(t_a),
        "channel_b_start": _ts(t_b),
        "temporal_gap_sec": gap,
        "temporal_precedence": "simultaneous" if gap == 0.0 else "A_before_B",
        "windows_overlap": overlap,
    }


def _all_pairs_rels(
    channels_and_offsets: list[tuple[str, int]], overlap: bool = True
) -> list[dict]:
    """Generate all N*(N-1)/2 pair relationships."""
    rels = []
    items = sorted(channels_and_offsets, key=lambda x: (x[1], x[0]))
    for i, (ca, ta) in enumerate(items):
        for cb, tb in items[i + 1:]:
            rels.append(_rel(ca, ta, cb, tb, overlap=overlap))
    return rels


def _make_char(
    sid: int,
    channels: list[str],
    offsets: list[int],
    rels: list[dict],
    channel_incident_ids: list[str] | None = None,
) -> dict[str, Any]:
    activation_order = [ch for ch, _ in sorted(zip(channels, offsets), key=lambda x: (x[1], x[0]))]
    return {
        "spacecraft_incident_id": sid,
        "start_time": _ts(min(offsets)),
        "end_time": _ts(max(offsets) + 60),
        "duration_sec": float(max(offsets) - min(offsets) + 60),
        "n_channels_affected": len(channels),
        "channels_affected": sorted(channels),
        "channel_activation_order": activation_order,
        "is_multi_channel": len(channels) > 1,
        "n_events_total": len(channels) * 5,
        "event_density_per_min": float(len(channels)),
        "peak_anomaly_score": 0.95,
        "mean_anomaly_score": 0.75,
        "score_std": 0.05,
        "persistence_class": "SHORT",
        "segment_span": len(channels),
        "timeline": [],
        "channel_incident_ids": channel_incident_ids or [f"INC-{sid}-{c}" for c in channels],
        "channel_temporal_relationships": rels,
    }


def _make_scores(sig: float = 80.0, sev: float = 7.0, conf: float = 0.8) -> dict[str, Any]:
    return {
        "significance_score": sig,
        "severity_score": sev,
        "investigation_confidence": conf,
        "severity_label": "HIGH",
    }


def _make_hypothesis(
    sid: int,
    n_channels: int,
    hyp_type: str = "multi_channel",
    confidence: float = 0.9,
) -> dict[str, Any]:
    return {
        "hypothesis_id": f"HYP-{sid}",
        "hypothesis_type": hyp_type,
        "summary": "Test hypothesis summary.",
        "chain": [],
        "supporting_evidence": [],
        "hypothesis_confidence": confidence,
        "scientific_caveat": "Temporal correlation observed; physical causality not confirmed.",
        "observed_evidence": [f"{n_channels} channels affected."],
        "temporal_relationships": [],
        "n_corroborating_pairs": 0,
    }


def _count_edge_relations(graph: EvidenceGraph) -> dict[str, int]:
    counts: dict[str, int] = {}
    for edge in graph.edges:
        counts[edge.relation] = counts.get(edge.relation, 0) + 1
    return counts


def _count_node_types(graph: EvidenceGraph) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in graph.nodes:
        counts[node.node_type] = counts.get(node.node_type, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# 1. Single-channel incident
# ---------------------------------------------------------------------------

class TestSingleChannel:
    def _build(self) -> EvidenceGraph:
        char = _make_char(1, ["CH-A"], [0], [])
        scores = _make_scores()
        hyp = _make_hypothesis(1, 1, hyp_type="single_channel", confidence=0.0)
        return build_evidence_graph(char, scores, hyp)

    def test_node_count(self):
        graph = self._build()
        # incident(1) + channel(1) + hypothesis(1) = 3
        assert len(graph.nodes) == 3

    def test_node_types(self):
        graph = self._build()
        types = _count_node_types(graph)
        assert types["incident"] == 1
        assert types["channel"] == 1
        assert types["hypothesis"] == 1

    def test_no_temporal_edges(self):
        graph = self._build()
        rels = _count_edge_relations(graph)
        assert rels.get("temporal_precedence", 0) == 0
        assert rels.get("temporal_overlap", 0) == 0

    def test_affected_channel_edge_present(self):
        graph = self._build()
        rels = _count_edge_relations(graph)
        assert rels.get("affected_channel", 0) == 1

    def test_supports_hypothesis_edge_present(self):
        graph = self._build()
        rels = _count_edge_relations(graph)
        assert rels.get("supports_hypothesis", 0) == 1

    def test_has_hypothesis_edge_present(self):
        graph = self._build()
        rels = _count_edge_relations(graph)
        assert rels.get("has_hypothesis", 0) == 1

    def test_total_edge_count(self):
        graph = self._build()
        # affected_channel(1) + supports_hypothesis(1) + has_hypothesis(1) = 3
        assert len(graph.edges) == 3


# ---------------------------------------------------------------------------
# 2. Two-channel incident
# ---------------------------------------------------------------------------

class TestTwoChannel:
    def _build(self, overlap: bool = True) -> EvidenceGraph:
        channels = ["CH-A", "CH-B"]
        offsets = [0, 30]
        rels = _all_pairs_rels(list(zip(channels, offsets)), overlap=overlap)
        char = _make_char(2, channels, offsets, rels)
        scores = _make_scores()
        hyp = _make_hypothesis(2, 2, confidence=0.7)
        return build_evidence_graph(char, scores, hyp)

    def test_node_count(self):
        graph = self._build()
        assert len(graph.nodes) == 4  # incident + 2 channels + hypothesis

    def test_node_types(self):
        graph = self._build()
        types = _count_node_types(graph)
        assert types["incident"] == 1
        assert types["channel"] == 2
        assert types["hypothesis"] == 1

    def test_temporal_precedence_edge(self):
        graph = self._build(overlap=False)
        rels = _count_edge_relations(graph)
        assert rels.get("temporal_precedence", 0) == 1

    def test_temporal_overlap_edge_when_overlap(self):
        graph = self._build(overlap=True)
        rels = _count_edge_relations(graph)
        # 1 precedence + 1 overlap for the single pair
        assert rels.get("temporal_overlap", 0) == 1

    def test_no_temporal_overlap_when_no_overlap(self):
        graph = self._build(overlap=False)
        rels = _count_edge_relations(graph)
        assert rels.get("temporal_overlap", 0) == 0

    def test_channel_hypothesis_edges(self):
        graph = self._build()
        rels = _count_edge_relations(graph)
        assert rels.get("supports_hypothesis", 0) == 2

    def test_affected_channel_edges(self):
        graph = self._build()
        rels = _count_edge_relations(graph)
        assert rels.get("affected_channel", 0) == 2

    def test_has_hypothesis_edge(self):
        graph = self._build()
        rels = _count_edge_relations(graph)
        assert rels.get("has_hypothesis", 0) == 1


# ---------------------------------------------------------------------------
# 3. Five-channel incident — 10 unique temporal relationships
# ---------------------------------------------------------------------------

class TestFiveChannel:
    def _build(self, overlap: bool = True) -> EvidenceGraph:
        channels = ["CH-A", "CH-B", "CH-C", "CH-D", "CH-E"]
        offsets = [0, 10, 20, 30, 40]
        rels = _all_pairs_rels(list(zip(channels, offsets)), overlap=overlap)
        assert len(rels) == 10, f"Expected 10 pairs, got {len(rels)}"
        char = _make_char(988, channels, offsets, rels)
        scores = _make_scores()
        hyp = _make_hypothesis(988, 5, confidence=0.99)
        return build_evidence_graph(char, scores, hyp)

    def test_node_count(self):
        graph = self._build()
        assert len(graph.nodes) == 7  # 1 incident + 5 channels + 1 hypothesis

    def test_channel_node_count(self):
        graph = self._build()
        types = _count_node_types(graph)
        assert types["channel"] == 5

    def test_all_ten_relationships_representable(self):
        graph = self._build(overlap=False)
        rels = _count_edge_relations(graph)
        # 10 temporal_precedence edges (one per pair, no overlap)
        assert rels.get("temporal_precedence", 0) == 10

    def test_all_ten_relationships_with_overlap(self):
        graph = self._build(overlap=True)
        rels = _count_edge_relations(graph)
        # 10 temporal_precedence + 10 temporal_overlap
        assert rels.get("temporal_precedence", 0) == 10
        assert rels.get("temporal_overlap", 0) == 10

    def test_channel_hypothesis_edges(self):
        graph = self._build()
        rels = _count_edge_relations(graph)
        assert rels.get("supports_hypothesis", 0) == 5

    def test_affected_channel_edges(self):
        graph = self._build()
        rels = _count_edge_relations(graph)
        assert rels.get("affected_channel", 0) == 5

    def test_has_hypothesis_edge(self):
        graph = self._build()
        rels = _count_edge_relations(graph)
        assert rels.get("has_hypothesis", 0) == 1


# ---------------------------------------------------------------------------
# 4. No temporal relationships
# ---------------------------------------------------------------------------

class TestNoTemporalRelationships:
    def _build(self) -> EvidenceGraph:
        channels = ["CH-A", "CH-B", "CH-C"]
        offsets = [0, 15, 30]
        char = _make_char(3, channels, offsets, rels=[])
        scores = _make_scores()
        hyp = _make_hypothesis(3, 3, hyp_type="insufficient_evidence", confidence=0.0)
        return build_evidence_graph(char, scores, hyp)

    def test_channel_nodes_present(self):
        graph = self._build()
        types = _count_node_types(graph)
        assert types["channel"] == 3

    def test_no_temporal_edges(self):
        graph = self._build()
        rels = _count_edge_relations(graph)
        assert rels.get("temporal_precedence", 0) == 0
        assert rels.get("temporal_overlap", 0) == 0

    def test_other_edges_still_present(self):
        graph = self._build()
        rels = _count_edge_relations(graph)
        assert rels.get("affected_channel", 0) == 3
        assert rels.get("supports_hypothesis", 0) == 3
        assert rels.get("has_hypothesis", 0) == 1


# ---------------------------------------------------------------------------
# 5. Overlapping relationships
# ---------------------------------------------------------------------------

class TestOverlappingRelationships:
    def test_temporal_overlap_edge_added(self):
        channels = ["CH-A", "CH-B"]
        offsets = [0, 10]
        rels = [_rel("CH-A", 0, "CH-B", 10, overlap=True)]
        char = _make_char(4, channels, offsets, rels)
        graph = build_evidence_graph(char, {}, _make_hypothesis(4, 2, confidence=0.5))
        edge_rels = _count_edge_relations(graph)
        assert edge_rels.get("temporal_overlap", 0) >= 1

    def test_overlap_edge_label_contains_gap(self):
        channels = ["CH-A", "CH-B"]
        offsets = [0, 20]
        rels = [_rel("CH-A", 0, "CH-B", 20, overlap=True)]
        char = _make_char(5, channels, offsets, rels)
        graph = build_evidence_graph(char, {}, _make_hypothesis(5, 2))
        overlap_edges = [e for e in graph.edges if e.relation == "temporal_overlap"]
        assert len(overlap_edges) == 1
        assert "20.0" in overlap_edges[0].label


# ---------------------------------------------------------------------------
# 6. Non-overlapping relationships
# ---------------------------------------------------------------------------

class TestNonOverlappingRelationships:
    def test_no_overlap_edge_when_overlap_false(self):
        channels = ["CH-A", "CH-B"]
        offsets = [0, 400]
        rels = [_rel("CH-A", 0, "CH-B", 400, overlap=False)]
        char = _make_char(6, channels, offsets, rels)
        graph = build_evidence_graph(char, {}, _make_hypothesis(6, 2))
        edge_rels = _count_edge_relations(graph)
        assert edge_rels.get("temporal_overlap", 0) == 0

    def test_precedence_edge_still_present(self):
        channels = ["CH-A", "CH-B"]
        offsets = [0, 400]
        rels = [_rel("CH-A", 0, "CH-B", 400, overlap=False)]
        char = _make_char(7, channels, offsets, rels)
        graph = build_evidence_graph(char, {}, _make_hypothesis(7, 2))
        edge_rels = _count_edge_relations(graph)
        assert edge_rels.get("temporal_precedence", 0) == 1


# ---------------------------------------------------------------------------
# 7. Duplicate prevention
# ---------------------------------------------------------------------------

class TestDuplicatePrevention:
    def test_no_duplicate_nodes(self):
        channels = ["CH-A", "CH-B"]
        offsets = [0, 10]
        rels = _all_pairs_rels(list(zip(channels, offsets)))
        char = _make_char(8, channels, offsets, rels)
        graph = build_evidence_graph(char, _make_scores(), _make_hypothesis(8, 2))

        node_ids = [n.node_id for n in graph.nodes]
        assert len(node_ids) == len(set(node_ids)), "Duplicate node_ids found"

    def test_no_duplicate_edges(self):
        channels = ["CH-A", "CH-B", "CH-C"]
        offsets = [0, 10, 20]
        rels = _all_pairs_rels(list(zip(channels, offsets)))
        char = _make_char(9, channels, offsets, rels)
        graph = build_evidence_graph(char, _make_scores(), _make_hypothesis(9, 3))

        edge_keys = [(e.source, e.target, e.relation) for e in graph.edges]
        assert len(edge_keys) == len(set(edge_keys)), "Duplicate (source,target,relation) found"

    def test_duplicate_rels_in_input_not_doubled(self):
        """If the same relationship appears twice in input, only one edge is created."""
        rel = _rel("CH-A", 0, "CH-B", 10, overlap=False)
        rels = [rel, rel]  # Intentional duplicate
        char = _make_char(10, ["CH-A", "CH-B"], [0, 10], rels)
        graph = build_evidence_graph(char, {}, _make_hypothesis(10, 2))
        prec_edges = [e for e in graph.edges if e.relation == "temporal_precedence"]
        assert len(prec_edges) == 1


# ---------------------------------------------------------------------------
# 8. Deterministic output
# ---------------------------------------------------------------------------

class TestDeterministicOutput:
    def test_same_input_same_graph(self):
        channels = ["CH-B", "CH-A", "CH-D", "CH-C"]
        offsets = [5, 0, 15, 10]
        rels = _all_pairs_rels(list(zip(channels, offsets)))
        char = _make_char(11, channels, offsets, rels)
        scores = _make_scores()
        hyp = _make_hypothesis(11, 4)

        g1 = build_evidence_graph(char, scores, hyp)
        g2 = build_evidence_graph(char, scores, hyp)

        assert [n.node_id for n in g1.nodes] == [n.node_id for n in g2.nodes]
        assert [(e.source, e.target, e.relation) for e in g1.edges] == \
               [(e.source, e.target, e.relation) for e in g2.edges]

    def test_node_order_is_sorted(self):
        """Channel nodes should appear in sorted(channels_affected) order."""
        channels = ["CH-Z", "CH-A", "CH-M"]
        offsets = [0, 10, 5]
        rels = _all_pairs_rels(list(zip(channels, offsets)))
        char = _make_char(12, channels, offsets, rels)
        graph = build_evidence_graph(char, {}, _make_hypothesis(12, 3))

        channel_nodes = [n for n in graph.nodes if n.node_type == "channel"]
        channel_names = [n.attributes["channel"] for n in channel_nodes]
        assert channel_names == sorted(channel_names)


# ---------------------------------------------------------------------------
# 9. Hypothesis node
# ---------------------------------------------------------------------------

class TestHypothesisNode:
    def _build(self) -> EvidenceGraph:
        channels = ["CH-A", "CH-B"]
        offsets = [0, 20]
        rels = _all_pairs_rels(list(zip(channels, offsets)))
        char = _make_char(13, channels, offsets, rels)
        hyp = _make_hypothesis(13, 2, confidence=0.85)
        return build_evidence_graph(char, _make_scores(), hyp)

    def test_hypothesis_node_exists(self):
        graph = self._build()
        hyp_nodes = [n for n in graph.nodes if n.node_type == "hypothesis"]
        assert len(hyp_nodes) == 1

    def test_hypothesis_node_id_format(self):
        graph = self._build()
        hyp_nodes = [n for n in graph.nodes if n.node_type == "hypothesis"]
        assert hyp_nodes[0].node_id.startswith("hypothesis:HYP-")

    def test_hypothesis_confidence_preserved(self):
        graph = self._build()
        hyp_nodes = [n for n in graph.nodes if n.node_type == "hypothesis"]
        assert abs(hyp_nodes[0].attributes["hypothesis_confidence"] - 0.85) < 1e-9

    def test_hypothesis_type_preserved(self):
        graph = self._build()
        hyp_nodes = [n for n in graph.nodes if n.node_type == "hypothesis"]
        assert hyp_nodes[0].attributes["hypothesis_type"] == "multi_channel"

    def test_scientific_caveat_in_hypothesis_node(self):
        graph = self._build()
        hyp_nodes = [n for n in graph.nodes if n.node_type == "hypothesis"]
        caveat = hyp_nodes[0].attributes.get("scientific_caveat", "")
        assert "causality" in caveat.lower() or "temporal correlation" in caveat.lower()


# ---------------------------------------------------------------------------
# 10. Invalid input
# ---------------------------------------------------------------------------

class TestInvalidInput:
    def test_missing_spacecraft_incident_id_raises(self):
        bad_char = {"channels_affected": ["CH-A"]}
        with pytest.raises(ValueError, match="spacecraft_incident_id"):
            build_evidence_graph(bad_char, {}, {"hypothesis_id": "HYP-1"})

    def test_missing_channels_affected_raises(self):
        bad_char = {"spacecraft_incident_id": 1}
        with pytest.raises(ValueError, match="channels_affected"):
            build_evidence_graph(bad_char, {}, {"hypothesis_id": "HYP-1"})

    def test_missing_hypothesis_id_raises(self):
        char = _make_char(14, ["CH-A"], [0], [])
        with pytest.raises(ValueError, match="hypothesis_id"):
            build_evidence_graph(char, {}, {"hypothesis_type": "single_channel"})

    def test_non_dict_char_dict_raises(self):
        with pytest.raises(ValueError):
            build_evidence_graph("not a dict", {}, {"hypothesis_id": "HYP-1"})

    def test_non_dict_hypothesis_dict_raises(self):
        char = _make_char(15, ["CH-A"], [0], [])
        with pytest.raises(ValueError):
            build_evidence_graph(char, {}, "not a dict")

    def test_empty_scores_dict_accepted(self):
        char = _make_char(16, ["CH-A"], [0], [])
        hyp = _make_hypothesis(16, 1, hyp_type="single_channel", confidence=0.0)
        # Should not raise
        graph = build_evidence_graph(char, {}, hyp)
        assert len(graph.nodes) > 0

    def test_none_scores_dict_accepted(self):
        char = _make_char(17, ["CH-A"], [0], [])
        hyp = _make_hypothesis(17, 1, hyp_type="single_channel", confidence=0.0)
        graph = build_evidence_graph(char, None, hyp)  # type: ignore[arg-type]
        assert len(graph.nodes) > 0


# ---------------------------------------------------------------------------
# 11. No causal terminology in any edge
# ---------------------------------------------------------------------------

class TestNoCausalTerminology:
    _CAUSAL_PATTERN = re.compile(
        r"\b(caus(e|ed|es|al)|responsible_for|caused_by)\b", re.IGNORECASE
    )

    def _check_graph(self, graph: EvidenceGraph) -> None:
        for edge in graph.edges:
            assert edge.relation not in _FORBIDDEN_RELATIONS, (
                f"Forbidden relation '{edge.relation}' found in edge "
                f"{edge.source} → {edge.target}"
            )
            assert not self._CAUSAL_PATTERN.search(edge.relation), (
                f"Causal language in relation: {edge.relation}"
            )
            assert not self._CAUSAL_PATTERN.search(edge.label), (
                f"Causal language in edge label: {edge.label}"
            )

    def test_single_channel_no_causal(self):
        char = _make_char(18, ["CH-A"], [0], [])
        graph = build_evidence_graph(char, {}, _make_hypothesis(18, 1, hyp_type="single_channel", confidence=0.0))
        self._check_graph(graph)

    def test_five_channel_no_causal(self):
        channels = ["CH-A", "CH-B", "CH-C", "CH-D", "CH-E"]
        offsets = [0, 10, 20, 30, 40]
        rels = _all_pairs_rels(list(zip(channels, offsets)))
        char = _make_char(19, channels, offsets, rels)
        graph = build_evidence_graph(char, _make_scores(), _make_hypothesis(19, 5))
        self._check_graph(graph)

    def test_forbidden_relations_set_is_complete(self):
        """Confirm the constant contains the expected forbidden terms."""
        assert "causes" in _FORBIDDEN_RELATIONS
        assert "caused_by" in _FORBIDDEN_RELATIONS
        assert "causal" in _FORBIDDEN_RELATIONS
        assert "responsible_for" in _FORBIDDEN_RELATIONS


# ---------------------------------------------------------------------------
# 12 + 13. Node and edge count formulae
# ---------------------------------------------------------------------------

class TestCountFormulae:
    @pytest.mark.parametrize("n_channels,n_rels,overlap", [
        (1, 0, False),
        (2, 1, False),
        (2, 1, True),
        (3, 3, False),
        (3, 3, True),
        (5, 10, False),
        (5, 10, True),
    ])
    def test_node_count_formula(self, n_channels, n_rels, overlap):
        channels = [f"CH-{chr(65+i)}" for i in range(n_channels)]
        offsets = list(range(0, n_channels * 10, 10))
        rels = _all_pairs_rels(list(zip(channels, offsets)), overlap=overlap)[:n_rels]
        char = _make_char(20 + n_channels, channels, offsets, rels)
        graph = build_evidence_graph(char, {}, _make_hypothesis(20 + n_channels, n_channels))
        # Always: 1 incident + n_channels + 1 hypothesis
        assert len(graph.nodes) == 1 + n_channels + 1

    @pytest.mark.parametrize("n_channels,n_rels,overlap,expected_temporal", [
        (1, 0, False, 0),      # no temporal at all
        (2, 1, False, 1),      # 1 precedence only
        (2, 1, True,  2),      # 1 precedence + 1 overlap
        (3, 3, False, 3),      # 3 precedence
        (3, 3, True,  6),      # 3 precedence + 3 overlap
    ])
    def test_edge_count_formula(self, n_channels, n_rels, overlap, expected_temporal):
        channels = [f"CH-{chr(65+i)}" for i in range(n_channels)]
        offsets = list(range(0, n_channels * 10, 10))
        rels = _all_pairs_rels(list(zip(channels, offsets)), overlap=overlap)[:n_rels]
        char = _make_char(30 + n_channels, channels, offsets, rels)
        graph = build_evidence_graph(char, {}, _make_hypothesis(30 + n_channels, n_channels))

        edge_rels = _count_edge_relations(graph)
        assert edge_rels.get("affected_channel", 0) == n_channels
        assert edge_rels.get("supports_hypothesis", 0) == n_channels
        assert edge_rels.get("has_hypothesis", 0) == 1

        temporal_count = (
            edge_rels.get("temporal_precedence", 0)
            + edge_rels.get("temporal_overlap", 0)
        )
        assert temporal_count == expected_temporal


# ---------------------------------------------------------------------------
# 14. Temporal edge attributes
# ---------------------------------------------------------------------------

class TestTemporalEdgeAttributes:
    def test_gap_in_label(self):
        rels = [_rel("CH-A", 0, "CH-B", 45, overlap=False)]
        char = _make_char(40, ["CH-A", "CH-B"], [0, 45], rels)
        graph = build_evidence_graph(char, {}, _make_hypothesis(40, 2))
        prec_edges = [e for e in graph.edges if e.relation == "temporal_precedence"]
        assert len(prec_edges) == 1
        assert "45.0" in prec_edges[0].label

    def test_overlap_in_label(self):
        rels = [_rel("CH-A", 0, "CH-B", 10, overlap=True)]
        char = _make_char(41, ["CH-A", "CH-B"], [0, 10], rels)
        graph = build_evidence_graph(char, {}, _make_hypothesis(41, 2))
        prec_edges = [e for e in graph.edges if e.relation == "temporal_precedence"]
        assert "overlap=True" in prec_edges[0].label

    def test_edge_weight_is_normalised(self):
        """Edge weight = 1 - gap/3600, clipped to [0,1]."""
        rels = [_rel("CH-A", 0, "CH-B", 360, overlap=False)]  # 360s gap → weight 0.9
        char = _make_char(42, ["CH-A", "CH-B"], [0, 360], rels)
        graph = build_evidence_graph(char, {}, _make_hypothesis(42, 2))
        prec_edges = [e for e in graph.edges if e.relation == "temporal_precedence"]
        assert len(prec_edges) == 1
        assert abs(prec_edges[0].weight - 0.9) < 1e-6

    def test_simultaneous_creates_overlap_edge(self):
        rels = [_rel("CH-A", 0, "CH-B", 0, overlap=True)]
        char = _make_char(43, ["CH-A", "CH-B"], [0, 0], rels)
        graph = build_evidence_graph(char, {}, _make_hypothesis(43, 2))
        overlap_edges = [e for e in graph.edges if e.relation == "temporal_overlap"]
        prec_edges = [e for e in graph.edges if e.relation == "temporal_precedence"]
        assert len(overlap_edges) == 1
        assert len(prec_edges) == 0  # simultaneous → no precedence edge


# ---------------------------------------------------------------------------
# 15. Real incident 988 — end-to-end integration
# ---------------------------------------------------------------------------

class TestRealIncident988:
    """
    Integration test using real OPS-SAT-AD CSV data for spacecraft incident 988.

    Expected from prior pipeline validation:
      - 5 channels
      - 10 unique temporal pairs
      - 4 chronological chain links
      - significance 98.75
      - severity 9.375
      - investigation confidence 0.7879
      - hypothesis confidence 0.9981
    """

    # Class-level cache populated by setup_class
    _graph: EvidenceGraph
    _char: dict
    _scores: dict
    _hyp: dict
    _skipped: bool = False

    @classmethod
    def setup_class(cls) -> None:
        from pathlib import Path
        data_dir = Path("data")
        ae_path = data_dir / "anomaly_events.csv"
        inc_path = data_dir / "incidents.csv"
        si_path = data_dir / "spacecraft_incidents.csv"

        if not ae_path.exists() or not inc_path.exists() or not si_path.exists():
            cls._skipped = True
            return

        from member2.loaders import (
            load_anomaly_events_csv,
            load_incidents_csv,
            load_spacecraft_incidents_csv,
        )
        from member2.characteriser import get_incident_characterisation
        from member2.scorer import score_incident
        from member2.hypothesis import build_hypothesis

        ae_df = load_anomaly_events_csv(ae_path)
        inc_df = load_incidents_csv(inc_path)
        si_df = load_spacecraft_incidents_csv(si_path)

        cls._char = get_incident_characterisation(988, ae_df, inc_df, si_df)
        cls._scores = score_incident(cls._char)
        cls._hyp = build_hypothesis(cls._char, cls._scores)
        cls._graph = build_evidence_graph(cls._char, cls._scores, cls._hyp)

    def _require_data(self) -> None:
        if self.__class__._skipped:
            pytest.skip("Real CSV data files not available")

    def test_node_count(self):
        self._require_data()
        n_ch = self._char["n_channels_affected"]
        expected = 1 + n_ch + 1
        assert len(self._graph.nodes) == expected, (
            f"Expected {expected} nodes (1 incident + {n_ch} channels + 1 hypothesis), "
            f"got {len(self._graph.nodes)}"
        )

    def test_five_channels(self):
        self._require_data()
        types = _count_node_types(self._graph)
        assert types["channel"] == 5, f"Expected 5 channel nodes, got {types.get('channel')}"

    def test_ten_temporal_pairs(self):
        self._require_data()
        n_rels = len(self._char["channel_temporal_relationships"])
        assert n_rels == 10, f"Expected 10 temporal relationships, got {n_rels}"

    def test_all_temporal_edges_present(self):
        self._require_data()
        edge_rels = _count_edge_relations(self._graph)
        temporal_count = (
            edge_rels.get("temporal_precedence", 0)
            + edge_rels.get("temporal_overlap", 0)
        )
        assert temporal_count >= 10, (
            f"Expected at least 10 temporal edges, got {temporal_count}. "
            f"Edge distribution: {edge_rels}"
        )

    def test_no_duplicate_edges(self):
        self._require_data()
        edge_keys = [(e.source, e.target, e.relation) for e in self._graph.edges]
        assert len(edge_keys) == len(set(edge_keys)), "Duplicate edges found in incident 988 graph"

    def test_no_duplicate_nodes(self):
        self._require_data()
        node_ids = [n.node_id for n in self._graph.nodes]
        assert len(node_ids) == len(set(node_ids)), "Duplicate node_ids in incident 988 graph"

    def test_no_causal_terminology(self):
        self._require_data()
        causal_pattern = re.compile(
            r"\b(caus(e|ed|es|al)|responsible_for|caused_by)\b", re.IGNORECASE
        )
        for edge in self._graph.edges:
            assert edge.relation not in _FORBIDDEN_RELATIONS, (
                f"Forbidden relation: {edge.relation}"
            )
            assert not causal_pattern.search(edge.relation), (
                f"Causal language in relation: {edge.relation}"
            )

    def test_incident_node_has_severity_score(self):
        self._require_data()
        inc_nodes = [n for n in self._graph.nodes if n.node_type == "incident"]
        assert len(inc_nodes) == 1
        assert "severity_score" in inc_nodes[0].attributes

    def test_hypothesis_confidence_preserved(self):
        self._require_data()
        hyp_nodes = [n for n in self._graph.nodes if n.node_type == "hypothesis"]
        assert len(hyp_nodes) == 1
        stored = hyp_nodes[0].attributes["hypothesis_confidence"]
        expected = self._hyp["hypothesis_confidence"]
        assert abs(stored - expected) < 1e-9

    def test_graph_is_evidence_graph_instance(self):
        self._require_data()
        assert isinstance(self._graph, EvidenceGraph)

    def test_print_statistics(self, capsys):
        """Print full graph statistics for incident 988 (not an assertion test)."""
        self._require_data()
        types = _count_node_types(self._graph)
        edge_rels = _count_edge_relations(self._graph)
        temporal_count = (
            edge_rels.get("temporal_precedence", 0)
            + edge_rels.get("temporal_overlap", 0)
        )
        edge_keys = [(e.source, e.target, e.relation) for e in self._graph.edges]
        duplicate_edges = len(edge_keys) - len(set(edge_keys))

        causal_pattern = re.compile(
            r"\b(caus(e|ed|es|al)|responsible_for|caused_by)\b", re.IGNORECASE
        )
        causal_found = [
            e.relation for e in self._graph.edges
            if causal_pattern.search(e.relation) or e.relation in _FORBIDDEN_RELATIONS
        ]

        print("\n" + "=" * 60)
        print("INCIDENT 988 EVIDENCE GRAPH STATISTICS")
        print("=" * 60)
        print(f"Total nodes        : {len(self._graph.nodes)}")
        for ntype, count in sorted(types.items()):
            print(f"  {ntype:<20}: {count}")
        print(f"Total edges        : {len(self._graph.edges)}")
        for rel, count in sorted(edge_rels.items()):
            print(f"  {rel:<30}: {count}")
        print(f"Temporal edges     : {temporal_count}")
        print(f"Duplicate edges    : {duplicate_edges}")
        print(f"Causal terminology : {causal_found if causal_found else 'NONE'}")
        print(f"hypothesis_confidence : {self._hyp['hypothesis_confidence']}")
        print(f"significance_score    : {self._scores.get('significance_score')}")
        print(f"severity_score        : {self._scores.get('severity_score')}")
        print(f"investigation_conf    : {self._scores.get('investigation_confidence')}")
        print("=" * 60)
        assert True
