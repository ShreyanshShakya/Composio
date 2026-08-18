import asyncio
import os
from dotenv import load_dotenv
load_dotenv(r'D:\Composio Assignment\composio-app-research\.env')
from openai import AsyncOpenAI

async def test():
    client = AsyncOpenAI(
        base_url='https://integrate.api.nvidia.com/v1',
        api_key=os.getenv('NVIDIA_API_KEY'),
    )
    
    completion = await client.chat.completions.create(
        model='nvidia/nemotron-3-super-120b-a12b',
        messages=[
            {'role': 'system', 'content': 'Return ONLY valid JSON. No explanations, no markdown, no extra text. Only the requested JSON object.'},
            {'role': 'user', 'content': 'Return JSON: {"a": 1}'}
        ],
        temperature=0.1,
        max_tokens=50,
        stream=False,
    )
    print('Response:', repr(completion.choices[0].message.content))

asyncio.run(test())