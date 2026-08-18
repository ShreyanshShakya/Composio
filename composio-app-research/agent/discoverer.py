import asyncio
import json
import os
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from agent.firecrawl_search import FirecrawlSearcher, SearchResult
from agent.url_scorer import URLScorer, ScoredURL, score_results_by_category
from agent.models import SourceType


@dataclass
class DiscoveryResult:
    developer_docs: List[ScoredURL]
    auth_docs: List[ScoredURL]
    api_docs: List[ScoredURL]
    mcp_docs: List[ScoredURL]
    pricing_docs: List[ScoredURL]

    def to_dict(self):
        return {
            'developer_docs': [asdict(u) for u in self.developer_docs],
            'auth_docs': [asdict(u) for u in self.auth_docs],
            'api_docs': [asdict(u) for u in self.api_docs],
            'mcp_docs': [asdict(u) for u in self.mcp_docs],
            'pricing_docs': [asdict(u) for u in self.pricing_docs],
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            developer_docs=[ScoredURL(**u) for u in data.get('developer_docs', [])],
            auth_docs=[ScoredURL(**u) for u in data.get('auth_docs', [])],
            api_docs=[ScoredURL(**u) for u in data.get('api_docs', [])],
            mcp_docs=[ScoredURL(**u) for u in data.get('mcp_docs', [])],
            pricing_docs=[ScoredURL(**u) for u in data.get('pricing_docs', [])],
        )


class Discoverer:
    """Coordinate discovery for a single app."""

    def __init__(self, firecrawl_searcher: FirecrawlSearcher, cache_dir: str = "data/discovered_urls"):
        self.searcher = firecrawl_searcher
        self.scorer = URLScorer()
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

    def _cache_path(self, app: str) -> str:
        safe_app = app.lower().replace(' ', '_').replace('/', '_')
        return os.path.join(self.cache_dir, f"{safe_app}.json")

    def load_cache(self, app: str) -> Optional[DiscoveryResult]:
        path = self._cache_path(app)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return DiscoveryResult.from_dict(json.load(f))
        return None

    def save_cache(self, app: str, result: DiscoveryResult):
        path = self._cache_path(app)
        with open(path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)

    async def discover(self, app: str, website: str, use_cache: bool = True) -> DiscoveryResult:
        """Run all searches in parallel, score, deduplicate, return top URLs per category."""
        # Check cache first
        if use_cache:
            cached = self.load_cache(app)
            if cached:
                return cached

        # Run searches in parallel using asyncio.gather
        search_tasks = {
            'developer_docs': self.searcher.find_developer_docs(app, website),
            'auth_docs': self.searcher.find_auth_docs(app, website),
            'api_docs': self.searcher.find_api_reference(app, website),
            'mcp_docs': self.searcher.find_mcp_evidence(app, website),
            'pricing_docs': self.searcher.find_pricing_access(app, website),
        }

        # Run all searches in parallel
        task_names = list(search_tasks.keys())
        tasks = list(search_tasks.values())
        
        results = {}
        try:
            completed = await asyncio.gather(*tasks, return_exceptions=True)
            for category, result in zip(task_names, completed):
                if isinstance(result, Exception):
                    print(f"[{app}] Search failed for {category}: {result}")
                    results[category] = []
                else:
                    results[category] = result
        except Exception as e:
            print(f"[{app}] Search failed: {e}")
            results = {cat: [] for cat in search_tasks.keys()}

        # Score and select best URLs
        all_scored = []
        for category, search_results in results.items():
            if search_results:
                scored = self.scorer.score(search_results, category)
                all_scored.extend(scored)

        deduplicated = self.scorer.deduplicate(all_scored)
        
        # Build result object with categorized URLs directly from deduplicated
        result = DiscoveryResult(
            developer_docs=[u for u in deduplicated if u.category == 'developer_docs'],
            auth_docs=[u for u in deduplicated if u.category == 'auth_docs'],
            api_docs=[u for u in deduplicated if u.category == 'api_docs'],
            mcp_docs=[u for u in deduplicated if u.category == 'mcp_docs'],
            pricing_docs=[u for u in deduplicated if u.category == 'pricing_docs'],
        )

        # Save cache
        self.save_cache(app, result)
        return result