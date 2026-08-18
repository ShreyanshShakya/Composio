import os
from typing import Any

import aiohttp


class GeminiClient:
    """Minimal Gemini REST client implementing the interface used by the extractor."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-flash-latest")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required")
        self.base_url = os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/models",
        )
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def complete_async(self, prompt: str, temperature: float = 0.1, max_tokens: int = 2000) -> str:
        session = await self._get_session()
        url = f"{self.base_url.rstrip('/')}/{self.model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
            },
        }
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key,
        }
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=90)) as response:
            body = await response.text()
            if response.status >= 400:
                raise RuntimeError(f"Gemini HTTP {response.status}: {body[:1000]}")
            data = await response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise RuntimeError("Gemini returned no candidates")
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
            if not text:
                raise RuntimeError("Gemini returned an empty response")
            return text

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None
