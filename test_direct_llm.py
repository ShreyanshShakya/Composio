import os
from dotenv import load_dotenv
load_dotenv(r'D:\Composio Assignment\composio-app-research\.env')

from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.getenv("NVIDIA_API_KEY"),
)

async def test():
    print("Calling LLM...")
    completion = await client.chat.completions.create(
        model="nvidia/nemotron-3-super-120b-a12b",
        messages=[{"role": "user", "content": "Say hello"}],
        temperature=0.1,
        top_p=0.95,
        max_tokens=100,
        extra_body={
            "chat_template_kwargs": {"enable_thinking": True},
            "reasoning_budget": 16384,
        },
        stream=True,
    )
    
    content_parts = []
    async for chunk in completion:
        if not chunk.choices:
            continue
        if chunk.choices[0].delta.content is not None:
            content_parts.append(chunk.choices[0].delta.content)
    
    print("Response:", "".join(content_parts))

import asyncio
asyncio.run(test())