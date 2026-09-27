from typing import Optional
from pydantic import BaseModel, Field

class TranslationRequest(BaseModel):
    text: str
    source_language: str = "te-IN"
    target_language: str = "en-IN"
    model: str = "sarvam-translate:v1"

class TranslationResult(BaseModel):
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    latency_sec: float = 0.0
