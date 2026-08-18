import os
import asyncio
import json
from typing import Any
from dataclasses import dataclass
from agent.models import AppResearch, SourceType, Evidence
from agent.evidence import normalize_source_type, calculate_confidence


@dataclass
class FirecrawlResult:
    url: str
    content: str
    metadata: dict
    success: bool
    error: str | None = None


class ComposioMCPClient:
    """Composio MCP client for querying available integrations/toolkits and Firecrawl."""
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("COMPOSIO_API_KEY")
        self.mcp_url = "https://connect.composio.dev/mcp"
        self.headers = {
            "x-consumer-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        self._session = None
        self._tools_cache: list[dict] | None = None
        self._initialized = False
    
    async def _get_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None
    
    async def _ensure_initialized(self):
        """Initialize MCP connection if not done."""
        if self._initialized:
            return
        
        session = await self._get_session()
        
        # MCP initialize
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "app-research-agent", "version": "1.0"}
            }
        }
        
        async with session.post(self.mcp_url, headers=self.headers, json=init_payload) as resp:
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"MCP initialize failed: {resp.status} - {error_text}")
        
        self._initialized = True
    
    async def list_toolkits(self) -> list[dict]:
        """Get list of available toolkits/integrations from Composio via MCP."""
        if self._tools_cache is not None:
            return self._tools_cache
        
        try:
            await self._ensure_initialized()
            session = await self._get_session()
            
            # List tools
            tools_payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            
            async with session.post(self.mcp_url, headers=self.headers, json=tools_payload) as resp:
                if resp.status != 200:
                    return []
                
                # Parse SSE response
                text = await resp.text()
                for line in text.split('\n'):
                    if line.startswith('data: '):
                        import json
                        data = json.loads(line[6:])
                        if 'result' in data and 'tools' in data['result']:
                            tools = data['result']['tools']
                            self._tools_cache = tools
                            return tools
                
                return []
                
        except Exception as e:
            print(f"[ComposioMCP] Error fetching toolkits: {e}")
            return []
    
    def check_app_supported(self, app_name: str, tools: list[dict] | None = None) -> tuple[bool, str | None]:
        """Check if an app is supported by Composio."""
        if tools is None:
            import asyncio
            tools = asyncio.run(self.list_toolkits())
        
        app_lower = app_name.lower().replace(" ", "").replace("-", "").replace("_", "")
        
        for tool in tools:
            tool_name = tool.get("name", "").lower().replace(" ", "").replace("-", "").replace("_", "")
            tool_desc = tool.get("description", "").lower()
            
            # Match by name or description
            if app_lower in tool_name or tool_name in app_lower:
                return True, tool.get("name")
            if app_lower in tool_desc:
                return True, tool.get("name")
        
        # Fuzzy matching for common variations
        variations = {
            "salesforce": ["salesforce", "sfdc"],
            "github": ["github", "gh"],
            "googleads": ["googleads", "google-ads", "adwords"],
            "metaads": ["metaads", "facebook-ads", "fb-ads"],
            "linkedinads": ["linkedinads", "linkedin-ads"],
            "whatsappbusiness": ["whatsapp", "whatsapp-business", "wa-business"],
            "amazonsellingpartner": ["amazon-sp-api", "amazon-selling-partner", "sp-api"],
            "woocommerce": ["woocommerce", "wc-api"],
            "salesforcecommercecloud": ["salesforce-commerce", "sfcc"],
            "adobecommerce": ["magento", "adobe-commerce"],
            "datadoghq": ["datadog", "datadoghq"],
            "mongodb": ["mongodb-atlas", "mongo-atlas"],
            "googlecloud": ["gcp", "google-cloud"],
            "aws": ["amazon-web-services", "aws"],
            "azure": ["microsoft-azure", "azure"],
        }
        
        for key, aliases in variations.items():
            if app_lower == key or app_lower in aliases:
                for tool in tools:
                    tool_name = tool.get("name", "").lower()
                    for alias in aliases:
                        if alias in tool_name:
                            return True, tool.get("name")
        
        return False, None
    
    async def firecrawl_scrape(self, url: str, params: dict | None = None) -> "FirecrawlResult":
        """Scrape a single URL using Firecrawl via Composio MCP."""
        from agent.researcher import FirecrawlResult
        
        await self._ensure_initialized()
        
        default_params = {
            "url": url,
            "max_pages": 1,
            "only_main_content": True,
            "wait_for": 1000,
            "formats": ["markdown"],
        }
        if params:
            default_params.update(params)
        
        session = await self._get_session()
        
        # Call Firecrawl tool via MCP - try common tool names
        tool_names = ["firecrawl_scrape", "firecrawl", "scrape"]
        
        for tool_name in tool_names:
            call_payload = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": default_params
                }
            }
            
            try:
                async with session.post(self.mcp_url, headers=self.headers, json=call_payload) as resp:
                    if resp.status != 200:
                        continue
                    
                    data = await resp.json()
                    
                    if "error" in data:
                        continue
                    
                    result = data.get("result", {})
                    content = result.get("content", "")
                    if isinstance(content, list):
                        content = "\n".join(str(c) for c in content)
                    
                    return FirecrawlResult(
                        url=url,
                        content=content,
                        metadata=result.get("metadata", {}),
                        success=True,
                        error=None
                    )
            except Exception:
                continue
        
        return FirecrawlResult(
            url=url,
            content="",
            metadata={},
            success=False,
            error="Firecrawl tool not found or failed"
        )
    
    async def firecrawl_crawl(self, url: str, params: dict | None = None) -> list["FirecrawlResult"]:
        """Crawl multiple pages from a starting URL."""
        from agent.researcher import FirecrawlResult
        
        await self._ensure_initialized()
        
        default_params = {
            "url": url,
            "max_pages": 3,
            "only_main_content": True,
            "wait_for": 1000,
            "formats": ["markdown"],
        }
        if params:
            default_params.update(params)
        
        session = await self._get_session()
        
        tool_names = ["firecrawl_crawl", "firecrawl_crawl", "crawl"]
        
        for tool_name in tool_names:
            call_payload = {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": default_params
                }
            }
            
            try:
                async with session.post(self.mcp_url, headers=self.headers, json=call_payload) as resp:
                    if resp.status != 200:
                        continue
                    
                    data = await resp.json()
                    result = data.get("result", {})
                    content = result.get("content", "")
                    
                    if isinstance(content, list):
                        return [FirecrawlResult(
                            url=url,
                            content=str(c),
                            metadata={},
                            success=True
                        ) for c in content]
                    
                    return [FirecrawlResult(
                        url=url,
                        content=str(content),
                        metadata={},
                        success=True
                    )]
            except Exception:
                continue
        
        return []


class HTTPScraper:
    """Simple HTTP-based web scraper as Firecrawl fallback."""
    
    def __init__(self):
        self._client = None
    
    async def _get_client(self):
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": "Mozilla/5.0 (compatible; AppResearchBot/1.0)"},
                follow_redirects=True,
            )
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def scrape(self, url: str) -> FirecrawlResult:
        """Scrape a single URL using HTTP + basic HTML parsing."""
        client = await self._get_client()
        
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                return FirecrawlResult(
                    url=url,
                    content="",
                    metadata={},
                    success=False,
                    error=f"HTTP {resp.status_code}"
                )
            
            # Basic HTML content extraction
            content = resp.text
            
            # Try to extract main content (remove scripts, styles, etc.)
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    script.decompose()
                
                # Get text content
                text = soup.get_text(separator='\n', strip=True)
                
                # Clean problematic Unicode characters
                text = text.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
                
                # Limit length
                if len(text) > 10000:
                    text = text[:10000] + "... [truncated]"
                
                content = text
            except ImportError:
                # BeautifulSoup not available, use raw HTML (truncated)
                if len(content) > 10000:
                    content = content[:10000] + "... [truncated]"
            
            return FirecrawlResult(
                url=url,
                content=content,
                metadata={"status_code": resp.status_code},
                success=True,
                error=None
            )
        except Exception as e:
            return FirecrawlResult(
                url=url,
                content="",
                metadata={},
                success=False,
                error=str(e)
            )


class Researcher:
    """Orchestrates adaptive research for a single app."""
    
    def __init__(self, llm_client: Any, composio_mcp: ComposioMCPClient | None = None):
        self.llm = llm_client
        self.composio_mcp = composio_mcp or ComposioMCPClient()
        self.http_scraper = HTTPScraper()
    
    async def close(self):
        """Close all connections."""
        await self.composio_mcp.close()
        await self.http_scraper.close()
    
    def build_research_urls(self, app: str, website: str, category: str) -> list[tuple[str, str]]:
        """Build prioritized URLs for research passes."""
        base = website.rstrip("/")
        if not base.startswith("http"):
            base = f"https://{base}"
        
        pass1_urls = [
            (f"{base}/developers", "official_docs"),
            (f"{base}/docs", "official_docs"),
            (f"{base}/api", "official_docs"),
            (f"{base}/developer", "official_docs"),
        ]
        
        pass1_auth = [
            (f"{base}/developers/auth", "auth_docs"),
            (f"{base}/docs/auth", "auth_docs"),
            (f"{base}/docs/authentication", "auth_docs"),
            (f"{base}/api/auth", "auth_docs"),
            (f"{base}/auth", "auth_docs"),
        ]
        
        pass1_api = [
            (f"{base}/developers/api", "official_docs"),
            (f"{base}/docs/api", "official_docs"),
            (f"{base}/api/reference", "official_docs"),
            (f"{base}/docs/reference", "official_docs"),
        ]
        
        urls = []
        for url, stype in pass1_urls[:3]:
            urls.append((url, stype))
        for url, stype in pass1_auth[:2]:
            urls.append((url, stype))
        for url, stype in pass1_api[:2]:
            urls.append((url, stype))
        
        return urls
    
    def build_targeted_urls(self, research: AppResearch, gaps: list[str]) -> list[tuple[str, str]]:
        """Build URLs for specific knowledge gaps."""
        urls = []
        base = f"https://{research.app.lower().replace(' ', '')}.com"
        
        if "credential_access" in gaps:
            urls.extend([
                (f"{base}/pricing", "pricing_docs"),
                (f"{base}/developers/pricing", "pricing_docs"),
                (f"{base}/get-started", "official_docs"),
            ])
        
        if "mcp" in gaps:
            urls.extend([
                (f"{base}/mcp", "mcp_registry"),
                (f"https://github.com/search?q={research.app}+mcp", "web"),
                (f"https://modelcontextprotocol.io/servers", "mcp_registry"),
            ])
        
        if "auth" in gaps:
            urls.extend([
                (f"{base}/docs/auth", "auth_docs"),
                (f"{base}/developers/authentication", "auth_docs"),
            ])
        
        return urls[:3]
    
    async def research_app(self, app: str, website: str, category: str) -> AppResearch:
        """Run adaptive research for a single app."""
        
        # Pass 1: Core documentation
        urls = self.build_research_urls(app, website, category)
        evidence = []
        
        for url, expected_type in urls:
            result = await self.http_scraper.scrape(url)
            if result.success and result.content:
                source_type = normalize_source_type(url, expected_type)
                evidence.append(Evidence(
                    claim=f"Documentation from {url}",
                    url=url,
                    source_type=source_type,
                    supporting_text=result.content[:3000],
                ))
        
        # Check Composio registry for supported integrations
        composio_tools = await self.composio_mcp.list_toolkits()
        supported, tool_name = self.composio_mcp.check_app_supported(app, composio_tools)
        if supported:
            evidence.append(Evidence(
                claim=f"Composio supports {app} via {tool_name}",
                url="https://connect.composio.dev",
                source_type=SourceType.COMPOSIO_REGISTRY,
                supporting_text=f"Found in Composio toolkits: {tool_name}",
            ))
        
        # Extract structured data via LLM
        research = await self.extract_with_llm(app, category, evidence)
        
        # Override composio_supported based on actual registry check
        from agent.models import MCPStatus
        research.composio_supported = MCPStatus.YES if supported else MCPStatus.NO
        if tool_name:
            research.evidence.append(Evidence(
                claim=f"Composio integration: {tool_name}",
                url="https://connect.composio.dev",
                source_type=SourceType.COMPOSIO_REGISTRY,
                supporting_text=f"Verified in Composio registry: {tool_name}",
            ))
        
        # Identify gaps
        gaps = self.identify_gaps(research)
        
        # Pass 2: Targeted research if needed
        if gaps and research.confidence < 0.8:
            targeted_urls = self.build_targeted_urls(research, gaps)
            for url, expected_type in targeted_urls:
                result = await self.http_scraper.scrape(url)
                if result.success and result.content:
                    source_type = normalize_source_type(url, expected_type)
                    evidence.append(Evidence(
                        claim=f"Targeted research: {expected_type} from {url}",
                        url=url,
                        source_type=source_type,
                        supporting_text=result.content[:3000],
                    ))
            
            # Re-extract with additional evidence
            research = await self.extract_with_llm(app, category, evidence)
            # Re-check Composio after re-extraction
            supported, tool_name = self.composio_mcp.check_app_supported(app, composio_tools)
            research.composio_supported = MCPStatus.YES if supported else MCPStatus.NO
        
        # Final confidence calculation
        research.confidence = calculate_confidence(research)
        research.sources = list(set(e.url for e in research.evidence))
        
        return research
    
    def identify_gaps(self, research: AppResearch) -> list[str]:
        """Identify knowledge gaps requiring targeted research."""
        gaps = []
        
        if research.auth_methods == [research.auth_methods[0]] if research.auth_methods else [] and research.auth_methods[0].value == "unknown":
            gaps.append("auth")
        
        if research.credential_access.value == "unknown":
            gaps.append("credential_access")
        
        if research.api_types == [research.api_types[0]] if research.api_types else [] and research.api_types[0].value == "other":
            gaps.append("api")
        
        if research.mcp_public.value == "unknown":
            gaps.append("mcp")
        
        if research.buildability.value == "unknown":
            gaps.append("buildability")
        
        return gaps
    
    async def extract_with_llm(self, app: str, category: str, evidence: list) -> AppResearch:
        """Extract structured research using LLM."""
        
        evidence_text = "\n\n---\n\n".join([
            f"SOURCE: {e.url}\nTYPE: {e.source_type.value}\nCONTENT: {e.supporting_text}"
            for e in evidence[:10]
        ])
        
        prompt = f"""You are an integration research analyst. Research {app} ({category}) using ONLY the evidence below.

EVIDENCE:
{evidence_text}

Return JSON matching this exact schema:
{{
  "app": "{app}",
  "category": "{category}",
  "description": "1-2 sentence description",
  "auth_methods": ["oauth2" | "api_key" | "basic" | "bearer_token" | "pat" | "service_account" | "other" | "multiple" | "unknown"],
  "credential_access": "self_serve" | "self_serve_with_trial" | "paid_plan_required" | "admin_approval" | "partner_required" | "contact_sales" | "unknown",
  "api_types": ["rest" | "graphql" | "soap" | "grpc" | "webhooks" | "mcp" | "other"],
  "api_breadth": "broad" | "limited" | "unknown",
  "mcp_public": "yes" | "no" | "unknown",
  "composio_supported": "yes" | "no" | "unknown",
  "buildability": "ready" | "buildable_with_caveat" | "human_outreach_required" | "blocked" | "unknown",
  "blocker": "specific blocker description or null",
  "uncertainty": ["list of specific uncertainties"]
}}

CRITICAL RULES:
1. Only use evidence provided. Mark "unknown" if evidence insufficient.
2. Distinguish API existence from credential accessibility.
3. Self-serve = developer can get credentials without sales/contact.
4. MCP = public MCP server exists (not just Composio toolkit).
5. Composio_supported = only if evidence shows Composio has this integration.
6. Buildability: ready=all green, caveat=minor issues, outreach=needs partnership, blocked=hard barrier.
7. Return ONLY valid JSON. No markdown, no explanation."""

        response = await self.llm.complete_async(prompt, temperature=0.1, max_tokens=16384)
        
        from agent.evidence import extract_json_from_response, validate_and_repair_research
        data = extract_json_from_response(response)
        
        if data:
            data["app"] = app
            data["category"] = category
            data["evidence"] = [e.model_dump() for e in evidence]
            validated = validate_and_repair_research(data, app, max_retries=1)
            if validated:
                return validated
        
        # Fallback if parsing fails
        from agent.models import AppResearch, AuthMethod, CredentialAccess, APIType, APIBreadth, MCPStatus, Buildability
        return AppResearch(
            app=app,
            category=category,
            description=f"Research placeholder for {app}",
            auth_methods=[AuthMethod.UNKNOWN],
            credential_access=CredentialAccess.UNKNOWN,
            api_types=[APIType.OTHER],
            api_breadth=APIBreadth.UNKNOWN,
            mcp_public=MCPStatus.UNKNOWN,
            composio_supported=MCPStatus.UNKNOWN,
            buildability=Buildability.UNKNOWN,
            blocker="LLM response parsing failed",
            evidence=evidence,
            uncertainty=["LLM response parsing failed"],
            confidence=0.0,
        )


class NemotronClient:
    """NVIDIA Nemotron API client using OpenAI SDK."""
    
    def __init__(self, api_key: str | None = None, base_url: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("NVIDIA_API_KEY")
        self.base_url = base_url or os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
        self.model = model or os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-super-120b-a12b")
        self._client = None
    
    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        return self._client
    
    def complete(self, prompt: str, temperature: float = 0.1, max_tokens: int = 16384) -> str:
        """Call Nemotron API with reasoning support."""
        client = self._get_client()
        
        completion = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            top_p=0.95,
            max_tokens=max_tokens,
            extra_body={
                "chat_template_kwargs": {"enable_thinking": True},
                "reasoning_budget": 16384,
            },
            stream=True,
        )
        
        content_parts = []
        for chunk in completion:
            if not chunk.choices:
                continue
            if chunk.choices[0].delta.content is not None:
                content_parts.append(chunk.choices[0].delta.content)
        
        return "".join(content_parts)
    
    async def complete_async(self, prompt: str, temperature: float = 0.1, max_tokens: int = 16384) -> str:
        """Async wrapper for sync complete method."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.complete, prompt, temperature, max_tokens)