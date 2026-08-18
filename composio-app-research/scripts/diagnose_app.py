"""Run one app through discovery, scraping, extraction, and confidence with diagnostics.

Usage:
  python scripts/diagnose_app.py Slack https://slack.com/ --category communication

This intentionally does not write research output files.
"""
import argparse
import asyncio
import os
from collections import Counter

from agent.researcher import ComposioMCPClient, Researcher, create_llm_client
from agent.evidence import calculate_confidence


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("app")
    parser.add_argument("website")
    parser.add_argument("--category", default="unknown")
    args = parser.parse_args()

    os.environ.setdefault("LLM_DEBUG", "1")
    llm = create_llm_client()
    composio = ComposioMCPClient()
    researcher = Researcher(llm, composio)

    try:
        print(f"=== DIAGNOSTIC: {args.app} ===")
        print(f"LLM provider: {type(llm).__name__}")

        discovery = await researcher.discoverer.discover(args.app, args.website)
        groups = {
            "developer_docs": discovery.developer_docs,
            "auth_docs": discovery.auth_docs,
            "api_docs": discovery.api_docs,
            "mcp_docs": discovery.mcp_docs,
            "pricing_docs": discovery.pricing_docs,
        }
        print("\n--- DISCOVERY ---")
        for name, urls in groups.items():
            print(f"{name}: {len(urls)}")
            for item in urls[:5]:
                print(f"  {item.url}")

        all_scored = [item for urls in groups.values() for item in urls]
        deduped = researcher.scorer.deduplicate(all_scored)
        selected = researcher.scorer.select_best(deduped)
        print(f"\nSelected URLs: {len(selected)}")
        for item in selected:
            print(f"  [{item.source_type.value}] {item.url}")

        evidence = []
        print("\n--- SCRAPING ---")
        for item in selected:
            result = await researcher._scrape_with_fallback(item.url)
            status = "OK" if result.success and result.content else "FAIL"
            print(f"{status}: {item.url} ({len(result.content)} chars)")
            if result.success and result.content:
                from agent.models import Evidence
                evidence.append(Evidence(
                    claim=f"Documentation from {item.url}",
                    url=item.url,
                    source_type=item.source_type,
                    supporting_text=result.content[:3000],
                ))

        tools = await composio.list_toolkits()
        supported, tool_name = composio.check_app_supported(args.app, tools)
        print(f"\nComposio support: {supported} ({tool_name})")
        print(f"Evidence count: {len(evidence)}")
        print(f"Evidence types: {dict(Counter(e.source_type.value for e in evidence))}")

        if not evidence:
            print("\nNO SCRAPED EVIDENCE. Extraction cannot be meaningful.")
            return

        print("\n--- EXTRACTION ---")
        auth = await researcher.extractor.extract_auth(evidence)
        print(f"auth: methods={auth.auth_methods} confidence={auth.confidence} citations={auth.citations}")
        cred = await researcher.extractor.extract_credential(evidence)
        print(f"credential: access={cred.credential_access} confidence={cred.confidence} citations={cred.citations}")
        api = await researcher.extractor.extract_api(evidence)
        print(f"api: types={api.api_types} breadth={api.api_breadth} confidence={api.confidence} citations={api.citations}")
        mcp = await researcher.extractor.extract_mcp(evidence)
        print(f"mcp: public={mcp.mcp_public} confidence={mcp.confidence} citations={mcp.citations}")

        buildability, blocker = researcher.extractor.determine_buildability(auth, cred, api, mcp)
        from agent.models import AppResearch, MCPStatus
        result = AppResearch(
            app=args.app,
            category=args.category,
            description=f"Integration research for {args.app}",
            auth_methods=auth.auth_methods,
            credential_access=cred.credential_access,
            api_types=api.api_types,
            api_breadth=api.api_breadth,
            mcp_public=mcp.mcp_public,
            composio_supported=MCPStatus.YES if supported else MCPStatus.NO,
            buildability=buildability,
            blocker=blocker,
            evidence=evidence,
            confidence=0.0,
        )
        result.confidence = calculate_confidence(result)
        print("\n--- FINAL ---")
        print(f"buildability: {result.buildability}")
        print(f"blocker: {result.blocker}")
        print(f"confidence: {result.confidence:.2f}")
    finally:
        await researcher.close()


if __name__ == "__main__":
    asyncio.run(main())
