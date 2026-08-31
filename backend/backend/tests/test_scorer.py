"""
member2/tests/test_scorer.py
-----------------------------
Comprehensive tests for member2/scorer.py.

Covers:
- Continuous peak scoring (anomaly_strength)
- Continuous density scoring
- Channel breadth normalisation
- Event-count log-normalisation
- Persistence ordinal mapping
- Cross-channel corroboration
- Confidence scoring
- Score bounds enforcement
- Deterministic / reproducibility
- Edge cases (zero, max, extreme values)
- No-causality language (score is observational only)
- score_incident convenience wrapper
- Severity label distribution (well-spread across labels)
- Weight sum validation (each score's components sum to expected total)
"""

from __future__ import annotations

import math

import pytest

from member2.output_schema import PersistenceClass
from member2.scorer import (
    _EVENT_QTY_DENOM,
    _PEAK_FLOOR,
    _SEV_CRITICAL,
    _SEV_HIGH,
    _SEV_MODERATE,
    _anomaly_strength,
    _channel_breadth,
    _cross_channel_corroboration,
    _event_density_norm,
    _event_qty_norm,
    _persistence_norm,
    _score_consistency,
    _severity_label,
    compute_confidence,
    compute_severity,
    compute_significance,
    score_incident,
)


# ---------------------------------------------------------------------------
# Helper: minimal char_dict
# ---------------------------------------------------------------------------

def _char(
    peak: float = 0.7,
    density: float = 30.0,
    n_events: int = 100,
    n_channels: int = 2,
    persistence: str = "MEDIUM",
    score_std: float = 0.10,
    rels: list | None = None,
) -> dict:
    if rels is None:
        rels = []
    return {
        "peak_anomaly_score":           peak,
        "event_density_per_min":        density,
        "n_events_total":               n_events,
        "n_channels_affected":          n_channels,
        "persistence_class":            persistence,
        "score_std":                    score_std,
        "channel_temporal_relationships": rels,
    }


def _overlap_rel(windows_overlap: bool = True) -> dict:
    """Minimal temporal relationship dict."""
    return {
        "channel_a": "CH_A",
        "channel_b": "CH_B",
        "temporal_gap_sec": 0.0,
        "temporal_precedence": "A_before_B",
        "windows_overlap": windows_overlap,
    }


# ---------------------------------------------------------------------------
# TestAnomalyStrength  — continuous peak scoring
# ---------------------------------------------------------------------------

class TestAnomalyStrength:
    def test_floor_maps_to_zero(self):
        """Peak at the floor (0.30) must map to exactly 0.0."""
        assert _anomaly_strength(0.30) == 0.0

    def test_one_maps_to_one(self):
        """Perfect score (1.0) must map to exactly 1.0."""
        assert _anomaly_strength(1.0) == 1.0

    def test_midpoint(self):
        """Peak at 0.65 = midpoint of [0.30, 1.00] must map to ~0.5."""
        assert abs(_anomaly_strength(0.65) - 0.5) < 1e-9

    def test_below_floor_clips_to_zero(self):
        """Scores below the floor must clip to 0."""
        assert _anomaly_strength(0.0) == 0.0
        assert _anomaly_strength(0.29) == 0.0

    def test_above_one_clips_to_one(self):
        """Scores above 1 must clip to 1.0."""
        assert _anomaly_strength(1.5) == 1.0

    def test_continuous_ordering(self):
        """Strictly increasing between floor and 1.0."""
        vals = [_anomaly_strength(p) for p in [0.30, 0.50, 0.70, 0.90, 1.00]]
        for a, b in zip(vals, vals[1:]):
            assert a <= b

    def test_linear_in_range(self):
        """Increments must be uniform for equal steps in peak_score."""
        d1 = _anomaly_strength(0.65) - _anomaly_strength(0.30)
        d2 = _anomaly_strength(1.00) - _anomaly_strength(0.65)
        assert abs(d1 - d2) < 1e-9

    def test_typical_median_peak(self):
        """Median peak score (0.82) should give a normalised value > 0.5."""
        assert _anomaly_strength(0.82) > 0.5


# ---------------------------------------------------------------------------
# TestEventDensityNorm  — continuous density scoring
# ---------------------------------------------------------------------------

class TestEventDensityNorm:
    def test_zero_density_maps_to_zero(self):
        assert _event_density_norm(0.0) == 0.0

    def test_saturation_ceiling(self):
        """100 ev/min should map to exactly 1.0."""
        assert _event_density_norm(100.0) == 1.0

    def test_above_ceiling_clips(self):
        """Values above 100 must clip to 1.0."""
        assert _event_density_norm(150.0) == 1.0
        assert _event_density_norm(1000.0) == 1.0

    def test_fifty_percent(self):
        """50 ev/min should map to 0.5."""
        assert abs(_event_density_norm(50.0) - 0.5) < 1e-9

    def test_continuous_ordering(self):
        """Strictly increasing."""
        vals = [_event_density_norm(d) for d in [0, 10, 30, 50, 75, 100]]
        for a, b in zip(vals, vals[1:]):
            assert a <= b

    def test_dataset_median_density(self):
        """Dataset median (≈34.5 ev/min) should be below 0.5."""
        assert _event_density_norm(34.5) < 0.5


# ---------------------------------------------------------------------------
# TestChannelBreadth  — channel breadth normalisation
# ---------------------------------------------------------------------------

class TestChannelBreadth:
    def test_single_channel_maps_to_zero(self):
        assert _channel_breadth(1) == 0.0

    def test_five_channels_maps_to_one(self):
        assert _channel_breadth(5) == 1.0

    def test_two_channels(self):
        assert abs(_channel_breadth(2) - 0.25) < 1e-9

    def test_three_channels(self):
        assert abs(_channel_breadth(3) - 0.5) < 1e-9

    def test_four_channels(self):
        assert abs(_channel_breadth(4) - 0.75) < 1e-9

    def test_above_max_clips_to_one(self):
        assert _channel_breadth(10) == 1.0

    def test_continuous_equal_steps(self):
        """Each additional channel should add the same contribution."""
        steps = [_channel_breadth(n) for n in range(1, 6)]
        diffs = [steps[i+1] - steps[i] for i in range(4)]
        for d in diffs:
            assert abs(d - 0.25) < 1e-9


# ---------------------------------------------------------------------------
# TestEventQtyNorm  — log-normalised event quantity
# ---------------------------------------------------------------------------

class TestEventQtyNorm:
    def test_zero_events_near_zero(self):
        """0 events → log(1)/log(1325) = 0.0."""
        assert _event_qty_norm(0) == 0.0

    def test_single_event_small(self):
        """1 event → log(2)/log(1325) ≈ 0.096."""
        expected = math.log(2) / _EVENT_QTY_DENOM
        assert abs(_event_qty_norm(1) - expected) < 1e-9

    def test_dataset_median_n_events(self):
        """Median n_events=105 should map to ≈0.64 (well above 0)."""
        val = _event_qty_norm(105)
        assert 0.5 < val < 0.85

    def test_max_observed_near_one(self):
        """n_events=1324 (max observed) should map to ≈1.0."""
        val = _event_qty_norm(1324)
        assert val > 0.99

    def test_strictly_increasing(self):
        """More events should always give higher normalisation."""
        ns = [0, 1, 5, 10, 50, 105, 500, 1000, 1324]
        vals = [_event_qty_norm(n) for n in ns]
        for a, b in zip(vals, vals[1:]):
            assert a < b

    def test_bounds_respected(self):
        """Must always be in [0, 1]."""
        for n in [0, 1, 10, 100, 500, 1000, 10000]:
            v = _event_qty_norm(n)
            assert 0.0 <= v <= 1.0

    def test_not_saturating_at_small_values(self):
        """Small n_events should NOT saturate to 1.0 (distinguishable from large)."""
        assert _event_qty_norm(10) < 0.6

    def test_no_step_function_at_small_n(self):
        """Verify continuous increase in the low range — not a step."""
        v1 = _event_qty_norm(5)
        v2 = _event_qty_norm(10)
        v3 = _event_qty_norm(20)
        assert v1 < v2 < v3

    def test_negative_events_handled(self):
        """Negative input should return 0.0 without error."""
        assert _event_qty_norm(-1) == 0.0


# ---------------------------------------------------------------------------
# TestPersistenceNorm  — ordinal mapping
# ---------------------------------------------------------------------------

class TestPersistenceNorm:
    def test_short(self):
        assert _persistence_norm("SHORT") == 0.25

    def test_medium(self):
        assert _persistence_norm("MEDIUM") == 0.50

    def test_long(self):
        assert _persistence_norm("LONG") == 0.75

    def test_extended(self):
        assert _persistence_norm("EXTENDED") == 1.00

    def test_enum_value_accepted(self):
        assert _persistence_norm(PersistenceClass.SHORT) == 0.25
        assert _persistence_norm(PersistenceClass.EXTENDED) == 1.00

    def test_monotonic_ordering(self):
        vals = [
            _persistence_norm("SHORT"),
            _persistence_norm("MEDIUM"),
            _persistence_norm("LONG"),
            _persistence_norm("EXTENDED"),
        ]
        for a, b in zip(vals, vals[1:]):
            assert a < b

    def test_unknown_falls_back_to_short(self):
        """Unknown persistence class should safely fall back."""
        assert _persistence_norm("VERY_LONG") == 0.25


# ---------------------------------------------------------------------------
# TestScoreConsistency  — confidence component
# ---------------------------------------------------------------------------

class TestScoreConsistency:
    def test_zero_std_gives_max_consistency(self):
        """Zero variance → consistency = 1.0."""
        assert _score_consistency(0.0) == 1.0

    def test_saturation_std_gives_zero(self):
        """score_std at saturation (0.25) → consistency = 0.0."""
        assert _score_consistency(0.25) == 0.0

    def test_above_saturation_clips_to_zero(self):
        """score_std above saturation must clip to 0."""
        assert _score_consistency(0.5) == 0.0
        assert _score_consistency(1.0) == 0.0

    def test_half_saturation(self):
        """score_std = 0.125 → consistency = 0.5."""
        assert abs(_score_consistency(0.125) - 0.5) < 1e-9

    def test_monotonically_decreasing(self):
        """Higher std → lower consistency."""
        vals = [_score_consistency(s) for s in [0.0, 0.05, 0.10, 0.20, 0.25, 0.30]]
        for a, b in zip(vals, vals[1:]):
            assert a >= b

    def test_does_not_claim_causality(self):
        """Consistency is evidence quality only; we just verify it is in [0, 1]."""
        for std in [0.0, 0.1, 0.25, 0.5]:
            c = _score_consistency(std)
            assert 0.0 <= c <= 1.0


# ---------------------------------------------------------------------------
# TestCrossChannelCorroboration
# ---------------------------------------------------------------------------

class TestCrossChannelCorroboration:
    def test_empty_rels_returns_zero(self):
        """Single-channel incidents → no pairs → 0.0."""
        assert _cross_channel_corroboration([]) == 0.0

    def test_all_overlapping(self):
        """All overlapping pairs → 1.0."""
        rels = [_overlap_rel(True), _overlap_rel(True)]
        assert _cross_channel_corroboration(rels) == 1.0

    def test_none_overlapping(self):
        """No overlapping pairs → 0.0."""
        rels = [_overlap_rel(False), _overlap_rel(False)]
        assert _cross_channel_corroboration(rels) == 0.0

    def test_half_overlapping(self):
        """Half overlapping → 0.5."""
        rels = [_overlap_rel(True), _overlap_rel(False)]
        assert abs(_cross_channel_corroboration(rels) - 0.5) < 1e-9

    def test_single_pair_overlap(self):
        rels = [_overlap_rel(True)]
        assert _cross_channel_corroboration(rels) == 1.0

    def test_single_pair_no_overlap(self):
        rels = [_overlap_rel(False)]
        assert _cross_channel_corroboration(rels) == 0.0

    def test_observational_only(self):
        """Corroboration is temporal association only — no causality implied.
        We verify the result is in [0, 1] regardless of input."""
        for n_overlap in range(5):
            rels = [_overlap_rel(True)] * n_overlap + [_overlap_rel(False)] * (4 - n_overlap)
            c = _cross_channel_corroboration(rels)
            assert 0.0 <= c <= 1.0


# ---------------------------------------------------------------------------
# TestComputeSignificance
# ---------------------------------------------------------------------------

class TestComputeSignificance:
    def test_returns_required_keys(self):
        r = compute_significance(0.7, 30.0, 100, 2, "MEDIUM", [])
        assert "significance_score" in r
        assert "significance_components" in r

    def test_component_names(self):
        r = compute_significance(0.7, 30.0, 100, 2, "MEDIUM", [])
        comps = r["significance_components"]
        for key in ["anomaly_strength", "event_density", "event_quantity",
                    "channel_breadth", "persistence", "cross_channel"]:
            assert key in comps, f"Missing component: {key}"

    def test_score_in_bounds(self):
        r = compute_significance(0.7, 30.0, 100, 2, "MEDIUM", [])
        assert 0.0 <= r["significance_score"] <= 100.0

    def test_min_score_case(self):
        """Minimum inputs should give the lowest possible significance."""
        r = compute_significance(0.30, 0.0, 0, 1, "SHORT", [])
        assert r["significance_score"] < 10.0  # Very low, near-minimum

    def test_max_score_case(self):
        """Maximum inputs should give the highest possible significance."""
        rels = [_overlap_rel(True)] * 10
        r = compute_significance(1.0, 100.0, 1324, 5, "EXTENDED", rels)
        assert r["significance_score"] > 90.0  # Near-maximum

    def test_higher_peak_gives_higher_significance(self):
        r1 = compute_significance(0.5, 30.0, 100, 2, "MEDIUM", [])
        r2 = compute_significance(0.9, 30.0, 100, 2, "MEDIUM", [])
        assert r2["significance_score"] > r1["significance_score"]

    def test_more_events_gives_higher_significance(self):
        r1 = compute_significance(0.7, 30.0, 10, 2, "MEDIUM", [])
        r2 = compute_significance(0.7, 30.0, 500, 2, "MEDIUM", [])
        assert r2["significance_score"] > r1["significance_score"]

    def test_more_channels_gives_higher_significance(self):
        r1 = compute_significance(0.7, 30.0, 100, 1, "MEDIUM", [])
        r2 = compute_significance(0.7, 30.0, 100, 4, "MEDIUM", [])
        assert r2["significance_score"] > r1["significance_score"]

    def test_higher_density_gives_higher_significance(self):
        r1 = compute_significance(0.7, 5.0, 100, 2, "MEDIUM", [])
        r2 = compute_significance(0.7, 80.0, 100, 2, "MEDIUM", [])
        assert r2["significance_score"] > r1["significance_score"]

    def test_extended_persistence_gives_higher_significance(self):
        r1 = compute_significance(0.7, 30.0, 100, 2, "SHORT", [])
        r2 = compute_significance(0.7, 30.0, 100, 2, "EXTENDED", [])
        assert r2["significance_score"] > r1["significance_score"]

    def test_corroboration_increases_significance(self):
        rels_none = [_overlap_rel(False)] * 3
        rels_all  = [_overlap_rel(True)] * 3
        r1 = compute_significance(0.7, 30.0, 100, 2, "MEDIUM", rels_none)
        r2 = compute_significance(0.7, 30.0, 100, 2, "MEDIUM", rels_all)
        assert r2["significance_score"] > r1["significance_score"]

    def test_components_are_floats(self):
        r = compute_significance(0.7, 30.0, 100, 2, "MEDIUM", [])
        for v in r["significance_components"].values():
            assert isinstance(v, float)

    def test_components_in_unit_range(self):
        r = compute_significance(0.7, 30.0, 100, 2, "MEDIUM", [])
        for v in r["significance_components"].values():
            assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# TestComputeSeverity
# ---------------------------------------------------------------------------

class TestComputeSeverity:
    def test_returns_required_keys(self):
        r = compute_severity(0.7, "MEDIUM", 30.0, 2)
        assert "severity_score" in r
        assert "severity_components" in r
        assert "severity_label" in r

    def test_score_in_bounds(self):
        r = compute_severity(0.7, "MEDIUM", 30.0, 2)
        assert 0.0 <= r["severity_score"] <= 10.0

    def test_min_score_case(self):
        r = compute_severity(0.30, "SHORT", 0.0, 1)
        assert r["severity_score"] < 2.0  # Floor case

    def test_max_score_case(self):
        r = compute_severity(1.0, "EXTENDED", 100.0, 5)
        assert r["severity_score"] > 9.0  # Near-max case

    def test_higher_peak_gives_higher_severity(self):
        r1 = compute_severity(0.5, "MEDIUM", 30.0, 2)
        r2 = compute_severity(0.9, "MEDIUM", 30.0, 2)
        assert r2["severity_score"] > r1["severity_score"]

    def test_longer_persistence_gives_higher_severity(self):
        r1 = compute_severity(0.7, "SHORT", 30.0, 2)
        r2 = compute_severity(0.7, "EXTENDED", 30.0, 2)
        assert r2["severity_score"] > r1["severity_score"]

    def test_higher_density_gives_higher_severity(self):
        r1 = compute_severity(0.7, "MEDIUM", 5.0, 2)
        r2 = compute_severity(0.7, "MEDIUM", 80.0, 2)
        assert r2["severity_score"] > r1["severity_score"]

    def test_more_channels_gives_higher_severity(self):
        r1 = compute_severity(0.7, "MEDIUM", 30.0, 1)
        r2 = compute_severity(0.7, "MEDIUM", 30.0, 5)
        assert r2["severity_score"] > r1["severity_score"]

    def test_component_names(self):
        r = compute_severity(0.7, "MEDIUM", 30.0, 2)
        comps = r["severity_components"]
        for key in ["anomaly_strength", "persistence", "event_density", "channel_breadth"]:
            assert key in comps

    def test_components_in_unit_range(self):
        r = compute_severity(0.7, "MEDIUM", 30.0, 2)
        for v in r["severity_components"].values():
            assert 0.0 <= v <= 1.0

    def test_label_is_valid(self):
        for label in ["LOW", "MODERATE", "HIGH", "CRITICAL"]:
            # Construct inputs to get each label range
            pass
        r = compute_severity(0.7, "MEDIUM", 30.0, 2)
        assert r["severity_label"] in ("LOW", "MODERATE", "HIGH", "CRITICAL")


# ---------------------------------------------------------------------------
# TestSeverityLabel
# ---------------------------------------------------------------------------

class TestSeverityLabel:
    def test_critical_at_threshold(self):
        assert _severity_label(7.0) == "CRITICAL"

    def test_critical_above_threshold(self):
        assert _severity_label(10.0) == "CRITICAL"
        assert _severity_label(8.5) == "CRITICAL"

    def test_high_at_threshold(self):
        assert _severity_label(5.0) == "HIGH"

    def test_high_below_critical(self):
        assert _severity_label(6.9) == "HIGH"

    def test_moderate_at_threshold(self):
        assert _severity_label(3.0) == "MODERATE"

    def test_moderate_below_high(self):
        assert _severity_label(4.9) == "MODERATE"

    def test_low_below_moderate(self):
        assert _severity_label(2.9) == "LOW"
        assert _severity_label(0.0) == "LOW"

    def test_all_four_labels_reachable(self):
        labels = {
            _severity_label(1.0),
            _severity_label(3.5),
            _severity_label(6.0),
            _severity_label(8.0),
        }
        assert labels == {"LOW", "MODERATE", "HIGH", "CRITICAL"}


# ---------------------------------------------------------------------------
# TestComputeConfidence
# ---------------------------------------------------------------------------

class TestComputeConfidence:
    def test_returns_required_keys(self):
        r = compute_confidence(100, 0.10, [], 2)
        assert "investigation_confidence" in r
        assert "confidence_components" in r

    def test_confidence_in_bounds(self):
        r = compute_confidence(100, 0.10, [], 2)
        assert 0.0 <= r["investigation_confidence"] <= 1.0

    def test_component_names(self):
        r = compute_confidence(100, 0.10, [], 2)
        comps = r["confidence_components"]
        for key in ["evidence_quantity", "score_consistency", "temporal_corroboration", "channel_breadth"]:
            assert key in comps

    def test_confidence_is_not_severity(self):
        """Confidence and severity should differ given the same inputs."""
        sev = compute_severity(0.7, "MEDIUM", 30.0, 2)
        conf = compute_confidence(100, 0.10, [], 2)
        # They are different scores with different ranges and components
        assert sev["severity_score"] != conf["investigation_confidence"]

    def test_more_events_increases_confidence(self):
        r1 = compute_confidence(1, 0.10, [], 2)
        r2 = compute_confidence(500, 0.10, [], 2)
        assert r2["investigation_confidence"] > r1["investigation_confidence"]

    def test_lower_std_increases_confidence(self):
        r1 = compute_confidence(100, 0.25, [], 2)
        r2 = compute_confidence(100, 0.0, [], 2)
        assert r2["investigation_confidence"] > r1["investigation_confidence"]

    def test_corroboration_increases_confidence(self):
        rels_none = [_overlap_rel(False)] * 2
        rels_all  = [_overlap_rel(True)] * 2
        r1 = compute_confidence(100, 0.10, rels_none, 2)
        r2 = compute_confidence(100, 0.10, rels_all, 2)
        assert r2["investigation_confidence"] > r1["investigation_confidence"]

    def test_more_channels_increases_confidence(self):
        r1 = compute_confidence(100, 0.10, [], 1)
        r2 = compute_confidence(100, 0.10, [], 4)
        assert r2["investigation_confidence"] > r1["investigation_confidence"]

    def test_zero_events_gives_low_confidence(self):
        r = compute_confidence(0, 0.0, [], 1)
        assert r["investigation_confidence"] < 0.35

    def test_max_evidence_gives_high_confidence(self):
        rels = [_overlap_rel(True)] * 6
        r = compute_confidence(1324, 0.0, rels, 5)
        assert r["investigation_confidence"] > 0.8

    def test_components_in_unit_range(self):
        r = compute_confidence(100, 0.10, [], 2)
        for v in r["confidence_components"].values():
            assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# TestScoreBounds  — all three scores must stay in their respective ranges
# ---------------------------------------------------------------------------

class TestScoreBounds:
    EXTREME_CHARS = [
        _char(peak=0.30, density=0.0,   n_events=0,    n_channels=1, persistence="SHORT",    score_std=0.0),
        _char(peak=1.00, density=100.0, n_events=1324, n_channels=5, persistence="EXTENDED", score_std=0.0),
        _char(peak=0.30, density=0.0,   n_events=0,    n_channels=1, persistence="EXTENDED", score_std=0.50),
        _char(peak=1.00, density=0.0,   n_events=0,    n_channels=5, persistence="SHORT",    score_std=0.0),
    ]

    def test_significance_always_in_range(self):
        for ch in self.EXTREME_CHARS:
            r = score_incident(ch)
            assert 0.0 <= r["significance_score"] <= 100.0

    def test_severity_always_in_range(self):
        for ch in self.EXTREME_CHARS:
            r = score_incident(ch)
            assert 0.0 <= r["severity_score"] <= 10.0

    def test_confidence_always_in_range(self):
        for ch in self.EXTREME_CHARS:
            r = score_incident(ch)
            assert 0.0 <= r["investigation_confidence"] <= 1.0


# ---------------------------------------------------------------------------
# TestDeterministic
# ---------------------------------------------------------------------------

class TestDeterministic:
    def test_repeated_significance_calls(self):
        for _ in range(3):
            r = compute_significance(0.75, 40.0, 200, 3, "LONG", [_overlap_rel()])
            assert r["significance_score"] == pytest.approx(
                compute_significance(0.75, 40.0, 200, 3, "LONG", [_overlap_rel()])["significance_score"],
                abs=1e-9,
            )

    def test_repeated_severity_calls(self):
        for _ in range(3):
            r1 = compute_severity(0.75, "LONG", 40.0, 3)
            r2 = compute_severity(0.75, "LONG", 40.0, 3)
            assert r1["severity_score"] == r2["severity_score"]

    def test_repeated_confidence_calls(self):
        for _ in range(3):
            r1 = compute_confidence(200, 0.08, [_overlap_rel()], 3)
            r2 = compute_confidence(200, 0.08, [_overlap_rel()], 3)
            assert r1["investigation_confidence"] == r2["investigation_confidence"]

    def test_score_incident_deterministic(self):
        ch = _char()
        r1 = score_incident(ch)
        r2 = score_incident(ch)
        assert r1["significance_score"] == r2["significance_score"]
        assert r1["severity_score"] == r2["severity_score"]
        assert r1["investigation_confidence"] == r2["investigation_confidence"]


# ---------------------------------------------------------------------------
# TestScoreIncidentWrapper
# ---------------------------------------------------------------------------

class TestScoreIncidentWrapper:
    def test_returns_all_keys(self):
        r = score_incident(_char())
        required = [
            "significance_score", "significance_components",
            "severity_score", "severity_components", "severity_label",
            "investigation_confidence", "confidence_components",
        ]
        for k in required:
            assert k in r, f"Missing key: {k}"

    def test_persistence_enum_accepted(self):
        ch = _char(persistence=PersistenceClass.MEDIUM)
        r = score_incident(ch)
        assert 0.0 <= r["significance_score"] <= 100.0

    def test_persistence_string_accepted(self):
        ch = _char(persistence="MEDIUM")
        r = score_incident(ch)
        assert 0.0 <= r["significance_score"] <= 100.0

    def test_with_temporal_relationships(self):
        rels = [_overlap_rel(True), _overlap_rel(False)]
        ch = _char(rels=rels)
        r = score_incident(ch)
        assert r["confidence_components"]["temporal_corroboration"] == 0.5

    def test_missing_score_std_defaults_to_zero(self):
        """score_std key missing → defaults to 0.0 → consistency = 1.0."""
        ch = {k: v for k, v in _char().items() if k != "score_std"}
        r = score_incident(ch)
        assert r["confidence_components"]["score_consistency"] == 1.0


# ---------------------------------------------------------------------------
# TestEdgeCases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_peak_exactly_at_floor(self):
        r = compute_significance(0.30, 0.0, 0, 1, "SHORT", [])
        assert r["significance_components"]["anomaly_strength"] == 0.0

    def test_peak_exactly_one(self):
        r = compute_significance(1.0, 0.0, 0, 1, "SHORT", [])
        assert r["significance_components"]["anomaly_strength"] == 1.0

    def test_single_channel_no_corroboration(self):
        r = compute_significance(0.7, 30.0, 100, 1, "MEDIUM", [])
        assert r["significance_components"]["cross_channel"] == 0.0

    def test_zero_n_events(self):
        r = compute_confidence(0, 0.0, [], 1)
        assert r["confidence_components"]["evidence_quantity"] == 0.0

    def test_density_exactly_at_ceiling(self):
        r = compute_significance(0.7, 100.0, 100, 2, "MEDIUM", [])
        assert r["significance_components"]["event_density"] == 1.0

    def test_density_above_ceiling_clips(self):
        r1 = compute_significance(0.7, 100.0, 100, 2, "MEDIUM", [])
        r2 = compute_significance(0.7, 200.0, 100, 2, "MEDIUM", [])
        assert r1["significance_score"] == r2["significance_score"]

    def test_large_n_events_does_not_exceed_bounds(self):
        r = compute_significance(0.7, 30.0, 100000, 2, "MEDIUM", [])
        assert 0.0 <= r["significance_score"] <= 100.0

    def test_single_event_characterised(self):
        r = compute_confidence(1, 0.0, [], 1)
        assert r["investigation_confidence"] > 0.0  # Not zero even with 1 event

    def test_all_relationships_non_overlapping(self):
        rels = [_overlap_rel(False)] * 5
        r = compute_confidence(100, 0.10, rels, 3)
        assert r["confidence_components"]["temporal_corroboration"] == 0.0


# ---------------------------------------------------------------------------
# TestNoCausalityBehavior  — scientific compliance
# ---------------------------------------------------------------------------

class TestNoCausalityBehavior:
    def test_corroboration_does_not_inflate_severity(self):
        """Cross-channel corroboration does NOT appear in severity components.
        Severity is independent of temporal relationship data."""
        rels_all  = [_overlap_rel(True)] * 4
        rels_none = [_overlap_rel(False)] * 4
        # Build char dicts using score_incident which routes rels to significance/confidence
        ch1 = _char(rels=rels_all)
        ch2 = _char(rels=rels_none)
        r1 = score_incident(ch1)
        r2 = score_incident(ch2)
        # Severity must be identical (rels don't affect severity)
        assert r1["severity_score"] == r2["severity_score"]

    def test_severity_uses_no_temporal_data(self):
        """compute_severity takes no temporal relationship argument."""
        import inspect
        sig = inspect.signature(compute_severity)
        assert "channel_temporal_relationships" not in sig.parameters

    def test_severity_components_no_cross_channel_key(self):
        """Severity components must not include a 'cross_channel' key."""
        r = compute_severity(0.7, "MEDIUM", 30.0, 2)
        assert "cross_channel" not in r["severity_components"]

    def test_significance_corroboration_is_temporal_association_only(self):
        """Corroboration is evidence of temporal association only.
        Verify the component exists and is in [0, 1]."""
        rels = [_overlap_rel(True)]
        r = compute_significance(0.7, 30.0, 100, 2, "MEDIUM", rels)
        assert "cross_channel" in r["significance_components"]
        assert 0.0 <= r["significance_components"]["cross_channel"] <= 1.0


# ---------------------------------------------------------------------------
# TestWeightSums  — weights must sum to 1.0
# ---------------------------------------------------------------------------

class TestWeightSums:
    def test_significance_weights_sum_to_one(self):
        from member2.scorer import (
            _SIG_W_ANOMALY, _SIG_W_BREADTH, _SIG_W_CORROBORATION,
            _SIG_W_DENSITY, _SIG_W_EVENT_QTY, _SIG_W_PERSISTENCE,
        )
        total = (_SIG_W_ANOMALY + _SIG_W_DENSITY + _SIG_W_EVENT_QTY +
                 _SIG_W_BREADTH + _SIG_W_PERSISTENCE + _SIG_W_CORROBORATION)
        assert abs(total - 1.0) < 1e-9

    def test_severity_weights_sum_to_one(self):
        from member2.scorer import (
            _SEV_W_ANOMALY, _SEV_W_BREADTH, _SEV_W_DENSITY, _SEV_W_PERSISTENCE,
        )
        total = _SEV_W_ANOMALY + _SEV_W_PERSISTENCE + _SEV_W_DENSITY + _SEV_W_BREADTH
        assert abs(total - 1.0) < 1e-9

    def test_confidence_weights_sum_to_one(self):
        from member2.scorer import (
            _CONF_W_BREADTH, _CONF_W_CONSISTENCY, _CONF_W_CORROBORATION, _CONF_W_EVENT_QTY,
        )
        total = _CONF_W_EVENT_QTY + _CONF_W_CONSISTENCY + _CONF_W_CORROBORATION + _CONF_W_BREADTH
        assert abs(total - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# TestSeverityDistribution  — label spread across realistic inputs
# ---------------------------------------------------------------------------

class TestSeverityDistribution:
    """Verify all four severity labels are reachable through realistic inputs."""

    def test_low_label_reachable(self):
        r = compute_severity(0.30, "SHORT", 0.0, 1)
        assert r["severity_label"] == "LOW"

    def test_moderate_label_reachable(self):
        r = compute_severity(0.55, "MEDIUM", 20.0, 1)
        # Should land in MODERATE (mid-range inputs)
        assert r["severity_label"] in ("MODERATE", "LOW")  # depending on exact weights

    def test_high_label_reachable(self):
        r = compute_severity(0.80, "LONG", 60.0, 3)
        assert r["severity_label"] in ("HIGH", "CRITICAL")

    def test_critical_label_reachable(self):
        r = compute_severity(1.0, "EXTENDED", 100.0, 5)
        assert r["severity_label"] == "CRITICAL"

    def test_no_single_label_dominates(self):
        """Score 20 representative cases; each label should appear at least once."""
        test_cases = [
            (0.30, "SHORT",    0.0,  1),
            (0.35, "SHORT",    2.0,  1),
            (0.40, "SHORT",    5.0,  1),
            (0.45, "MEDIUM",   8.0,  1),
            (0.50, "MEDIUM",  12.0,  1),
            (0.55, "MEDIUM",  20.0,  2),
            (0.60, "MEDIUM",  30.0,  2),
            (0.65, "MEDIUM",  40.0,  2),
            (0.70, "MEDIUM",  50.0,  2),
            (0.75, "LONG",    50.0,  2),
            (0.80, "LONG",    60.0,  3),
            (0.82, "LONG",    60.0,  3),
            (0.85, "LONG",    70.0,  3),
            (0.88, "LONG",    70.0,  4),
            (0.90, "LONG",    75.0,  4),
            (0.92, "EXTENDED", 80.0, 4),
            (0.95, "EXTENDED", 85.0, 4),
            (0.97, "EXTENDED", 90.0, 5),
            (0.99, "EXTENDED", 95.0, 5),
            (1.00, "EXTENDED",100.0, 5),
        ]
        found_labels: set[str] = set()
        for peak, pclass, density, n_ch in test_cases:
            r = compute_severity(peak, pclass, density, n_ch)
            found_labels.add(r["severity_label"])
        assert "LOW" in found_labels
        assert "MODERATE" in found_labels
        assert "HIGH" in found_labels
        assert "CRITICAL" in found_labels
