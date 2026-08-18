import asyncio
import os
from dotenv import load_dotenv
load_dotenv(r'D:\Composio Assignment\composio-app-research\.env')
import sys
sys.path.insert(0, r'D:\Composio Assignment\composio-app-research')

async def test():
    from agent.researcher import NemotronClient
    
    client = NemotronClient()
    prompt = 'Return ONLY valid JSON: {"auth_methods": ["oauth2"], "confidence": 0.9, "citations": ["https://api.slack.com/docs"]}'
    response = await client.complete_async(prompt, temperature=0.1, max_tokens=200)
    print('Response:', repr(response))

asyncio.run(test())