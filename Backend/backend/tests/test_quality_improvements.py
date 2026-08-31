"""
member2/tests/test_quality_improvements.py
-------------------------------------------
Regression tests for the six quality improvements applied before UI integration.

Fix 1 — Single-channel hypothesis enrichment
Fix 2 — Low score-consistency explanation
Fix 3 — Timeline truncation metadata (timeline_truncated / timeline_shown_count)
Fix 4 — Hypothesis statement deduplication (no per-pair gap redundancy)
Fix 5 — Stable investigation IDs (INV-{sid}, no embedded timestamp)
Fix 6 — Dataset observation note in investigation_summary.json

Real-data tests require data/spacecraft_incidents.csv, data/incidents.csv,
data/anomaly_events.csv to be present.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from member2.hypothesis import SCIENTIFIC_CAVEAT, build_hypothesis
from member2.investigator import investigate_incident
from member2.output_schema import Investigation, InvestigationReport

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_AE_CSV  = _DATA_DIR / "anomaly_events.csv"
_INC_CSV = _DATA_DIR / "incidents.csv"
_SI_CSV  = _DATA_DIR / "spacecraft_incidents.csv"

_DATA_AVAILABLE = _AE_CSV.exists() and _INC_CSV.exists() and _SI_CSV.exists()
_SKIP = pytest.mark.skipif(not _DATA_AVAILABLE, reason="Real OPS-SAT-AD CSV files not found")

# ---------------------------------------------------------------------------
# Minimal fixture helpers (no real CSV needed)
# ---------------------------------------------------------------------------

_BASE_TS = pd.Timestamp("2022-01-01T00:00:00Z")

def _ae(channel="CH_A", segment=1, n=5, score=0.8, value=0.5):
    rows = [{"timestamp": _BASE_TS + pd.Timedelta(seconds=i),
             "channel": channel, "segment": segment, "value": value,
             "anomaly_score": score} for i in range(n)]
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df

def _inc(incident_id="INC_1", channel="CH_A", segment=1, sid=1,
         duration=100.0, n_events=5, peak=0.8, mean=0.6,
         start_off=0, end_off=100):
    return pd.DataFrame([{
        "incident_id": incident_id, "channel": channel, "segment": segment,
        "start_time": _BASE_TS + pd.Timedelta(seconds=start_off),
        "end_time":   _BASE_TS + pd.Timedelta(seconds=end_off),
        "duration_sec": duration, "n_events": n_events,
        "peak_anomaly_score": peak, "mean_anomaly_score": mean,
        "spacecraft_incident_id": sid,
    }])

def _si(sid=1, channels=None, duration=100.0, n_events=5,
        peak=0.8, mean=0.6, n_ch=1, start_off=0, end_off=100):
    if channels is None:
        channels = ["CH_A"]
    return pd.DataFrame([{
        "spacecraft_incident_id": sid,
        "start_time": _BASE_TS + pd.Timedelta(seconds=start_off),
        "end_time":   _BASE_TS + pd.Timedelta(seconds=end_off),
        "duration_sec": duration, "channels_affected": channels,
        "n_channels_affected": n_ch, "n_events_total": n_events,
        "peak_anomaly_score": peak, "mean_anomaly_score": mean,
        "segments_affected": list(range(1, n_ch + 1)),
    }])

def _single_fixtures(n_events=5, score=0.8, duration=100.0):
    ae = _ae(n=n_events, score=score)
    inc = _inc(n_events=n_events, peak=score, duration=duration)
    si  = _si(n_events=n_events, peak=score, duration=duration)
    return ae, inc, si

def _multi_fixtures():
    ae = pd.concat([
        _ae("CH_A", 1, 5, 0.9),
        _ae("CH_B", 2, 3, 0.7) .assign(
            timestamp=lambda df: df["timestamp"] + pd.Timedelta(seconds=10)
        ),
    ], ignore_index=True)
    inc = pd.concat([
        _inc("INC_A", "CH_A", 1, 1, 200.0, 5, 0.9, 0.7, 0, 200),
        _inc("INC_B", "CH_B", 2, 1, 180.0, 3, 0.7, 0.5, 10, 190),
    ], ignore_index=True)
    si = _si(1, ["CH_A", "CH_B"], 200.0, 8, 0.9, 0.7, 2, 0, 200)
    return ae, inc, si


# ==========================================================================
# Fix 1 — Single-channel hypothesis enrichment
# ==========================================================================

class TestFix1SingleChannelEnrichment:
    """Hypothesis for single-channel incidents is now per-incident, not a fixed template."""

    def test_summary_includes_event_count(self):
        ae, inc, si = _single_fixtures(n_events=7)
        r = investigate_incident(1, ae, inc, si)
        summary = r.investigations[0].hypothesis_statements[0]
        assert "7 event(s)" in summary

    def test_summary_includes_duration(self):
        ae, inc, si = _single_fixtures(duration=120.0)
        r = investigate_incident(1, ae, inc, si)
        summary = r.investigations[0].hypothesis_statements[0]
        assert "120 s" in summary

    def test_summary_includes_peak_score(self):
        ae, inc, si = _single_fixtures(score=0.75)
        r = investigate_incident(1, ae, inc, si)
        summary = r.investigations[0].hypothesis_statements[0]
        assert "0.750" in summary

    def test_summary_includes_channel_name(self):
        ae, inc, si = _single_fixtures()
        r = investigate_incident(1, ae, inc, si)
        summary = r.investigations[0].hypothesis_statements[0]
        assert "CH_A" in summary

    def test_observed_evidence_includes_event_density(self):
        ae, inc, si = _single_fixtures()
        r = investigate_incident(1, ae, inc, si)
        stmts = r.investigations[0].hypothesis_statements
        combined = " ".join(stmts).lower()
        assert "events/min" in combined or "density" in combined

    def test_observed_evidence_includes_score_std(self):
        ae, inc, si = _single_fixtures()
        r = investigate_incident(1, ae, inc, si)
        stmts = r.investigations[0].hypothesis_statements
        combined = " ".join(stmts).lower()
        assert "std" in combined or "variability" in combined

    def test_observed_evidence_includes_severity(self):
        ae, inc, si = _single_fixtures()
        r = investigate_incident(1, ae, inc, si)
        stmts = r.investigations[0].hypothesis_statements
        combined = " ".join(stmts).lower()
        assert "severity" in combined

    def test_observed_evidence_includes_persistence(self):
        ae, inc, si = _single_fixtures(duration=400.0)
        r = investigate_incident(1, ae, inc, si)
        stmts = r.investigations[0].hypothesis_statements
        combined = " ".join(stmts).lower()
        assert "long" in combined or "medium" in combined or "short" in combined or "extended" in combined

    def test_two_different_incidents_have_different_summaries(self):
        """After Fix 1, summaries must differ when incident parameters differ."""
        ae1, inc1, si1 = _single_fixtures(n_events=3, score=0.5, duration=40.0)
        ae2, inc2, si2 = _single_fixtures(n_events=100, score=0.99, duration=600.0)
        r1 = investigate_incident(1, ae1, inc1, si1)
        r2 = investigate_incident(1, ae2, inc2, si2)
        s1 = r1.investigations[0].hypothesis_statements[0]
        s2 = r2.investigations[0].hypothesis_statements[0]
        assert s1 != s2, "Different incidents must produce different hypothesis summaries"

    def test_no_causal_language_in_enriched_hypothesis(self):
        ae, inc, si = _single_fixtures()
        r = investigate_incident(1, ae, inc, si)
        text = " ".join(r.investigations[0].hypothesis_statements).lower()
        causal = ["caused by", "root cause", "caused the", "is responsible for"]
        for term in causal:
            assert term not in text, f"Causal term '{term}' found in enriched hypothesis"

    def test_scientific_note_still_present(self):
        ae, inc, si = _single_fixtures()
        r = investigate_incident(1, ae, inc, si)
        inv = r.investigations[0]
        assert "Temporal correlation" in inv.scientific_note

    def test_hypothesis_basis_still_includes_channel_ref(self):
        ae, inc, si = _single_fixtures()
        r = investigate_incident(1, ae, inc, si)
        basis = r.investigations[0].hypothesis_basis
        assert any("CH_A" in b for b in basis)

    def test_multi_channel_unaffected(self):
        """Multi-channel investigations must still produce multi_channel type hypothesis."""
        ae, inc, si = _multi_fixtures()
        r = investigate_incident(1, ae, inc, si)
        inv = r.investigations[0]
        combined = " ".join(inv.hypothesis_statements).lower()
        assert "ch_a" in combined or "ch_b" in combined
        # Must NOT have single-channel boilerplate
        assert "no inter-channel temporal sequence" not in combined

    def test_build_hypothesis_directly_single_channel(self):
        """Unit-level: build_hypothesis single-channel includes enriched fields."""
        char_dict = {
            "spacecraft_incident_id": 42,
            "n_channels_affected": 1,
            "channels_affected": ["CHAN_X"],
            "channel_activation_order": ["CHAN_X"],
            "channel_temporal_relationships": [],
            "channel_incident_ids": ["CHAN_X_1_001"],
            "start_time": datetime(2022, 1, 1, tzinfo=timezone.utc),
            "end_time":   datetime(2022, 1, 1, 0, 2, tzinfo=timezone.utc),
            "n_events_total": 12,
            "duration_sec": 120.0,
            "peak_anomaly_score": 0.85,
            "mean_anomaly_score": 0.60,
            "score_std": 0.15,
            "event_density_per_min": 6.0,
            "persistence_class": "MEDIUM",
            "segment_span": 1,
        }
        scores_dict = {
            "severity_label": "MODERATE",
            "severity_score": 4.5,
            "significance_score": 38.0,
            "investigation_confidence": 0.35,
        }
        hyp = build_hypothesis(char_dict, scores_dict)
        assert hyp["hypothesis_type"] == "single_channel"
        summary = hyp["summary"]
        assert "12 event(s)" in summary
        assert "120 s" in summary
        assert "0.850" in summary
        combined = " ".join(hyp["observed_evidence"])
        assert "6.0 events/min" in combined
        assert "0.150" in combined

    @_SKIP
    def test_real_single_channel_summaries_not_identical(self):
        from member2.loaders import (load_anomaly_events_csv,
                                     load_incidents_csv,
                                     load_spacecraft_incidents_csv)
        ae = load_anomaly_events_csv(_AE_CSV)
        inc = load_incidents_csv(_INC_CSV)
        si = load_spacecraft_incidents_csv(_SI_CSV)
        from member2.generate_investigations import generate_all
        result = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        single_invs = [inv for inv in result.investigations if not inv.is_multi_channel]
        summaries = [inv.hypothesis_statements[0] for inv in single_invs]
        # After Fix 1, single-channel summaries must NOT all be identical
        assert len(set(summaries)) > 1, (
            "All single-channel hypotheses are still identical — Fix 1 not applied"
        )


# ==========================================================================
# Fix 2 — Low score-consistency explanation
# ==========================================================================

class TestFix2ScoreConsistencyExplanation:

    def _make_high_std_char(self, score_std=0.30, n_events=50):
        """Build a single-channel char_dict with given score_std."""
        return {
            "spacecraft_incident_id": 99,
            "n_channels_affected": 1,
            "channels_affected": ["CH_HIGH_STD"],
            "channel_activation_order": ["CH_HIGH_STD"],
            "channel_temporal_relationships": [],
            "channel_incident_ids": ["CH_HIGH_STD_1_001"],
            "start_time": datetime(2022, 1, 1, tzinfo=timezone.utc),
            "end_time":   datetime(2022, 1, 1, 0, 5, tzinfo=timezone.utc),
            "n_events_total": n_events,
            "duration_sec": 300.0,
            "peak_anomaly_score": 1.0,
            "mean_anomaly_score": 0.5,
            "score_std": score_std,
            "event_density_per_min": 10.0,
            "persistence_class": "MEDIUM",
            "segment_span": 1,
        }

    def _scores(self, severity="HIGH"):
        return {
            "severity_label": severity,
            "severity_score": 6.0,
            "significance_score": 55.0,
            "investigation_confidence": 0.28,
        }

    def test_high_std_adds_explanation_to_basis(self):
        char = self._make_high_std_char(score_std=0.30)
        hyp = build_hypothesis(char, self._scores())
        assert len(hyp["score_consistency_basis"]) == 1
        note = hyp["score_consistency_basis"][0]
        assert "0.300" in note or "0.30" in note
        assert "standard deviation" in note.lower() or "variability" in note.lower()

    def test_high_std_explanation_in_investigator_basis(self):
        """The score_consistency_basis must appear in hypothesis_basis from investigator."""
        ae, inc, si = self._high_std_fixtures()
        r = investigate_incident(1, ae, inc, si)
        basis = r.investigations[0].hypothesis_basis
        combined = " ".join(basis).lower()
        assert "standard deviation" in combined or "variability" in combined

    def _high_std_fixtures(self):
        """Build fixtures that produce score_std >= 0.25 via bimodal scores."""
        # Mix of high (1.0) and low (0.0) scores → high std
        import math
        scores_hi = [1.0] * 50
        scores_lo = [0.0] * 50
        all_scores = scores_hi + scores_lo
        rows = []
        for i, sc in enumerate(all_scores):
            rows.append({
                "timestamp": _BASE_TS + pd.Timedelta(seconds=i),
                "channel": "CH_A", "segment": 1,
                "value": float(sc), "anomaly_score": float(sc),
            })
        ae = pd.DataFrame(rows)
        ae["timestamp"] = pd.to_datetime(ae["timestamp"], utc=True)
        inc = _inc(n_events=100, peak=1.0, mean=0.5, duration=100.0)
        si  = _si(n_events=100, peak=1.0, mean=0.5, duration=100.0)
        return ae, inc, si

    def test_low_std_no_explanation(self):
        """When std is low, no score_consistency_basis should be added."""
        char = self._make_high_std_char(score_std=0.10)
        hyp = build_hypothesis(char, self._scores())
        assert hyp["score_consistency_basis"] == []

    def test_threshold_boundary_exactly_025(self):
        """At the threshold (0.25), explanation IS added."""
        char = self._make_high_std_char(score_std=0.25)
        hyp = build_hypothesis(char, self._scores())
        assert len(hyp["score_consistency_basis"]) == 1

    def test_threshold_boundary_just_below_025(self):
        """Just below threshold (0.2499), explanation is NOT added."""
        char = self._make_high_std_char(score_std=0.2499)
        hyp = build_hypothesis(char, self._scores())
        assert hyp["score_consistency_basis"] == []

    def test_explanation_contains_no_causal_language(self):
        char = self._make_high_std_char(score_std=0.35)
        hyp = build_hypothesis(char, self._scores())
        for note in hyp["score_consistency_basis"]:
            assert "caused by" not in note.lower()
            assert "root cause" not in note.lower()

    def test_scientific_caveat_still_last_in_basis(self):
        """Scientific caveat must still be the final item in hypothesis_basis."""
        ae, inc, si = self._high_std_fixtures()
        r = investigate_incident(1, ae, inc, si)
        basis = r.investigations[0].hypothesis_basis
        assert SCIENTIFIC_CAVEAT in basis[-1]

    def test_multi_channel_high_std_also_gets_explanation(self):
        """Fix 2 applies to multi-channel paths too."""
        # Build a 2-channel char with high std
        char = {
            "spacecraft_incident_id": 77,
            "n_channels_affected": 2,
            "channels_affected": ["CH_A", "CH_B"],
            "channel_activation_order": ["CH_A", "CH_B"],
            "channel_temporal_relationships": [{
                "channel_a": "CH_A", "channel_b": "CH_B",
                "temporal_gap_sec": 5.0, "temporal_precedence": "A_before_B",
                "windows_overlap": True,
            }],
            "channel_incident_ids": ["CH_A_1_001", "CH_B_2_001"],
            "start_time": datetime(2022, 1, 1, tzinfo=timezone.utc),
            "end_time":   datetime(2022, 1, 1, 0, 5, tzinfo=timezone.utc),
            "n_events_total": 20,
            "duration_sec": 300.0,
            "score_std": 0.30,
        }
        hyp = build_hypothesis(char, self._scores())
        assert len(hyp["score_consistency_basis"]) == 1

    @_SKIP
    def test_real_score_consistency_basis_present_in_high_std_incidents(self):
        from member2.generate_investigations import generate_all
        result = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        high_std = [inv for inv in result.investigations if inv.score_std >= 0.25]
        assert len(high_std) > 0, "No high-std incidents found in dataset"
        for inv in high_std:
            combined = " ".join(inv.hypothesis_basis).lower()
            assert "standard deviation" in combined or "variability" in combined, (
                f"SID={inv.spacecraft_incident_id} std={inv.score_std:.3f} "
                f"missing score_consistency explanation in hypothesis_basis"
            )


# ==========================================================================
# Fix 3 — Timeline truncation metadata
# ==========================================================================

class TestFix3TimelineTruncation:

    def test_no_truncation_when_events_le_1000(self):
        ae, inc, si = _single_fixtures(n_events=5)
        r = investigate_incident(1, ae, inc, si)
        inv = r.investigations[0]
        assert inv.timeline_truncated is False
        assert inv.timeline_shown_count == 5

    def test_timeline_shown_count_equals_len_timeline(self):
        ae, inc, si = _single_fixtures(n_events=10)
        r = investigate_incident(1, ae, inc, si)
        inv = r.investigations[0]
        assert inv.timeline_shown_count == len(inv.timeline)

    def test_n_events_total_independent_of_truncation(self):
        ae, inc, si = _single_fixtures(n_events=5)
        r = investigate_incident(1, ae, inc, si)
        inv = r.investigations[0]
        assert inv.n_events_total == 5

    def test_schema_fields_present(self):
        """timeline_truncated and timeline_shown_count fields exist in schema."""
        ae, inc, si = _single_fixtures()
        r = investigate_incident(1, ae, inc, si)
        inv = r.investigations[0]
        assert hasattr(inv, "timeline_truncated")
        assert hasattr(inv, "timeline_shown_count")

    def test_timeline_shown_count_non_negative(self):
        # Use a minimal 1-event fixture (0-event produces empty DataFrame
        # without column structure, which the loader rejects)
        ae, inc, si = _single_fixtures(n_events=1)
        r = investigate_incident(1, ae, inc, si)
        assert r.investigations[0].timeline_shown_count >= 0

    def test_pydantic_roundtrip_preserves_truncation_fields(self):
        ae, inc, si = _single_fixtures(n_events=5)
        r = investigate_incident(1, ae, inc, si)
        inv = r.investigations[0]
        dumped = inv.model_dump()
        restored = Investigation.model_validate(dumped)
        assert restored.timeline_truncated == inv.timeline_truncated
        assert restored.timeline_shown_count == inv.timeline_shown_count

    def test_json_serialisation_includes_truncation_fields(self):
        ae, inc, si = _single_fixtures(n_events=5)
        r = investigate_incident(1, ae, inc, si)
        j = json.loads(r.investigations[0].model_dump_json())
        assert "timeline_truncated" in j
        assert "timeline_shown_count" in j
        assert j["timeline_truncated"] is False

    @_SKIP
    def test_real_truncated_incidents_have_flag_set(self):
        from member2.generate_investigations import generate_all
        result = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        truncated = [inv for inv in result.investigations if inv.timeline_truncated]
        not_truncated = [inv for inv in result.investigations if not inv.timeline_truncated]
        # We know 9 incidents have >1000 events in this dataset
        assert len(truncated) >= 9, f"Expected >=9 truncated, got {len(truncated)}"
        for inv in truncated:
            assert inv.n_events_total > inv.timeline_shown_count
            assert inv.timeline_shown_count == len(inv.timeline)
        for inv in not_truncated:
            assert inv.n_events_total == inv.timeline_shown_count

    @_SKIP
    def test_real_sid_988_truncated(self):
        """SID 988 has 1335 events — must be flagged as truncated."""
        from member2.loaders import (load_anomaly_events_csv,
                                     load_incidents_csv,
                                     load_spacecraft_incidents_csv)
        ae = load_anomaly_events_csv(_AE_CSV)
        inc = load_incidents_csv(_INC_CSV)
        si = load_spacecraft_incidents_csv(_SI_CSV)
        r = investigate_incident(988, ae, inc, si)
        inv = r.investigations[0]
        assert inv.timeline_truncated is True
        assert inv.timeline_shown_count == 1000
        assert inv.n_events_total == 1335


# ==========================================================================
# Fix 4 — Hypothesis statement deduplication
# ==========================================================================

class TestFix4HypothesisDeduplication:

    def _two_channel_char(self):
        return {
            "spacecraft_incident_id": 10,
            "n_channels_affected": 2,
            "channels_affected": ["CH_A", "CH_B"],
            "channel_activation_order": ["CH_A", "CH_B"],
            "channel_temporal_relationships": [{
                "channel_a": "CH_A", "channel_b": "CH_B",
                "temporal_gap_sec": 15.0, "temporal_precedence": "A_before_B",
                "windows_overlap": True,
            }],
            "channel_incident_ids": ["CH_A_1_001", "CH_B_1_002"],
            "start_time": datetime(2022, 1, 1, tzinfo=timezone.utc),
            "end_time":   datetime(2022, 1, 1, 0, 5, tzinfo=timezone.utc),
            "score_std": 0.1,
            "n_events_total": 10,
        }

    def test_two_channel_temporal_statements_no_all_pairs_duplication(self):
        """For 2 channels, temporal_relationships should have 1 chain link, not 2 entries."""
        hyp = build_hypothesis(self._two_channel_char(), {})
        # observed_evidence no longer has per-pair gap lines
        obs = hyp["observed_evidence"]
        # Count lines that look like "X preceded Y by Z s."
        pair_gap_lines = [s for s in obs if "preceded" in s and " s." in s]
        assert len(pair_gap_lines) == 0, (
            f"Fix 4: per-pair gap lines should not appear in observed_evidence: {pair_gap_lines}"
        )

    def test_two_channel_temporal_bullets_are_chain_only(self):
        """temporal_relationships list contains exactly n_channels-1 = 1 chain step."""
        hyp = build_hypothesis(self._two_channel_char(), {})
        temporal = hyp["temporal_relationships"]
        # 2 channels → 1 chain link
        assert len(temporal) == 1

    def test_five_channel_temporal_bullets_are_chain_only(self):
        """5 channels → 4 chain links (not C(5,2)=10)."""
        char = {
            "spacecraft_incident_id": 50,
            "n_channels_affected": 5,
            "channels_affected": ["A", "B", "C", "D", "E"],
            "channel_activation_order": ["A", "B", "C", "D", "E"],
            "channel_temporal_relationships": [
                {"channel_a": a, "channel_b": b,
                 "temporal_gap_sec": float(abs(j-i)*5),
                 "temporal_precedence": "A_before_B" if i < j else "simultaneous",
                 "windows_overlap": True}
                for i, a in enumerate(["A","B","C","D","E"])
                for j, b in enumerate(["A","B","C","D","E"])
                if i < j
            ],
            "channel_incident_ids": [f"CH_{c}_1_001" for c in "ABCDE"],
            "start_time": datetime(2022, 1, 1, tzinfo=timezone.utc),
            "end_time":   datetime(2022, 1, 1, 0, 10, tzinfo=timezone.utc),
            "score_std": 0.1,
            "n_events_total": 100,
        }
        hyp = build_hypothesis(char, {})
        assert len(hyp["temporal_relationships"]) == 4, (
            f"Expected 4 chain links (n-1), got {len(hyp['temporal_relationships'])}"
        )

    def test_no_duplicate_statements_in_final_report(self):
        ae, inc, si = _multi_fixtures()
        r = investigate_incident(1, ae, inc, si)
        stmts = r.investigations[0].hypothesis_statements
        assert len(stmts) == len(set(stmts)), "Duplicate hypothesis statements found"

    def test_activation_chain_info_still_present(self):
        """After deduplication, chain link info must still appear in temporal_relationships."""
        hyp = build_hypothesis(self._two_channel_char(), {})
        temporal = hyp["temporal_relationships"]
        combined = " ".join(temporal)
        assert "CH_A" in combined or "CH_B" in combined
        assert "15.0" in combined

    def test_observed_evidence_still_has_activation_order(self):
        """observed_evidence must still describe the activation order."""
        hyp = build_hypothesis(self._two_channel_char(), {})
        combined = " ".join(hyp["observed_evidence"])
        assert "CH_A" in combined
        assert "CH_B" in combined

    @_SKIP
    def test_real_five_channel_statements_count_reduced(self):
        """SID=988 was 18 statements; with Fix 4 should be <=10."""
        from member2.loaders import (load_anomaly_events_csv,
                                     load_incidents_csv,
                                     load_spacecraft_incidents_csv)
        ae = load_anomaly_events_csv(_AE_CSV)
        inc = load_incidents_csv(_INC_CSV)
        si = load_spacecraft_incidents_csv(_SI_CSV)
        r = investigate_incident(988, ae, inc, si)
        inv = r.investigations[0]
        assert len(inv.hypothesis_statements) <= 10, (
            f"Expected <=10 statements (after dedup), got {len(inv.hypothesis_statements)}"
        )
        # No duplicates
        assert len(inv.hypothesis_statements) == len(set(inv.hypothesis_statements))


# ==========================================================================
# Fix 5 — Stable investigation IDs
# ==========================================================================

class TestFix5StableInvestigationIds:

    def test_id_is_inv_sid(self):
        ae, inc, si = _single_fixtures()
        r = investigate_incident(1, ae, inc, si)
        assert r.investigations[0].investigation_id == "INV-1"

    def test_id_is_stable_across_two_calls(self):
        ae, inc, si = _single_fixtures()
        r1 = investigate_incident(1, ae, inc, si)
        r2 = investigate_incident(1, ae, inc, si)
        assert r1.investigations[0].investigation_id == r2.investigations[0].investigation_id

    def test_different_sids_different_ids(self):
        ae = pd.concat([_ae("CH_A", 1, 5, 0.8), _ae("CH_X", 9, 3, 0.5)], ignore_index=True)
        inc = pd.concat([_inc(), _inc("INC_2", "CH_X", 9, 2)], ignore_index=True)
        si  = pd.concat([_si(1), _si(2, ["CH_X"], end_off=50, duration=50.0, n_events=3,
                                      peak=0.5, mean=0.4)], ignore_index=True)
        r1 = investigate_incident(1, ae, inc, si)
        r2 = investigate_incident(2, ae, inc, si)
        assert r1.investigations[0].investigation_id == "INV-1"
        assert r2.investigations[0].investigation_id == "INV-2"
        assert r1.investigations[0].investigation_id != r2.investigations[0].investigation_id

    def test_no_timestamp_embedded_in_id(self):
        ae, inc, si = _single_fixtures()
        r = investigate_incident(1, ae, inc, si)
        inv_id = r.investigations[0].investigation_id
        # Should be exactly "INV-1", no trailing date/time
        assert inv_id == "INV-1", f"Expected 'INV-1', got '{inv_id}'"

    def test_generated_at_still_present(self):
        ae, inc, si = _single_fixtures()
        r = investigate_incident(1, ae, inc, si)
        inv = r.investigations[0]
        assert inv.generated_at is not None
        assert inv.generated_at.tzinfo is not None

    @_SKIP
    def test_real_all_ids_stable_format(self):
        from member2.generate_investigations import generate_all
        result = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        for inv in result.investigations:
            expected = f"INV-{inv.spacecraft_incident_id}"
            assert inv.investigation_id == expected, (
                f"Expected {expected}, got {inv.investigation_id}"
            )

    @_SKIP
    def test_real_ids_unique_and_stable(self):
        from member2.generate_investigations import generate_all
        r1 = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        r2 = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        ids1 = [inv.investigation_id for inv in r1.investigations]
        ids2 = [inv.investigation_id for inv in r2.investigations]
        assert ids1 == ids2, "IDs differ between two runs — not stable"
        assert len(ids1) == len(set(ids1)), "Duplicate IDs found"


# ==========================================================================
# Fix 6 — Dataset observation note
# ==========================================================================

class TestFix6DatasetObservationNote:

    @_SKIP
    def test_summary_contains_dataset_observation(self):
        from member2.generate_investigations import generate_all, build_summary
        result = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        summary = build_summary(result)
        assert "dataset_observation" in summary, "dataset_observation key missing from summary"

    @_SKIP
    def test_dataset_observation_is_non_empty_string(self):
        from member2.generate_investigations import generate_all, build_summary
        result = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        summary = build_summary(result)
        obs = summary["dataset_observation"]
        assert isinstance(obs, str) and len(obs) > 20

    @_SKIP
    def test_dataset_observation_mentions_opssat(self):
        from member2.generate_investigations import generate_all, build_summary
        result = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        summary = build_summary(result)
        obs = summary["dataset_observation"].lower()
        assert "ops-sat" in obs or "opssat" in obs or "dataset observation" in obs.lower()

    @_SKIP
    def test_dataset_observation_does_not_alter_relationship_data(self):
        """Fix 6 must be read-only — no channel_temporal_relationships are changed."""
        from member2.generate_investigations import generate_all, build_summary
        result = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        # Verify a known incident's rels are unchanged
        inv988 = next(inv for inv in result.investigations if inv.spacecraft_incident_id == 988)
        assert len(inv988.channel_temporal_relationships) == 10
        all_overlap = all(
            r["windows_overlap"] for r in inv988.channel_temporal_relationships
        )
        assert all_overlap

    @_SKIP
    def test_summary_json_written_with_observation(self, tmp_path):
        from member2.generate_investigations import generate_all, build_summary, write_outputs
        result = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        summary = build_summary(result)
        _, sum_path = write_outputs(result, summary, tmp_path / "out")
        data = json.loads(sum_path.read_text(encoding="utf-8"))
        assert "dataset_observation" in data

    def test_build_summary_empty_result_has_observation_key(self):
        """build_summary with empty result must still return dataset_observation key."""
        from member2.generate_investigations import GenerationResult, build_summary
        empty = GenerationResult()
        summary = build_summary(empty)
        assert "dataset_observation" in summary

    def test_source_files_unchanged_by_build_summary(self):
        """build_summary is read-only — Member 1 CSV files must not be touched."""
        import hashlib
        from member2.generate_investigations import GenerationResult, build_summary
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in [_AE_CSV, _INC_CSV, _SI_CSV] if p.exists()}
        build_summary(GenerationResult())
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in [_AE_CSV, _INC_CSV, _SI_CSV] if p.exists()}
        assert before == after, "Source CSV files were modified by build_summary"


# ==========================================================================
# Cross-cutting: no regression in scientific safety
# ==========================================================================

class TestScientificSafetyRegression:
    """All improvements must preserve zero-causal-language guarantee."""

    CAUSAL_TERMS = [
        "caused by", "root cause", "caused the", "is responsible for",
        "triggered by", "results in malfunction",
    ]

    def _all_text(self, inv):
        return " ".join([
            inv.scientific_note,
            " ".join(inv.hypothesis_statements),
            " ".join(inv.hypothesis_basis),
            " ".join(inv.mission_impact_basis),
            " ".join(inv.recommended_actions),
        ]).lower()

    def test_single_channel_enriched_no_causal(self):
        ae, inc, si = _single_fixtures()
        r = investigate_incident(1, ae, inc, si)
        text = self._all_text(r.investigations[0])
        for term in self.CAUSAL_TERMS:
            assert term not in text

    def test_high_std_note_no_causal(self):
        ae, inc, si = _single_fixtures(score=0.8)
        # Force high std by mixing scores
        import numpy as np
        scores = ([1.0] * 50) + ([0.0] * 50)
        ae = pd.DataFrame([{
            "timestamp": _BASE_TS + pd.Timedelta(seconds=i),
            "channel": "CH_A", "segment": 1,
            "value": float(sc), "anomaly_score": float(sc),
        } for i, sc in enumerate(scores)])
        ae["timestamp"] = pd.to_datetime(ae["timestamp"], utc=True)
        inc = _inc(n_events=100, peak=1.0, mean=0.5, duration=100.0)
        si  = _si(n_events=100, peak=1.0, mean=0.5, duration=100.0)
        r = investigate_incident(1, ae, inc, si)
        text = self._all_text(r.investigations[0])
        for term in self.CAUSAL_TERMS:
            assert term not in text

    def test_multi_channel_no_causal(self):
        ae, inc, si = _multi_fixtures()
        r = investigate_incident(1, ae, inc, si)
        text = self._all_text(r.investigations[0])
        for term in self.CAUSAL_TERMS:
            assert term not in text

    @_SKIP
    def test_real_all_805_no_causal(self):
        from member2.generate_investigations import generate_all
        result = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        for inv in result.investigations:
            text = self._all_text(inv)
            for term in self.CAUSAL_TERMS:
                assert term not in text, (
                    f"SID={inv.spacecraft_incident_id}: causal term '{term}' found"
                )
