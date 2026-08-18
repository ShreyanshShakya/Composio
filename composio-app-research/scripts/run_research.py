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
    with open(csv_file, encoding="utf-8") as f:
        return list(csv.DictReader(f))


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
    parser.add_argument("--concurrent", type=int, default=2, help="Max concurrent app workers")
    parser.add_argument("--apps", default="data/apps.csv", help="Apps CSV file")
    parser.add_argument("--retries", type=int, default=3, help="Max retries per app")
    args = parser.parse_args()

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
    print(f"Loaded {len(apps)} apps from {args.apps}")
    print(f"LLM provider: {provider}")
    print(f"Using {args.concurrent} concurrent app workers; Firecrawl discovery is capped at 2 concurrent searches")

    config = PipelineConfig(max_concurrent=args.concurrent, max_retries=args.retries, resume=args.resume)
    pipeline = ResearchPipeline(config)
    results = await pipeline.run(apps)

    print(f"\nCompleted: {len(results)} apps")
    print(f"Results saved to data/research_raw.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
