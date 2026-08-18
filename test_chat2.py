import os
import requests
from dotenv import load_dotenv
load_dotenv(r'D:\Composio Assignment\composio-app-research\.env')

headers = {
    'Authorization': f'Bearer {os.getenv("NVIDIA_API_KEY")}',
    'Content-Type': 'application/json',
}

print('Sending request...')
try:
    resp = requests.post(
        'https://integrate.api.nvidia.com/v1/chat/completions',
        headers=headers,
        json={
            'model': 'nvidia/nemotron-3-super-120b-a12b',
            'messages': [{'role': 'user', 'content': 'Say hello'}],
            'temperature': 0.1,
            'max_tokens': 50,
        },
        timeout=10
    )
    print('Status:', resp.status_code)
    print(resp.text[:500])
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()