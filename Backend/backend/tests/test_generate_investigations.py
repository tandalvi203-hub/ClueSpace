"""
member2/tests/test_generate_investigations.py
----------------------------------------------
Tests for member2/generate_investigations.py.

Verifies:
    1.  All 805 spacecraft incidents are processed
    2.  No duplicate investigation IDs
    3.  Valid schema for every report (Pydantic round-trip)
    4.  Stable ordering by spacecraft_incident_id ascending
    5.  Severity distribution covers expected labels
    6.  Output files are created in the correct location
    7.  Deterministic regeneration (identical scores on two runs)
    8.  No source CSV files are modified

All tests that touch the real data files are guarded with a skipif that checks
for the existence of the three CSV files.  This ensures the test suite
remains runnable in CI environments where the data files are not present.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest

from member2.generate_investigations import (
    GenerationResult,
    build_summary,
    generate_all,
    write_outputs,
)
from member2.output_schema import (
    SCHEMA_VERSION,
    SCIENTIFIC_NOTE,
    Investigation,
    InvestigationReport,
    MissionImpactLevel,
)

# ---------------------------------------------------------------------------
# Data file paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _PROJECT_ROOT / "data"
_AE_CSV = _DATA_DIR / "anomaly_events.csv"
_INC_CSV = _DATA_DIR / "incidents.csv"
_SI_CSV = _DATA_DIR / "spacecraft_incidents.csv"

_DATA_AVAILABLE = _AE_CSV.exists() and _INC_CSV.exists() and _SI_CSV.exists()
_SKIP_NO_DATA = pytest.mark.skipif(
    not _DATA_AVAILABLE,
    reason="Real OPS-SAT-AD CSV files not found in data/",
)

# Expected total
_EXPECTED_COUNT = 805

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def result() -> GenerationResult:
    """Run generate_all() once for the entire module."""
    return generate_all(_AE_CSV, _INC_CSV, _SI_CSV)


@pytest.fixture(scope="module")
def summary(result: GenerationResult) -> dict:
    return build_summary(result)


@pytest.fixture(scope="module")
def written_paths(result: GenerationResult, summary: dict, tmp_path_factory) -> tuple[Path, Path]:
    """Write outputs to a temporary directory shared across the module."""
    out_dir = tmp_path_factory.mktemp("outputs")
    return write_outputs(result, summary, out_dir)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _csv_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# 1. All 805 incidents processed
# ---------------------------------------------------------------------------

@_SKIP_NO_DATA
class TestAllIncidentsProcessed:
    def test_count_equals_expected(self, result: GenerationResult):
        assert result.n_processed == _EXPECTED_COUNT, (
            f"Expected {_EXPECTED_COUNT} investigations, got {result.n_processed}"
        )

    def test_investigations_list_length(self, result: GenerationResult):
        assert len(result.investigations) == _EXPECTED_COUNT

    def test_no_generation_errors(self, result: GenerationResult):
        assert result.generation_errors == [], (
            f"Generation errors: {result.generation_errors}"
        )

    def test_all_ids_present(self, result: GenerationResult):
        """Every spacecraft_incident_id from the CSV must appear in the output."""
        import pandas as pd
        si_df = pd.read_csv(_SI_CSV)
        expected_ids = set(int(v) for v in si_df["spacecraft_incident_id"].dropna().unique())
        generated_ids = {inv.spacecraft_incident_id for inv in result.investigations}
        missing = expected_ids - generated_ids
        assert missing == set(), f"Missing IDs: {sorted(missing)[:20]}"

    def test_elapsed_time_recorded(self, result: GenerationResult):
        assert result.elapsed_sec > 0.0


# ---------------------------------------------------------------------------
# 2. No duplicate investigation IDs
# ---------------------------------------------------------------------------

@_SKIP_NO_DATA
class TestNoDuplicates:
    def test_no_duplicate_spacecraft_incident_ids(self, result: GenerationResult):
        ids = [inv.spacecraft_incident_id for inv in result.investigations]
        assert len(ids) == len(set(ids)), "Duplicate spacecraft_incident_id found"

    def test_no_duplicate_investigation_ids(self, result: GenerationResult):
        # Fix 5: investigation_id is now the stable "INV-{sid}" — fully unique
        inv_ids = [inv.investigation_id for inv in result.investigations]
        assert len(inv_ids) == len(set(inv_ids)), (
            "Duplicate investigation_id values found"
        )

    def test_investigation_id_stable_format(self, result: GenerationResult):
        """Fix 5: every investigation_id must be INV-{spacecraft_incident_id}."""
        for inv in result.investigations:
            expected = f"INV-{inv.spacecraft_incident_id}"
            assert inv.investigation_id == expected, (
                f"Expected {expected}, got {inv.investigation_id}"
            )


# ---------------------------------------------------------------------------
# 3. Valid schema for every report
# ---------------------------------------------------------------------------

@_SKIP_NO_DATA
class TestValidSchema:
    def test_all_investigations_are_investigation_instances(self, result: GenerationResult):
        for inv in result.investigations:
            assert isinstance(inv, Investigation), (
                f"SID {inv.spacecraft_incident_id} is not an Investigation"
            )

    def test_schema_roundtrip_for_sampled_incidents(self, result: GenerationResult):
        """Pydantic round-trip for a sample of 10 incidents."""
        sample_step = max(1, len(result.investigations) // 10)
        sample = result.investigations[::sample_step][:10]
        for inv in sample:
            dumped = inv.model_dump()
            recovered = Investigation.model_validate(dumped)
            assert recovered.spacecraft_incident_id == inv.spacecraft_incident_id

    def test_full_report_roundtrip(self, written_paths: tuple[Path, Path]):
        inv_path, _ = written_paths
        raw = json.loads(inv_path.read_text(encoding="utf-8"))
        report = InvestigationReport.model_validate(raw)
        assert len(report.investigations) == _EXPECTED_COUNT

    def test_schema_version_correct(self, written_paths: tuple[Path, Path]):
        inv_path, _ = written_paths
        raw = json.loads(inv_path.read_text(encoding="utf-8"))
        assert raw["schema_version"] == SCHEMA_VERSION

    def test_scientific_note_preserved_in_every_investigation(self, result: GenerationResult):
        for inv in result.investigations:
            assert inv.scientific_note == SCIENTIFIC_NOTE, (
                f"SID {inv.spacecraft_incident_id} missing scientific_note"
            )

    def test_all_significance_scores_in_range(self, result: GenerationResult):
        for inv in result.investigations:
            assert 0.0 <= inv.significance_score <= 100.0, (
                f"SID {inv.spacecraft_incident_id} significance out of range: "
                f"{inv.significance_score}"
            )

    def test_all_severity_scores_in_range(self, result: GenerationResult):
        for inv in result.investigations:
            assert 0.0 <= inv.severity_score <= 10.0, (
                f"SID {inv.spacecraft_incident_id} severity out of range: "
                f"{inv.severity_score}"
            )

    def test_all_confidence_scores_in_range(self, result: GenerationResult):
        for inv in result.investigations:
            assert 0.0 <= inv.investigation_confidence <= 1.0, (
                f"SID {inv.spacecraft_incident_id} confidence out of range: "
                f"{inv.investigation_confidence}"
            )

    def test_no_raw_anomaly_events_in_json(self, written_paths: tuple[Path, Path]):
        """Raw anomaly_events columns absent from InvestigationReport schema must not appear."""
        inv_path, _ = written_paths
        raw_text = inv_path.read_text(encoding="utf-8")
        # Columns that exist in anomaly_events.csv but have NO corresponding field
        # in any output_schema model (TimelineEvent, Investigation, etc.).
        # Note: "label" is intentionally excluded — GraphEdge has a "label" field
        # that is part of the evidence graph schema and will appear in the output.
        forbidden_keys = ['"anomaly"', '"train"', '"predicted_anomaly"',
                          '"deviation_sigma"', '"expected_range"', '"detection_method"']
        for key in forbidden_keys:
            assert key not in raw_text, (
                f"Raw anomaly_events field {key} found in investigations.json"
            )

    def test_traceability_channel_incident_ids_present(self, result: GenerationResult):
        for inv in result.investigations:
            assert isinstance(inv.channel_incident_ids, list)
            assert len(inv.channel_incident_ids) >= 1, (
                f"SID {inv.spacecraft_incident_id} has no channel_incident_ids"
            )


# ---------------------------------------------------------------------------
# 4. Stable ordering by spacecraft_incident_id
# ---------------------------------------------------------------------------

@_SKIP_NO_DATA
class TestStableOrdering:
    def test_ordered_ascending(self, result: GenerationResult):
        ids = [inv.spacecraft_incident_id for inv in result.investigations]
        assert ids == sorted(ids), "Investigations are not sorted by spacecraft_incident_id"

    def test_first_id_is_minimum(self, result: GenerationResult):
        import pandas as pd
        si_df = pd.read_csv(_SI_CSV)
        min_id = int(si_df["spacecraft_incident_id"].min())
        assert result.investigations[0].spacecraft_incident_id == min_id

    def test_last_id_is_maximum(self, result: GenerationResult):
        import pandas as pd
        si_df = pd.read_csv(_SI_CSV)
        max_id = int(si_df["spacecraft_incident_id"].max())
        assert result.investigations[-1].spacecraft_incident_id == max_id

    def test_json_output_ordering_preserved(self, written_paths: tuple[Path, Path]):
        inv_path, _ = written_paths
        raw = json.loads(inv_path.read_text(encoding="utf-8"))
        ids = [inv["spacecraft_incident_id"] for inv in raw["investigations"]]
        assert ids == sorted(ids), "JSON output is not sorted by spacecraft_incident_id"


# ---------------------------------------------------------------------------
# 5. Severity distribution
# ---------------------------------------------------------------------------

@_SKIP_NO_DATA
class TestSeverityDistribution:
    def test_severity_distribution_keys_are_valid_labels(self, summary: dict):
        valid = {level.value for level in MissionImpactLevel}
        for label in summary["severity_distribution"]:
            assert label in valid, f"Unknown severity label: {label}"

    def test_severity_distribution_sums_to_total(self, summary: dict):
        total = sum(summary["severity_distribution"].values())
        assert total == _EXPECTED_COUNT, (
            f"Severity distribution sum {total} != {_EXPECTED_COUNT}"
        )

    def test_at_least_two_severity_levels_present(self, summary: dict):
        assert len(summary["severity_distribution"]) >= 2, (
            "Expected at least 2 distinct severity levels across 805 incidents"
        )

    def test_multi_plus_single_equals_total(self, summary: dict):
        assert (
            summary["multi_channel_count"] + summary["single_channel_count"]
            == _EXPECTED_COUNT
        )

    def test_averages_are_finite_and_positive(self, summary: dict):
        import math
        for key in ("average_significance", "average_severity", "average_confidence"):
            val = summary[key]
            assert math.isfinite(val), f"{key} is not finite: {val}"
            assert val >= 0.0, f"{key} is negative: {val}"

    def test_average_significance_in_range(self, summary: dict):
        assert 0.0 <= summary["average_significance"] <= 100.0

    def test_average_severity_in_range(self, summary: dict):
        assert 0.0 <= summary["average_severity"] <= 10.0

    def test_average_confidence_in_range(self, summary: dict):
        assert 0.0 <= summary["average_confidence"] <= 1.0

    def test_summary_total_incidents_field(self, summary: dict):
        assert summary["total_incidents"] == _EXPECTED_COUNT


# ---------------------------------------------------------------------------
# 6. Output files created
# ---------------------------------------------------------------------------

@_SKIP_NO_DATA
class TestOutputFilesCreated:
    def test_investigations_json_exists(self, written_paths: tuple[Path, Path]):
        inv_path, _ = written_paths
        assert inv_path.exists(), f"{inv_path} was not created"

    def test_summary_json_exists(self, written_paths: tuple[Path, Path]):
        _, sum_path = written_paths
        assert sum_path.exists(), f"{sum_path} was not created"

    def test_investigations_json_is_valid_json(self, written_paths: tuple[Path, Path]):
        inv_path, _ = written_paths
        data = json.loads(inv_path.read_text(encoding="utf-8"))
        assert "investigations" in data

    def test_summary_json_is_valid_json(self, written_paths: tuple[Path, Path]):
        _, sum_path = written_paths
        data = json.loads(sum_path.read_text(encoding="utf-8"))
        assert "total_incidents" in data

    def test_investigations_json_non_empty(self, written_paths: tuple[Path, Path]):
        inv_path, _ = written_paths
        assert inv_path.stat().st_size > 1000

    def test_summary_json_non_empty(self, written_paths: tuple[Path, Path]):
        _, sum_path = written_paths
        assert sum_path.stat().st_size > 50

    def test_output_directory_created_if_missing(self, result: GenerationResult, summary: dict, tmp_path: Path):
        new_dir = tmp_path / "new_output_dir" / "nested"
        assert not new_dir.exists()
        write_outputs(result, summary, new_dir)
        assert new_dir.exists()

    def test_investigations_json_filename(self, written_paths: tuple[Path, Path]):
        inv_path, _ = written_paths
        assert inv_path.name == "investigations.json"

    def test_summary_json_filename(self, written_paths: tuple[Path, Path]):
        _, sum_path = written_paths
        assert sum_path.name == "investigation_summary.json"

    def test_investigations_json_count_in_file(self, written_paths: tuple[Path, Path]):
        inv_path, _ = written_paths
        data = json.loads(inv_path.read_text(encoding="utf-8"))
        assert len(data["investigations"]) == _EXPECTED_COUNT

    def test_source_files_recorded_in_envelope(self, written_paths: tuple[Path, Path]):
        inv_path, _ = written_paths
        data = json.loads(inv_path.read_text(encoding="utf-8"))
        sf = data["source_files"]
        assert "anomaly_events" in sf
        assert "incidents" in sf
        assert "spacecraft_incidents" in sf

    def test_dataset_stats_in_envelope(self, written_paths: tuple[Path, Path]):
        inv_path, _ = written_paths
        data = json.loads(inv_path.read_text(encoding="utf-8"))
        ds = data["dataset_stats"]
        assert ds["total_spacecraft_incidents"] == _EXPECTED_COUNT
        assert ds["total_channel_incidents"] > 0
        assert ds["total_anomaly_events"] > 0


# ---------------------------------------------------------------------------
# 7. Deterministic regeneration
# ---------------------------------------------------------------------------

@_SKIP_NO_DATA
class TestDeterministicRegeneration:
    def test_same_scores_on_second_run(self):
        """Two separate generate_all() calls must produce identical numeric scores."""
        r1 = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        r2 = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)

        assert len(r1.investigations) == len(r2.investigations)

        for inv1, inv2 in zip(r1.investigations, r2.investigations):
            assert inv1.spacecraft_incident_id == inv2.spacecraft_incident_id
            assert inv1.significance_score == inv2.significance_score, (
                f"SID {inv1.spacecraft_incident_id}: significance mismatch"
            )
            assert inv1.severity_score == inv2.severity_score, (
                f"SID {inv1.spacecraft_incident_id}: severity mismatch"
            )
            assert inv1.investigation_confidence == inv2.investigation_confidence, (
                f"SID {inv1.spacecraft_incident_id}: confidence mismatch"
            )

    def test_same_hypothesis_statements_on_second_run(self):
        r1 = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        r2 = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)

        # Spot-check first and last incident
        assert (r1.investigations[0].hypothesis_statements
                == r2.investigations[0].hypothesis_statements)
        assert (r1.investigations[-1].hypothesis_statements
                == r2.investigations[-1].hypothesis_statements)

    def test_same_graph_structure_on_second_run(self):
        r1 = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        r2 = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)

        # Spot-check node IDs for first and last incident
        for i in [0, -1]:
            ids1 = sorted(n.node_id for n in r1.investigations[i].evidence_graph.nodes)
            ids2 = sorted(n.node_id for n in r2.investigations[i].evidence_graph.nodes)
            assert ids1 == ids2, (
                f"Evidence graph node mismatch for index {i}"
            )

    def test_same_ordering_on_second_run(self):
        r1 = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        r2 = generate_all(_AE_CSV, _INC_CSV, _SI_CSV)

        ids1 = [inv.spacecraft_incident_id for inv in r1.investigations]
        ids2 = [inv.spacecraft_incident_id for inv in r2.investigations]
        assert ids1 == ids2


# ---------------------------------------------------------------------------
# 8. No source CSV modifications
# ---------------------------------------------------------------------------

@_SKIP_NO_DATA
class TestNoSourceCsvModifications:
    """
    Verify that the generation run does not modify the source CSV files.

    Strategy: capture the SHA-256 hash of each CSV before and after a full
    generate_all() run; they must be identical.
    """

    def test_anomaly_events_csv_unchanged(self):
        before = _csv_sha256(_AE_CSV)
        generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        after = _csv_sha256(_AE_CSV)
        assert before == after, "anomaly_events.csv was modified"

    def test_incidents_csv_unchanged(self):
        before = _csv_sha256(_INC_CSV)
        generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        after = _csv_sha256(_INC_CSV)
        assert before == after, "incidents.csv was modified"

    def test_spacecraft_incidents_csv_unchanged(self):
        before = _csv_sha256(_SI_CSV)
        generate_all(_AE_CSV, _INC_CSV, _SI_CSV)
        after = _csv_sha256(_SI_CSV)
        assert before == after, "spacecraft_incidents.csv was modified"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

@_SKIP_NO_DATA
class TestErrorHandling:
    def test_missing_ae_file_raises(self):
        with pytest.raises(FileNotFoundError):
            generate_all(
                ae_path=_DATA_DIR / "does_not_exist.csv",
                inc_path=_INC_CSV,
                si_path=_SI_CSV,
            )

    def test_missing_inc_file_raises(self):
        with pytest.raises(FileNotFoundError):
            generate_all(
                ae_path=_AE_CSV,
                inc_path=_DATA_DIR / "does_not_exist.csv",
                si_path=_SI_CSV,
            )

    def test_missing_si_file_raises(self):
        with pytest.raises(FileNotFoundError):
            generate_all(
                ae_path=_AE_CSV,
                inc_path=_INC_CSV,
                si_path=_DATA_DIR / "does_not_exist.csv",
            )

    def test_build_summary_empty_result(self):
        """build_summary must handle an empty result without dividing by zero."""
        empty = GenerationResult()
        summary = build_summary(empty)
        assert summary["total_incidents"] == 0
        assert summary["average_significance"] == 0.0
        assert summary["average_severity"] == 0.0
        assert summary["average_confidence"] == 0.0
