import os
import time
import httpx
from typing import Optional
from ...models.translation import TranslationRequest, TranslationResult
from .base import TranslationProvider

SARVAM_TRANSLATE_URL = "https://api.sarvam.ai/translate"

class SarvamTranslationProvider(TranslationProvider):
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SARVAM_API_KEY", "")

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY is not configured for translation.")

        start_time = time.time()
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "input": request.text,
            "source_language_code": request.source_language,
            "target_language_code": request.target_language,
            "model": request.model or "sarvam-translate:v1"
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(SARVAM_TRANSLATE_URL, headers=headers, json=payload)
            if res.status_code != 200:
                raise RuntimeError(f"Sarvam Translation API error ({res.status_code}): {res.text}")
            data = res.json()

        latency = time.time() - start_time
        translated_text = data.get("translated_text", "")

        return TranslationResult(
            original_text=request.text,
            translated_text=translated_text,
            source_language=request.source_language,
            target_language=request.target_language,
            latency_sec=round(latency, 3)
        )
