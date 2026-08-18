import os
import asyncio
from dotenv import load_dotenv
load_dotenv(r'D:\Composio Assignment\composio-app-research\.env')
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url='https://integrate.api.nvidia.com/v1',
    api_key=os.getenv('NVIDIA_API_KEY'),
)

async def test():
    completion = await client.chat.completions.create(
        model='nvidia/nemotron-3-super-120b-a12b',
        messages=[{'role': 'user', 'content': 'Return only JSON: {"auth_methods": ["oauth2"], "confidence": 0.9}'}],
        temperature=0.1,
        max_tokens=200,
    )
    print(completion.choices[0].message.content)

asyncio.run(test())