"""
member2/tests/test_schema.py
-----------------------------
Unit tests for the Member 2 input schema / validation layer.
Covers happy-path loading, per-field error cases, and edge cases.

Run from the project root:
    python -m pytest member2/tests/test_schema.py -v
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from member2.schema import AnomalyEvent, AnomalyEventInput, load_anomaly_events

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_FILE = Path("data/mock/anomaly_events.json")


def _make_event(**overrides) -> dict:
    """Return a valid raw anomaly-event dict, with optional field overrides."""
    base = {
        "event_id": "evt_test",
        "timestamp": "2026-08-23T10:00:00Z",
        "channel": "channel_X",
        "anomaly_score": 0.75,
        "raw_value": 55.0,
        "expected_range": [40.0, 60.0],
        "deviation_sigma": 2.1,
        "detection_method": "isolation_forest",
    }
    base.update(overrides)
    return base


def _make_input(**event_overrides) -> dict:
    """Return a valid raw top-level payload dict."""
    return {
        "schema_version": "1.0",
        "generated_at": "2026-08-23T10:00:00Z",
        "source_dataset": "OPS-SAT-AD",
        "events": [_make_event(**event_overrides)],
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_load_mock_file(self):
        """The real mock file should pass validation without errors."""
        data = load_anomaly_events(MOCK_FILE)
        assert isinstance(data, AnomalyEventInput)
        assert len(data.events) == 5

    def test_event_fields_are_parsed(self):
        data = load_anomaly_events(MOCK_FILE)
        evt = data.events[0]
        assert evt.event_id == "evt_001"
        assert isinstance(evt.timestamp, datetime)
        assert evt.timestamp.tzinfo is not None  # timezone-aware
        assert evt.channel == "channel_A"
        assert 0.0 <= evt.anomaly_score <= 1.0
        assert isinstance(evt.raw_value, float)
        assert len(evt.expected_range) == 2
        assert isinstance(evt.deviation_sigma, float)
        assert evt.detection_method == "isolation_forest"

    def test_timestamp_is_utc_aware(self):
        data = load_anomaly_events(MOCK_FILE)
        for evt in data.events:
            assert evt.timestamp.utcoffset().total_seconds() == 0  # type: ignore[union-attr]

    def test_anomaly_event_direct_construction(self):
        evt = AnomalyEvent(**_make_event())
        assert evt.event_id == "evt_test"

    def test_naive_timestamp_gets_utc(self):
        """Naive ISO timestamps (no Z / offset) should be accepted and made UTC."""
        evt = AnomalyEvent(**_make_event(timestamp="2026-08-23T10:00:00"))
        assert evt.timestamp.tzinfo == timezone.utc

    def test_timestamp_with_positive_offset(self):
        evt = AnomalyEvent(**_make_event(timestamp="2026-08-23T12:00:00+02:00"))
        assert evt.timestamp.utcoffset().total_seconds() == 7200  # type: ignore[union-attr]

    def test_source_dataset_present(self):
        data = load_anomaly_events(MOCK_FILE)
        assert data.source_dataset == "OPS-SAT-AD"

    def test_schema_version_default(self):
        """schema_version should default to '1.0' if omitted."""
        payload = _make_input()
        del payload["schema_version"]
        result = AnomalyEventInput.model_validate(payload)
        assert result.schema_version == "1.0"


# ---------------------------------------------------------------------------
# event_id validation
# ---------------------------------------------------------------------------


class TestEventId:
    def test_empty_string_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AnomalyEvent(**_make_event(event_id=""))
        assert "event_id" in str(exc_info.value)

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError):
            AnomalyEvent(**_make_event(event_id="   "))

    def test_whitespace_is_stripped(self):
        evt = AnomalyEvent(**_make_event(event_id="  evt_001  "))
        assert evt.event_id == "evt_001"

    def test_non_string_rejected(self):
        with pytest.raises(ValidationError):
            AnomalyEvent(**_make_event(event_id=123))


# ---------------------------------------------------------------------------
# timestamp validation
# ---------------------------------------------------------------------------


class TestTimestamp:
    def test_invalid_string_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AnomalyEvent(**_make_event(timestamp="not-a-date"))
        assert "timestamp" in str(exc_info.value)

    def test_non_string_non_datetime_rejected(self):
        with pytest.raises(ValidationError):
            AnomalyEvent(**_make_event(timestamp=12345))

    def test_datetime_object_accepted(self):
        dt = datetime(2026, 8, 23, 10, 0, 0, tzinfo=timezone.utc)
        evt = AnomalyEvent(**_make_event(timestamp=dt))
        assert evt.timestamp == dt


# ---------------------------------------------------------------------------
# channel validation
# ---------------------------------------------------------------------------


class TestChannel:
    def test_empty_channel_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AnomalyEvent(**_make_event(channel=""))
        assert "channel" in str(exc_info.value)

    def test_whitespace_channel_rejected(self):
        with pytest.raises(ValidationError):
            AnomalyEvent(**_make_event(channel="  "))


# ---------------------------------------------------------------------------
# anomaly_score validation
# ---------------------------------------------------------------------------


class TestAnomalyScore:
    def test_score_below_zero_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AnomalyEvent(**_make_event(anomaly_score=-0.1))
        assert "anomaly_score" in str(exc_info.value)

    def test_score_above_one_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AnomalyEvent(**_make_event(anomaly_score=1.01))
        assert "anomaly_score" in str(exc_info.value)

    def test_boundary_values_accepted(self):
        AnomalyEvent(**_make_event(anomaly_score=0.0))
        AnomalyEvent(**_make_event(anomaly_score=1.0))

    def test_non_numeric_rejected(self):
        with pytest.raises(ValidationError):
            AnomalyEvent(**_make_event(anomaly_score="high"))


# ---------------------------------------------------------------------------
# raw_value validation
# ---------------------------------------------------------------------------


class TestRawValue:
    def test_integer_coerced_to_float(self):
        evt = AnomalyEvent(**_make_event(raw_value=42))
        assert isinstance(evt.raw_value, float)
        assert evt.raw_value == 42.0

    def test_non_numeric_rejected(self):
        with pytest.raises(ValidationError):
            AnomalyEvent(**_make_event(raw_value="not-a-number"))

    def test_negative_raw_value_accepted(self):
        """Negative sensor readings are physically valid."""
        evt = AnomalyEvent(**_make_event(raw_value=-10.5))
        assert evt.raw_value == -10.5


# ---------------------------------------------------------------------------
# expected_range validation
# ---------------------------------------------------------------------------


class TestExpectedRange:
    def test_non_list_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AnomalyEvent(**_make_event(expected_range="40-60"))
        assert "expected_range" in str(exc_info.value)

    def test_single_element_list_rejected(self):
        with pytest.raises(ValidationError):
            AnomalyEvent(**_make_event(expected_range=[40.0]))

    def test_three_element_list_rejected(self):
        with pytest.raises(ValidationError):
            AnomalyEvent(**_make_event(expected_range=[10.0, 20.0, 30.0]))

    def test_non_numeric_element_rejected(self):
        with pytest.raises(ValidationError):
            AnomalyEvent(**_make_event(expected_range=["low", "high"]))

    def test_inverted_range_rejected(self):
        """Lower bound greater than upper bound should be rejected."""
        with pytest.raises(ValidationError):
            AnomalyEvent(**_make_event(expected_range=[60.0, 40.0]))

    def test_integer_elements_coerced(self):
        evt = AnomalyEvent(**_make_event(expected_range=[40, 60]))
        assert evt.expected_range == (40.0, 60.0)

    def test_equal_bounds_accepted(self):
        """Degenerate range (point) is technically valid."""
        evt = AnomalyEvent(**_make_event(expected_range=[50.0, 50.0]))
        assert evt.expected_range == (50.0, 50.0)


# ---------------------------------------------------------------------------
# deviation_sigma validation
# ---------------------------------------------------------------------------


class TestDeviationSigma:
    def test_non_numeric_rejected(self):
        with pytest.raises(ValidationError):
            AnomalyEvent(**_make_event(deviation_sigma="large"))

    def test_negative_sigma_accepted(self):
        """Negative sigma is uncommon but not physically impossible."""
        evt = AnomalyEvent(**_make_event(deviation_sigma=-1.5))
        assert evt.deviation_sigma == -1.5


# ---------------------------------------------------------------------------
# detection_method validation
# ---------------------------------------------------------------------------


class TestDetectionMethod:
    def test_empty_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            AnomalyEvent(**_make_event(detection_method=""))
        assert "detection_method" in str(exc_info.value)

    def test_whitespace_only_rejected(self):
        with pytest.raises(ValidationError):
            AnomalyEvent(**_make_event(detection_method="  "))

    def test_whitespace_stripped(self):
        evt = AnomalyEvent(**_make_event(detection_method="  lof  "))
        assert evt.detection_method == "lof"


# ---------------------------------------------------------------------------
# AnomalyEventInput container validation
# ---------------------------------------------------------------------------


class TestAnomalyEventInput:
    def test_empty_events_rejected(self):
        payload = _make_input()
        payload["events"] = []
        with pytest.raises(ValidationError) as exc_info:
            AnomalyEventInput.model_validate(payload)
        assert "events" in str(exc_info.value)

    def test_invalid_event_in_list_propagates_error(self):
        payload = _make_input(event_id="")
        with pytest.raises(ValidationError):
            AnomalyEventInput.model_validate(payload)

    def test_generated_at_parsed(self):
        payload = _make_input()
        result = AnomalyEventInput.model_validate(payload)
        assert isinstance(result.generated_at, datetime)

    def test_invalid_generated_at_rejected(self):
        payload = _make_input()
        payload["generated_at"] = "not-a-date"
        with pytest.raises(ValidationError):
            AnomalyEventInput.model_validate(payload)

    def test_empty_source_dataset_rejected(self):
        payload = _make_input()
        payload["source_dataset"] = ""
        with pytest.raises(ValidationError):
            AnomalyEventInput.model_validate(payload)

    def test_multiple_events_all_validated(self):
        payload = _make_input()
        payload["events"] = [_make_event(event_id=f"evt_{i:03d}") for i in range(10)]
        result = AnomalyEventInput.model_validate(payload)
        assert len(result.events) == 10


# ---------------------------------------------------------------------------
# load_anomaly_events integration
# ---------------------------------------------------------------------------


class TestLoadAnomalyEvents:
    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_anomaly_events(tmp_path / "nonexistent.json")

    def test_invalid_json_raises_json_error(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{ not valid json }", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            load_anomaly_events(bad_file)

    def test_valid_custom_file(self, tmp_path):
        payload = _make_input()
        f = tmp_path / "events.json"
        f.write_text(json.dumps(payload), encoding="utf-8")
        result = load_anomaly_events(f)
        assert len(result.events) == 1
        assert result.events[0].event_id == "evt_test"
