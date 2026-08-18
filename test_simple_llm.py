import asyncio
import os
from dotenv import load_dotenv
load_dotenv(r'D:\Composio Assignment\composio-app-research\.env')
import sys
sys.path.insert(0, r'D:\Composio Assignment\composio-app-research')

async def test():
    from agent.researcher import NemotronClient
    
    client = NemotronClient()
    prompt = 'What is 2+2? Return JSON: {"answer": 4}'
    response = await client.complete_async(prompt, temperature=0.1, max_tokens=50)
    print('Response:', response)

asyncio.run(test())