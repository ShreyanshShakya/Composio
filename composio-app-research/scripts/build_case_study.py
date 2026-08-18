#!/usr/bin/env python3
"""
Case study HTML generator.
Usage: python scripts/build_case_study.py [--input FILE] [--output DIR]
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))
sys.path.insert(0, project_root)

from analysis.patterns import load_research, analyze_patterns, export_for_web


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build interactive HTML case study")
    parser.add_argument("--input", default="data/research_final.jsonl", help="Final research data")
    parser.add_argument("--output", default="web", help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading research data...")
    research = load_research(args.input, strict=True)
    print(f"Loaded {len(research)} validated apps")

    print("Analyzing patterns...")
    analysis = analyze_patterns(research)

    print("Exporting analysis for web...")
    export_for_web(analysis, output_dir / "analysis.json")

    # Export research data for web (simplified from the validated source records).
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

    with open(output_dir / "research.json", "w", encoding="utf-8") as f:
        json.dump(web_research, f, indent=2)

    print("Generating charts...")
    from analysis.charts import generate_all_charts
    try:
        generate_all_charts(args.input, str(output_dir / "charts"))
    except Exception as exc:
        # A stale/partial chart set must never make the case study appear complete.
        raise RuntimeError(f"Chart generation failed; case-study build aborted: {exc}") from exc

    print(f"\nCase study data prepared in {output_dir}/")
    print("Open web/index.html to view")


if __name__ == "__main__":
    main()
