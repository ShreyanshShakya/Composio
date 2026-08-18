import asyncio
import os
import json
from dotenv import load_dotenv
load_dotenv(r'D:\Composio Assignment\composio-app-research\.env')

async def test():
    from agent.researcher import ComposioMCPClient
    
    composio = ComposioMCPClient()
    
    # List available tools
    tools = await composio.list_toolkits()
    print(f'Total tools: {len(tools)}')
    for tool in tools:
        name = tool.get('name', '')
        if 'firecrawl' in name.lower() or 'search' in name.lower():
            print(f'  FIRECRAWL RELATED: {name} - {tool.get("description", "")[:100]}')
        if 'search' in tool.get('name', '').lower():
            print(f'  SEARCH: {name}')
    
    # Check if FIRECRAWL_SEARCH exists
    firecrawl_tools = [t for t in tools if 'firecrawl' in t.get('name', '').lower()]
    print(f'\nFirecrawl tools: {len(firecrawl_tools)}')
    for t in firecrawl_tools:
        print(f'  {t.get("name")}: {t.get("description", "")[:200]}')
    
    await composio.close()

asyncio.run(test())