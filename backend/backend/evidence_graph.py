"""
member2/evidence_graph.py
-------------------------
Evidence Graph Builder for Member 2 — Incident Investigation Engineer.

PURPOSE
-------
Convert the factual output of characteriser.py + scorer.py + hypothesis.py for
one spacecraft incident into a structured evidence graph that Member 3 can
directly visualise.

This module does NOT:
- Create a graph database
- Use NetworkX
- Duplicate channel pairs
- Claim physical causality

SCIENTIFIC RULE
---------------
All temporal edges are strictly observational.
The following labels are NEVER used:
    causes, caused_by, causal, responsible_for

Permitted relation labels:
    affected_channel       — incident links to a channel node
    temporal_precedence    — channel_a activated before channel_b
    temporal_overlap       — channel windows overlap / are proximate
    supports_hypothesis    — channel node supports the hypothesis
    has_hypothesis         — incident node references the hypothesis

PUBLIC API
----------
build_evidence_graph(char_dict, scores_dict, hypothesis_dict) → EvidenceGraph

Node types
----------
    incident    — the spacecraft-level incident
    channel     — one affected telemetry channel
    hypothesis  — the failure-chain hypothesis

Node attributes carry enough context for the UI to show:
    why a channel is involved, when it activated, which channels
    preceded / followed it, whether windows overlapped, severity /
    significance, confidence, and which hypothesis it supports.

Determinism guarantee
---------------------
Nodes and edges are added in a fixed, sorted order.  Duplicate nodes
(same node_id) and duplicate edges (same source / target / relation triple)
are silently discarded.
"""

from __future__ import annotations

from typing import Any

from member2.output_schema import EvidenceGraph, GraphEdge, GraphNode

# ---------------------------------------------------------------------------
# Forbidden relation labels — checked on every edge
# ---------------------------------------------------------------------------

_FORBIDDEN_RELATIONS: frozenset[str] = frozenset(
    {"causes", "caused_by", "causal", "responsible_for"}
)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _safe_float(val: Any, default: float = 0.0) -> float:
    """Return a finite float or *default*."""
    try:
        f = float(val)
        import math
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _make_node(node_id: str, node_type: str, attributes: dict[str, Any]) -> GraphNode:
    return GraphNode(node_id=node_id, node_type=node_type, attributes=attributes)


def _make_edge(
    source: str,
    target: str,
    relation: str,
    weight: float = 0.0,
    label: str = "",
) -> GraphEdge:
    if relation in _FORBIDDEN_RELATIONS:
        raise ValueError(
            f"Forbidden relation label '{relation}'. "
            f"Use one of: temporal_precedence, temporal_overlap, "
            f"supports_hypothesis, affected_channel, has_hypothesis."
        )
    return GraphEdge(source=source, target=target, relation=relation,
                     weight=weight, label=label)


class _GraphBuilder:
    """Accumulates nodes and edges with deduplication."""

    def __init__(self) -> None:
        self._node_ids: set[str] = set()
        self._edge_keys: set[tuple[str, str, str]] = set()
        self._nodes: list[GraphNode] = []
        self._edges: list[GraphEdge] = []

    def add_node(self, node: GraphNode) -> None:
        if node.node_id not in self._node_ids:
            self._node_ids.add(node.node_id)
            self._nodes.append(node)

    def add_edge(self, edge: GraphEdge) -> None:
        key = (edge.source, edge.target, edge.relation)
        if key not in self._edge_keys:
            self._edge_keys.add(key)
            self._edges.append(edge)

    def build(self) -> EvidenceGraph:
        return EvidenceGraph(nodes=list(self._nodes), edges=list(self._edges))


def _incident_node_id(spacecraft_incident_id: int) -> str:
    return f"incident:{spacecraft_incident_id}"


def _channel_node_id(channel: str) -> str:
    return f"channel:{channel}"


def _hypothesis_node_id(hypothesis_id: str) -> str:
    return f"hypothesis:{hypothesis_id}"


# ---------------------------------------------------------------------------
# Internal builders for each node / edge category
# ---------------------------------------------------------------------------

def _add_incident_node(
    builder: _GraphBuilder,
    char_dict: dict[str, Any],
    scores_dict: dict[str, Any],
) -> str:
    """Create and register the incident node; return its node_id."""
    sid = int(char_dict["spacecraft_incident_id"])
    node_id = _incident_node_id(sid)

    attrs: dict[str, Any] = {
        "spacecraft_incident_id": sid,
        "start_time": str(char_dict.get("start_time", "")),
        "end_time": str(char_dict.get("end_time", "")),
        "duration_sec": _safe_float(char_dict.get("duration_sec")),
        "n_channels_affected": int(char_dict.get("n_channels_affected", 0)),
        "is_multi_channel": bool(char_dict.get("is_multi_channel", False)),
        "n_events_total": int(char_dict.get("n_events_total", 0)),
        "persistence_class": str(char_dict.get("persistence_class", "")),
        "segment_span": int(char_dict.get("segment_span", 0)),
        # Scores — only added when present
    }

    if scores_dict:
        attrs["significance_score"] = _safe_float(scores_dict.get("significance_score"))
        attrs["severity_score"] = _safe_float(scores_dict.get("severity_score"))
        attrs["investigation_confidence"] = _safe_float(
            scores_dict.get("investigation_confidence")
        )
        attrs["severity_label"] = str(scores_dict.get("severity_label", ""))

    builder.add_node(_make_node(node_id, "incident", attrs))
    return node_id


def _add_channel_nodes(
    builder: _GraphBuilder,
    char_dict: dict[str, Any],
) -> dict[str, str]:
    """Create channel nodes and return {channel_name: node_id}."""
    channels_affected: list[str] = list(char_dict.get("channels_affected", []))
    activation_order: list[str] = list(char_dict.get("channel_activation_order", []))
    channel_incident_ids: list[str] = list(char_dict.get("channel_incident_ids", []))
    rels: list[dict[str, Any]] = list(
        char_dict.get("channel_temporal_relationships", [])
    )

    # Build a lookup: channel → first_activation timestamp (from rels or start_time)
    channel_first_activation: dict[str, str] = {}
    for rel in rels:
        ch_a = rel.get("channel_a", "")
        ch_b = rel.get("channel_b", "")
        if ch_a and ch_a not in channel_first_activation:
            channel_first_activation[ch_a] = str(rel.get("channel_a_start", ""))
        if ch_b and ch_b not in channel_first_activation:
            channel_first_activation[ch_b] = str(rel.get("channel_b_start", ""))

    # Build channel → channel_incident_id lookup
    # activation_order and channel_incident_ids are positionally aligned
    ch_inc_id_lookup: dict[str, str] = {}
    for i, ch in enumerate(activation_order):
        if i < len(channel_incident_ids):
            ch_inc_id_lookup[ch] = channel_incident_ids[i]

    # Determine activation position for each channel
    activation_pos: dict[str, int] = {
        ch: idx for idx, ch in enumerate(activation_order)
    }

    node_ids: dict[str, str] = {}
    for channel in sorted(channels_affected):
        node_id = _channel_node_id(channel)
        node_ids[channel] = node_id

        pos = activation_pos.get(channel, -1)
        role = "primary" if pos == 0 else ("secondary" if pos > 0 else "unknown")

        attrs: dict[str, Any] = {
            "channel": channel,
            "activation_rank": pos,
            "role": role,
        }
        if channel in channel_first_activation:
            attrs["first_activation"] = channel_first_activation[channel]
        if channel in ch_inc_id_lookup:
            attrs["channel_incident_id"] = ch_inc_id_lookup[channel]

        builder.add_node(_make_node(node_id, "channel", attrs))

    return node_ids


def _add_hypothesis_node(
    builder: _GraphBuilder,
    hypothesis_dict: dict[str, Any],
    scores_dict: dict[str, Any],
) -> str:
    """Create the hypothesis node; return its node_id."""
    hyp_id = str(hypothesis_dict.get("hypothesis_id", "HYP-unknown"))
    node_id = _hypothesis_node_id(hyp_id)

    attrs: dict[str, Any] = {
        "hypothesis_id": hyp_id,
        "hypothesis_type": str(hypothesis_dict.get("hypothesis_type", "")),
        "summary": str(hypothesis_dict.get("summary", "")),
        "hypothesis_confidence": _safe_float(
            hypothesis_dict.get("hypothesis_confidence")
        ),
        "n_corroborating_pairs": int(
            hypothesis_dict.get("n_corroborating_pairs", 0)
        ),
        "scientific_caveat": str(hypothesis_dict.get("scientific_caveat", "")),
        "observed_evidence": list(hypothesis_dict.get("observed_evidence", [])),
        "temporal_relationships": list(
            hypothesis_dict.get("temporal_relationships", [])
        ),
    }

    if scores_dict:
        attrs["significance_score"] = _safe_float(scores_dict.get("significance_score"))
        attrs["severity_score"] = _safe_float(scores_dict.get("severity_score"))

    builder.add_node(_make_node(node_id, "hypothesis", attrs))
    return node_id


def _add_incident_channel_edges(
    builder: _GraphBuilder,
    incident_node_id: str,
    channel_node_ids: dict[str, str],
    char_dict: dict[str, Any],
) -> None:
    """Add incident → channel edges (relation = affected_channel)."""
    channels_affected: list[str] = list(char_dict.get("channels_affected", []))
    for channel in sorted(channels_affected):
        if channel not in channel_node_ids:
            continue
        builder.add_edge(
            _make_edge(
                source=incident_node_id,
                target=channel_node_ids[channel],
                relation="affected_channel",
                weight=1.0,
                label=f"incident affected channel {channel}",
            )
        )


def _add_temporal_edges(
    builder: _GraphBuilder,
    channel_node_ids: dict[str, str],
    char_dict: dict[str, Any],
) -> None:
    """
    Add channel → channel temporal edges from channel_temporal_relationships.

    For each relationship:
    - If windows_overlap is True  → add a `temporal_overlap` edge
    - If temporal_precedence != "simultaneous"  → add a `temporal_precedence` edge
    - If simultaneous             → add a `temporal_overlap` edge only

    All pairs are stored as directed edges from channel_a to channel_b
    (channel_a is always the earlier-activating channel per characteriser).
    Edge weight = gap_seconds (normalised to [0,1] ceiling 3600 s; 0 = same instant).
    """
    rels: list[dict[str, Any]] = list(
        char_dict.get("channel_temporal_relationships", [])
    )

    # Sort for determinism (characteriser already sorts, but be explicit)
    rels_sorted = sorted(rels, key=lambda r: (r.get("channel_a", ""), r.get("channel_b", "")))

    for rel in rels_sorted:
        ch_a = rel.get("channel_a", "")
        ch_b = rel.get("channel_b", "")
        if not ch_a or not ch_b:
            continue
        if ch_a not in channel_node_ids or ch_b not in channel_node_ids:
            continue

        src = channel_node_ids[ch_a]
        tgt = channel_node_ids[ch_b]

        gap_sec = _safe_float(rel.get("temporal_gap_sec"), default=0.0)
        overlap = bool(rel.get("windows_overlap", False))
        precedence = str(rel.get("temporal_precedence", ""))

        # Normalised weight: 1.0 = same instant, 0.0 = ≥ 3600 s apart
        weight = round(max(0.0, 1.0 - gap_sec / 3600.0), 6)

        edge_attrs_label = (
            f"gap={gap_sec:.1f}s overlap={overlap} precedence={precedence}"
        )

        if precedence == "simultaneous":
            # Only one edge needed: temporal_overlap
            builder.add_edge(
                _make_edge(
                    source=src,
                    target=tgt,
                    relation="temporal_overlap",
                    weight=weight,
                    label=f"simultaneous activation; {edge_attrs_label}",
                )
            )
        else:
            # Directed precedence edge
            builder.add_edge(
                _make_edge(
                    source=src,
                    target=tgt,
                    relation="temporal_precedence",
                    weight=weight,
                    label=edge_attrs_label,
                )
            )
            # Plus overlap edge when applicable
            if overlap:
                builder.add_edge(
                    _make_edge(
                        source=src,
                        target=tgt,
                        relation="temporal_overlap",
                        weight=weight,
                        label=f"windows overlap; {edge_attrs_label}",
                    )
                )


def _add_channel_hypothesis_edges(
    builder: _GraphBuilder,
    channel_node_ids: dict[str, str],
    hypothesis_node_id: str,
    hypothesis_dict: dict[str, Any],
) -> None:
    """Add channel → hypothesis edges (relation = supports_hypothesis)."""
    # Edge weight = hypothesis_confidence (shared across all channels)
    confidence = _safe_float(hypothesis_dict.get("hypothesis_confidence"), default=0.0)

    for channel in sorted(channel_node_ids.keys()):
        src = channel_node_ids[channel]
        builder.add_edge(
            _make_edge(
                source=src,
                target=hypothesis_node_id,
                relation="supports_hypothesis",
                weight=round(confidence, 6),
                label=f"channel {channel} supports hypothesis",
            )
        )


def _add_incident_hypothesis_edge(
    builder: _GraphBuilder,
    incident_node_id: str,
    hypothesis_node_id: str,
) -> None:
    """Add incident → hypothesis edge (relation = has_hypothesis)."""
    builder.add_edge(
        _make_edge(
            source=incident_node_id,
            target=hypothesis_node_id,
            relation="has_hypothesis",
            weight=1.0,
            label="incident has hypothesis",
        )
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_evidence_graph(
    char_dict: dict[str, Any],
    scores_dict: dict[str, Any],
    hypothesis_dict: dict[str, Any],
) -> EvidenceGraph:
    """
    Build a structured evidence graph for one spacecraft incident.

    Parameters
    ----------
    char_dict:
        Dict as returned by ``characteriser.get_incident_characterisation``.
        Required keys: spacecraft_incident_id, channels_affected,
        channel_activation_order, channel_temporal_relationships,
        channel_incident_ids.
    scores_dict:
        Dict as returned by ``scorer.score_incident``.
        May be empty; scores are included when present.
    hypothesis_dict:
        Dict as returned by ``hypothesis.build_hypothesis``.
        Required keys: hypothesis_id, hypothesis_type.

    Returns
    -------
    EvidenceGraph
        Plain Pydantic model (nodes + edges lists) ready for JSON serialisation
        and direct consumption by Member 3.

    Raises
    ------
    ValueError
        If char_dict or hypothesis_dict are missing required keys.
    """
    # --- Validate required inputs ---
    if not isinstance(char_dict, dict):
        raise ValueError("char_dict must be a dict")
    if not isinstance(hypothesis_dict, dict):
        raise ValueError("hypothesis_dict must be a dict")

    required_char = ["spacecraft_incident_id", "channels_affected"]
    missing = [k for k in required_char if k not in char_dict]
    if missing:
        raise ValueError(f"char_dict missing required keys: {missing}")

    if "hypothesis_id" not in hypothesis_dict:
        raise ValueError("hypothesis_dict missing required key: hypothesis_id")

    scores: dict[str, Any] = scores_dict if isinstance(scores_dict, dict) else {}

    builder = _GraphBuilder()

    # 1. Incident node
    inc_node_id = _add_incident_node(builder, char_dict, scores)

    # 2. Channel nodes
    ch_node_ids = _add_channel_nodes(builder, char_dict)

    # 3. Hypothesis node
    hyp_node_id = _add_hypothesis_node(builder, hypothesis_dict, scores)

    # 4. incident → channel edges
    _add_incident_channel_edges(builder, inc_node_id, ch_node_ids, char_dict)

    # 5. channel ↔ channel temporal edges
    _add_temporal_edges(builder, ch_node_ids, char_dict)

    # 6. channel → hypothesis edges
    _add_channel_hypothesis_edges(builder, ch_node_ids, hyp_node_id, hypothesis_dict)

    # 7. incident → hypothesis edge
    _add_incident_hypothesis_edge(builder, inc_node_id, hyp_node_id)

    return builder.build()
