import requests
import json
import os
from dotenv import load_dotenv
load_dotenv(r'D:\Composio Assignment\composio-app-research\.env')

print('Step 1: Loading env')
api_key = os.getenv('COMPOSIO_API_KEY')
print('API Key:', api_key[:20] + '...' if api_key else 'NOT SET')

mcp_url = 'https://connect.composio.dev/mcp'
headers = {
    'x-consumer-api-key': api_key,
    'Content-Type': 'application/json',
    'Accept': 'application/json, text/event-stream',
}

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
try:
    resp = requests.post(mcp_url, headers=headers, json=init_payload, timeout=30)
    print('INIT status:', resp.status_code)
    print('INIT:', resp.text[:200])
except Exception as e:
    print('INIT ERROR:', e)
    import traceback
    traceback.print_exc()

tools_payload = {
    'jsonrpc': '2.0',
    'id': 2,
    'method': 'tools/list',
    'params': {}
}

print('Listing tools...')
try:
    resp = requests.post('https://connect.composio.dev/mcp', headers=headers, json=tools_payload, timeout=30)
    print('TOOLS status:', resp.status_code)
    print('TOOLS response length:', len(resp.text))
    
    for line in resp.text.split('\n'):
        if line.startswith('data: '):
            data = json.loads(line[6:])
            if 'result' in data and 'tools' in data['result']:
                for tool in data['result']['tools']:
                    name = tool.get('name', '')
                    if 'firecrawl' in name.lower() or 'search' in name.lower():
                        print('  ' + name + ': ' + tool.get('description', '')[:100])
except Exception as e:
    print('ERROR:', e)
    import traceback
    traceback.print_exc()

print('Done')