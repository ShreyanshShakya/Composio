import asyncio
import os
from dotenv import load_dotenv
load_dotenv(r'D:\Composio Assignment\composio-app-research\.env')
import sys
sys.path.insert(0, r'D:\Composio Assignment\composio-app-research')

async def test():
    from agent.researcher import NemotronClient
    
    print("Creating client...")
    client = NemotronClient()
    print("Client created")
    
    prompt = """You are an integration research analyst. Determine the authentication methods for this app using ONLY the evidence below.

EVIDENCE:
SOURCE: https://api.slack.com/docs
TYPE: official_docs
CONTENT: Slack uses OAuth 2.0 for authentication. Apps can use OAuth 2.0 to authenticate users and access Slack APIs.

Return JSON:
{
  "auth_methods": ["oauth2" | "api_key" | "basic" | "bearer_token" | "pat" | "service_account" | "other" | "multiple" | "unknown"],
  "confidence": 0.0-1.0,
  "citations": ["URL1", "URL2"]
}

RULES:
1. Only use evidence provided. Mark "unknown" if evidence insufficient.
2. Distinguish between auth methods (OAuth2, API key, etc.) and credential accessibility.
3. If multiple methods are clearly documented, use "multiple".
4. Return ONLY valid JSON."""

    print("Calling LLM...")
    response = await client.complete_async(prompt, temperature=0.1, max_tokens=2000)
    print('Response:')
    print(response)

asyncio.run(test())