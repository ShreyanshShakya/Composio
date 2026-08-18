"""Run a small cross-app validation matrix before the full 100-app batch.

Usage:
  python scripts/pilot_validate.py
  python scripts/pilot_validate.py --apps Slack GitHub Stripe Notion
  python scripts/pilot_validate.py --limit 5 --output data/pilot_results.json

The harness intentionally runs apps sequentially so Gemini rate limiting is not
made worse by launching multiple full extraction pipelines at once. Each app's
internal Firecrawl discovery semaphore remains responsible for search concurrency.
"""
import argparse
import asyncio
import csv
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.evidence import calculate_confidence
from agent.models import AppResearch, MCPStatus
from agent.researcher import ComposioMCPClient, Researcher, create_llm_client

DEFAULT_APPS = [
    "Slack", "GitHub", "Stripe", "Notion", "HubSpot",
    "Linear", "Salesforce", "Airtable", "Monday.com", "Discord",
]


def load_apps(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = csv.DictReader(f)
        return {row["app"].strip().lower(): row for row in rows if row.get("app")}


async def run_one(researcher: Researcher, composio: ComposioMCPClient, row: dict[str, str]) -> dict:
    app = row["app"]
    website = row["website"]
    category = row.get("category", "unknown")
    try:
        discovery = await researcher.discoverer.discover(app, website)
        groups = [
            discovery.developer_docs, discovery.auth_docs, discovery.api_docs,
            discovery.mcp_docs, discovery.pricing_docs,
        ]
        selected = researcher.scorer.select_best(researcher.scorer.deduplicate([u for g in groups for u in g]))

        evidence = []
        for item in selected:
            scraped = await researcher._scrape_with_fallback(item.url)
            if scraped.success and scraped.content:
                from agent.models import Evidence
                evidence.append(Evidence(
                    claim=f"Documentation from {item.url}",
                    url=item.url,
                    source_type=item.source_type,
                    supporting_text=scraped.content[:3000],
                ))

        tools = await composio.list_toolkits()
        supported, _ = composio.check_app_supported(app, tools)

        if not evidence:
            return {
                "app": app, "category": category, "website": website,
                "status": "NO_EVIDENCE", "discovered": len([u for g in groups for u in g]),
                "selected": len(selected), "evidence": 0,
            }

        auth = await researcher.extractor.extract_auth(evidence)
        cred = await researcher.extractor.extract_credential(evidence)
        api = await researcher.extractor.extract_api(evidence)
        mcp = await researcher.extractor.extract_mcp(evidence)
        buildability, blocker = researcher.extractor.determine_buildability(auth, cred, api, mcp)

        result = AppResearch(
            app=app,
            category=category,
            description=f"Integration research for {app}",
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

        def values(items):
            return [getattr(x, "value", str(x)) for x in items]

        return {
            "app": app, "category": category, "website": website, "status": "OK",
            "discovered": len([u for g in groups for u in g]), "selected": len(selected),
            "evidence": len(evidence), "auth": values(auth.auth_methods),
            "credential": getattr(cred.credential_access, "value", str(cred.credential_access)),
            "api_types": values(api.api_types),
            "api_breadth": getattr(api.api_breadth, "value", str(api.api_breadth)),
            "mcp": getattr(mcp.mcp_public, "value", str(mcp.mcp_public)),
            "composio": supported,
            "buildability": getattr(buildability, "value", str(buildability)),
            "blocker": blocker,
            "confidence": round(result.confidence, 2),
            "citations": len(set(c for obj in (auth, cred, api, mcp) for c in obj.citations)),
        }
    except Exception as exc:
        return {"app": app, "category": category, "website": website, "status": "ERROR", "error": str(exc)}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apps", nargs="+", default=DEFAULT_APPS)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", default="data/pilot_results.json")
    args = parser.parse_args()

    csv_path = PROJECT_ROOT / "data" / "apps.csv"
    app_map = load_apps(csv_path)
    requested = args.apps[:args.limit] if args.limit else args.apps

    rows = []
    missing = []
    for name in requested:
        row = app_map.get(name.lower())
        if row:
            rows.append(row)
        else:
            missing.append(name)

    if missing:
        print("Missing from data/apps.csv:", ", ".join(missing))
    if not rows:
        raise SystemExit("No requested apps found in data/apps.csv")

    os.environ.setdefault("LLM_DEBUG", "0")
    llm = create_llm_client()
    composio = ComposioMCPClient()
    researcher = Researcher(llm, composio)
    results = []

    print(f"Pilot validation: {len(rows)} apps; sequential app execution")
    try:
        for index, row in enumerate(rows, 1):
            print(f"\n[{index}/{len(rows)}] {row['app']} — {row['website']}")
            result = await run_one(researcher, composio, row)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False))
    finally:
        await researcher.close()

    output_path = PROJECT_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n=== PILOT SUMMARY ===")
    print("App | Status | Evidence | Auth | API | MCP | Buildability | Confidence")
    print("--- | --- | ---: | --- | --- | --- | --- | ---:")
    for r in results:
        print(f"{r['app']} | {r['status']} | {r.get('evidence', 0)} | {r.get('auth', ['-'])} | {r.get('api_types', ['-'])} | {r.get('mcp', '-')} | {r.get('buildability', '-')} | {r.get('confidence', '-')}")
    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
