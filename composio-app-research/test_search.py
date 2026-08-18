import asyncio
import json
import os
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")


async def main():
    api_key = os.getenv("COMPOSIO_API_KEY")
    if not api_key:
        raise RuntimeError("COMPOSIO_API_KEY is required")

    mcp_url = "https://connect.composio.dev/mcp"
    headers = {
        "x-consumer-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    async with aiohttp.ClientSession() as session:
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "composio-firecrawl-smoke-test", "version": "1.0"},
            },
        }
        async with session.post(mcp_url, headers=headers, json=init_payload) as resp:
            print("INIT:", (await resp.text())[:300])

        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "COMPOSIO_MULTI_EXECUTE_TOOL",
                "arguments": {
                    "tools": [{
                        "tool_slug": "FIRECRAWL_SEARCH",
                        "arguments": {
                            "query": "Slack developer documentation",
                            "limit": 5,
                            "scrape_options": {"formats": ["markdown"]},
                        },
                    }],
                    "memory": {},
                },
            },
        }
        async with session.post(mcp_url, headers=headers, json=payload) as resp:
            text = await resp.text()
            print("SEARCH RESPONSE:")
            print(text[:10000])


if __name__ == "__main__":
    asyncio.run(main())
