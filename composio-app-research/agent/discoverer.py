import asyncio
import json
import os
from dataclasses import dataclass, asdict
from typing import List, Optional
from agent.firecrawl_search import FirecrawlSearcher, SearchResult
from agent.url_scorer import URLScorer, ScoredURL
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
    """Coordinate bounded discovery for a single app."""

    def __init__(
        self,
        firecrawl_searcher: FirecrawlSearcher,
        cache_dir: str = "data/discovered_urls",
        max_concurrent_searches: int = 2,
    ):
        self.searcher = firecrawl_searcher
        self.scorer = URLScorer()
        self.cache_dir = cache_dir
        self.search_semaphore = asyncio.Semaphore(max_concurrent_searches)
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

    async def _bounded_search(self, category: str, app: str, website: str):
        """Run one discovery query under the global per-researcher search limit."""
        async with self.search_semaphore:
            if category == 'developer_docs':
                results = await self.searcher.find_developer_docs(app, website)
            elif category == 'auth_docs':
                results = await self.searcher.find_auth_docs(app, website)
            elif category == 'api_docs':
                results = await self.searcher.find_api_reference(app, website)
            elif category == 'mcp_docs':
                results = await self.searcher.find_mcp_evidence(app, website)
            elif category == 'pricing_docs':
                results = await self.searcher.find_pricing_access(app, website)
            else:
                return []

            # SearchResult objects are already normalized by FirecrawlSearcher.
            # Do not pass them through dict-style conversion again.
            for item in results:
                if isinstance(item, SearchResult):
                    try:
                        item.source_type = SourceType(item.source_type)
                    except (ValueError, TypeError):
                        item.source_type = SourceType.WEB
            return results

    async def discover(self, app: str, website: str, use_cache: bool = True) -> DiscoveryResult:
        """Run bounded searches, score/deduplicate once, and cache the result."""
        if use_cache:
            cached = self.load_cache(app)
            if cached:
                return cached

        categories = [
            'developer_docs',
            'auth_docs',
            'api_docs',
            'mcp_docs',
            'pricing_docs',
        ]

        # Keep category searches concurrent, but cap them. This prevents a
        # 5-app worker pool from turning into a 25-request burst upstream.
        tasks = [self._bounded_search(category, app, website) for category in categories]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        for category, result in zip(categories, completed):
            if isinstance(result, Exception):
                print(f"[{app}] Search failed for {category}: {result}")
                results[category] = []
            else:
                results[category] = result

        all_scored = []
        for category, search_results in results.items():
            if search_results:
                all_scored.extend(self.scorer.score(search_results, category))

        deduplicated = self.scorer.deduplicate(all_scored)
        result = DiscoveryResult(
            developer_docs=[u for u in deduplicated if u.category == 'developer_docs'],
            auth_docs=[u for u in deduplicated if u.category == 'auth_docs'],
            api_docs=[u for u in deduplicated if u.category == 'api_docs'],
            mcp_docs=[u for u in deduplicated if u.category == 'mcp_docs'],
            pricing_docs=[u for u in deduplicated if u.category == 'pricing_docs'],
        )

        self.save_cache(app, result)
        return result
