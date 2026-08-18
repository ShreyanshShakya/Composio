import asyncio
import os
from dotenv import load_dotenv
load_dotenv(r'D:\Composio Assignment\composio-app-research\.env')
import sys
sys.path.insert(0, r'D:\Composio Assignment\composio-app-research')

async def test():
    from agent.researcher import NemotronClient
    
    client = NemotronClient()
    response1 = await client.complete_async('Say hello', temperature=0.1, max_tokens=50)
    print('Response 1:', repr(response1))
    
    response2 = await client.complete_async('Return JSON: {"a": 1}', temperature=0.1, max_tokens=50)
    print('Response 2:', repr(response2))

asyncio.run(test())