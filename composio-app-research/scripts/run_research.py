#!/usr/bin/env python3
"""
Main research runner script.
Usage: python scripts/run_research.py [--resume] [--concurrent N] [--apps CSV_FILE]
"""

import asyncio
import argparse
import csv
import os
import sys

from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.pipeline import ResearchPipeline, PipelineConfig


def load_apps(csv_file: str) -> list[dict]:
    apps = []
    with open(csv_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            apps.append(row)
    return apps


async def main():
    parser = argparse.ArgumentParser(description="Run app research pipeline")
    parser.add_argument("--resume", action="store_true", help="Resume from existing results")
    parser.add_argument(
        "--concurrent", type=int, default=2,
        help="Max concurrent app workers (default: 2; discovery is separately rate-limited)"
    )
    parser.add_argument("--apps", default="data/apps.csv", help="Apps CSV file")
    parser.add_argument("--retries", type=int, default=3, help="Max retries per app")
    args = parser.parse_args()

    required = ["COMPOSIO_API_KEY", "NVIDIA_API_KEY"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"Missing required environment variables: {missing}")
        print("Copy .env.example to .env and fill in values")
        return 1

    apps = load_apps(args.apps)
    print(f"Loaded {len(apps)} apps from {args.apps}")
    print(f"Using {args.concurrent} concurrent app workers; Firecrawl discovery is capped at 2 concurrent searches")

    config = PipelineConfig(
        max_concurrent=args.concurrent,
        max_retries=args.retries,
        resume=args.resume,
    )

    pipeline = ResearchPipeline(config)
    results = await pipeline.run(apps)

    print(f"\nCompleted: {len(results)} apps")
    print(f"Results saved to data/research_raw.jsonl")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
