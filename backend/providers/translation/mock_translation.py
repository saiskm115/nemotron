import time
from ...models.translation import TranslationRequest, TranslationResult
from .base import TranslationProvider

TELUGU_TRANSLATION_MAP = {
    "నేను meeting కి 10 minutes late అవుతాను.": "I will be 10 minutes late to the meeting.",
    "Okay, no problem. మీరు వచ్చిన తర్వాత start చేద్దాం.": "Okay, no problem. Let's start after you arrive.",
    "నాకు project deadline గురించి clarity లేదు.": "I do not have clarity regarding the project deadline.",
    "Don't worry, Ramesh రేపు morning లో complete చేస్తాను అన్నారు.": "Don't worry, Ramesh said he will complete it tomorrow morning.",
    "మీరు ఎప్పుడు వస్తారు?": "When are you coming?",
    "నాకు రేపు office కి వెళ్లాలి.": "I need to go to the office tomorrow.",
    "మీరు report send చేశారా?": "Did you send the report?",
    "Yes, నేను already పంపించాను.": "Yes, I have already sent it.",
    "Project deadline ఎప్పుడు?": "When is the project deadline?",
    "రేపు morning లో complete చేస్తాను.": "I will complete it by tomorrow morning.",
    "నిన్న manager నాకు call చేశారు.": "Yesterday the manager called me.",
    "Okay, మనం తర్వాత discuss చేద్దాం.": "Okay, we will discuss it later."
}

class MockTranslationProvider(TranslationProvider):
    def __init__(self):
        pass

    async def translate(self, request: TranslationRequest) -> TranslationResult:
        start_time = time.time()
        
        # Check direct lookup
        clean_text = request.text.strip()
        translated = TELUGU_TRANSLATION_MAP.get(clean_text)
        
        if not translated:
            # Fallback for dynamic phrases: preserve english parts, add readable translation placeholder
            translated = f"[Translation to {request.target_language}]: {clean_text}"

        return TranslationResult(
            original_text=request.text,
            translated_text=translated,
            source_language=request.source_language,
            target_language=request.target_language,
            latency_sec=round(time.time() - start_time + 0.05, 3)
        )
