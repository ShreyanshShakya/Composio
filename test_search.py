import asyncio
import os
import json
from dotenv import load_dotenv
load_dotenv(r'D:\Composio Assignment\composio-app-research\.env')

async def test():
    import aiohttp
    api_key = os.getenv('COMPOSIO_API_KEY')
    mcp_url = 'https://connect.composio.dev/mcp'
    headers = {
        'x-consumer-api-key': api_key,
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
    }
    session = aiohttp.ClientSession()
    
    # Initialize
    init_payload = {
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'initialize',
        'params': {
            'protocolVersion': '2024-11-05',
            'capabilities': {},
            'clientInfo': {'name': 'test', 'version': '1.0'}
        }
    }
    
    async with session.post(mcp_url, headers=headers, json=init_payload) as resp:
        text = await resp.text()
        print('INIT:', text[:200])
    
    # Search
    call_payload = {
        'jsonrpc': '2.0',
        'id': 2,
        'method': 'tools/call',
        'params': {
            'name': 'COMPOSIO_MULTI_EXECUTE_TOOL',
            'arguments': {
                'tools': [
                    {
                        'tool_slug': 'FIRECRAWL_SEARCH',
                        'arguments': {
                            'query': 'Slack developer documentation',
                            'limit': 5,
                            'scrape_options': {'formats': ['markdown']}
                        }
                    }
                ],
                'memory': {}
            }
        }
    
    async with session.post(mcp_url, headers=headers, json=call_payload) as resp:
        text = await resp.text()
        print('SEARCH RESPONSE:')
        print(text[:5000])
    
    await session.close()

asyncio.run(test())