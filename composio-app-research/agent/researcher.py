import os
import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from agent.models import (AppResearch, SourceType, Evidence, AuthMethod,
                          CredentialAccess, APIType, APIBreadth, MCPStatus, Buildability)
from agent.evidence import normalize_source_type, calculate_confidence, extract_json_from_response, validate_and_repair_research
from agent.validation import validate_extraction_citations
from agent.firecrawl_search import FirecrawlSearcher
from agent.discoverer import Discoverer
from agent.url_scorer import URLScorer
from agent.extractor import NemotronExtractor
from agent.gemini_client import GeminiClient


@dataclass
class FirecrawlResult:
    url: str
    content: str
    metadata: dict
    success: bool
    error: str | None = None


class ComposioMCPClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("COMPOSIO_API_KEY")
        self.mcp_url = "https://connect.composio.dev/mcp"
        self.headers = {"x-consumer-api-key": self.api_key, "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        self._session = None
        self._tools_cache = None
        self._initialized = False

    async def _get_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session:
            await self._session.close(); self._session = None

    async def _ensure_initialized(self):
        if self._initialized: return
        if not self.api_key: raise ValueError("COMPOSIO_API_KEY is required")
        session = await self._get_session()
        payload = {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"app-research-agent","version":"1.0"}}}
        async with session.post(self.mcp_url, headers=self.headers, json=payload) as resp:
            if resp.status != 200: raise Exception(f"MCP initialize failed: {resp.status} - {await resp.text()}")
        self._initialized = True

    async def list_toolkits(self) -> list[dict]:
        if self._tools_cache is not None: return self._tools_cache
        try:
            await self._ensure_initialized(); session = await self._get_session()
            payload = {"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
            async with session.post(self.mcp_url, headers=self.headers, json=payload) as resp:
                if resp.status != 200: return []
                text = await resp.text()
                for line in text.split("\n"):
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if "result" in data and "tools" in data["result"]:
                            self._tools_cache = data["result"]["tools"]; return self._tools_cache
        except Exception as e:
            print(f"[ComposioMCP] Error fetching toolkits: {e}")
        return []

    def check_app_supported(self, app: str, tools: list[dict]) -> tuple[bool, str | None]:
        needle = "".join(ch for ch in app.lower() if ch.isalnum())
        for tool in tools or []:
            if not isinstance(tool, dict): continue
            haystack = " ".join(str(tool.get(k, "")) for k in ("name","title","description","toolkit","app"))
            normalized = "".join(ch for ch in haystack.lower() if ch.isalnum())
            if needle and needle in normalized: return True, str(tool.get("name") or tool.get("title") or app)
        return False, None

    async def firecrawl_scrape(self, url: str, params: dict | None = None) -> FirecrawlResult:
        await self._ensure_initialized()
        p = {"url":url,"formats":["markdown"],"onlyMainContent":True}; p.update(params or {})
        session = await self._get_session()
        payload = {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"COMPOSIO_MULTI_EXECUTE_TOOL","arguments":{"tools":[{"tool_slug":"FIRECRAWL_SCRAPE","arguments":p}],"memory":{}}}}
        try:
            async with session.post(self.mcp_url, headers=self.headers, json=payload) as resp:
                if resp.status != 200: return FirecrawlResult(url,"",{},False,f"HTTP {resp.status}: {await resp.text()}")
                text = await resp.text()
                for line in text.split("\n"):
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if "result" in data and "content" in data["result"]:
                            result_data = json.loads(data["result"]["content"][0]["text"])
                            results = result_data.get("data",{}).get("results",[])
                            if results:
                                markdown = results[0].get("response",{}).get("data",{}).get("data",{}).get("markdown")
                                if markdown: return FirecrawlResult(url,markdown,{"tool":"FIRECRAWL_SCRAPE"},True,None)
                return FirecrawlResult(url,"",{},False,"Failed to parse Firecrawl response")
        except Exception as e:
            return FirecrawlResult(url,"",{},False,str(e))


class HTTPScraper:
    def __init__(self): self._client = None
    async def _get_client(self):
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(timeout=30.0,headers={"User-Agent":"Mozilla/5.0 (compatible; AppResearchBot/1.0)"},follow_redirects=True)
        return self._client
    async def close(self):
        if self._client: await self._client.aclose(); self._client=None
    async def scrape(self,url:str)->FirecrawlResult:
        client=await self._get_client()
        try:
            resp=await client.get(url)
            if resp.status_code!=200:return FirecrawlResult(url,"",{},False,f"HTTP {resp.status_code}")
            content=resp.text
            try:
                from bs4 import BeautifulSoup
                soup=BeautifulSoup(content,"html.parser")
                for script in soup(["script","style","nav","footer","header","aside"]): script.decompose()
                content=soup.get_text(separator="\n",strip=True)
                if len(content)>10000: content=content[:10000]+"... [truncated]"
            except ImportError:
                if len(content)>10000: content=content[:10000]+"... [truncated]"
            return FirecrawlResult(url,content,{"status_code":resp.status_code},True,None)
        except Exception as e:return FirecrawlResult(url,"",{},False,str(e))


class Researcher:
    def __init__(self,llm_client:Any,composio_mcp:ComposioMCPClient|None=None):
        self.llm=llm_client; self.composio_mcp=composio_mcp or ComposioMCPClient(); self.http_scraper=HTTPScraper()
        self.firecrawl_searcher=FirecrawlSearcher(self.composio_mcp); self.discoverer=Discoverer(self.firecrawl_searcher); self.scorer=URLScorer(); self.extractor=NemotronExtractor(llm_client)

    async def close(self):
        await self.composio_mcp.close(); await self.http_scraper.close()
        close=getattr(self.llm,"close",None)
        if close:
            result=close()
            if asyncio.iscoroutine(result): await result

    async def _scrape_with_fallback(self,url:str)->FirecrawlResult:
        result=await self.composio_mcp.firecrawl_scrape(url)
        if result.success and result.content:return result
        return await self.http_scraper.scrape(url)

    async def research_app(self,app:str,website:str,category:str)->AppResearch:
        discovery=await self.discoverer.discover(app,website)
        all_scored=discovery.developer_docs+discovery.auth_docs+discovery.api_docs+discovery.mcp_docs+discovery.pricing_docs
        selected_urls=self.scorer.select_best(self.scorer.deduplicate(all_scored)); evidence=[]
        for url_obj in selected_urls:
            result=await self._scrape_with_fallback(url_obj.url)
            if result.success and result.content:
                evidence.append(Evidence(claim=f"Documentation from {url_obj.url}",url=url_obj.url,source_type=url_obj.source_type,supporting_text=result.content[:3000]))
        composio_tools=await self.composio_mcp.list_toolkits(); supported,tool_name=self.composio_mcp.check_app_supported(app,composio_tools)
        if supported:
            evidence.append(Evidence(claim=f"Composio supports {app} via {tool_name}",url="https://connect.composio.dev",source_type=SourceType.COMPOSIO_REGISTRY,supporting_text=f"Found in Composio toolkits: {tool_name}"))
        auth_ext=await self.extractor.extract_auth(evidence); cred_ext=await self.extractor.extract_credential(evidence); api_ext=await self.extractor.extract_api(evidence); mcp_ext=await self.extractor.extract_mcp(evidence)
        validations=[validate_extraction_citations(auth_ext,evidence,"auth"),validate_extraction_citations(cred_ext,evidence,"credential"),validate_extraction_citations(api_ext,evidence,"api"),validate_extraction_citations(mcp_ext,evidence,"mcp")]
        for result in validations:
            for warning in result.warnings: print(f"[Validation] {warning}")
        buildability,blocker=self.extractor.determine_buildability(auth_ext,cred_ext,api_ext,mcp_ext)
        research=AppResearch(app=app,category=category,description=f"Integration research for {app}",auth_methods=auth_ext.auth_methods,credential_access=cred_ext.credential_access,api_types=api_ext.api_types,api_breadth=api_ext.api_breadth,mcp_public=mcp_ext.mcp_public,composio_supported=MCPStatus.YES if supported else MCPStatus.NO,buildability=buildability,blocker=blocker,evidence=evidence,confidence=0.0)
        for ext,field in [(auth_ext,"auth"),(cred_ext,"credential"),(api_ext,"api"),(mcp_ext,"mcp")]:
            for citation in ext.citations:
                for e in evidence:
                    if e.url==citation:e.claim+=f" (cited for {field})"
        research.confidence=calculate_confidence(research); research.sources=list(set(e.url for e in evidence)); return research


class NemotronClient:
    def __init__(self,api_key:str|None=None,base_url:str|None=None,model:str|None=None):
        self.api_key=api_key or os.getenv("NVIDIA_API_KEY"); self.base_url=base_url or os.getenv("NVIDIA_BASE_URL","https://integrate.api.nvidia.com/v1"); self.model=model or os.getenv("NVIDIA_MODEL","nvidia/nemotron-3-super-120b-a12b"); self._sync_client=None; self._async_client=None
    def _get_sync_client(self):
        if self._sync_client is None:
            from openai import OpenAI; self._sync_client=OpenAI(base_url=self.base_url,api_key=self.api_key)
        return self._sync_client
    def _get_async_client(self):
        if self._async_client is None:
            from openai import AsyncOpenAI; self._async_client=AsyncOpenAI(base_url=self.base_url,api_key=self.api_key)
        return self._async_client
    def complete(self,prompt:str,temperature:float=.1,max_tokens:int=16384)->str:
        completion=self._get_sync_client().chat.completions.create(model=self.model,messages=[{"role":"user","content":prompt}],temperature=temperature,top_p=.95,max_tokens=max_tokens,extra_body={"chat_template_kwargs":{"enable_thinking":True},"reasoning_budget":16384},stream=True)
        return "".join(chunk.choices[0].delta.content for chunk in completion if chunk.choices and chunk.choices[0].delta.content is not None)
    async def complete_async(self,prompt:str,temperature:float=.1,max_tokens:int=16384)->str:
        completion=await self._get_async_client().chat.completions.create(model=self.model,messages=[{"role":"system","content":"You are a concise research analyst. Return ONLY valid JSON. No explanations, no markdown, no extra text. Only the requested JSON object."},{"role":"user","content":prompt}],temperature=temperature,top_p=.95,max_tokens=max_tokens,extra_body={"chat_template_kwargs":{"enable_thinking":False}},stream=False)
        return completion.choices[0].message.content or ""


def create_llm_client()->Any:
    provider=os.getenv("LLM_PROVIDER","gemini").strip().lower()
    if provider=="gemini":return GeminiClient()
    if provider=="nemotron":return NemotronClient()
    raise ValueError(f"Unsupported LLM_PROVIDER={provider!r}; use 'gemini' or 'nemotron'")
