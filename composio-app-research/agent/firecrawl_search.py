import asyncio
import json
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
from agent.models import SourceType


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    source_type: SourceType
    confidence: float


class FirecrawlSearcher:
    """Firecrawl /search via Composio MCP with claim-specific fallback discovery."""

    def __init__(self, composio_mcp_client):
        self.composio_mcp = composio_mcp_client
        self.doc_patterns = {
            'developer_docs': ['/developers', '/docs', '/api', '/developer', '/reference', '/guides', '/tutorials', '/getting-started', '/quickstart'],
            'auth_docs': ['/developers/auth', '/docs/auth', '/docs/authentication', '/api/auth', '/auth', '/developers/authentication', '/docs/authorization', '/api/authorization', '/oauth', '/oauth2'],
            'api_docs': ['/developers/api', '/docs/api', '/api/reference', '/docs/reference', '/api/docs', '/reference', '/graphql', '/rest-api', '/api/v1', '/api/v2'],
            'mcp_docs': ['/mcp', '/modelcontextprotocol', '/mcp-server', '/.well-known/mcp', '/mcp/documentation'],
            'pricing_docs': ['/pricing', '/plans', '/billing', '/pricing/developer', '/developers/pricing', '/plans/developer', '/signup'],
        }
        self.known_domains = {
            'slack.com': 'https://api.slack.com', 'github.com': 'https://docs.github.com', 'stripe.com': 'https://stripe.com/docs',
            'salesforce.com': 'https://developer.salesforce.com', 'hubspot.com': 'https://developers.hubspot.com', 'notion.so': 'https://developers.notion.com',
            'airtable.com': 'https://airtable.com/developers', 'linear.app': 'https://developers.linear.app', 'atlassian.com': 'https://developer.atlassian.com',
            'asana.com': 'https://developers.asana.com', 'monday.com': 'https://developer.monday.com', 'clickup.com': 'https://clickup.com/api',
            'coda.io': 'https://coda.io/developers', 'smartsheet.com': 'https://smartsheet.com/developers', 'harvestapp.com': 'https://help.getharvest.com/api-v2',
            'twilio.com': 'https://www.twilio.com/docs', 'sendgrid.com': 'https://sendgrid.com/docs', 'mailchimp.com': 'https://mailchimp.com/developer',
            'klaviyo.com': 'https://developers.klaviyo.com', 'shopify.dev': 'https://shopify.dev', 'woocommerce.com': 'https://woocommerce.com/document/woocommerce-rest-api',
            'bigcommerce.com': 'https://developer.bigcommerce.com', 'squareup.com': 'https://developer.squareup.com', 'paypal.com': 'https://developer.paypal.com',
            'braintreepayments.com': 'https://developer.paypal.com/braintree', 'authorize.net': 'https://developer.authorize.net', 'adyen.com': 'https://docs.adyen.com',
            'plaid.com': 'https://plaid.com/docs', 'zendesk.com': 'https://developer.zendesk.com', 'intercom.com': 'https://developers.intercom.com',
            'freshdesk.com': 'https://developers.freshdesk.com', 'gorgias.com': 'https://developers.gorgias.com', 'front.com': 'https://dev.frontapp.com',
            'pipedrive.com': 'https://developers.pipedrive.com', 'close.com': 'https://developer.close.com', 'attio.com': 'https://docs.attio.com',
            'zoho.com': 'https://www.zoho.com/developer', 'freshworks.com': 'https://developers.freshworks.com', 'servicenow.com': 'https://developer.servicenow.com',
            'workday.com': 'https://community.workday.com', 'successfactors.com': 'https://api.sap.com', 'oracle.com': 'https://docs.oracle.com',
            'microsoft.com': 'https://learn.microsoft.com', 'google.com': 'https://developers.google.com', 'amazon.com': 'https://docs.aws.amazon.com',
            'digitalocean.com': 'https://docs.digitalocean.com', 'cloudflare.com': 'https://developers.cloudflare.com', 'vercel.com': 'https://vercel.com/docs',
            'netlify.com': 'https://docs.netlify.com', 'heroku.com': 'https://devcenter.heroku.com', 'supabase.com': 'https://supabase.com/docs',
            'planetscale.com': 'https://docs.planetscale.com', 'neon.tech': 'https://neon.tech/docs', 'supabase.io': 'https://supabase.io/docs',
            'railway.app': 'https://docs.railway.app', 'render.com': 'https://render.com/docs', 'fly.io': 'https://fly.io/docs',
        }

    async def search(self, query: str, limit: int = 5, website: str | None = None) -> list[SearchResult]:
        try:
            results = await self._firecrawl_search(query, limit)
            if results:
                print(f"[Firecrawl] {query!r}: {len(results)} valid results")
                return results
            print(f"[Firecrawl] {query!r}: 0 valid results; using claim-specific website fallback")
        except Exception as e:
            print(f"Firecrawl search failed, falling back to claim-specific app-domain patterns: {e}")
        return await self._fallback_search(query, limit, website)

    async def _firecrawl_search(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Call FIRECRAWL_SEARCH through Composio's multi-tool executor.

        Firecrawl search supports scrape options; explicitly requesting markdown is
        important because the returned result objects otherwise vary by tool/schema
        and can contain no usable page payload.
        """
        await self.composio_mcp._ensure_initialized()
        session = await self.composio_mcp._get_session()
        arguments = {
            'query': query,
            'limit': limit,
            'scrape_options': {'formats': ['markdown']},
        }
        payload = {
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
            'params': {
                'name': 'COMPOSIO_MULTI_EXECUTE_TOOL',
                'arguments': {
                    'tools': [{'tool_slug': 'FIRECRAWL_SEARCH', 'arguments': arguments}],
                    'memory': {},
                },
            },
        }
        async with session.post(self.composio_mcp.mcp_url, headers=self.composio_mcp.headers, json=payload) as resp:
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}: {await resp.text()}")
            text = await resp.text()
            for line in text.splitlines():
                if not line.startswith('data: '):
                    continue
                data = json.loads(line[6:])
                if 'error' in data:
                    raise Exception(f"MCP error: {data['error']}")
                content = data.get('result', {}).get('content', [])
                for block in content if isinstance(content, list) else []:
                    raw = block.get('text', '') if isinstance(block, dict) else str(block)
                    if not raw:
                        continue
                    parsed = self._parse_json_payload(raw)
                    if parsed is None:
                        continue
                    results = self._parse_search_results(parsed)
                    if results:
                        return results[:limit]
        return []

    @staticmethod
    def _parse_json_payload(raw: str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', raw, flags=re.DOTALL)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None

    def _parse_search_results(self, data: object) -> list[SearchResult]:
        candidates = []

        def walk(node, depth=0):
            if depth > 6:
                return
            if isinstance(node, dict):
                if node.get('url'):
                    candidates.append(node)
                for value in node.values():
                    walk(value, depth + 1)
            elif isinstance(node, list):
                for value in node:
                    walk(value, depth + 1)

        walk(data)
        results, seen = [], set()
        for item in candidates:
            url = str(item.get('url') or '').strip()
            parsed = urlparse(url)
            if not url or not parsed.scheme or not parsed.netloc or url in seen:
                continue
            seen.add(url)
            results.append(SearchResult(
                url=url,
                title=str(item.get('title') or ''),
                snippet=str(item.get('description') or item.get('snippet') or item.get('markdown') or '')[:500],
                source_type=self._classify_source(url),
                confidence=float(item.get('score') or 0.5),
            ))
        return results

    def _infer_category(self, query: str) -> str:
        q = query.lower()
        if any(x in q for x in ('pricing', 'plans', 'billing')): return 'pricing_docs'
        if any(x in q for x in ('mcp', 'model context protocol')): return 'mcp_docs'
        if any(x in q for x in ('authentication', 'authorization', 'oauth', 'api key', 'credentials')): return 'auth_docs'
        if any(x in q for x in ('api reference', 'api documentation', 'api docs', 'rest api', 'graphql')): return 'api_docs'
        return 'developer_docs'

    async def _fallback_search(self, query: str, limit: int = 5, website: str | None = None) -> list[SearchResult]:
        if not website:
            print('Firecrawl fallback skipped: no app website was supplied')
            return []
        app = query.split()[0] if query else 'unknown'
        category = self._infer_category(query)
        results = self.generate_urls(app, website, categories=[category])
        fallback = [self._to_search_result(item, self._classify_source_for_category(category)) for item in results.get(category, [])[:limit]]
        print(f"[Fallback] {query!r}: generated {len(fallback)} {category} candidates from {website}")
        return fallback

    def _classify_source(self, url: str) -> SourceType:
        u = url.lower()
        if 'mcp' in u or 'modelcontextprotocol' in u: return SourceType.MCP_REGISTRY
        if 'composio' in u: return SourceType.COMPOSIO_REGISTRY
        if any(x in u for x in ('developer.', 'docs.', 'api.', 'developer-docs.')):
            if any(x in u for x in ('auth', 'oauth', 'authorization')): return SourceType.AUTH_DOCS
            if 'pricing' in u or 'plan' in u: return SourceType.PRICING_DOCS
            return SourceType.OFFICIAL_DOCS
        return SourceType.WEB

    def generate_urls(self, app: str, website: str, categories: list[str] | None = None) -> dict:
        selected = categories or list(self.doc_patterns)
        results = {k: [] for k in selected}
        if not website.startswith(('http://', 'https://')): website = 'https://' + website
        parsed = urlparse(website)
        domain = parsed.netloc.lower().removeprefix('www.')
        base_url = self.known_domains.get(domain, f'https://{domain}')
        for category in selected:
            for pattern in self.doc_patterns.get(category, [])[:5]:
                results[category].append({
                    'url': urljoin(base_url, pattern),
                    'title': f'{category.replace("_", " ").title()} for {app}',
                    'snippet': f'Generated from pattern: {pattern}',
                    'source_type': self._classify_source_for_category(category),
                    'confidence': 0.7,
                })
        return results

    def _classify_source_for_category(self, category: str) -> SourceType:
        return {
            'developer_docs': SourceType.OFFICIAL_DOCS,
            'auth_docs': SourceType.AUTH_DOCS,
            'api_docs': SourceType.OFFICIAL_DOCS,
            'mcp_docs': SourceType.MCP_REGISTRY,
            'pricing_docs': SourceType.PRICING_DOCS,
        }.get(category, SourceType.WEB)

    def set_app(self, app: str): self.app = app
    async def find_developer_docs(self, app: str, website: str): self.set_app(app); return await self.search(f'{app} developer documentation', 5, website)
    async def find_auth_docs(self, app: str, website: str): self.set_app(app); return await self.search(f'{app} API authentication', 5, website)
    async def find_api_reference(self, app: str, website: str): self.set_app(app); return await self.search(f'{app} API reference', 5, website)
    async def find_mcp_evidence(self, app: str, website: str): self.set_app(app); return await self.search(f'{app} MCP server', 5, website)
    async def find_pricing_access(self, app: str, website: str): self.set_app(app); return await self.search(f'{app} pricing plans developer', 5, website)

    def _to_search_result(self, item: dict, source_type: SourceType) -> SearchResult:
        url = str(item.get('url') or '').strip()
        if not url:
            raise ValueError('Fallback generated an empty URL')
        return SearchResult(url=url, title=item.get('title', ''), snippet=item.get('snippet', ''), source_type=SourceType(item.get('source_type', source_type)), confidence=item.get('confidence', 0.7))
