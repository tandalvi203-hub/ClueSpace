"""
member2/tests/test_characteriser.py
-------------------------------------
Unit tests for member2/characteriser.py.

Covers classify_persistence, get_channel_temporal_relationships,
and get_incident_characterisation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

from member2.characteriser import (
    classify_persistence,
    get_channel_temporal_relationships,
    get_incident_characterisation,
)
from member2.output_schema import PersistenceClass, TimelineEvent


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _ts(offset_sec: int = 0) -> datetime:
    """Return a UTC datetime offset from epoch."""
    return datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset_sec)


def _dt(offset_sec: int = 0) -> str:
    """Return an ISO-8601 UTC string offset from epoch."""
    return _ts(offset_sec).isoformat()


def _make_ae(channel: str, segment: int, timestamp_offset: int, score: float = 0.5, value: float = 1.0) -> dict:
    return {
        "timestamp": _ts(timestamp_offset),
        "channel": channel,
        "segment": segment,
        "anomaly_score": score,
        "value": value,
    }


def _make_inc(incident_id: str, spacecraft_incident_id: int, channel: str, segment: int,
              start_offset: int = 0, end_offset: int = 300, n_events: int = 5,
              peak: float = 0.7, mean: float = 0.5) -> dict:
    return {
        "incident_id": incident_id,
        "spacecraft_incident_id": spacecraft_incident_id,
        "channel": channel,
        "segment": segment,
        "start_time": _ts(start_offset),
        "end_time": _ts(end_offset),
        "duration_sec": float(end_offset - start_offset),
        "n_events": n_events,
        "peak_anomaly_score": peak,
        "mean_anomaly_score": mean,
    }


def _make_si(spacecraft_incident_id: int, channels: list[str], start_offset: int = 0,
             end_offset: int = 300, n_events: int = 5) -> dict:
    all_segs = list(range(1, len(channels) + 1))
    return {
        "spacecraft_incident_id": spacecraft_incident_id,
        "start_time": _ts(start_offset),
        "end_time": _ts(end_offset),
        "duration_sec": float(end_offset - start_offset),
        "channels_affected": channels,
        "n_channels_affected": len(channels),
        "n_events_total": n_events,
        "peak_anomaly_score": 0.7,
        "mean_anomaly_score": 0.5,
        "segments_affected": [str(s) for s in all_segs],
    }


def _char_single():
    """Build DataFrames for a minimal single-channel incident."""
    ae = pd.DataFrame([
        _make_ae("CH_A", 1, 10, score=0.6),
        _make_ae("CH_A", 1, 20, score=0.8),
        _make_ae("CH_A", 1, 30, score=0.7),
    ])
    inc = pd.DataFrame([_make_inc("INC-1", 1, "CH_A", 1, start_offset=10, end_offset=310, n_events=3)])
    si = pd.DataFrame([_make_si(1, ["CH_A"], start_offset=10, end_offset=310, n_events=3)])
    return ae, inc, si


def _char_multi():
    """Build DataFrames for a two-channel incident."""
    ae = pd.DataFrame([
        _make_ae("CH_A", 1, 10, score=0.6),
        _make_ae("CH_A", 1, 20, score=0.8),
        _make_ae("CH_B", 2, 50, score=0.7),
        _make_ae("CH_B", 2, 60, score=0.9),
    ])
    inc = pd.DataFrame([
        _make_inc("INC-1", 1, "CH_A", 1, start_offset=10, end_offset=310, n_events=2),
        _make_inc("INC-2", 1, "CH_B", 2, start_offset=50, end_offset=310, n_events=2),
    ])
    si = pd.DataFrame([_make_si(1, ["CH_A", "CH_B"], start_offset=10, end_offset=310, n_events=4)])
    return ae, inc, si


# ---------------------------------------------------------------------------
# TestBasicStructure
# ---------------------------------------------------------------------------

class TestBasicStructure:
    def test_single_channel_returns_dict(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        assert isinstance(result, dict)

    def test_multi_channel_returns_dict(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        assert isinstance(result, dict)

    def test_all_required_keys_present_single(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        required_keys = [
            "spacecraft_incident_id", "start_time", "end_time", "duration_sec",
            "n_channels_affected", "channels_affected", "channel_activation_order",
            "is_multi_channel", "n_events_total", "event_density_per_min",
            "peak_anomaly_score", "mean_anomaly_score", "score_std",
            "persistence_class", "segment_span", "timeline",
            "channel_incident_ids", "channel_temporal_relationships",
        ]
        for k in required_keys:
            assert k in result, f"Missing key: {k}"

    def test_all_required_keys_present_multi(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        assert "channel_temporal_relationships" in result

    def test_spacecraft_incident_id_preserved(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["spacecraft_incident_id"] == 1


# ---------------------------------------------------------------------------
# TestDuration
# ---------------------------------------------------------------------------

class TestDuration:
    def test_duration_single(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["duration_sec"] == 300.0

    def test_duration_multi(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["duration_sec"] == 300.0

    def test_start_time_is_utc(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["start_time"].tzinfo is not None

    def test_end_time_is_utc(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["end_time"].tzinfo is not None


# ---------------------------------------------------------------------------
# TestEventCount
# ---------------------------------------------------------------------------

class TestEventCount:
    def test_n_events_single(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["n_events_total"] == 3

    def test_n_events_multi(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["n_events_total"] == 4


# ---------------------------------------------------------------------------
# TestEventDensity
# ---------------------------------------------------------------------------

class TestEventDensity:
    def test_density_single(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        # 3 events / (300 sec / 60) = 3 / 5 = 0.6 ev/min
        assert abs(result["event_density_per_min"] - 0.6) < 1e-6

    def test_density_multi(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        # 4 events / (300 sec / 60) = 4 / 5 = 0.8 ev/min
        assert abs(result["event_density_per_min"] - 0.8) < 1e-6

    def test_zero_duration_density_is_zero(self):
        ae = pd.DataFrame([_make_ae("CH_A", 1, 0)])
        inc = pd.DataFrame([_make_inc("INC-1", 1, "CH_A", 1, start_offset=0, end_offset=0, n_events=1)])
        si_row = _make_si(1, ["CH_A"], start_offset=0, end_offset=0, n_events=1)
        si_row["duration_sec"] = 0.0
        si = pd.DataFrame([si_row])
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["event_density_per_min"] == 0.0


# ---------------------------------------------------------------------------
# TestScoreStatistics
# ---------------------------------------------------------------------------

class TestScoreStatistics:
    def test_peak_score_single(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        assert abs(result["peak_anomaly_score"] - 0.8) < 1e-6

    def test_mean_score_single(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        expected_mean = (0.6 + 0.8 + 0.7) / 3
        assert abs(result["mean_anomaly_score"] - expected_mean) < 1e-6

    def test_score_std_single(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        expected_std = float(np.std([0.6, 0.8, 0.7], ddof=1))
        assert abs(result["score_std"] - expected_std) < 1e-6

    def test_peak_score_multi(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        assert abs(result["peak_anomaly_score"] - 0.9) < 1e-6

    def test_mean_score_multi(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        expected_mean = (0.6 + 0.8 + 0.7 + 0.9) / 4
        assert abs(result["mean_anomaly_score"] - expected_mean) < 1e-6

    def test_score_std_multi(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        expected_std = float(np.std([0.6, 0.8, 0.7, 0.9], ddof=1))
        assert abs(result["score_std"] - expected_std) < 1e-6

    def test_single_event_std_is_zero(self):
        ae = pd.DataFrame([_make_ae("CH_A", 1, 10, score=0.5)])
        inc = pd.DataFrame([_make_inc("INC-1", 1, "CH_A", 1, start_offset=10, end_offset=70)])
        si = pd.DataFrame([_make_si(1, ["CH_A"], start_offset=10, end_offset=70, n_events=1)])
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["score_std"] == 0.0


# ---------------------------------------------------------------------------
# TestChannelActivationOrder
# ---------------------------------------------------------------------------

class TestChannelActivationOrder:
    def test_single_channel_activation_order(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["channel_activation_order"] == ["CH_A"]

    def test_multi_channel_activation_order_cha_first(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        # CH_A starts at offset=10, CH_B at offset=50
        assert result["channel_activation_order"][0] == "CH_A"
        assert result["channel_activation_order"][1] == "CH_B"

    def test_activation_order_reversed_when_b_first(self):
        ae = pd.DataFrame([
            _make_ae("CH_B", 2, 5, score=0.6),
            _make_ae("CH_A", 1, 100, score=0.7),
        ])
        inc = pd.DataFrame([
            _make_inc("INC-1", 1, "CH_A", 1, start_offset=100, end_offset=400),
            _make_inc("INC-2", 1, "CH_B", 2, start_offset=5, end_offset=400),
        ])
        si = pd.DataFrame([_make_si(1, ["CH_A", "CH_B"], start_offset=5, end_offset=400)])
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["channel_activation_order"][0] == "CH_B"

    def test_temporal_precedence_gap_seconds(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        rels = result["channel_temporal_relationships"]
        assert len(rels) > 0
        assert rels[0]["temporal_gap_sec"] >= 0.0

    def test_temporal_precedence_label_a_before_b(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        rels = result["channel_temporal_relationships"]
        # CH_A starts before CH_B so precedence should be A_before_B
        assert rels[0]["temporal_precedence"] in ("A_before_B", "simultaneous")


# ---------------------------------------------------------------------------
# TestChannelWindowOverlap
# ---------------------------------------------------------------------------

class TestChannelWindowOverlap:
    def _make_two_channel_si(self, a_start: int, a_end: int, b_start: int, b_end: int):
        ae = pd.DataFrame([
            _make_ae("CH_A", 1, a_start),
            _make_ae("CH_B", 2, b_start),
        ])
        inc = pd.DataFrame([
            _make_inc("INC-1", 1, "CH_A", 1, start_offset=a_start, end_offset=a_end),
            _make_inc("INC-2", 1, "CH_B", 2, start_offset=b_start, end_offset=b_end),
        ])
        overall_start = min(a_start, b_start)
        overall_end = max(a_end, b_end)
        si = pd.DataFrame([_make_si(1, ["CH_A", "CH_B"], start_offset=overall_start, end_offset=overall_end)])
        return ae, inc, si

    def test_overlapping_windows(self):
        ae, inc, si = self._make_two_channel_si(0, 200, 100, 300)
        result = get_incident_characterisation(1, ae, inc, si)
        rels = result["channel_temporal_relationships"]
        assert rels[0]["windows_overlap"] is True

    def test_non_overlapping_but_proximate_windows(self):
        # Gap is 30 sec < 60 sec proximity threshold
        ae, inc, si = self._make_two_channel_si(0, 100, 130, 200)
        result = get_incident_characterisation(1, ae, inc, si)
        rels = result["channel_temporal_relationships"]
        assert rels[0]["windows_overlap"] is True

    def test_non_overlapping_and_non_proximate_windows(self):
        # Gap is 200 sec > 60 sec proximity threshold
        ae, inc, si = self._make_two_channel_si(0, 100, 300, 400)
        result = get_incident_characterisation(1, ae, inc, si)
        rels = result["channel_temporal_relationships"]
        assert rels[0]["windows_overlap"] is False


# ---------------------------------------------------------------------------
# TestPersistenceClassification
# ---------------------------------------------------------------------------

class TestPersistenceClassification:
    def test_short_boundary_zero(self):
        assert classify_persistence(0) == PersistenceClass.SHORT

    def test_short_just_below_60(self):
        assert classify_persistence(59.9) == PersistenceClass.SHORT

    def test_medium_at_60(self):
        assert classify_persistence(60) == PersistenceClass.MEDIUM

    def test_medium_at_299(self):
        assert classify_persistence(299) == PersistenceClass.MEDIUM

    def test_long_at_300(self):
        assert classify_persistence(300) == PersistenceClass.LONG

    def test_long_at_899(self):
        assert classify_persistence(899) == PersistenceClass.LONG

    def test_extended_at_900(self):
        assert classify_persistence(900) == PersistenceClass.EXTENDED

    def test_extended_large(self):
        assert classify_persistence(10000) == PersistenceClass.EXTENDED

    def test_negative_raises(self):
        with pytest.raises(ValueError):
            classify_persistence(-1)

    def test_inf_raises(self):
        import math
        with pytest.raises(ValueError):
            classify_persistence(math.inf)

    def test_short_in_characterisation(self):
        ae, inc, si = _char_single()
        # duration 300 sec → LONG
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["persistence_class"] == PersistenceClass.LONG

    def test_medium_in_characterisation(self):
        # Build a 60-sec incident
        ae = pd.DataFrame([_make_ae("CH_A", 1, 0)])
        inc = pd.DataFrame([_make_inc("INC-1", 1, "CH_A", 1, start_offset=0, end_offset=60)])
        si_row = _make_si(1, ["CH_A"], start_offset=0, end_offset=60, n_events=1)
        si_row["duration_sec"] = 60.0
        si = pd.DataFrame([si_row])
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["persistence_class"] == PersistenceClass.MEDIUM

    def test_long_in_characterisation(self):
        ae = pd.DataFrame([_make_ae("CH_A", 1, 0)])
        inc = pd.DataFrame([_make_inc("INC-1", 1, "CH_A", 1, start_offset=0, end_offset=300)])
        si_row = _make_si(1, ["CH_A"], start_offset=0, end_offset=300, n_events=1)
        si_row["duration_sec"] = 300.0
        si = pd.DataFrame([si_row])
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["persistence_class"] == PersistenceClass.LONG

    def test_extended_in_characterisation(self):
        ae = pd.DataFrame([_make_ae("CH_A", 1, 0)])
        inc = pd.DataFrame([_make_inc("INC-1", 1, "CH_A", 1, start_offset=0, end_offset=900)])
        si_row = _make_si(1, ["CH_A"], start_offset=0, end_offset=900, n_events=1)
        si_row["duration_sec"] = 900.0
        si = pd.DataFrame([si_row])
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["persistence_class"] == PersistenceClass.EXTENDED


# ---------------------------------------------------------------------------
# TestZeroDuration
# ---------------------------------------------------------------------------

class TestZeroDuration:
    def test_zero_duration_no_crash(self):
        ae = pd.DataFrame([_make_ae("CH_A", 1, 0)])
        inc = pd.DataFrame([_make_inc("INC-1", 1, "CH_A", 1, start_offset=0, end_offset=0)])
        si_row = _make_si(1, ["CH_A"], start_offset=0, end_offset=0, n_events=1)
        si_row["duration_sec"] = 0.0
        si = pd.DataFrame([si_row])
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["event_density_per_min"] == 0.0


# ---------------------------------------------------------------------------
# TestSegmentSpan
# ---------------------------------------------------------------------------

class TestSegmentSpan:
    def test_single_segment(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["segment_span"] == 1

    def test_multi_segment_from_multi_channel(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["segment_span"] == 2

    def test_three_segments(self):
        ae = pd.DataFrame([
            _make_ae("CH_A", 1, 0),
            _make_ae("CH_B", 2, 10),
            _make_ae("CH_C", 3, 20),
        ])
        inc = pd.DataFrame([
            _make_inc("INC-1", 1, "CH_A", 1, 0, 300),
            _make_inc("INC-2", 1, "CH_B", 2, 10, 300),
            _make_inc("INC-3", 1, "CH_C", 3, 20, 300),
        ])
        si = pd.DataFrame([_make_si(1, ["CH_A", "CH_B", "CH_C"], 0, 300, 3)])
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["segment_span"] == 3


# ---------------------------------------------------------------------------
# TestDeterministicOrdering
# ---------------------------------------------------------------------------

class TestDeterministicOrdering:
    def test_same_start_time_alphabetic_order(self):
        ae = pd.DataFrame([
            _make_ae("CH_Z", 2, 0),
            _make_ae("CH_A", 1, 0),
        ])
        inc = pd.DataFrame([
            _make_inc("INC-1", 1, "CH_Z", 2, start_offset=0, end_offset=300),
            _make_inc("INC-2", 1, "CH_A", 1, start_offset=0, end_offset=300),
        ])
        si = pd.DataFrame([_make_si(1, ["CH_A", "CH_Z"], 0, 300)])
        result = get_incident_characterisation(1, ae, inc, si)
        # Both start at the same time; alphabetic tiebreak → CH_A first
        assert result["channel_activation_order"][0] == "CH_A"

    def test_repeated_calls_same_result(self):
        ae, inc, si = _char_multi()
        r1 = get_incident_characterisation(1, ae, inc, si)
        r2 = get_incident_characterisation(1, ae, inc, si)
        assert r1["channel_activation_order"] == r2["channel_activation_order"]
        assert r1["n_events_total"] == r2["n_events_total"]


# ---------------------------------------------------------------------------
# TestValidationErrors
# ---------------------------------------------------------------------------

class TestValidationErrors:
    def test_invalid_spacecraft_incident_id(self):
        ae, inc, si = _char_single()
        with pytest.raises(ValueError, match="not found"):
            get_incident_characterisation(999, ae, inc, si)

    def test_missing_column_in_ae(self):
        ae, inc, si = _char_single()
        ae_bad = ae.drop(columns=["anomaly_score"])
        with pytest.raises(ValueError):
            get_incident_characterisation(1, ae_bad, inc, si)

    def test_missing_channel_column_in_ae(self):
        ae, inc, si = _char_single()
        ae_bad = ae.drop(columns=["channel"])
        with pytest.raises(ValueError):
            get_incident_characterisation(1, ae_bad, inc, si)

    def test_missing_column_in_incidents(self):
        ae, inc, si = _char_single()
        inc_bad = inc.drop(columns=["start_time"])
        with pytest.raises(ValueError):
            get_incident_characterisation(1, ae, inc_bad, si)

    def test_missing_spacecraft_incident_id_column_in_incidents(self):
        ae, inc, si = _char_single()
        inc_bad = inc.drop(columns=["spacecraft_incident_id"])
        with pytest.raises(ValueError):
            get_incident_characterisation(1, ae, inc_bad, si)

    def test_no_linked_channel_incidents(self):
        ae, inc, si = _char_single()
        # Replace spacecraft_incident_id with a different value
        inc_bad = inc.copy()
        inc_bad["spacecraft_incident_id"] = 999
        with pytest.raises(ValueError, match="No channel-level incidents"):
            get_incident_characterisation(1, ae, inc_bad, si)

    def test_missing_column_in_si(self):
        ae, inc, si = _char_single()
        si_bad = si.drop(columns=["duration_sec"])
        with pytest.raises(ValueError):
            get_incident_characterisation(1, ae, inc, si_bad)


# ---------------------------------------------------------------------------
# TestTimeline
# ---------------------------------------------------------------------------

class TestTimeline:
    def test_timeline_is_list_of_timeline_events(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        assert isinstance(result["timeline"], list)
        for te in result["timeline"]:
            assert isinstance(te, TimelineEvent)

    def test_timeline_sorted_chronologically(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        tl = result["timeline"]
        for i in range(len(tl) - 1):
            assert tl[i].timestamp <= tl[i + 1].timestamp

    def test_timeline_small_count_not_capped(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        # Only 3 events, well below cap of 1000
        assert len(result["timeline"]) == 3

    def test_timeline_capped_at_1000(self):
        rows = [_make_ae("CH_A", 1, i * 2, score=0.5) for i in range(1500)]
        ae = pd.DataFrame(rows)
        inc = pd.DataFrame([_make_inc("INC-1", 1, "CH_A", 1, start_offset=0, end_offset=3000, n_events=1500)])
        si_row = _make_si(1, ["CH_A"], start_offset=0, end_offset=3000, n_events=1500)
        si_row["duration_sec"] = 3000.0
        si = pd.DataFrame([si_row])
        result = get_incident_characterisation(1, ae, inc, si)
        assert len(result["timeline"]) <= 1000

    def test_timeline_cap_preserves_first_event(self):
        rows = [_make_ae("CH_A", 1, i * 2, score=0.5) for i in range(1500)]
        ae = pd.DataFrame(rows)
        inc = pd.DataFrame([_make_inc("INC-1", 1, "CH_A", 1, start_offset=0, end_offset=3000, n_events=1500)])
        si_row = _make_si(1, ["CH_A"], start_offset=0, end_offset=3000, n_events=1500)
        si_row["duration_sec"] = 3000.0
        si = pd.DataFrame([si_row])
        result = get_incident_characterisation(1, ae, inc, si)
        tl = result["timeline"]
        first_ts = min(r["timestamp"] for _, r in ae.iterrows())
        assert tl[0].timestamp == first_ts

    def test_timeline_cap_preserves_last_event(self):
        rows = [_make_ae("CH_A", 1, i * 2, score=0.5) for i in range(1500)]
        ae = pd.DataFrame(rows)
        inc = pd.DataFrame([_make_inc("INC-1", 1, "CH_A", 1, start_offset=0, end_offset=3000, n_events=1500)])
        si_row = _make_si(1, ["CH_A"], start_offset=0, end_offset=3000, n_events=1500)
        si_row["duration_sec"] = 3000.0
        si = pd.DataFrame([si_row])
        result = get_incident_characterisation(1, ae, inc, si)
        tl = result["timeline"]
        last_ts = max(r["timestamp"] for _, r in ae.iterrows())
        assert tl[-1].timestamp == last_ts


# ---------------------------------------------------------------------------
# TestSimultaneousActivation
# ---------------------------------------------------------------------------

class TestSimultaneousActivation:
    def test_simultaneous_gap_is_zero(self):
        ae = pd.DataFrame([
            _make_ae("CH_A", 1, 0),
            _make_ae("CH_B", 2, 0),  # same time
        ])
        inc = pd.DataFrame([
            _make_inc("INC-1", 1, "CH_A", 1, start_offset=0, end_offset=300),
            _make_inc("INC-2", 1, "CH_B", 2, start_offset=0, end_offset=300),
        ])
        si = pd.DataFrame([_make_si(1, ["CH_A", "CH_B"], 0, 300)])
        result = get_incident_characterisation(1, ae, inc, si)
        rels = result["channel_temporal_relationships"]
        assert rels[0]["temporal_gap_sec"] == 0.0
        assert rels[0]["temporal_precedence"] == "simultaneous"


# ---------------------------------------------------------------------------
# TestTemporalRelationshipsSingleChannel
# ---------------------------------------------------------------------------

class TestTemporalRelationshipsSingleChannel:
    def test_single_channel_returns_empty_list(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["channel_temporal_relationships"] == []

    def test_direct_function_single_channel(self):
        ch_inc = pd.DataFrame([_make_inc("INC-1", 1, "CH_A", 1, 0, 300)])
        rels = get_channel_temporal_relationships(ch_inc)
        assert rels == []


# ---------------------------------------------------------------------------
# TestTraceability
# ---------------------------------------------------------------------------

class TestTraceability:
    def test_channel_incident_ids_present(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        assert isinstance(result["channel_incident_ids"], list)
        assert len(result["channel_incident_ids"]) >= 1

    def test_channel_incident_ids_multi(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        assert len(result["channel_incident_ids"]) == 2

    def test_single_channel_not_multi(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["is_multi_channel"] is False

    def test_multi_channel_is_multi(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["is_multi_channel"] is True

    def test_n_channels_affected_single(self):
        ae, inc, si = _char_single()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["n_channels_affected"] == 1

    def test_n_channels_affected_multi(self):
        ae, inc, si = _char_multi()
        result = get_incident_characterisation(1, ae, inc, si)
        assert result["n_channels_affected"] == 2


# ---------------------------------------------------------------------------
# TestTemporalRelationshipPairCount  (regression for loop-variable mutation bug)
# ---------------------------------------------------------------------------

def _make_ch_inc_df(channels_and_offsets: list[tuple[str, int, int]]) -> pd.DataFrame:
    """
    Build a minimal incidents DataFrame for get_channel_temporal_relationships.

    Each tuple is (channel_name, start_offset_sec, end_offset_sec).
    Segment numbers are assigned sequentially (1, 2, 3, …).
    """
    rows = []
    for idx, (ch, start, end) in enumerate(channels_and_offsets, start=1):
        rows.append(_make_inc(f"INC-{idx}", 1, ch, idx,
                              start_offset=start, end_offset=end))
    return pd.DataFrame(rows)


class TestTemporalRelationshipPairCount:
    """
    Regression tests for the inner-loop mutation bug in
    get_channel_temporal_relationships().

    For N distinct channels the function must return exactly N*(N-1)//2
    unordered pairs — each pair appearing exactly once.
    """

    def test_one_channel_zero_pairs(self):
        df = _make_ch_inc_df([("CH_A", 0, 300)])
        rels = get_channel_temporal_relationships(df)
        assert len(rels) == 0

    def test_two_channels_one_pair(self):
        df = _make_ch_inc_df([("CH_A", 0, 300), ("CH_B", 10, 300)])
        rels = get_channel_temporal_relationships(df)
        assert len(rels) == 1

    def test_three_channels_three_pairs(self):
        df = _make_ch_inc_df([
            ("CH_A", 0, 300),
            ("CH_B", 10, 300),
            ("CH_C", 20, 300),
        ])
        rels = get_channel_temporal_relationships(df)
        assert len(rels) == 3

    def test_four_channels_six_pairs(self):
        df = _make_ch_inc_df([
            ("CH_A", 0, 300),
            ("CH_B", 10, 300),
            ("CH_C", 20, 300),
            ("CH_D", 30, 300),
        ])
        rels = get_channel_temporal_relationships(df)
        assert len(rels) == 6

    def test_five_channels_ten_pairs(self):
        df = _make_ch_inc_df([
            ("CH_A", 0, 300),
            ("CH_B", 10, 300),
            ("CH_C", 20, 300),
            ("CH_D", 30, 300),
            ("CH_E", 40, 300),
        ])
        rels = get_channel_temporal_relationships(df)
        assert len(rels) == 10

    def test_no_duplicate_unordered_pairs(self):
        """Every unordered {channel_a, channel_b} pair must appear exactly once."""
        df = _make_ch_inc_df([
            ("CH_A", 0, 300),
            ("CH_B", 10, 300),
            ("CH_C", 20, 300),
            ("CH_D", 30, 300),
            ("CH_E", 40, 300),
        ])
        rels = get_channel_temporal_relationships(df)
        seen: set[frozenset] = set()
        for r in rels:
            pair = frozenset({r["channel_a"], r["channel_b"]})
            assert pair not in seen, f"Duplicate pair: {r['channel_a']} / {r['channel_b']}"
            seen.add(pair)

    def test_chronological_ordering_preserved(self):
        """
        channel_a must always be the earlier-activating channel of the pair.
        If start times are equal, temporal_gap_sec must be 0 and
        temporal_precedence must be 'simultaneous'.
        """
        df = _make_ch_inc_df([
            ("CH_A", 0, 300),   # earliest
            ("CH_B", 50, 300),
            ("CH_C", 100, 300), # latest
        ])
        rels = get_channel_temporal_relationships(df)
        for r in rels:
            assert r["temporal_gap_sec"] >= 0.0, (
                f"Negative gap for {r['channel_a']}/{r['channel_b']}: {r['temporal_gap_sec']}"
            )

        # Check specific pair: CH_A vs CH_C — CH_A must be channel_a
        ac = next(r for r in rels
                  if frozenset({r["channel_a"], r["channel_b"]}) == frozenset({"CH_A", "CH_C"}))
        assert ac["channel_a"] == "CH_A"
        assert ac["channel_b"] == "CH_C"
        assert ac["temporal_precedence"] == "A_before_B"

    def test_overlap_field_present_in_all_pairs(self):
        """Every pair dict must contain the windows_overlap boolean field."""
        df = _make_ch_inc_df([
            ("CH_A", 0, 200),
            ("CH_B", 100, 300),
            ("CH_C", 250, 400),
        ])
        rels = get_channel_temporal_relationships(df)
        for r in rels:
            assert "windows_overlap" in r
            assert isinstance(r["windows_overlap"], bool)

    def test_overlap_true_when_windows_overlap(self):
        """
        CH_A [0, 200] and CH_B [100, 300] overlap directly → windows_overlap True.
        """
        df = _make_ch_inc_df([("CH_A", 0, 200), ("CH_B", 100, 300)])
        rels = get_channel_temporal_relationships(df)
        assert len(rels) == 1
        assert rels[0]["windows_overlap"] is True

    def test_overlap_false_when_far_apart(self):
        """
        CH_A [0, 100] and CH_B [300, 400]: gap = 200 s > 60 s → windows_overlap False.
        """
        df = _make_ch_inc_df([("CH_A", 0, 100), ("CH_B", 300, 400)])
        rels = get_channel_temporal_relationships(df)
        assert len(rels) == 1
        assert rels[0]["windows_overlap"] is False
