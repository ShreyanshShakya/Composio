import asyncio
import json
import os
import random
from pathlib import Path
from dataclasses import dataclass
from agent.models import AppResearch
from agent.researcher import Researcher, NemotronClient, ComposioMCPClient
from agent.evidence import validate_and_repair_research


@dataclass
class PipelineConfig:
    max_concurrent: int = 2
    max_retries: int = 3
    base_delay: float = 2.0
    max_delay: float = 60.0
    output_dir: str = "data"
    resume: bool = True
    min_resume_confidence: float = 0.10


class RateLimiter:
    """Bound concurrent app research; outbound search has a separate limiter."""

    def __init__(self, max_concurrent: int = 2):
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def acquire(self):
        await self.semaphore.acquire()

    def release(self):
        self.semaphore.release()

    async def wait_for_retry(self, attempt: int, base_delay: float = 2.0, max_delay: float = 60.0):
        delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
        await asyncio.sleep(delay)


class ResearchPipeline:
    """Orchestrates research across 100 apps with bounded concurrency and persistence."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.raw_file = self.output_dir / "research_raw.jsonl"
        self.final_file = self.output_dir / "research_final.jsonl"
        self.llm = NemotronClient()
        self.composio_mcp = ComposioMCPClient()
        self.researcher = Researcher(self.llm, self.composio_mcp)
        self.rate_limiter = RateLimiter(config.max_concurrent)
        self.completed: set[str] = set()
        self.failed: dict[str, int] = {}

    def _is_resume_quality(self, research: AppResearch) -> bool:
        """Only treat materially useful results as completed for --resume.

        A low-confidence record can be produced when the upstream LLM is
        rate-limited and returns UNKNOWN fallbacks. Such a record must not
        permanently prevent a later run from retrying the app.
        """
        return research.confidence > self.config.min_resume_confidence

    def load_existing(self) -> list[AppResearch]:
        """Load existing research; only quality results reserve an app on resume."""
        if not self.raw_file.exists():
            return []

        results_by_app: dict[str, AppResearch] = {}
        with open(self.raw_file, encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    research = AppResearch(**data)
                    # Keep the highest-confidence record if an app appears more
                    # than once after a previous retry/resume cycle.
                    previous = results_by_app.get(research.app)
                    if previous is None or research.confidence > previous.confidence:
                        results_by_app[research.app] = research
                    if self._is_resume_quality(research):
                        self.completed.add(research.app)
                except Exception:
                    continue
        return list(results_by_app.values())

    def save_result(self, research: AppResearch) -> bool:
        """Persist a useful result; do not save low-confidence retry fallbacks."""
        if not self._is_resume_quality(research):
            print(
                f"[{research.app}] Result confidence {research.confidence:.2f} "
                f"<= {self.config.min_resume_confidence:.2f}; not marking completed"
            )
            return False
        with open(self.raw_file, "a", encoding="utf-8") as f:
            f.write(research.model_dump_json() + "\n")
        self.completed.add(research.app)
        return True

    async def research_with_retry(self, app: str, website: str, category: str) -> AppResearch | None:
        """Research one app with exponential backoff and 429-aware retry."""
        last_error = None
        for attempt in range(self.config.max_retries + 1):
            try:
                await self.rate_limiter.acquire()
                try:
                    research = await self.researcher.research_app(app, website, category)
                    validated = validate_and_repair_research(research.model_dump(), app, max_retries=2)
                    if validated:
                        return validated
                    raise ValueError("Validation failed after repair attempts")
                finally:
                    self.rate_limiter.release()
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                retryable = any(x in error_str for x in ["429", "500", "502", "503", "504", "timeout", "rate limit"])
                if attempt < self.config.max_retries and retryable:
                    base_delay = self.config.base_delay * (2 ** attempt)
                    if "429" in error_str:
                        base_delay *= 2
                    delay = min(base_delay + random.uniform(0, 1), self.config.max_delay)
                    print(f"[{app}] Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue
                break

        self.failed[app] = self.failed.get(app, 0) + 1
        print(f"[FAILED] {app}: {last_error}")
        return None

    async def run(self, apps: list[dict[str, str]]):
        """Run research pipeline for all apps."""
        if self.config.resume:
            existing = self.load_existing()
            quality_completed = len(self.completed)
            print(f"Resumed: {quality_completed} quality apps already completed")

        remaining = [a for a in apps if a["app"] not in self.completed]
        print(f"Researching {len(remaining)} apps with {self.config.max_concurrent} workers...")

        semaphore = asyncio.Semaphore(self.config.max_concurrent)

        async def bounded_research(app_data):
            async with semaphore:
                return await self.research_with_retry(app_data["app"], app_data["website"], app_data["category"])

        tasks = [bounded_research(app) for app in remaining]
        completed = 0
        for coro in asyncio.as_completed(tasks):
            result = await coro
            completed += 1
            if result:
                saved = self.save_result(result)
                if saved:
                    print(f"[{completed}/{len(remaining)}] OK {result.app} (confidence: {result.confidence:.2f})")
                else:
                    print(f"[{completed}/{len(remaining)}] RETRY {result.app} (confidence: {result.confidence:.2f})")
            else:
                print(f"[{completed}/{len(remaining)}] FAIL Failed")
            if completed % 10 == 0:
                self.print_summary()

        self.print_summary()
        await self.researcher.close()
        return self.load_existing()

    def print_summary(self):
        total = len(self.completed) + sum(self.failed.values())
        print(f"\n--- Progress: {len(self.completed)}/{total} completed, {len(self.failed)} failed ---")


async def main():
    import csv
    apps = []
    with open("data/apps.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            apps.append(row)
    config = PipelineConfig(max_concurrent=2, max_retries=3, resume=True)
    pipeline = ResearchPipeline(config)
    results = await pipeline.run(apps)
    print(f"\nDone! {len(results)} apps researched.")
    print(f"Results saved to {pipeline.raw_file}")


if __name__ == "__main__":
    asyncio.run(main())
