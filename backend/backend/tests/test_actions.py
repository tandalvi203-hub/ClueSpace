"""
member2/tests/test_actions.py
------------------------------
Unit tests for member2/actions.py.

Covers:
  1.  Single-channel incident — only REVIEW_INITIAL_CHANNEL generated
  2.  Multi-channel incident with temporal overlap — temporal + overlap actions
  3.  High severity — PRIORITIZE_OPERATOR_INVESTIGATION generated
  4.  Low severity + low significance — no PRIORITIZE action
  5.  High event density — REVIEW_HIGH_DENSITY_WINDOW generated
  6.  Low event density — no density action
  7.  LONG persistence — REVIEW_LONG_DURATION generated
  8.  EXTENDED persistence — REVIEW_LONG_DURATION generated
  9.  SHORT/MEDIUM persistence — no duration action
 10.  Temporal overlap present — REVIEW_OVERLAPPING_CHANNELS generated
 11.  No temporal overlap — no overlap action
 12.  Missing temporal relationships — no temporal sequence or overlap actions
 13.  Deterministic output — same input produces same list twice
 14.  Action IDs are stable and sequential (ACT-{id}-{n})
 15.  All evidence_refs are non-empty strings (no invented evidence)
 16.  No causal language in any action field
 17.  No autonomous commands in any action field
 18.  Priority values are all integers in [1, 5]
 19.  Category values are all recognised constants
 20.  Missing required keys raise ValueError
 21.  Real incident 988 integration — actions generated and verified
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from member2.actions import (
    CAT_PRIORITIZE_OPERATOR,
    CAT_REVIEW_HIGH_DENSITY_WINDOW,
    CAT_REVIEW_INITIAL_CHANNEL,
    CAT_REVIEW_LONG_DURATION,
    CAT_REVIEW_OVERLAPPING_CHANNELS,
    CAT_REVIEW_TEMPORAL_SEQUENCE,
    HIGH_DENSITY_THRESHOLD,
    SEVERITY_HIGH_THRESHOLD,
    SIGNIFICANCE_HIGH_THRESHOLD,
    generate_actions,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EPOCH = datetime(2024, 1, 1, tzinfo=timezone.utc)

_ALL_CATEGORIES = {
    CAT_REVIEW_INITIAL_CHANNEL,
    CAT_REVIEW_TEMPORAL_SEQUENCE,
    CAT_REVIEW_OVERLAPPING_CHANNELS,
    CAT_REVIEW_HIGH_DENSITY_WINDOW,
    CAT_REVIEW_LONG_DURATION,
    CAT_PRIORITIZE_OPERATOR,
}

# Phrases that would indicate causal claims — must never appear
_CAUSAL_PATTERNS = [
    r"\bcaus(es?|ed|al)\b",
    r"\bresponsible for\b",
    r"\btriggered by\b",    # ok in rationale for thresholds, but NOT for channels
    r"\broot cause\b",
]

# Phrases that would indicate autonomous commands
_COMMAND_PATTERNS = [
    r"\bcommand\b",
    r"\bsend\b.*\btelemetry\b",
    r"\brestart\b",
    r"\breset\b",
    r"\bpower cycle\b",
    r"\bautonomous\b.*\baction\b",
]


def _ts(offset_sec: int = 0) -> str:
    return (_EPOCH + timedelta(seconds=offset_sec)).isoformat()


def _rel(
    ch_a: str,
    t_a: int,
    ch_b: str,
    t_b: int,
    overlap: bool = True,
) -> dict[str, Any]:
    """Build a minimal temporal relationship dict."""
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


def _make_char(
    sid: int = 1,
    channels: list[str] | None = None,
    activation_order: list[str] | None = None,
    rels: list[dict] | None = None,
    n_events: int = 20,
    density: float = 10.0,
    duration_sec: float = 120.0,
    persistence_class: str = "MEDIUM",
    peak: float = 0.75,
    channel_incident_ids: list[str] | None = None,
) -> dict[str, Any]:
    if channels is None:
        channels = ["CH-A"]
    if activation_order is None:
        activation_order = list(channels)
    if rels is None:
        rels = []
    if channel_incident_ids is None:
        channel_incident_ids = [f"INC-{sid}-{c}" for c in channels]
    return {
        "spacecraft_incident_id": sid,
        "n_channels_affected": len(channels),
        "channels_affected": sorted(channels),
        "channel_activation_order": activation_order,
        "channel_temporal_relationships": rels,
        "n_events_total": n_events,
        "event_density_per_min": density,
        "duration_sec": duration_sec,
        "persistence_class": persistence_class,
        "peak_anomaly_score": peak,
        "mean_anomaly_score": peak - 0.05,
        "score_std": 0.05,
        "start_time": _ts(0),
        "end_time": _ts(int(duration_sec)),
        "channel_incident_ids": channel_incident_ids,
    }


def _make_scores(
    severity: float = 3.0,
    significance: float = 40.0,
    severity_label: str = "MODERATE",
    confidence: float = 0.6,
) -> dict[str, Any]:
    return {
        "severity_score": severity,
        "significance_score": significance,
        "severity_label": severity_label,
        "investigation_confidence": confidence,
    }


def _make_hyp(
    sid: int = 1,
    hyp_type: str = "single_channel",
    chain: list[dict] | None = None,
    n_corroborating_pairs: int = 0,
) -> dict[str, Any]:
    return {
        "hypothesis_id": f"HYP-{sid}",
        "hypothesis_type": hyp_type,
        "summary": "Test hypothesis summary.",
        "chain": chain or [],
        "supporting_evidence": [],
        "hypothesis_confidence": 0.0,
        "scientific_caveat": "Temporal correlation observed; physical causality not confirmed.",
        "observed_evidence": [],
        "temporal_relationships": [],
        "n_corroborating_pairs": n_corroborating_pairs,
    }


def _categories(actions: list[dict]) -> list[str]:
    return [a["category"] for a in actions]


def _action_by_cat(actions: list[dict], cat: str) -> dict | None:
    for a in actions:
        if a["category"] == cat:
            return a
    return None


def _all_text(action: dict) -> str:
    """Concatenate all string fields for pattern checking."""
    parts = [
        action.get("title", ""),
        action.get("description", ""),
        action.get("rationale", ""),
    ]
    parts.extend(str(r) for r in action.get("evidence_refs", []))
    return " ".join(parts)


# ---------------------------------------------------------------------------
# 1. Single-channel incident
# ---------------------------------------------------------------------------

class TestSingleChannel:
    def _build(self) -> list[dict]:
        char = _make_char(sid=1, channels=["CH-A"])
        scores = _make_scores(severity=2.0, significance=30.0, severity_label="LOW")
        hyp = _make_hyp(sid=1, hyp_type="single_channel")
        return generate_actions(char, scores, hyp)

    def test_initial_channel_always_present(self):
        actions = self._build()
        assert CAT_REVIEW_INITIAL_CHANNEL in _categories(actions)

    def test_no_temporal_sequence_action(self):
        """Single channel → no inter-channel temporal action."""
        actions = self._build()
        assert CAT_REVIEW_TEMPORAL_SEQUENCE not in _categories(actions)

    def test_no_overlapping_channels_action(self):
        """Single channel → no cross-channel overlap action."""
        actions = self._build()
        assert CAT_REVIEW_OVERLAPPING_CHANNELS not in _categories(actions)

    def test_action_id_format(self):
        actions = self._build()
        for a in actions:
            assert re.match(r"^ACT-\d+-\d+$", a["action_id"])

    def test_evidence_refs_nonempty(self):
        actions = self._build()
        for a in actions:
            assert isinstance(a["evidence_refs"], list)
            assert len(a["evidence_refs"]) >= 1
            for ref in a["evidence_refs"]:
                assert isinstance(ref, str) and ref.strip()

    def test_initial_channel_references_correct_channel(self):
        actions = self._build()
        action = _action_by_cat(actions, CAT_REVIEW_INITIAL_CHANNEL)
        assert action is not None
        assert "CH-A" in action["title"] or "CH-A" in action["description"]


# ---------------------------------------------------------------------------
# 2. Multi-channel incident with temporal overlap
# ---------------------------------------------------------------------------

class TestMultiChannelWithOverlap:
    def _build(
        self,
        channels: list[str] | None = None,
        overlap: bool = True,
    ) -> list[dict]:
        if channels is None:
            channels = ["CH-A", "CH-B", "CH-C"]
        rels = [
            _rel("CH-A", 0, "CH-B", 60, overlap=overlap),
            _rel("CH-A", 0, "CH-C", 120, overlap=overlap),
            _rel("CH-B", 60, "CH-C", 120, overlap=overlap),
        ]
        char = _make_char(
            sid=10,
            channels=channels,
            activation_order=["CH-A", "CH-B", "CH-C"],
            rels=rels,
            density=10.0,
            persistence_class="MEDIUM",
        )
        n_overlapping = len([r for r in rels if r["windows_overlap"]])
        scores = _make_scores(severity=4.0, significance=50.0)
        hyp = _make_hyp(sid=10, hyp_type="multi_channel", n_corroborating_pairs=n_overlapping)
        return generate_actions(char, scores, hyp)

    def test_initial_channel_present(self):
        assert CAT_REVIEW_INITIAL_CHANNEL in _categories(self._build())

    def test_temporal_sequence_present(self):
        assert CAT_REVIEW_TEMPORAL_SEQUENCE in _categories(self._build())

    def test_overlapping_channels_present_when_overlap(self):
        assert CAT_REVIEW_OVERLAPPING_CHANNELS in _categories(self._build(overlap=True))

    def test_no_overlapping_channels_when_no_overlap(self):
        assert CAT_REVIEW_OVERLAPPING_CHANNELS not in _categories(self._build(overlap=False))

    def test_temporal_sequence_references_all_rels(self):
        actions = self._build()
        action = _action_by_cat(actions, CAT_REVIEW_TEMPORAL_SEQUENCE)
        assert action is not None
        # Should have evidence refs for each of the 3 relationships
        rel_refs = [r for r in action["evidence_refs"] if r.startswith("temporal_rel:")]
        assert len(rel_refs) == 3

    def test_overlap_action_references_pairs(self):
        actions = self._build()
        action = _action_by_cat(actions, CAT_REVIEW_OVERLAPPING_CHANNELS)
        assert action is not None
        overlap_refs = [r for r in action["evidence_refs"] if r.startswith("overlapping_pair:")]
        assert len(overlap_refs) == 3  # all 3 pairs overlap

    def test_action_ids_sequential(self):
        actions = self._build()
        for i, a in enumerate(actions, start=1):
            assert a["action_id"] == f"ACT-10-{i}"


# ---------------------------------------------------------------------------
# 3. High severity
# ---------------------------------------------------------------------------

class TestHighSeverity:
    def _build(self, severity: float, significance: float, label: str) -> list[dict]:
        char = _make_char(sid=20, channels=["CH-A"])
        scores = _make_scores(severity=severity, significance=significance, severity_label=label)
        hyp = _make_hyp(sid=20)
        return generate_actions(char, scores, hyp)

    def test_critical_generates_prioritize(self):
        actions = self._build(8.0, 80.0, "CRITICAL")
        assert CAT_PRIORITIZE_OPERATOR in _categories(actions)

    def test_high_generates_prioritize(self):
        actions = self._build(SEVERITY_HIGH_THRESHOLD, 40.0, "HIGH")
        assert CAT_PRIORITIZE_OPERATOR in _categories(actions)

    def test_high_significance_alone_generates_prioritize(self):
        # severity below threshold, significance above
        actions = self._build(2.0, SIGNIFICANCE_HIGH_THRESHOLD, "LOW")
        assert CAT_PRIORITIZE_OPERATOR in _categories(actions)

    def test_prioritize_action_contains_severity_label(self):
        actions = self._build(7.5, 75.0, "CRITICAL")
        action = _action_by_cat(actions, CAT_PRIORITIZE_OPERATOR)
        assert action is not None
        assert "CRITICAL" in action["title"] or "CRITICAL" in action["description"]

    def test_prioritize_evidence_includes_score_refs(self):
        actions = self._build(7.5, 75.0, "CRITICAL")
        action = _action_by_cat(actions, CAT_PRIORITIZE_OPERATOR)
        assert action is not None
        ref_keys = {r.split(":")[0] for r in action["evidence_refs"]}
        assert "severity_score" in ref_keys
        assert "significance_score" in ref_keys


# ---------------------------------------------------------------------------
# 4. Low severity
# ---------------------------------------------------------------------------

class TestLowSeverity:
    def test_no_prioritize_action_when_below_thresholds(self):
        char = _make_char(sid=30, channels=["CH-A"])
        scores = _make_scores(
            severity=SEVERITY_HIGH_THRESHOLD - 0.1,
            significance=SIGNIFICANCE_HIGH_THRESHOLD - 0.1,
            severity_label="MODERATE",
        )
        hyp = _make_hyp(sid=30)
        actions = generate_actions(char, scores, hyp)
        assert CAT_PRIORITIZE_OPERATOR not in _categories(actions)


# ---------------------------------------------------------------------------
# 5. High event density
# ---------------------------------------------------------------------------

class TestHighDensity:
    def test_high_density_generates_density_action(self):
        char = _make_char(
            sid=40, channels=["CH-A"],
            density=HIGH_DENSITY_THRESHOLD + 1.0,
            n_events=200,
        )
        scores = _make_scores()
        hyp = _make_hyp(sid=40)
        actions = generate_actions(char, scores, hyp)
        assert CAT_REVIEW_HIGH_DENSITY_WINDOW in _categories(actions)

    def test_density_action_references_density_value(self):
        density_val = HIGH_DENSITY_THRESHOLD + 15.0
        char = _make_char(sid=40, channels=["CH-A"], density=density_val, n_events=300)
        scores = _make_scores()
        hyp = _make_hyp(sid=40)
        actions = generate_actions(char, scores, hyp)
        action = _action_by_cat(actions, CAT_REVIEW_HIGH_DENSITY_WINDOW)
        assert action is not None
        density_refs = [r for r in action["evidence_refs"] if "event_density" in r]
        assert density_refs, "No event_density ref found"
        # Value should be in the ref string
        assert str(int(density_val)) in density_refs[0] or f"{density_val:.2f}" in density_refs[0]

    def test_density_action_references_n_events(self):
        char = _make_char(sid=40, channels=["CH-A"], density=50.0, n_events=500)
        scores = _make_scores()
        hyp = _make_hyp(sid=40)
        actions = generate_actions(char, scores, hyp)
        action = _action_by_cat(actions, CAT_REVIEW_HIGH_DENSITY_WINDOW)
        assert action is not None
        n_refs = [r for r in action["evidence_refs"] if "n_events_total" in r]
        assert n_refs


# ---------------------------------------------------------------------------
# 6. Low event density
# ---------------------------------------------------------------------------

class TestLowDensity:
    def test_no_density_action_when_below_threshold(self):
        char = _make_char(sid=50, channels=["CH-A"], density=HIGH_DENSITY_THRESHOLD - 1.0)
        scores = _make_scores()
        hyp = _make_hyp(sid=50)
        actions = generate_actions(char, scores, hyp)
        assert CAT_REVIEW_HIGH_DENSITY_WINDOW not in _categories(actions)


# ---------------------------------------------------------------------------
# 7. LONG persistence
# ---------------------------------------------------------------------------

class TestLongPersistence:
    def test_long_generates_duration_action(self):
        char = _make_char(sid=60, channels=["CH-A"], persistence_class="LONG", duration_sec=500.0)
        scores = _make_scores()
        hyp = _make_hyp(sid=60)
        actions = generate_actions(char, scores, hyp)
        assert CAT_REVIEW_LONG_DURATION in _categories(actions)

    def test_long_duration_action_says_long(self):
        char = _make_char(sid=60, channels=["CH-A"], persistence_class="LONG", duration_sec=600.0)
        scores = _make_scores()
        hyp = _make_hyp(sid=60)
        actions = generate_actions(char, scores, hyp)
        action = _action_by_cat(actions, CAT_REVIEW_LONG_DURATION)
        assert action is not None
        assert "LONG" in action["description"] or "LONG" in action["title"]


# ---------------------------------------------------------------------------
# 8. EXTENDED persistence
# ---------------------------------------------------------------------------

class TestExtendedPersistence:
    def test_extended_generates_duration_action(self):
        char = _make_char(sid=70, channels=["CH-A"], persistence_class="EXTENDED", duration_sec=1200.0)
        scores = _make_scores()
        hyp = _make_hyp(sid=70)
        actions = generate_actions(char, scores, hyp)
        assert CAT_REVIEW_LONG_DURATION in _categories(actions)

    def test_extended_duration_action_says_extended(self):
        char = _make_char(sid=70, channels=["CH-A"], persistence_class="EXTENDED", duration_sec=1200.0)
        scores = _make_scores()
        hyp = _make_hyp(sid=70)
        actions = generate_actions(char, scores, hyp)
        action = _action_by_cat(actions, CAT_REVIEW_LONG_DURATION)
        assert action is not None
        assert "EXTENDED" in action["description"] or "EXTENDED" in action["title"]

    def test_extended_references_persistence_class(self):
        char = _make_char(sid=70, channels=["CH-A"], persistence_class="EXTENDED", duration_sec=1200.0)
        scores = _make_scores()
        hyp = _make_hyp(sid=70)
        actions = generate_actions(char, scores, hyp)
        action = _action_by_cat(actions, CAT_REVIEW_LONG_DURATION)
        assert action is not None
        persist_refs = [r for r in action["evidence_refs"] if "persistence_class" in r]
        assert persist_refs


# ---------------------------------------------------------------------------
# 9. SHORT / MEDIUM persistence
# ---------------------------------------------------------------------------

class TestShortMediumPersistence:
    @pytest.mark.parametrize("cls", ["SHORT", "MEDIUM"])
    def test_no_duration_action(self, cls: str):
        char = _make_char(sid=80, channels=["CH-A"], persistence_class=cls, duration_sec=100.0)
        scores = _make_scores()
        hyp = _make_hyp(sid=80)
        actions = generate_actions(char, scores, hyp)
        assert CAT_REVIEW_LONG_DURATION not in _categories(actions)


# ---------------------------------------------------------------------------
# 10. Temporal overlap present
# ---------------------------------------------------------------------------

class TestTemporalOverlap:
    def test_overlap_action_generated(self):
        rels = [_rel("CH-A", 0, "CH-B", 30, overlap=True)]
        char = _make_char(
            sid=90,
            channels=["CH-A", "CH-B"],
            activation_order=["CH-A", "CH-B"],
            rels=rels,
        )
        scores = _make_scores()
        hyp = _make_hyp(sid=90, hyp_type="multi_channel", n_corroborating_pairs=1)
        actions = generate_actions(char, scores, hyp)
        assert CAT_REVIEW_OVERLAPPING_CHANNELS in _categories(actions)

    def test_overlap_pair_names_in_evidence(self):
        rels = [_rel("CH-A", 0, "CH-B", 30, overlap=True)]
        char = _make_char(
            sid=90,
            channels=["CH-A", "CH-B"],
            activation_order=["CH-A", "CH-B"],
            rels=rels,
        )
        scores = _make_scores()
        hyp = _make_hyp(sid=90, hyp_type="multi_channel", n_corroborating_pairs=1)
        actions = generate_actions(char, scores, hyp)
        action = _action_by_cat(actions, CAT_REVIEW_OVERLAPPING_CHANNELS)
        assert action is not None
        pair_refs = [r for r in action["evidence_refs"] if "overlapping_pair:" in r]
        assert len(pair_refs) == 1
        assert "CH-A+CH-B" in pair_refs[0] or "CH-B+CH-A" in pair_refs[0]


# ---------------------------------------------------------------------------
# 11. No temporal overlap
# ---------------------------------------------------------------------------

class TestNoOverlap:
    def test_no_overlap_action_when_no_overlapping_pairs(self):
        rels = [_rel("CH-A", 0, "CH-B", 3600, overlap=False)]
        char = _make_char(
            sid=100,
            channels=["CH-A", "CH-B"],
            activation_order=["CH-A", "CH-B"],
            rels=rels,
        )
        scores = _make_scores()
        hyp = _make_hyp(sid=100, hyp_type="multi_channel", n_corroborating_pairs=0)
        actions = generate_actions(char, scores, hyp)
        assert CAT_REVIEW_OVERLAPPING_CHANNELS not in _categories(actions)


# ---------------------------------------------------------------------------
# 12. Missing temporal relationships
# ---------------------------------------------------------------------------

class TestMissingTemporalRelationships:
    def test_no_temporal_sequence_action_without_rels(self):
        char = _make_char(
            sid=110,
            channels=["CH-A", "CH-B"],
            activation_order=["CH-A", "CH-B"],
            rels=[],  # empty
        )
        scores = _make_scores()
        hyp = _make_hyp(sid=110, hyp_type="insufficient_evidence")
        actions = generate_actions(char, scores, hyp)
        assert CAT_REVIEW_TEMPORAL_SEQUENCE not in _categories(actions)

    def test_no_overlap_action_without_rels(self):
        char = _make_char(
            sid=110,
            channels=["CH-A", "CH-B"],
            activation_order=["CH-A", "CH-B"],
            rels=[],
        )
        scores = _make_scores()
        hyp = _make_hyp(sid=110, hyp_type="insufficient_evidence")
        actions = generate_actions(char, scores, hyp)
        assert CAT_REVIEW_OVERLAPPING_CHANNELS not in _categories(actions)

    def test_initial_channel_still_generated_without_rels(self):
        char = _make_char(
            sid=110,
            channels=["CH-A", "CH-B"],
            activation_order=["CH-A", "CH-B"],
            rels=[],
        )
        scores = _make_scores()
        hyp = _make_hyp(sid=110, hyp_type="insufficient_evidence")
        actions = generate_actions(char, scores, hyp)
        assert CAT_REVIEW_INITIAL_CHANNEL in _categories(actions)


# ---------------------------------------------------------------------------
# 13. Deterministic output
# ---------------------------------------------------------------------------

class TestDeterminism:
    def _full_char(self) -> tuple[dict, dict, dict]:
        rels = [
            _rel("CH-A", 0, "CH-B", 30, overlap=True),
            _rel("CH-A", 0, "CH-C", 90, overlap=False),
            _rel("CH-B", 30, "CH-C", 90, overlap=True),
        ]
        char = _make_char(
            sid=200,
            channels=["CH-A", "CH-B", "CH-C"],
            activation_order=["CH-A", "CH-B", "CH-C"],
            rels=rels,
            density=50.0,
            persistence_class="EXTENDED",
            duration_sec=1000.0,
        )
        scores = _make_scores(severity=7.5, significance=80.0, severity_label="CRITICAL")
        hyp = _make_hyp(sid=200, hyp_type="multi_channel", n_corroborating_pairs=2)
        return char, scores, hyp

    def test_identical_calls_produce_same_list(self):
        char, scores, hyp = self._full_char()
        result_a = generate_actions(char, scores, hyp)
        result_b = generate_actions(char, scores, hyp)
        assert result_a == result_b

    def test_action_ids_same_across_calls(self):
        char, scores, hyp = self._full_char()
        result_a = generate_actions(char, scores, hyp)
        result_b = generate_actions(char, scores, hyp)
        assert [a["action_id"] for a in result_a] == [a["action_id"] for a in result_b]

    def test_categories_same_across_calls(self):
        char, scores, hyp = self._full_char()
        result_a = generate_actions(char, scores, hyp)
        result_b = generate_actions(char, scores, hyp)
        assert _categories(result_a) == _categories(result_b)


# ---------------------------------------------------------------------------
# 14. Action IDs are stable and sequential
# ---------------------------------------------------------------------------

class TestActionIds:
    def test_ids_are_sequential_from_one(self):
        rels = [_rel("CH-A", 0, "CH-B", 60, overlap=True)]
        char = _make_char(
            sid=300,
            channels=["CH-A", "CH-B"],
            activation_order=["CH-A", "CH-B"],
            rels=rels,
            density=50.0,
            persistence_class="LONG",
            duration_sec=400.0,
        )
        scores = _make_scores(severity=7.0, significance=70.0, severity_label="CRITICAL")
        hyp = _make_hyp(sid=300, hyp_type="multi_channel", n_corroborating_pairs=1)
        actions = generate_actions(char, scores, hyp)
        for i, a in enumerate(actions, start=1):
            assert a["action_id"] == f"ACT-300-{i}"

    def test_single_channel_id_format(self):
        char = _make_char(sid=999, channels=["CH-X"])
        scores = _make_scores()
        hyp = _make_hyp(sid=999)
        actions = generate_actions(char, scores, hyp)
        for a in actions:
            assert a["action_id"].startswith("ACT-999-")

    def test_no_gaps_in_sequence(self):
        char = _make_char(sid=301, channels=["CH-A"])
        scores = _make_scores()
        hyp = _make_hyp(sid=301)
        actions = generate_actions(char, scores, hyp)
        nums = [int(a["action_id"].split("-")[-1]) for a in actions]
        assert nums == list(range(1, len(actions) + 1))


# ---------------------------------------------------------------------------
# 15. All evidence_refs are non-empty strings (no invented evidence)
# ---------------------------------------------------------------------------

class TestEvidenceRefs:
    def test_all_refs_are_strings(self):
        char = _make_char(sid=400, channels=["CH-A", "CH-B"],
                          activation_order=["CH-A", "CH-B"],
                          rels=[_rel("CH-A", 0, "CH-B", 60, overlap=True)])
        scores = _make_scores(severity=6.0, significance=65.0, severity_label="HIGH")
        hyp = _make_hyp(sid=400, hyp_type="multi_channel", n_corroborating_pairs=1)
        actions = generate_actions(char, scores, hyp)
        for a in actions:
            for ref in a["evidence_refs"]:
                assert isinstance(ref, str), f"Non-string ref in {a['category']}: {ref!r}"
                assert ref.strip(), f"Empty ref in {a['category']}"

    def test_refs_contain_real_values(self):
        """Evidence refs should contain values from the input, not made-up data."""
        char = _make_char(sid=400, channels=["CH-A", "CH-B"],
                          activation_order=["CH-A", "CH-B"],
                          rels=[_rel("CH-A", 0, "CH-B", 60, overlap=True)],
                          density=50.0, persistence_class="LONG", duration_sec=500.0)
        scores = _make_scores(severity=6.0, significance=65.0, severity_label="HIGH")
        hyp = _make_hyp(sid=400, hyp_type="multi_channel", n_corroborating_pairs=1)
        actions = generate_actions(char, scores, hyp)

        # Initial channel action should reference CH-A
        init_action = _action_by_cat(actions, CAT_REVIEW_INITIAL_CHANNEL)
        assert init_action is not None
        assert any("CH-A" in r for r in init_action["evidence_refs"])

        # High density action should reference density value
        density_action = _action_by_cat(actions, CAT_REVIEW_HIGH_DENSITY_WINDOW)
        assert density_action is not None
        assert any("50" in r for r in density_action["evidence_refs"])


# ---------------------------------------------------------------------------
# 16. No causal language
# ---------------------------------------------------------------------------

class TestNoCausalLanguage:
    """All action text must avoid causal claims between channels."""

    def _all_actions(self) -> list[dict]:
        rels = [
            _rel("CH-A", 0, "CH-B", 30, overlap=True),
            _rel("CH-B", 30, "CH-C", 60, overlap=True),
            _rel("CH-A", 0, "CH-C", 60, overlap=True),
        ]
        char = _make_char(
            sid=500,
            channels=["CH-A", "CH-B", "CH-C"],
            activation_order=["CH-A", "CH-B", "CH-C"],
            rels=rels,
            density=60.0,
            persistence_class="EXTENDED",
            duration_sec=1200.0,
        )
        scores = _make_scores(severity=8.0, significance=85.0, severity_label="CRITICAL")
        hyp = _make_hyp(sid=500, hyp_type="multi_channel", n_corroborating_pairs=3)
        return generate_actions(char, scores, hyp)

    def test_no_causes_language(self):
        for action in self._all_actions():
            text = _all_text(action)
            assert not re.search(r"\bcause[sd]?\b", text, re.IGNORECASE), (
                f"Causal 'cause' found in {action['category']}: {text!r}"
            )

    def test_no_causal_adjective(self):
        for action in self._all_actions():
            text = _all_text(action)
            assert not re.search(r"\bcausal\b", text, re.IGNORECASE), (
                f"Word 'causal' found in {action['category']}: {text!r}"
            )

    def test_no_responsible_for(self):
        for action in self._all_actions():
            text = _all_text(action)
            assert not re.search(r"\bresponsible for\b", text, re.IGNORECASE), (
                f"'responsible for' found in {action['category']}: {text!r}"
            )

    def test_no_root_cause_claim(self):
        for action in self._all_actions():
            text = _all_text(action)
            assert not re.search(r"\broot cause\b", text, re.IGNORECASE), (
                f"'root cause' found in {action['category']}: {text!r}"
            )


# ---------------------------------------------------------------------------
# 17. No autonomous commands
# ---------------------------------------------------------------------------

class TestNoAutonomousCommands:
    def _all_actions(self) -> list[dict]:
        char = _make_char(sid=600, channels=["CH-A"])
        scores = _make_scores(severity=9.0, significance=90.0, severity_label="CRITICAL")
        hyp = _make_hyp(sid=600)
        return generate_actions(char, scores, hyp)

    def test_no_command_word_in_actions(self):
        """The word 'command' in action context means spacecraft command."""
        for action in self._all_actions():
            text = _all_text(action)
            # "command" is only allowed in the context of "no autonomous command"
            # or "recommended actions" — not as an imperative directive
            assert not re.search(r"\bsend command\b", text, re.IGNORECASE)
            assert not re.search(r"\bpower cycle\b", text, re.IGNORECASE)
            assert not re.search(r"\brestart\b", text, re.IGNORECASE)
            assert not re.search(r"\bexecute\b.*\bcommand\b", text, re.IGNORECASE)

    def test_actions_are_investigative_in_nature(self):
        """Titles should contain investigative verbs (Review, Prioritise, Examine)."""
        for action in self._all_actions():
            title = action["title"]
            assert re.search(
                r"\b(Review|Prioritis[e]|Prioritize|Examine|Investigate)\b",
                title,
                re.IGNORECASE,
            ), f"Title lacks investigative verb: {title!r}"


# ---------------------------------------------------------------------------
# 18. Priority values are integers in [1, 5]
# ---------------------------------------------------------------------------

class TestPriorityValues:
    def test_all_priorities_in_range(self):
        rels = [_rel("CH-A", 0, "CH-B", 30, overlap=True)]
        char = _make_char(
            sid=700,
            channels=["CH-A", "CH-B"],
            activation_order=["CH-A", "CH-B"],
            rels=rels,
            density=60.0,
            persistence_class="EXTENDED",
            duration_sec=1200.0,
        )
        scores = _make_scores(severity=8.0, significance=90.0, severity_label="CRITICAL")
        hyp = _make_hyp(sid=700, hyp_type="multi_channel", n_corroborating_pairs=1)
        actions = generate_actions(char, scores, hyp)
        for a in actions:
            assert isinstance(a["priority"], int), f"priority is not int: {a['priority']!r}"
            assert 1 <= a["priority"] <= 5, f"priority out of range: {a['priority']}"


# ---------------------------------------------------------------------------
# 19. Category values are recognised constants
# ---------------------------------------------------------------------------

class TestCategoryConstants:
    def test_all_categories_recognised(self):
        rels = [_rel("CH-A", 0, "CH-B", 30, overlap=True)]
        char = _make_char(
            sid=800,
            channels=["CH-A", "CH-B"],
            activation_order=["CH-A", "CH-B"],
            rels=rels,
            density=60.0,
            persistence_class="EXTENDED",
            duration_sec=1200.0,
        )
        scores = _make_scores(severity=8.0, significance=90.0, severity_label="CRITICAL")
        hyp = _make_hyp(sid=800, hyp_type="multi_channel", n_corroborating_pairs=1)
        actions = generate_actions(char, scores, hyp)
        for a in actions:
            assert a["category"] in _ALL_CATEGORIES, (
                f"Unrecognised category: {a['category']!r}"
            )


# ---------------------------------------------------------------------------
# 20. Missing required keys raise ValueError
# ---------------------------------------------------------------------------

class TestMissingKeys:
    def _valid_inputs(self) -> tuple[dict, dict, dict]:
        char = _make_char(sid=900, channels=["CH-A"])
        scores = _make_scores()
        hyp = _make_hyp(sid=900)
        return char, scores, hyp

    def test_missing_char_key_raises(self):
        char, scores, hyp = self._valid_inputs()
        del char["spacecraft_incident_id"]
        with pytest.raises(ValueError, match="spacecraft_incident_id"):
            generate_actions(char, scores, hyp)

    def test_missing_n_channels_raises(self):
        char, scores, hyp = self._valid_inputs()
        del char["n_channels_affected"]
        with pytest.raises(ValueError, match="n_channels_affected"):
            generate_actions(char, scores, hyp)

    def test_missing_scores_key_raises(self):
        char, scores, hyp = self._valid_inputs()
        del scores["severity_score"]
        with pytest.raises(ValueError, match="severity_score"):
            generate_actions(char, scores, hyp)

    def test_missing_significance_raises(self):
        char, scores, hyp = self._valid_inputs()
        del scores["significance_score"]
        with pytest.raises(ValueError, match="significance_score"):
            generate_actions(char, scores, hyp)

    def test_missing_hypothesis_type_raises(self):
        char, scores, hyp = self._valid_inputs()
        del hyp["hypothesis_type"]
        with pytest.raises(ValueError, match="hypothesis_type"):
            generate_actions(char, scores, hyp)

    def test_missing_hypothesis_chain_raises(self):
        char, scores, hyp = self._valid_inputs()
        del hyp["chain"]
        with pytest.raises(ValueError, match="chain"):
            generate_actions(char, scores, hyp)


# ---------------------------------------------------------------------------
# 21. Real incident 988 integration
# ---------------------------------------------------------------------------

class TestRealIncident988:
    """
    Integration test using a representative incident 988 profile derived from
    the OPS-SAT-AD dataset characteristics.

    The exact incident 988 from the loaders pipeline is a multi-channel incident
    (3 channels, EXTENDED persistence, high density).  We replicate its key
    characterisation parameters here to validate the full action pipeline.
    """

    def _build_988(self) -> list[dict]:
        # Incident 988: 3 channels, ~1200s duration, high density, multi-channel
        rels = [
            _rel("ADCS_1", 0,   "ADCS_2", 45,  overlap=True),
            _rel("ADCS_1", 0,   "ADCS_3", 120, overlap=True),
            _rel("ADCS_2", 45,  "ADCS_3", 120, overlap=False),
        ]
        char = _make_char(
            sid=988,
            channels=["ADCS_1", "ADCS_2", "ADCS_3"],
            activation_order=["ADCS_1", "ADCS_2", "ADCS_3"],
            rels=rels,
            n_events=150,
            density=45.0,
            duration_sec=1200.0,
            persistence_class="EXTENDED",
            peak=0.92,
            channel_incident_ids=["INC-988-A", "INC-988-B", "INC-988-C"],
        )
        scores = _make_scores(
            severity=7.8,
            significance=78.0,
            severity_label="CRITICAL",
            confidence=0.85,
        )
        hyp = _make_hyp(
            sid=988,
            hyp_type="multi_channel",
            n_corroborating_pairs=2,
        )
        return generate_actions(char, scores, hyp)

    def test_all_six_categories_generated(self):
        """All six categories are triggered by incident 988's profile."""
        actions = self._build_988()
        cats = set(_categories(actions))
        assert cats == _ALL_CATEGORIES, (
            f"Missing categories: {_ALL_CATEGORIES - cats}"
        )

    def test_six_actions_total(self):
        actions = self._build_988()
        assert len(actions) == 6

    def test_action_ids_correct(self):
        actions = self._build_988()
        assert [a["action_id"] for a in actions] == [f"ACT-988-{i}" for i in range(1, 7)]

    def test_initial_channel_is_adcs_1(self):
        actions = self._build_988()
        action = _action_by_cat(actions, CAT_REVIEW_INITIAL_CHANNEL)
        assert action is not None
        assert "ADCS_1" in action["title"]

    def test_temporal_sequence_has_3_rels(self):
        actions = self._build_988()
        action = _action_by_cat(actions, CAT_REVIEW_TEMPORAL_SEQUENCE)
        assert action is not None
        rel_refs = [r for r in action["evidence_refs"] if r.startswith("temporal_rel:")]
        assert len(rel_refs) == 3

    def test_overlap_action_references_2_pairs(self):
        """Only 2 of the 3 pairs overlap."""
        actions = self._build_988()
        action = _action_by_cat(actions, CAT_REVIEW_OVERLAPPING_CHANNELS)
        assert action is not None
        overlap_refs = [r for r in action["evidence_refs"] if "overlapping_pair:" in r]
        assert len(overlap_refs) == 2

    def test_prioritize_says_critical(self):
        actions = self._build_988()
        action = _action_by_cat(actions, CAT_PRIORITIZE_OPERATOR)
        assert action is not None
        assert "CRITICAL" in action["title"]

    def test_density_action_references_45_density(self):
        actions = self._build_988()
        action = _action_by_cat(actions, CAT_REVIEW_HIGH_DENSITY_WINDOW)
        assert action is not None
        assert any("45" in r for r in action["evidence_refs"])

    def test_duration_action_says_extended(self):
        actions = self._build_988()
        action = _action_by_cat(actions, CAT_REVIEW_LONG_DURATION)
        assert action is not None
        assert "EXTENDED" in action["title"] or "EXTENDED" in action["description"]

    def test_no_causal_language_in_988(self):
        actions = self._build_988()
        for a in actions:
            text = _all_text(a)
            assert not re.search(r"\bcause[sd]?\b", text, re.IGNORECASE), (
                f"Causal language in {a['category']}: {text!r}"
            )

    def test_deterministic_988(self):
        result_a = self._build_988()
        result_b = self._build_988()
        assert result_a == result_b

    def test_all_priorities_valid_988(self):
        actions = self._build_988()
        for a in actions:
            assert 1 <= a["priority"] <= 5

    def test_all_evidence_refs_nonempty_988(self):
        actions = self._build_988()
        for a in actions:
            for ref in a["evidence_refs"]:
                assert isinstance(ref, str) and ref.strip()
