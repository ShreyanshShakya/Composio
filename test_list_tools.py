import asyncio
import os
import json
import aiohttp
from dotenv import load_dotenv
load_dotenv(r'D:\Composio Assignment\composio-app-research\.env')

async def test():
    api_key = os.getenv('COMPOSIO_API_KEY')
    mcp_url = 'https://connect.composio.dev/mcp'
    headers = {
        'x-consumer-api-key': api_key,
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream',
    }
    session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
    
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
    
    print('Initializing...')
    async with session.post(mcp_url, headers=headers, json=init_payload) as resp:
        text = await resp.text()
        print('INIT:', resp.status, text[:200])
    
    tools_payload = {
        'jsonrpc': '2.0',
        'id': 2,
        'method': 'tools/list',
        'params': {}
    }
    
    print('Listing tools...')
    async with session.post(mcp_url, headers=headers, json=tools_payload) as resp:
        text = await resp.text()
        print('TOOLS status:', resp.status)
        print('TOOLS response length:', len(text))
        for line in text.split('\n'):
            if line.startswith('data: '):
                data = json.loads(line[6:])
                if 'result' in data and 'tools' in data['result']:
                    for tool in data['result']['tools']:
                        name = tool.get('name', '')
                        if 'firecrawl' in name.lower() or 'search' in name.lower():
                            print('  ' + name + ': ' + tool.get('description', '')[:100])
    
    await session.close()

asyncio.run(test())