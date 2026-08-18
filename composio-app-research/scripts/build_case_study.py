#!/usr/bin/env python3
"""Case study HTML generator.
Usage: python scripts/build_case_study.py [--input FILE] [--output DIR]
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))
sys.path.insert(0, project_root)

from analysis.patterns import load_research, analyze_patterns, export_for_web


def finalize_dataset(raw_input: str) -> dict:
    """Canonicalize raw JSONL before any web artifacts are generated."""
    from scripts.finalize_dataset import finalize

    data_dir = Path("data")
    manifest = finalize(
        Path(raw_input),
        data_dir / "apps.csv",
        data_dir / "research_final.jsonl",
        strict=False,
    )
    (data_dir / "research_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build interactive HTML case study")
    parser.add_argument("--input", default="data/research_raw.jsonl", help="Raw research JSONL")
    parser.add_argument("--output", default="web", help="Output directory")
    parser.add_argument("--strict", action="store_true", help="Abort unless all CSV apps have valid records")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Finalizing canonical research dataset...")
    manifest = finalize_dataset(args.input)
    print(f"Target apps: {manifest['target_apps']}")
    print(f"Canonical records: {manifest['final_records']}")
    print(f"Missing: {len(manifest['missing_apps'])}")
    print(f"Invalid skipped: {manifest['invalid_records_skipped']}")

    if args.strict and not manifest["complete"]:
        raise RuntimeError(
            "Case-study build aborted: dataset is incomplete. "
            "Run research with --resume to fill the missing apps."
        )

    input_path = Path("data/research_final.jsonl")
    print("Loading research data...")
    research = load_research(str(input_path), strict=True)
    print(f"Loaded {len(research)} canonical validated apps")

    print("Analyzing patterns...")
    analysis = analyze_patterns(research)

    print("Exporting analysis for web...")
    export_for_web(analysis, output_dir / "analysis.json")

    # Export exactly one record per canonical app.
    web_research = []
    for r in research:
        web_research.append({
            "app": r.app,
            "category": r.category,
            "description": r.description,
            "auth": [a.value for a in r.auth_methods],
            "credential_access": r.credential_access.value,
            "api_types": [a.value for a in r.api_types],
            "api_breadth": r.api_breadth.value,
            "mcp_public": r.mcp_public.value,
            "composio_supported": r.composio_supported.value,
            "buildability": r.buildability.value,
            "blocker": r.blocker,
            "confidence": r.confidence,
            "verification_status": r.verification_status.value,
            "evidence_count": len(r.evidence),
        })

    web_path = output_dir / "research.json"
    tmp_path = output_dir / ".research.json.tmp"
    tmp_path.write_text(json.dumps(web_research, indent=2), encoding="utf-8")
    os.replace(tmp_path, web_path)
    print(f"Exported {len(web_research)} records to {web_path}")

    print("Generating charts...")
    from analysis.charts import generate_all_charts
    try:
        generate_all_charts(str(input_path), str(output_dir / "charts"))
    except Exception as exc:
        raise RuntimeError(f"Chart generation failed; case-study build aborted: {exc}") from exc

    print("\nCase study data prepared in web/")
    print(f"Canonical dataset: {input_path}")
    print(f"Open web/index.html to view ({len(research)} apps)")


if __name__ == "__main__":
    main()
