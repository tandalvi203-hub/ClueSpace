"""
member2/tests/test_loaders.py
------------------------------
Unit tests for member2/loaders.py.

All tests use small in-memory DataFrames written to temporary CSV files —
the full 158 k-row dataset is never loaded.

Run from the project root:
    python -m pytest member2/tests/test_loaders.py -v
"""

from __future__ import annotations

import io
import math
import textwrap
from pathlib import Path

import pandas as pd
import pytest

from member2.loaders import (
    load_anomaly_events_csv,
    load_incidents_csv,
    load_spacecraft_incidents_csv,
)


# ---------------------------------------------------------------------------
# Fixture helpers — write minimal valid CSVs to tmp_path
# ---------------------------------------------------------------------------

ANOMALY_EVENTS_HEADER = (
    "timestamp,channel,segment,value,anomaly_score,"
    "predicted_anomaly,anomaly,label,train"
)

INCIDENTS_HEADER = (
    "incident_id,channel,segment,start_time,end_time,"
    "duration_sec,n_events,peak_anomaly_score,mean_anomaly_score,"
    "spacecraft_incident_id"
)

SPACECRAFT_INCIDENTS_HEADER = (
    "spacecraft_incident_id,start_time,end_time,duration_sec,"
    "channels_affected,n_channels_affected,n_events_total,"
    "peak_anomaly_score,mean_anomaly_score,segments_affected"
)


def _write_csv(tmp_path: Path, name: str, lines: list[str]) -> Path:
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _ae_file(tmp_path: Path, rows: list[str] | None = None) -> Path:
    default_rows = [
        "2022-06-01T23:42:54.000000Z,CADC0872,1,-2.1487e-05,0.644,1,1,anomaly,1",
        "2022-06-02T00:00:00.000000Z,CADC0886,2,1.5,0.3,0,0,nominal,0",
    ]
    return _write_csv(tmp_path, "anomaly_events.csv", [ANOMALY_EVENTS_HEADER] + (rows or default_rows))


def _inc_file(tmp_path: Path, rows: list[str] | None = None) -> Path:
    default_rows = [
        "INC_001,CADC0872,1,2022-06-01T23:42:54.000000Z,"
        "2022-06-01T23:47:33.000000Z,279.0,280,1.0,0.478,593",
    ]
    return _write_csv(tmp_path, "incidents.csv", [INCIDENTS_HEADER] + (rows or default_rows))


def _si_file(tmp_path: Path, rows: list[str] | None = None) -> Path:
    default_rows = [
        "593,2022-06-01T23:42:54.000000Z,2022-06-01T23:47:33.000000Z,"
        "279.0,CADC0872,1,280,1.0,0.478,1820",
    ]
    return _write_csv(tmp_path, "spacecraft_incidents.csv", [SPACECRAFT_INCIDENTS_HEADER] + (rows or default_rows))


# ---------------------------------------------------------------------------
# 1. Successful loading of all three files
# ---------------------------------------------------------------------------

class TestSuccessfulLoading:
    def test_load_anomaly_events_returns_dataframe(self, tmp_path):
        path = _ae_file(tmp_path)
        df = load_anomaly_events_csv(path)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2

    def test_load_incidents_returns_dataframe(self, tmp_path):
        path = _inc_file(tmp_path)
        df = load_incidents_csv(path)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1

    def test_load_spacecraft_incidents_returns_dataframe(self, tmp_path):
        path = _si_file(tmp_path)
        df = load_spacecraft_incidents_csv(path)
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 1

    def test_pass_through_columns_retained(self, tmp_path):
        """Columns anomaly, label, train must survive loading unchanged."""
        path = _ae_file(tmp_path)
        df = load_anomaly_events_csv(path)
        assert "anomaly" in df.columns
        assert "label" in df.columns
        assert "train" in df.columns

    def test_source_csv_not_modified(self, tmp_path):
        """Verify original file content is unchanged after loading."""
        path = _ae_file(tmp_path)
        original = path.read_text(encoding="utf-8")
        load_anomaly_events_csv(path)
        assert path.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# 2. Timestamp parsing
# ---------------------------------------------------------------------------

class TestTimestampParsing:
    def test_ae_timestamp_is_utc_aware(self, tmp_path):
        path = _ae_file(tmp_path)
        df = load_anomaly_events_csv(path)
        assert df["timestamp"].dt.tz is not None
        assert str(df["timestamp"].dt.tz) == "UTC"

    def test_inc_start_end_timestamps_utc(self, tmp_path):
        path = _inc_file(tmp_path)
        df = load_incidents_csv(path)
        for col in ("start_time", "end_time"):
            assert df[col].dt.tz is not None, f"{col} is not timezone-aware"
            assert str(df[col].dt.tz) == "UTC"

    def test_si_start_end_timestamps_utc(self, tmp_path):
        path = _si_file(tmp_path)
        df = load_spacecraft_incidents_csv(path)
        for col in ("start_time", "end_time"):
            assert df[col].dt.tz is not None
            assert str(df[col].dt.tz) == "UTC"

    def test_ae_malformed_timestamp_raises(self, tmp_path):
        rows = ["NOT-A-DATE,CADC0872,1,0.5,0.3,1,1,anomaly,1"]
        path = _ae_file(tmp_path, rows=rows)
        with pytest.raises(ValueError, match="timestamp"):
            load_anomaly_events_csv(path)

    def test_inc_malformed_timestamp_raises(self, tmp_path):
        rows = ["INC_001,CADC0872,1,BAD_DATE,2022-06-01T23:47:33.000000Z,279.0,280,1.0,0.478,593"]
        path = _inc_file(tmp_path, rows=rows)
        with pytest.raises(ValueError, match="start_time"):
            load_incidents_csv(path)


# ---------------------------------------------------------------------------
# 3. Required-column validation
# ---------------------------------------------------------------------------

class TestRequiredColumnValidation:
    def test_ae_missing_channel_raises(self, tmp_path):
        bad_header = "timestamp,segment,value,anomaly_score"
        path = _write_csv(tmp_path, "ae.csv", [
            bad_header,
            "2022-06-01T23:42:54.000000Z,1,0.5,0.3",
        ])
        with pytest.raises(ValueError, match="channel"):
            load_anomaly_events_csv(path)

    def test_ae_missing_timestamp_raises(self, tmp_path):
        bad_header = "channel,segment,value,anomaly_score"
        path = _write_csv(tmp_path, "ae.csv", [
            bad_header,
            "CADC0872,1,0.5,0.3",
        ])
        with pytest.raises(ValueError, match="timestamp"):
            load_anomaly_events_csv(path)

    def test_inc_missing_spacecraft_incident_id_raises(self, tmp_path):
        bad_header = (
            "incident_id,channel,segment,start_time,end_time,"
            "duration_sec,n_events,peak_anomaly_score,mean_anomaly_score"
        )
        path = _write_csv(tmp_path, "inc.csv", [
            bad_header,
            "INC_001,CADC0872,1,2022-06-01T23:42:54.000000Z,"
            "2022-06-01T23:47:33.000000Z,279.0,280,1.0,0.478",
        ])
        with pytest.raises(ValueError, match="spacecraft_incident_id"):
            load_incidents_csv(path)

    def test_si_missing_channels_affected_raises(self, tmp_path):
        bad_header = (
            "spacecraft_incident_id,start_time,end_time,duration_sec,"
            "n_channels_affected,n_events_total,"
            "peak_anomaly_score,mean_anomaly_score,segments_affected"
        )
        path = _write_csv(tmp_path, "si.csv", [
            bad_header,
            "593,2022-06-01T23:42:54.000000Z,2022-06-01T23:47:33.000000Z,"
            "279.0,1,280,1.0,0.478,1820",
        ])
        with pytest.raises(ValueError, match="channels_affected"):
            load_spacecraft_incidents_csv(path)

    def test_multiple_missing_columns_listed(self, tmp_path):
        path = _write_csv(tmp_path, "ae.csv", [
            "value,anomaly_score",
            "0.5,0.3",
        ])
        with pytest.raises(ValueError) as exc_info:
            load_anomaly_events_csv(path)
        msg = str(exc_info.value)
        assert "timestamp" in msg
        assert "channel" in msg


# ---------------------------------------------------------------------------
# 4. Pipe-delimited channel parsing
# ---------------------------------------------------------------------------

class TestPipeDelimitedChannels:
    def test_single_channel_becomes_list(self, tmp_path):
        path = _si_file(tmp_path)
        df = load_spacecraft_incidents_csv(path)
        assert df["channels_affected"].iloc[0] == ["CADC0872"]

    def test_two_channels_split_correctly(self, tmp_path):
        rows = [
            "593,2022-06-01T23:42:54.000000Z,2022-06-01T23:47:33.000000Z,"
            "279.0,CADC0872|CADC0886,2,280,1.0,0.478,1820|813",
        ]
        path = _si_file(tmp_path, rows=rows)
        df = load_spacecraft_incidents_csv(path)
        assert df["channels_affected"].iloc[0] == ["CADC0872", "CADC0886"]

    def test_three_channels_split_correctly(self, tmp_path):
        rows = [
            "1,2022-01-04T20:04:20.000000Z,2022-01-04T20:05:00.000000Z,"
            "40.0,CADC0872|CADC0886|CADC0873,3,5,0.9,0.7,10|20|30",
        ]
        path = _si_file(tmp_path, rows=rows)
        df = load_spacecraft_incidents_csv(path)
        assert df["channels_affected"].iloc[0] == ["CADC0872", "CADC0886", "CADC0873"]

    def test_channels_whitespace_stripped(self, tmp_path):
        rows = [
            "593,2022-06-01T23:42:54.000000Z,2022-06-01T23:47:33.000000Z,"
            "279.0, CADC0872 | CADC0886 ,2,280,1.0,0.478,1820|813",
        ]
        path = _si_file(tmp_path, rows=rows)
        df = load_spacecraft_incidents_csv(path)
        assert df["channels_affected"].iloc[0] == ["CADC0872", "CADC0886"]


# ---------------------------------------------------------------------------
# 5. Pipe-delimited segment parsing
# ---------------------------------------------------------------------------

class TestPipeDelimitedSegments:
    def test_single_segment_becomes_list(self, tmp_path):
        path = _si_file(tmp_path)
        df = load_spacecraft_incidents_csv(path)
        assert df["segments_affected"].iloc[0] == ["1820"]

    def test_two_segments_split_correctly(self, tmp_path):
        rows = [
            "593,2022-06-01T23:42:54.000000Z,2022-06-01T23:47:33.000000Z,"
            "279.0,CADC0872|CADC0886,2,280,1.0,0.478,1820|813",
        ]
        path = _si_file(tmp_path, rows=rows)
        df = load_spacecraft_incidents_csv(path)
        assert df["segments_affected"].iloc[0] == ["1820", "813"]

    def test_segments_whitespace_stripped(self, tmp_path):
        rows = [
            "593,2022-06-01T23:42:54.000000Z,2022-06-01T23:47:33.000000Z,"
            "279.0,CADC0872,1,280,1.0,0.478, 1820 | 813 ",
        ]
        path = _si_file(tmp_path, rows=rows)
        df = load_spacecraft_incidents_csv(path)
        assert df["segments_affected"].iloc[0] == ["1820", "813"]


# ---------------------------------------------------------------------------
# 6. Referential integrity
# ---------------------------------------------------------------------------

class TestReferentialIntegrity:
    def test_valid_reference_passes(self, tmp_path):
        inc_path = _inc_file(tmp_path)
        si_path = _si_file(tmp_path)
        inc_df = load_incidents_csv(inc_path)
        # Should not raise
        load_spacecraft_incidents_csv(si_path, incidents_df=inc_df)

    def test_orphaned_incident_id_raises(self, tmp_path):
        # incident references spacecraft_incident_id=999, which is absent from si
        inc_rows = [
            "INC_001,CADC0872,1,2022-06-01T23:42:54.000000Z,"
            "2022-06-01T23:47:33.000000Z,279.0,280,1.0,0.478,999",
        ]
        inc_path = _inc_file(tmp_path, rows=inc_rows)
        si_path = _si_file(tmp_path)  # only has id=593
        inc_df = load_incidents_csv(inc_path)
        with pytest.raises(ValueError, match="Referential integrity"):
            load_spacecraft_incidents_csv(si_path, incidents_df=inc_df)

    def test_orphaned_error_mentions_missing_id(self, tmp_path):
        inc_rows = [
            "INC_001,CADC0872,1,2022-06-01T23:42:54.000000Z,"
            "2022-06-01T23:47:33.000000Z,279.0,280,1.0,0.478,42",
        ]
        inc_path = _inc_file(tmp_path, rows=inc_rows)
        si_path = _si_file(tmp_path)
        inc_df = load_incidents_csv(inc_path)
        with pytest.raises(ValueError, match="42"):
            load_spacecraft_incidents_csv(si_path, incidents_df=inc_df)

    def test_no_incidents_df_skips_check(self, tmp_path):
        """Without incidents_df the referential check is skipped entirely."""
        si_path = _si_file(tmp_path)
        df = load_spacecraft_incidents_csv(si_path, incidents_df=None)
        assert len(df) == 1

    def test_multiple_orphans_all_reported(self, tmp_path):
        inc_rows = [
            "INC_001,CADC0872,1,2022-06-01T23:42:54.000000Z,"
            "2022-06-01T23:47:33.000000Z,279.0,280,1.0,0.478,777",
            "INC_002,CADC0872,2,2022-06-02T00:00:00.000000Z,"
            "2022-06-02T00:05:00.000000Z,300.0,100,0.9,0.5,888",
        ]
        inc_path = _inc_file(tmp_path, rows=inc_rows)
        si_path = _si_file(tmp_path)
        inc_df = load_incidents_csv(inc_path)
        with pytest.raises(ValueError, match="Referential integrity"):
            load_spacecraft_incidents_csv(si_path, incidents_df=inc_df)


# ---------------------------------------------------------------------------
# 7. Missing values in required fields
# ---------------------------------------------------------------------------

class TestMissingValues:
    def test_null_channel_in_ae_raises(self, tmp_path):
        rows = [
            "2022-06-01T23:42:54.000000Z,,1,-2.1487e-05,0.644,1,1,anomaly,1",
        ]
        path = _ae_file(tmp_path, rows=rows)
        with pytest.raises(ValueError, match="channel"):
            load_anomaly_events_csv(path)

    def test_null_channel_in_inc_raises(self, tmp_path):
        rows = [
            "INC_001,,1,2022-06-01T23:42:54.000000Z,"
            "2022-06-01T23:47:33.000000Z,279.0,280,1.0,0.478,593",
        ]
        path = _inc_file(tmp_path, rows=rows)
        with pytest.raises(ValueError, match="channel"):
            load_incidents_csv(path)

    def test_null_start_time_in_si_raises(self, tmp_path):
        rows = [
            "593,,2022-06-01T23:47:33.000000Z,"
            "279.0,CADC0872,1,280,1.0,0.478,1820",
        ]
        path = _si_file(tmp_path, rows=rows)
        with pytest.raises(ValueError):
            load_spacecraft_incidents_csv(path)

    def test_null_incident_id_in_inc_raises(self, tmp_path):
        rows = [
            ",CADC0872,1,2022-06-01T23:42:54.000000Z,"
            "2022-06-01T23:47:33.000000Z,279.0,280,1.0,0.478,593",
        ]
        path = _inc_file(tmp_path, rows=rows)
        with pytest.raises(ValueError, match="incident_id"):
            load_incidents_csv(path)


# ---------------------------------------------------------------------------
# 8. NaN / Inf detection in numeric fields
# ---------------------------------------------------------------------------

class TestNaNInfDetection:
    def test_nan_anomaly_score_in_ae_raises(self, tmp_path):
        rows = [
            "2022-06-01T23:42:54.000000Z,CADC0872,1,-2.1487e-05,,1,1,anomaly,1",
        ]
        path = _ae_file(tmp_path, rows=rows)
        with pytest.raises(ValueError):
            load_anomaly_events_csv(path)

    def test_nan_peak_score_in_inc_raises(self, tmp_path):
        rows = [
            "INC_001,CADC0872,1,2022-06-01T23:42:54.000000Z,"
            "2022-06-01T23:47:33.000000Z,279.0,280,,0.478,593",
        ]
        path = _inc_file(tmp_path, rows=rows)
        with pytest.raises(ValueError):
            load_incidents_csv(path)

    def test_inf_value_in_ae_raises(self, tmp_path):
        rows = [
            "2022-06-01T23:42:54.000000Z,CADC0872,1,inf,0.644,1,1,anomaly,1",
        ]
        path = _ae_file(tmp_path, rows=rows)
        with pytest.raises(ValueError, match="Inf"):
            load_anomaly_events_csv(path)

    def test_negative_inf_value_in_ae_raises(self, tmp_path):
        rows = [
            "2022-06-01T23:42:54.000000Z,CADC0872,1,-inf,0.644,1,1,anomaly,1",
        ]
        path = _ae_file(tmp_path, rows=rows)
        with pytest.raises(ValueError, match="Inf"):
            load_anomaly_events_csv(path)

    def test_nan_duration_in_si_raises(self, tmp_path):
        rows = [
            "593,2022-06-01T23:42:54.000000Z,2022-06-01T23:47:33.000000Z,"
            ",CADC0872,1,280,1.0,0.478,1820",
        ]
        path = _si_file(tmp_path, rows=rows)
        with pytest.raises(ValueError):
            load_spacecraft_incidents_csv(path)


# ---------------------------------------------------------------------------
# 9. Malformed input
# ---------------------------------------------------------------------------

class TestMalformedInput:
    def test_file_not_found_ae(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_anomaly_events_csv(tmp_path / "nonexistent.csv")

    def test_file_not_found_inc(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_incidents_csv(tmp_path / "nonexistent.csv")

    def test_file_not_found_si(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_spacecraft_incidents_csv(tmp_path / "nonexistent.csv")

    def test_non_numeric_value_field_in_ae_raises(self, tmp_path):
        rows = [
            "2022-06-01T23:42:54.000000Z,CADC0872,1,NOT_A_NUMBER,0.644,1,1,anomaly,1",
        ]
        path = _ae_file(tmp_path, rows=rows)
        with pytest.raises(ValueError, match="value"):
            load_anomaly_events_csv(path)

    def test_non_numeric_duration_in_si_raises(self, tmp_path):
        rows = [
            "593,2022-06-01T23:42:54.000000Z,2022-06-01T23:47:33.000000Z,"
            "OOPS,CADC0872,1,280,1.0,0.478,1820",
        ]
        path = _si_file(tmp_path, rows=rows)
        with pytest.raises(ValueError):
            load_spacecraft_incidents_csv(path)

    def test_empty_file_raises(self, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text("", encoding="utf-8")
        with pytest.raises((ValueError, pd.errors.EmptyDataError)):
            load_anomaly_events_csv(path)

    def test_header_only_no_rows_loads_empty_df(self, tmp_path):
        """A header-only file should load as an empty DataFrame (0 rows)."""
        path = _write_csv(tmp_path, "ae.csv", [ANOMALY_EVENTS_HEADER])
        df = load_anomaly_events_csv(path)
        assert len(df) == 0

    def test_non_numeric_n_events_in_inc_raises(self, tmp_path):
        rows = [
            "INC_001,CADC0872,1,2022-06-01T23:42:54.000000Z,"
            "2022-06-01T23:47:33.000000Z,279.0,MANY,1.0,0.478,593",
        ]
        path = _inc_file(tmp_path, rows=rows)
        with pytest.raises(ValueError):
            load_incidents_csv(path)


# ---------------------------------------------------------------------------
# 10. Numeric type correctness
# ---------------------------------------------------------------------------

class TestNumericTypes:
    def test_ae_value_is_float(self, tmp_path):
        df = load_anomaly_events_csv(_ae_file(tmp_path))
        assert df["value"].dtype == "float64"

    def test_ae_anomaly_score_is_float(self, tmp_path):
        df = load_anomaly_events_csv(_ae_file(tmp_path))
        assert df["anomaly_score"].dtype == "float64"

    def test_ae_segment_is_integer(self, tmp_path):
        df = load_anomaly_events_csv(_ae_file(tmp_path))
        assert pd.api.types.is_integer_dtype(df["segment"])

    def test_inc_duration_is_float(self, tmp_path):
        df = load_incidents_csv(_inc_file(tmp_path))
        assert df["duration_sec"].dtype == "float64"

    def test_inc_n_events_is_integer(self, tmp_path):
        df = load_incidents_csv(_inc_file(tmp_path))
        assert pd.api.types.is_integer_dtype(df["n_events"])

    def test_si_duration_is_float(self, tmp_path):
        df = load_spacecraft_incidents_csv(_si_file(tmp_path))
        assert df["duration_sec"].dtype == "float64"

    def test_si_n_channels_is_integer(self, tmp_path):
        df = load_spacecraft_incidents_csv(_si_file(tmp_path))
        assert pd.api.types.is_integer_dtype(df["n_channels_affected"])
