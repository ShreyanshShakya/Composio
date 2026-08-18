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
        def parse_url(item: dict) -> ScoredURL:
            item = dict(item)
            raw_source = item.get('source_type', SourceType.WEB)
            item['source_type'] = raw_source if isinstance(raw_source, SourceType) else SourceType(str(raw_source))
            return ScoredURL(**item)

        return cls(
            developer_docs=[parse_url(u) for u in data.get('developer_docs', [])],
            auth_docs=[parse_url(u) for u in data.get('auth_docs', [])],
            api_docs=[parse_url(u) for u in data.get('api_docs', [])],
            mcp_docs=[parse_url(u) for u in data.get('mcp_docs', [])],
            pricing_docs=[parse_url(u) for u in data.get('pricing_docs', [])],
        )

    def count(self) -> int:
        return sum(len(group) for group in (
            self.developer_docs, self.auth_docs, self.api_docs,
            self.mcp_docs, self.pricing_docs,
        ))


class Discoverer:
    """Coordinate bounded discovery for a single app."""

    def __init__(self, firecrawl_searcher: FirecrawlSearcher, cache_dir: str = "data/discovered_urls", max_concurrent_searches: int = 2):
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
            try:
                with open(path, 'r') as f:
                    result = DiscoveryResult.from_dict(json.load(f))
                groups = (
                    result.developer_docs, result.auth_docs, result.api_docs,
                    result.mcp_docs, result.pricing_docs,
                )
                if result.count() > 0 and all(
                    isinstance(u.url, str) and u.url.strip()
                    for group in groups for u in group
                ):
                    return result
                print(f"[{app}] Ignoring empty or malformed discovery cache: {path}")
            except (OSError, json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
                print(f"[{app}] Ignoring invalid discovery cache: {exc}")
        return None

    def save_cache(self, app: str, result: DiscoveryResult):
        if result.count() == 0:
            return
        path = self._cache_path(app)
        with open(path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)

    async def _bounded_search(self, category: str, app: str, website: str):
        queries = {
            'developer_docs': f"{app} developer documentation",
            'auth_docs': f"{app} API authentication",
            'api_docs': f"{app} API reference",
            'mcp_docs': f"{app} MCP server",
            'pricing_docs': f"{app} pricing plans developer",
        }
        async with self.search_semaphore:
            results = await self.searcher.search(queries[category], limit=5, website=website)
        source_by_category = {
            'developer_docs': SourceType.OFFICIAL_DOCS,
            'auth_docs': SourceType.AUTH_DOCS,
            'api_docs': SourceType.OFFICIAL_DOCS,
            'mcp_docs': SourceType.MCP_REGISTRY,
            'pricing_docs': SourceType.PRICING_DOCS,
        }
        source_type = source_by_category[category]
        for item in results:
            if isinstance(item, SearchResult):
                item.source_type = source_type
        return results

    async def discover(self, app: str, website: str, use_cache: bool = True) -> DiscoveryResult:
        if use_cache:
            cached = self.load_cache(app)
            if cached:
                return cached
        categories = ['developer_docs', 'auth_docs', 'api_docs', 'mcp_docs', 'pricing_docs']
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
