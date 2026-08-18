from dataclasses import dataclass
from typing import List, Dict, Set
from agent.models import SourceType
from agent.firecrawl_search import SearchResult


@dataclass
class ScoredURL:
    url: str
    title: str
    snippet: str
    source_type: SourceType
    confidence: float
    score: int
    category: str  # developer_docs, auth_docs, api_docs, mcp_docs, pricing_docs


class URLScorer:
    """Score and deduplicate discovered URLs."""

    SCORE_MAP = {
        SourceType.OFFICIAL_DOCS: 3,
        SourceType.AUTH_DOCS: 3,
        SourceType.PRICING_DOCS: 2,
        SourceType.MCP_REGISTRY: 3,
        SourceType.COMPOSIO_REGISTRY: 3,
        SourceType.WEB: 0,
    }

    def __init__(self, min_score: int = 2, max_per_category: int = 3):
        self.min_score = min_score
        self.max_per_category = max_per_category

    def score(self, results: List[SearchResult], category: str) -> List[ScoredURL]:
        """Score a list of search results."""
        scored = []
        for r in results:
            base_score = self.SCORE_MAP.get(r.source_type, 0)
            # Boost confidence
            confidence_boost = int(r.confidence * 2)  # 0-2
            total_score = base_score + confidence_boost
            scored.append(ScoredURL(
                url=r.url,
                title=r.title,
                snippet=r.snippet,
                source_type=r.source_type,
                confidence=r.confidence,
                score=total_score,
                category=category
            ))
        return scored

    def deduplicate(self, urls: List[ScoredURL]) -> List[ScoredURL]:
        """Deduplicate URLs, keeping highest scored."""
        seen: Dict[str, ScoredURL] = {}
        for u in urls:
            # Normalize URL
            normalized = self._normalize_url(u.url)
            if normalized not in seen or u.score > seen[normalized].score:
                seen[normalized] = u
        return list(seen.values())

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication."""
        # Remove trailing slashes, www, fragments
        url = url.lower().rstrip('/')
        if url.startswith('http://'):
            url = url[7:]
        elif url.startswith('https://'):
            url = url[8:]
        if url.startswith('www.'):
            url = url[4:]
        # Remove fragment
        if '#' in url:
            url = url.split('#')[0]
        return url

    def select_best(self, urls: List[ScoredURL], max_per_category: int = None) -> List[ScoredURL]:
        """Select best URLs per category up to max_per_category, returning ScoredURL objects."""
        if max_per_category is None:
            max_per_category = self.max_per_category

        # Group by category
        by_category: Dict[str, List[ScoredURL]] = {}
        for u in urls:
            if u.category not in by_category:
                by_category[u.category] = []
            by_category[u.category].append(u)

        selected = []
        for cat, urls_cat in by_category.items():
            # Sort by score descending
            urls_cat.sort(key=lambda x: x.score, reverse=True)
            # Filter by min score
            urls_cat = [u for u in urls_cat if u.score >= self.min_score]
            # Take top N
            for u in urls_cat[:max_per_category]:
                selected.append(u)
        return selected


def score_results_by_category(search_results: Dict[str, List[SearchResult]], 
                               min_score: int = 2, 
                               max_per_category: int = 3) -> List[ScoredURL]:
    """Convenience function to score all categories and select best URLs."""
    scorer = URLScorer(min_score=min_score, max_per_category=max_per_category)
    all_scored = []
    for category, results in search_results.items():
        if results:
            scored = scorer.score(results, category)
            all_scored.extend(scored)
    
    deduplicated = scorer.deduplicate(all_scored)
    return scorer.select_best(deduplicated)