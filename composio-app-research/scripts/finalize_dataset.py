#!/usr/bin/env python3
"""Build one canonical dataset from the append-only research log.

Usage:
  python scripts/finalize_dataset.py
  python scripts/finalize_dataset.py --strict
  python scripts/finalize_dataset.py --input data/research_raw.jsonl --output data/research_final.jsonl

The raw log may contain retries, duplicate app records, and truncated historical
records. This script keeps only apps present in data/apps.csv, validates each
record, and selects the strongest record per app deterministically.
"""

import argparse
import csv
import json
import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.models import AppResearch, VerificationStatus


def normalize_name(name: str) -> str:
    return " ".join(name.strip().casefold().split())


def load_target_apps(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = csv.DictReader(f)
        result = {}
        for row in rows:
            app = (row.get("app") or "").strip()
            if app:
                result[normalize_name(app)] = row
    if not result:
        raise ValueError(f"No apps found in {path}")
    return result


def quality_key(record: AppResearch) -> tuple:
    """Prefer verified, then confidence, evidence, and completeness."""
    verified = record.verification_status != VerificationStatus.UNVERIFIED
    non_unknown = sum([
        bool(record.auth_methods and all(a.value != "unknown" for a in record.auth_methods)),
        record.credential_access.value != "unknown",
        bool(record.api_types and all(a.value != "unknown" for a in record.api_types)),
        record.api_breadth.value != "unknown",
        record.mcp_public.value != "unknown",
        record.buildability.value != "unknown",
    ])
    return (
        1 if verified else 0,
        round(record.confidence, 6),
        non_unknown,
        len(record.evidence),
        len(record.sources),
    )


def load_best_records(raw_path: Path, targets: dict[str, dict[str, str]]) -> tuple[dict[str, AppResearch], int, int]:
    best: dict[str, AppResearch] = {}
    invalid = 0
    ignored = 0
    if not raw_path.exists():
        raise FileNotFoundError(raw_path)

    with raw_path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                record = AppResearch.model_validate_json(line)
            except Exception:
                invalid += 1
                continue

            key = normalize_name(record.app)
            if key not in targets:
                ignored += 1
                continue

            # Use the canonical CSV spelling/category rather than stale output metadata.
            row = targets[key]
            record.app = row["app"]
            record.category = row.get("category", record.category)

            previous = best.get(key)
            if previous is None or quality_key(record) > quality_key(previous):
                best[key] = record

    return best, invalid, ignored


def atomic_write(path: Path, records: list[AppResearch]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for record in records:
                f.write(record.model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def finalize(raw_path: Path, apps_path: Path, output_path: Path, strict: bool = False) -> dict:
    targets = load_target_apps(apps_path)
    best, invalid, ignored = load_best_records(raw_path, targets)
    missing = [row["app"] for key, row in targets.items() if key not in best]
    records = sorted(best.values(), key=lambda r: list(targets).index(normalize_name(r.app)))

    if strict and missing:
        raise RuntimeError(f"Dataset incomplete: {len(missing)} target apps missing: {', '.join(missing)}")

    atomic_write(output_path, records)
    manifest = {
        "target_apps": len(targets),
        "final_records": len(records),
        "missing_apps": missing,
        "duplicate_records_collapsed": max(0, sum(1 for _ in raw_path.open(encoding="utf-8")) - invalid - ignored - len(best)),
        "invalid_records_skipped": invalid,
        "out_of_scope_records_skipped": ignored,
        "complete": not missing,
    }
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize canonical research dataset")
    parser.add_argument("--input", default="data/research_raw.jsonl")
    parser.add_argument("--apps", default="data/apps.csv")
    parser.add_argument("--output", default="data/research_final.jsonl")
    parser.add_argument("--manifest", default="data/research_manifest.json")
    parser.add_argument("--strict", action="store_true", help="Fail unless every target app has a valid record")
    args = parser.parse_args()

    manifest = finalize(Path(args.input), Path(args.apps), Path(args.output), args.strict)
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("=== DATASET FINALIZATION ===")
    print(f"Target apps:      {manifest['target_apps']}")
    print(f"Canonical records: {manifest['final_records']}")
    print(f"Missing:           {len(manifest['missing_apps'])}")
    print(f"Invalid skipped:   {manifest['invalid_records_skipped']}")
    print(f"Out-of-scope:      {manifest['out_of_scope_records_skipped']}")
    print(f"Complete:          {manifest['complete']}")
    if manifest["missing_apps"]:
        print("Missing apps:")
        for app in manifest["missing_apps"]:
            print(f"  - {app}")
    print(f"Saved: {args.output}")
    print(f"Manifest: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
