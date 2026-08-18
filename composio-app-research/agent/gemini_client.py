import os
import re
from typing import Any

import aiohttp

from agent.rate_limiter import AsyncRateLimiter


class GeminiQuotaExhausted(RuntimeError):
    """Raised when Gemini reports a hard quota exhaustion rather than transient throttling."""


class GeminiClient:
    """Gemini 3.5 Flash-Lite REST client with RPM limiting and quota circuit breaker."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required")
        self.base_url = os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta/models",
        )
        rpm = int(os.getenv("GEMINI_RPM_LIMIT", "12"))
        self._rate_limiter = AsyncRateLimiter(max_calls=rpm, period_seconds=60.0)
        self._session: aiohttp.ClientSession | None = None
        self._quota_exhausted = False

    @property
    def quota_exhausted(self) -> bool:
        return self._quota_exhausted

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    @staticmethod
    def _is_hard_quota_error(status: int, body: str) -> bool:
        if status != 429:
            return False
        markers = (
            "generate_content_free_tier_requests",
            "daily quota",
            "free_tier_requests",
            "quota exceeded",
        )
        return any(marker in body.lower() for marker in markers)

    @staticmethod
    def _retry_after(body: str) -> float | None:
        match = re.search(r"retry in ([0-9]+(?:\\.[0-9]+)?)s", body, re.I)
        return float(match.group(1)) if match else None

    async def complete_async(self, prompt: str, temperature: float = 0.1, max_tokens: int = 2000) -> str:
        if self._quota_exhausted:
            raise GeminiQuotaExhausted("Gemini daily/free-tier quota is exhausted")

        await self._rate_limiter.acquire()
        session = await self._get_session()
        url = f"{self.base_url.rstrip('/')}/{self.model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json",
                "thinkingConfig": {"thinkingLevel": "minimal"},
            },
        }
        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key,
        }
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=90)) as response:
            body = await response.text()
            if response.status >= 400:
                if self._is_hard_quota_error(response.status, body):
                    self._quota_exhausted = True
                    retry_after = self._retry_after(body)
                    suffix = f"; server retry hint={retry_after:.1f}s" if retry_after is not None else ""
                    raise GeminiQuotaExhausted(f"Gemini hard quota exhausted{suffix}")
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
