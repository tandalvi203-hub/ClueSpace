"""
build_investigation_index.py
----------------------------
Reads outputs/investigations.json and extracts a lightweight index record
per investigation for consumption by Member 3's frontend dashboard.

Output: outputs/investigation_index.json
"""

import json
import sys
from pathlib import Path

INVESTIGATIONS_PATH = Path("outputs/investigations.json")
INDEX_PATH = Path("outputs/investigation_index.json")

REQUIRED_FIELDS = [
    "investigation_id",
    "spacecraft_incident_id",
    "severity_label",
    "severity_score",
    "significance_score",
    "investigation_confidence",
    "n_channels_affected",
    "n_events_total",
    "duration_sec",
    "persistence_class",
    "is_multi_channel",
]


def build_index(investigations_path: Path, index_path: Path) -> None:
    print(f"Reading {investigations_path} ...")
    with investigations_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    records = data["investigations"]
    print(f"Loaded {len(records)} investigations.")

    index_records = []
    for rec in records:
        index_records.append({
            "investigation_id": rec["investigation_id"],
            "spacecraft_incident_id": rec["spacecraft_incident_id"],
            "severity_label": rec["mission_impact_level"],
            "severity_score": rec["severity_score"],
            "significance_score": rec["significance_score"],
            "investigation_confidence": rec["investigation_confidence"],
            "n_channels_affected": rec["n_channels_affected"],
            "n_events_total": rec["n_events_total"],
            "duration_sec": rec["duration_sec"],
            "persistence_class": rec["persistence_class"],
            "is_multi_channel": rec["is_multi_channel"],
        })

    index = {
        "schema_version": "1.0",
        "total_investigations": len(index_records),
        "investigations": index_records,
    }

    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)

    print(f"Written: {index_path}")


def validate_index(index_path: Path, expected_count: int = 805) -> bool:
    print(f"\nValidating {index_path} ...")
    with index_path.open("r", encoding="utf-8") as f:
        index = json.load(f)

    records = index["investigations"]
    errors = []

    # 1. Exactly 805 records
    if len(records) != expected_count:
        errors.append(f"Expected {expected_count} records, got {len(records)}")

    # 2. Unique investigation_ids
    inv_ids = [r["investigation_id"] for r in records]
    if len(inv_ids) != len(set(inv_ids)):
        errors.append("Duplicate investigation_id values found")

    # 3. investigation_id follows INV-{spacecraft_incident_id} format
    for r in records:
        expected_id = f"INV-{r['spacecraft_incident_id']}"
        if r["investigation_id"] != expected_id:
            errors.append(
                f"ID mismatch: investigation_id={r['investigation_id']!r} "
                f"but spacecraft_incident_id={r['spacecraft_incident_id']}"
            )
            break  # report first mismatch only

    # 4. spacecraft_incident_id values are unique and non-null
    sc_ids = [r["spacecraft_incident_id"] for r in records]
    if len(sc_ids) != len(set(sc_ids)):
        errors.append("Duplicate spacecraft_incident_id values found")

    # 5. All required fields present in every record
    for r in records:
        for field in REQUIRED_FIELDS:
            if field not in r:
                errors.append(f"Missing field {field!r} in record {r.get('investigation_id')}")
                break

    # 6. No forbidden heavy fields
    forbidden = {"timeline", "evidence_graph", "hypothesis_statements", "recommended_actions",
                 "channel_temporal_relationships", "significance_components",
                 "severity_components", "confidence_components"}
    for r in records:
        present = forbidden & set(r.keys())
        if present:
            errors.append(f"Forbidden field(s) {present} found in record {r.get('investigation_id')}")
            break

    # 7. File size check (index must be smaller than source)
    index_size = index_path.stat().st_size
    source_size = INVESTIGATIONS_PATH.stat().st_size
    if index_size >= source_size:
        errors.append(
            f"Index ({index_size:,} bytes) is not smaller than source ({source_size:,} bytes)"
        )

    if errors:
        print("VALIDATION FAILED:")
        for e in errors:
            print(f"  ✗ {e}")
        return False

    print("All validations passed [OK]")
    return True


def main() -> None:
    build_index(INVESTIGATIONS_PATH, INDEX_PATH)
    ok = validate_index(INDEX_PATH)

    # Report
    with INDEX_PATH.open("r", encoding="utf-8") as f:
        index = json.load(f)
    records = index["investigations"]
    size_bytes = INDEX_PATH.stat().st_size
    size_mb = size_bytes / (1024 * 1024)

    print("\n--- Report ---")
    print(f"File created  : {INDEX_PATH}")
    print(f"File size     : {size_bytes:,} bytes ({size_mb:.2f} MB)")
    print(f"Records       : {len(records)}")
    print(f"First ID      : {records[0]['investigation_id']}")
    print(f"Last ID       : {records[-1]['investigation_id']}")
    print(f"Validation    : {'PASS' if ok else 'FAIL'}")

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
