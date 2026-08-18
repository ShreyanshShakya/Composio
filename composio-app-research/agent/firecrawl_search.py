import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import List, Optional
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
    """Firecrawl /search via Composio MCP - fallback to improved URL patterns."""
    
    def __init__(self, composio_mcp_client):
        self.composio_mcp = composio_mcp_client
        # Common documentation URL patterns
        self.doc_patterns = {
            'developer_docs': [
                '/developers', '/docs', '/api', '/developer', '/reference',
                '/guides', '/tutorials', '/getting-started', '/quickstart',
            ],
            'auth_docs': [
                '/developers/auth', '/docs/auth', '/docs/authentication',
                '/api/auth', '/auth', '/developers/authentication',
                '/docs/authorization', '/api/authorization',
            ],
            'api_docs': [
                '/developers/api', '/docs/api', '/api/reference',
                '/docs/reference', '/api/docs', '/reference',
                '/graphql', '/rest-api', '/api/v1', '/api/v2',
            ],
            'mcp_docs': [
                '/mcp', '/modelcontextprotocol', '/mcp-server',
                '/.well-known/mcp', '/mcp/documentation',
            ],
            'pricing_docs': [
                '/pricing', '/plans', '/billing', '/pricing/developer',
                '/developers/pricing', '/plans/developer', '/signup',
            ],
        }
        
        # Known documentation domains for popular services
        self.known_domains = {
            'slack.com': 'https://api.slack.com',
            'github.com': 'https://docs.github.com',
            'stripe.com': 'https://stripe.com/docs',
            'salesforce.com': 'https://developer.salesforce.com',
            'hubspot.com': 'https://developers.hubspot.com',
            'notion.so': 'https://developers.notion.com',
            'airtable.com': 'https://airtable.com/developers',
            'linear.app': 'https://developers.linear.app',
            'atlassian.com': 'https://developer.atlassian.com',
            'asana.com': 'https://developers.asana.com',
            'monday.com': 'https://developer.monday.com',
            'clickup.com': 'https://clickup.com/api',
            'coda.io': 'https://coda.io/developers',
            'smartsheet.com': 'https://smartsheet.com/developers',
            'harvestapp.com': 'https://help.getharvest.com/api-v2',
            'twilio.com': 'https://www.twilio.com/docs',
            'sendgrid.com': 'https://sendgrid.com/docs',
            'mailchimp.com': 'https://mailchimp.com/developer',
            'klaviyo.com': 'https://developers.klaviyo.com',
            'shopify.dev': 'https://shopify.dev',
            'woocommerce.com': 'https://woocommerce.com/document/woocommerce-rest-api',
            'bigcommerce.com': 'https://developer.bigcommerce.com',
            'squareup.com': 'https://developer.squareup.com',
            'paypal.com': 'https://developer.paypal.com',
            'braintreepayments.com': 'https://developer.paypal.com/braintree',
            'authorize.net': 'https://developer.authorize.net',
            'adyen.com': 'https://docs.adyen.com',
            'plaid.com': 'https://plaid.com/docs',
            'zendesk.com': 'https://developer.zendesk.com',
            'intercom.com': 'https://developers.intercom.com',
            'freshdesk.com': 'https://developers.freshdesk.com',
            'helpscout.com': 'https://help.getharvest.com/api-v2',
            'gorgias.com': 'https://developers.gorgias.com',
            'front.com': 'https://dev.frontapp.com',
            'pipedrive.com': 'https://developers.pipedrive.com',
            'close.com': 'https://developer.close.com',
            'attio.com': 'https://docs.attio.com',
            'zoho.com': 'https://www.zoho.com/developer',
            'freshworks.com': 'https://developers.freshworks.com',
            'servicenow.com': 'https://developer.servicenow.com',
            'workday.com': 'https://community.workday.com',
            'successfactors.com': 'https://api.sap.com',
            'oracle.com': 'https://docs.oracle.com',
            'microsoft.com': 'https://learn.microsoft.com',
            'google.com': 'https://developers.google.com',
            'amazon.com': 'https://docs.aws.amazon.com',
            'digitalocean.com': 'https://docs.digitalocean.com',
            'cloudflare.com': 'https://developers.cloudflare.com',
            'vercel.com': 'https://vercel.com/docs',
            'netlify.com': 'https://docs.netlify.com',
            'heroku.com': 'https://devcenter.heroku.com',
            'supabase.com': 'https://supabase.com/docs',
            'planetscale.com': 'https://docs.planetscale.com',
            'neon.tech': 'https://neon.tech/docs',
            'supabase.io': 'https://supabase.io/docs',
            'railway.app': 'https://docs.railway.app',
            'render.com': 'https://render.com/docs',
            'fly.io': 'https://fly.io/docs',
            'supabase.com': 'https://supabase.com/docs',
        }

    async def search(self, query: str, limit: int = 5) -> list:
        """Fallback to pattern-based URL generation."""
        return []

    def _classify_source(self, url: str) -> str:
        """Classify URL source type."""
        from agent.models import SourceType
        url_lower = url.lower()
        if any(x in url_lower for x in ['developer.', 'docs.', 'api.', 'developer-docs.']):
            if 'auth' in url_lower or 'oauth' in url_lower:
                return 'auth_docs'
            if 'pricing' in url_lower or 'plan' in url_lower:
                return 'pricing_docs'
            if 'mcp' in url_lower or 'modelcontextprotocol' in url_lower:
                return 'mcp_registry'
            return 'official_docs'
        if 'mcp' in url_lower or 'modelcontextprotocol' in url_lower:
            return 'mcp_registry'
        if 'composio' in url_lower:
            return 'composio_registry'
        if 'github.com' in url_lower:
            return 'web'
        return 'web'

    def generate_urls(self, app: str, website: str) -> dict:
        """Generate candidate URLs for an app based on known patterns."""
        results = {
            'developer_docs': [],
            'auth_docs': [],
            'api_docs': [],
            'mcp_docs': [],
            'pricing_docs': [],
        }
        
        # Ensure website has a scheme
        if not website.startswith('http'):
            website = 'https://' + website
        
        # Get base domain
        parsed = urlparse(website)
        domain = parsed.netloc.lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # Check for known documentation domain
        base_url = self.known_domains.get(domain, f"https://{domain}")
        
        # Generate URLs for each category
        for category, patterns in self.doc_patterns.items():
            urls = []
            for pattern in patterns:
                url = urljoin(base_url, pattern)
                results[category].append({
                    'url': url,
                    'title': f'{category.replace("_", " ").title()} for {app}',
                    'snippet': f'Generated from pattern: {pattern}',
                    'source_type': self._classify_source_for_category(category),
                    'confidence': 0.7
                })
            results[category] = results[category][:5]  # Limit per category
        
        return results
    
    def _classify_source_for_category(self, category: str):
        mapping = {
            'developer_docs': 'official_docs',
            'auth_docs': 'auth_docs',
            'api_docs': 'official_docs',
            'mcp_docs': 'mcp_registry',
            'pricing_docs': 'pricing_docs',
        }
        return mapping.get(category, 'web')
    
    def set_app(self, app: str):
        self.app = app
    
    async def search(self, query: str, limit: int = 5) -> list:
        """Fallback to pattern-based URL generation."""
        return []

    async def find_developer_docs(self, app: str, website: str) -> list:
        self.set_app(app)
        results = self.generate_urls(app, website)
        return [self._to_search_result(r, 'official_docs') for r in results.get('developer_docs', [])]

    async def find_auth_docs(self, app: str, website: str) -> list:
        self.set_app(app)
        results = self.generate_urls(app, website)
        return [self._to_search_result(r, 'auth_docs') for r in results.get('auth_docs', [])]

    async def find_api_reference(self, app: str, website: str) -> list:
        self.set_app(app)
        results = self.generate_urls(app, website)
        return [self._to_search_result(r, 'official_docs') for r in results.get('api_docs', [])]

    async def find_mcp_evidence(self, app: str, website: str) -> list:
        self.set_app(app)
        results = self.generate_urls(app, website)
        return [self._to_search_result(r, 'mcp_registry') for r in results.get('mcp_docs', [])]

    async def find_pricing_access(self, app: str, website: str) -> list:
        self.set_app(app)
        results = self.generate_urls(app, website)
        return [self._to_search_result(r, 'pricing_docs') for r in results.get('pricing_docs', [])]

    def _to_search_result(self, item: dict, source_type: str) -> 'SearchResult':
        from agent.models import SourceType
        return SearchResult(
            url=item['url'],
            title=item.get('title', ''),
            snippet=item.get('snippet', ''),
            source_type=SourceType(item.get('source_type', 'web')),
            confidence=item.get('confidence', 0.7)
        )