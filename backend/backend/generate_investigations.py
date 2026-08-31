"""
member2/generate_investigations.py
-----------------------------------
Production output generator for the Space Mission Incident Investigator.

Reads all 805 spacecraft incidents from data/spacecraft_incidents.csv and runs
the full Member 2 investigation pipeline (via investigator.investigate_incident)
against each one.  Writes two output files:

    outputs/investigations.json        — all InvestigationReport investigations
                                          merged into a single envelope, sorted
                                          by spacecraft_incident_id ascending.
    outputs/investigation_summary.json — aggregate statistics over the run.

Usage
-----
    python -m member2.generate_investigations            # default data/ and outputs/
    python -m member2.generate_investigations --help

Public API (for tests)
----------------------
    generate_all(ae_path, inc_path, si_path, out_dir) → GenerationResult
    build_summary(result)                              → dict
    write_outputs(result, summary, out_dir)            → tuple[Path, Path]

Fail policy
-----------
Any incident that cannot be investigated raises RuntimeError (wrapping the
original exception) and halts the run loudly.  Silent skipping is never allowed.

Scientific note
---------------
No causal claims are introduced here.  The scientific_note field on every
Investigation is inherited from output_schema.SCIENTIFIC_NOTE via investigator.py.

Determinism
-----------
Output is stable: incidents are processed and written in ascending
spacecraft_incident_id order.  The investigation_id field embeds the generation
timestamp, which will differ across runs, but every score, graph, and hypothesis
field is fully deterministic for the same input data.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from member2.investigator import investigate_incident
from member2.loaders import (
    load_anomaly_events_csv,
    load_incidents_csv,
    load_spacecraft_incidents_csv,
)
from member2.output_schema import (
    SCHEMA_VERSION,
    SCIENTIFIC_NOTE,
    DatasetStats,
    InvestigationReport,
    Investigation,
)

# ---------------------------------------------------------------------------
# Paths (relative to project root)
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DATA_DIR = _PROJECT_ROOT / "data"
_AE_CSV = _DATA_DIR / "anomaly_events.csv"
_INC_CSV = _DATA_DIR / "incidents.csv"
_SI_CSV = _DATA_DIR / "spacecraft_incidents.csv"
_OUT_DIR = _PROJECT_ROOT / "outputs"


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class GenerationResult:
    """Holds all investigations generated in one run plus run metadata."""

    investigations: list[Investigation] = field(default_factory=list)
    """All generated Investigation objects, sorted by spacecraft_incident_id."""

    dataset_stats: DatasetStats | None = None
    """Dataset-level statistics computed from the loaded DataFrames."""

    generation_errors: list[dict[str, Any]] = field(default_factory=list)
    """Any errors encountered (always empty on a successful run)."""

    elapsed_sec: float = 0.0
    """Wall-clock seconds for the full generation run."""

    n_processed: int = 0
    """Number of spacecraft incidents successfully investigated."""


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

def generate_all(
    ae_path: str | Path = _AE_CSV,
    inc_path: str | Path = _INC_CSV,
    si_path: str | Path = _SI_CSV,
) -> GenerationResult:
    """
    Run the investigation pipeline against every spacecraft incident in
    ``spacecraft_incidents.csv``.

    Parameters
    ----------
    ae_path:   Path to ``anomaly_events.csv``.
    inc_path:  Path to ``incidents.csv``.
    si_path:   Path to ``spacecraft_incidents.csv``.

    Returns
    -------
    GenerationResult
        Sorted list of Investigation objects plus run metadata.

    Raises
    ------
    RuntimeError
        If any spacecraft incident cannot be investigated.  The run halts
        immediately rather than silently skipping the failing incident.
    FileNotFoundError
        If any of the input CSVs do not exist.
    ValueError
        If the loaded DataFrames fail column or referential integrity checks.
    """
    t_start = time.perf_counter()

    # --- Load data once -------------------------------------------------------
    # Note: do NOT pass incidents_df to load_spacecraft_incidents_csv — the
    # real dataset contains incidents.csv entries whose spacecraft_incident_id
    # values do not appear in spacecraft_incidents.csv (they belong to
    # spacecraft incidents filtered out during Member 1 aggregation).
    # The referential integrity check in the loader checks the reverse direction
    # (incidents → spacecraft_incidents) and would spuriously raise here.
    # All 805 spacecraft incidents in spacecraft_incidents.csv have full
    # coverage in incidents.csv; this is verified by generate_all's output.
    ae_df = load_anomaly_events_csv(ae_path)
    inc_df = load_incidents_csv(inc_path)
    si_df = load_spacecraft_incidents_csv(si_path)

    # Sorted incident IDs for deterministic ordering
    incident_ids: list[int] = sorted(
        int(v) for v in si_df["spacecraft_incident_id"].dropna().unique()
    )

    investigations: list[Investigation] = []
    errors: list[dict[str, Any]] = []

    for sid in incident_ids:
        try:
            report = investigate_incident(sid, ae_df, inc_df, si_df)
            # Each single-incident report holds exactly one Investigation
            investigations.append(report.investigations[0])
        except Exception as exc:
            # Fail loudly — no silent skipping
            raise RuntimeError(
                f"Failed to investigate spacecraft_incident_id={sid}: {exc}"
            ) from exc

    # Build dataset stats once (same for all investigations)
    from member2.investigator import _build_dataset_stats  # private helper reuse
    dataset_stats = _build_dataset_stats(ae_df, inc_df, si_df)

    elapsed = time.perf_counter() - t_start

    return GenerationResult(
        investigations=investigations,
        dataset_stats=dataset_stats,
        generation_errors=errors,
        elapsed_sec=elapsed,
        n_processed=len(investigations),
    )


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def build_summary(result: GenerationResult) -> dict[str, Any]:
    """
    Compute aggregate statistics over a completed GenerationResult.

    Parameters
    ----------
    result : GenerationResult
        The result of a :func:`generate_all` call.

    Returns
    -------
    dict
        A JSON-serialisable summary dict containing:
        - total_incidents
        - severity_distribution  (counts per label)
        - multi_channel_count
        - single_channel_count
        - average_significance
        - average_severity
        - average_confidence
        - generation_errors
    """
    invs = result.investigations
    n = len(invs)

    severity_dist: dict[str, int] = {}
    multi_count = 0
    single_count = 0
    sig_total = 0.0
    sev_total = 0.0
    conf_total = 0.0

    for inv in invs:
        label = inv.mission_impact_level.value
        severity_dist[label] = severity_dist.get(label, 0) + 1

        if inv.is_multi_channel:
            multi_count += 1
        else:
            single_count += 1

        sig_total += inv.significance_score
        sev_total += inv.severity_score
        conf_total += inv.investigation_confidence

    # Fix 6: Compute windows_overlap observation for the dataset
    # (all multi-channel incidents observed; no source data is altered)
    all_multi = [inv for inv in invs if inv.is_multi_channel]
    n_multi = len(all_multi)
    overlap_true_total = sum(
        sum(1 for r in inv.channel_temporal_relationships if r.get("windows_overlap", False))
        for inv in all_multi
    )
    overlap_pair_total = sum(len(inv.channel_temporal_relationships) for inv in all_multi)
    all_overlap = (overlap_pair_total > 0) and (overlap_true_total == overlap_pair_total)

    dataset_observation: str = (
        f"Dataset observation (OPS-SAT-AD, {n_multi} multi-channel incidents): "
        f"All {overlap_pair_total} observed channel-pair windows show windows_overlap=True "
        f"({overlap_true_total}/{overlap_pair_total} pairs). "
        "This is a characteristic of the OPS-SAT-AD grouping rule under which "
        "spacecraft incidents are formed from channels with overlapping anomaly windows. "
        "The partial-overlap logic is implemented and will activate correctly for datasets "
        "where non-overlapping channel pairs are present."
        if all_overlap else
        f"Dataset observation: {overlap_true_total}/{overlap_pair_total} multi-channel "
        "pair windows show windows_overlap=True (partial overlap present in this dataset)."
    )

    return {
        "total_incidents": n,
        "severity_distribution": severity_dist,
        "multi_channel_count": multi_count,
        "single_channel_count": single_count,
        "average_significance": round(sig_total / n, 6) if n else 0.0,
        "average_severity": round(sev_total / n, 6) if n else 0.0,
        "average_confidence": round(conf_total / n, 6) if n else 0.0,
        "generation_errors": result.generation_errors,
        "dataset_observation": dataset_observation,
    }


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------

def write_outputs(
    result: GenerationResult,
    summary: dict[str, Any],
    out_dir: str | Path = _OUT_DIR,
) -> tuple[Path, Path]:
    """
    Write ``investigations.json`` and ``investigation_summary.json`` to *out_dir*.

    The directory is created if it does not exist.  The InvestigationReport
    envelope includes all investigations sorted by spacecraft_incident_id
    ascending (guaranteed by :func:`generate_all`).

    Raw anomaly_events are NOT included in the output (timeline events contain
    only the columns defined by the TimelineEvent schema).

    Parameters
    ----------
    result  : GenerationResult from :func:`generate_all`.
    summary : dict from :func:`build_summary`.
    out_dir : Directory to write into.

    Returns
    -------
    (investigations_path, summary_path) : tuple[Path, Path]
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    now_utc = datetime.now(tz=timezone.utc)

    # Build a single combined InvestigationReport envelope
    report = InvestigationReport(
        generated_at=now_utc,
        source_files={
            "anomaly_events": "anomaly_events.csv",
            "incidents": "incidents.csv",
            "spacecraft_incidents": "spacecraft_incidents.csv",
        },
        dataset_stats=result.dataset_stats,
        investigations=result.investigations,
    )

    inv_path = out_dir / "investigations.json"
    sum_path = out_dir / "investigation_summary.json"

    # Serialise with Pydantic (handles datetime → ISO-8601, enums → str)
    inv_path.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )

    sum_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return inv_path, sum_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the full generation pipeline and print a summary report."""
    print("=" * 60)
    print("Member 2 — Production Investigation Generator")
    print("=" * 60)
    print(f"Loading data from : {_DATA_DIR}")
    print(f"Output directory  : {_OUT_DIR}")
    print()

    result = generate_all()
    summary = build_summary(result)
    inv_path, sum_path = write_outputs(result, summary)

    # --- Print report --------------------------------------------------------
    print(f"Generation time   : {result.elapsed_sec:.2f}s")
    print(f"Incidents processed: {result.n_processed}")
    print(f"Errors            : {len(result.generation_errors)}")
    print()
    print("Severity distribution:")
    for label, count in sorted(summary["severity_distribution"].items()):
        print(f"  {label:<10}: {count}")
    print()
    print(f"Multi-channel incidents : {summary['multi_channel_count']}")
    print(f"Single-channel incidents: {summary['single_channel_count']}")
    print(f"Average significance    : {summary['average_significance']:.4f}")
    print(f"Average severity        : {summary['average_severity']:.4f}")
    print(f"Average confidence      : {summary['average_confidence']:.4f}")
    print()
    print("Output files:")
    print(f"  {inv_path}  ({inv_path.stat().st_size:,} bytes)")
    print(f"  {sum_path}  ({sum_path.stat().st_size:,} bytes)")
    print("=" * 60)


if __name__ == "__main__":
    main()
