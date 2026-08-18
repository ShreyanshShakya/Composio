import asyncio
import json
import os
import random
from datetime import datetime
from pathlib import Path
from typing import Any
from dataclasses import dataclass
from agent.models import AppResearch
from agent.researcher import Researcher, NemotronClient, ComposioMCPClient
from agent.evidence import validate_and_repair_research, extract_json_from_response


@dataclass
class PipelineConfig:
    max_concurrent: int = 5
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    output_dir: str = "data"
    resume: bool = True


class RateLimiter:
    """Token bucket rate limiter with exponential backoff."""
    
    def __init__(self, max_concurrent: int = 5):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.request_times: list[float] = []
    
    async def acquire(self):
        await self.semaphore.acquire()
    
    def release(self):
        self.semaphore.release()
    
    async def wait_for_retry(self, attempt: int, base_delay: float = 1.0, max_delay: float = 60.0):
        import random
        delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
        await asyncio.sleep(delay)


class ResearchPipeline:
    """Orchestrates research across 100 apps with concurrency control and persistence."""
    
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
    
    def load_existing(self) -> list[AppResearch]:
        """Load already completed research for resume."""
        if not self.raw_file.exists():
            return []
        
        results = []
        with open(self.raw_file, encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    results.append(AppResearch(**data))
                    self.completed.add(data["app"])
                except Exception:
                    pass
        return results
    
    def save_result(self, research: AppResearch):
        """Append result to JSONL file."""
        with open(self.raw_file, "a", encoding="utf-8") as f:
            f.write(research.model_dump_json() + "\n")
        self.completed.add(research.app)
    
async def research_with_retry(self, app: str, website: str, category: str) -> AppResearch | None:
        """Research single app with retry logic and exponential backoff."""
        last_error = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                await self.rate_limiter.acquire()
                try:
                    research = await self.researcher.research_app(app, website, category)
                    
                    # Validate and repair
                    validated = validate_and_repair_research(
                        research.model_dump(), app, max_retries=2
                    )
                    
                    if validated:
                        return validated
                    else:
                        raise ValueError("Validation failed after repair attempts")
                        
                finally:
                    self.rate_limiter.release()
                    
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check if retryable (429, 5xx, timeout, rate limit)
                retryable = any(x in error_str for x in ["429", "500", "502", "503", "504", "timeout", "rate limit"])
                
                if attempt < self.config.max_retries and retryable:
                    # Exponential backoff with jitter
                    import random
                    base_delay = self.config.base_delay * (2 ** attempt)
                    jitter = random.uniform(0, 0.5)
                    delay = min(base_delay + jitter, self.config.max_delay)
                    
                    # For 429, use longer delay
                    if "429" in error_str:
                        delay = min(delay * 2, self.config.max_delay)
                    
                    print(f"[{app}] Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                    continue
                
                break
            
        self.failed[app] = self.failed.get(app, 0) + 1
        print(f"[FAILED] {app}: {last_error}")
        return None
    
    async def run(self, apps: list[dict[str, str]]):
        """Run research pipeline for all apps."""
        
        # Load existing for resume
        if self.config.resume:
            existing = self.load_existing()
            print(f"Resumed: {len(existing)} apps already completed")
        
        # Filter remaining
        remaining = [a for a in apps if a["app"] not in self.completed]
        print(f"Researching {len(remaining)} apps with {self.config.max_concurrent} workers...")
        
        # Create tasks
        semaphore = asyncio.Semaphore(self.config.max_concurrent)
        
        async def bounded_research(app_data):
            async with semaphore:
                return await self.research_with_retry(app_data["app"], app_data["website"], app_data["category"])
        
        tasks = [bounded_research(app) for app in remaining]
        
        # Execute with progress
        completed = 0
        for coro in asyncio.as_completed(tasks):
            result = await coro
            completed += 1
            
            if result:
                self.save_result(result)
                print(f"[{completed}/{len(remaining)}] OK {result.app} (confidence: {result.confidence:.2f})")
            else:
                print(f"[{completed}/{len(remaining)}] FAIL Failed")
            
            # Periodic summary
            if completed % 10 == 0:
                self.print_summary()
        
        self.print_summary()
        # Cleanup
        await self.researcher.close()
        return self.load_existing()
    
    def print_summary(self):
        total = len(self.completed) + sum(self.failed.values())
        print(f"\n--- Progress: {len(self.completed)}/{total} completed, {len(self.failed)} failed ---")


async def main():
    import csv
    
    # Load apps from CSV
    apps = []
    with open("data/apps.csv") as f:
        reader = csv.DictReader(f)
        for row in reader:
            apps.append(row)
    
    config = PipelineConfig(
        max_concurrent=5,
        max_retries=3,
        resume=True,
    )
    
    pipeline = ResearchPipeline(config)
    results = await pipeline.run(apps)
    
    print(f"\nDone! {len(results)} apps researched.")
    print(f"Results saved to {pipeline.raw_file}")


if __name__ == "__main__":
    asyncio.run(main())