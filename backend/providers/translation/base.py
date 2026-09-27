from abc import ABC, abstractmethod
from ...models.translation import TranslationRequest, TranslationResult

class TranslationProvider(ABC):
    @abstractmethod
    async def translate(self, request: TranslationRequest) -> TranslationResult:
        """Translates input text from source language to target language."""
        pass
