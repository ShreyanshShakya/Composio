import os
from dotenv import load_dotenv
load_dotenv(r'D:\Composio Assignment\composio-app-research\.env')
from openai import OpenAI

client = OpenAI(
    base_url='https://integrate.api.nvidia.com/v1',
    api_key=os.getenv('NVIDIA_API_KEY'),
)

print('Calling...')
try:
    completion = client.chat.completions.create(
        model='nvidia/nemotron-3-super-120b-a12b',
        messages=[
            {'role': 'system', 'content': 'Return ONLY valid JSON. No explanations, no markdown, no extra text. Only the requested JSON object.'},
            {'role': 'user', 'content': 'Return JSON: {"a": 1}'}
        ],
        temperature=0.1,
        max_tokens=50,
        timeout=30,
    )
    print('Response:', completion.choices[0].message.content)
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()

print('Done')