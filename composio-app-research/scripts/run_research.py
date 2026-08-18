#!/usr/bin/env python3
"""
Main research runner script.

Usage:
  python scripts/run_research.py --resume
  python scripts/run_research.py --resume --only-missing
  python scripts/run_research.py --resume --only-apps "Pipedrive,Pylon,Xero"
"""

import asyncio
import argparse
import csv
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))
sys.path.insert(0, project_root)

from agent.pipeline import ResearchPipeline, PipelineConfig


def load_apps(csv_file: str) -> list[dict]:
    with open(csv_file, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def normalize(name: str) -> str:
    return " ".join(name.strip().casefold().split())


def find_missing_apps(apps: list[dict], raw_file: str = "data/research_raw.jsonl") -> list[dict]:
    """Return target CSV apps without a valid parseable raw result."""
    existing: set[str] = set()
    path = Path(raw_file)
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    app = record.get("app")
                    if app:
                        existing.add(normalize(app))
                except json.JSONDecodeError:
                    # Truncated historical lines do not count as completed.
                    continue
    return [app for app in apps if normalize(app["app"]) not in existing]


def parse_only_apps(value: str) -> set[str]:
    return {normalize(item) for item in value.split(",") if item.strip()}


def validate_llm_config() -> tuple[bool, str]:
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if provider == "gemini":
        return bool(os.getenv("GEMINI_API_KEY")), "GEMINI_API_KEY"
    if provider == "nemotron":
        return bool(os.getenv("NVIDIA_API_KEY")), "NVIDIA_API_KEY"
    return False, f"unsupported LLM_PROVIDER={provider!r}"


async def main():
    parser = argparse.ArgumentParser(description="Run app research pipeline")
    parser.add_argument("--resume", action="store_true", help="Resume from existing results")
    parser.add_argument(
        "--only-missing",
        action="store_true",
        help="Research only target apps with no parseable record in data/research_raw.jsonl",
    )
    parser.add_argument(
        "--only-apps",
        help="Comma-separated explicit app names to research; must be used with --resume",
    )
    parser.add_argument("--concurrent", type=int, default=2, help="Max concurrent app workers")
    parser.add_argument("--apps", default="data/apps.csv", help="Apps CSV file")
    parser.add_argument("--retries", type=int, default=3, help="Max retries per app")
    args = parser.parse_args()

    if args.only_apps and not args.resume:
        parser.error("--only-apps requires --resume")

    if args.only_missing and args.only_apps:
        parser.error("use either --only-missing or --only-apps, not both")

    if not os.getenv("COMPOSIO_API_KEY"):
        print("Missing required environment variable: COMPOSIO_API_KEY")
        return 1

    llm_ok, llm_key = validate_llm_config()
    if not llm_ok:
        print(f"Missing or invalid LLM configuration: {llm_key}")
        print("Set LLM_PROVIDER=gemini with GEMINI_API_KEY, or LLM_PROVIDER=nemotron with NVIDIA_API_KEY")
        return 1

    apps = load_apps(args.apps)
    provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

    if args.only_missing:
        selected_apps = find_missing_apps(apps)
        mode = "only missing"
    elif args.only_apps:
        requested = parse_only_apps(args.only_apps)
        selected_apps = [app for app in apps if normalize(app["app"]) in requested]
        missing_from_csv = requested - {normalize(app["app"]) for app in selected_apps}
        if missing_from_csv:
            print(f"Unknown app name(s) in --only-apps: {', '.join(sorted(missing_from_csv))}")
            return 1
        mode = "explicit app list"
    else:
        selected_apps = apps
        mode = "all targets"

    print(f"Loaded {len(apps)} target apps from {args.apps}")
    print(f"Selected {len(selected_apps)} apps ({mode})")
    print(f"LLM provider: {provider}")
    print(f"Using {args.concurrent} concurrent app workers; Firecrawl discovery is capped at 2 concurrent searches")

    if not selected_apps:
        print("Nothing to research.")
        return 0

    config = PipelineConfig(max_concurrent=args.concurrent, max_retries=args.retries, resume=args.resume)
    pipeline = ResearchPipeline(config)
    results = await pipeline.run(selected_apps)

    print(f"\nCompleted/loaded: {len(results)} apps")
    print(f"Results saved to data/research_raw.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
