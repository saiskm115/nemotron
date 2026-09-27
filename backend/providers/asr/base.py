from abc import ABC, abstractmethod
from typing import AsyncGenerator
from ...models.audio import AudioInput, AudioFrame
from ...models.asr import ASROptions, ASRResult, ASRChunk

class ASRStream(ABC):
    @abstractmethod
    async def push_audio(self, frame: AudioFrame) -> None:
        """Pushes an incoming streaming audio frame (16kHz PCM)."""
        pass

    @abstractmethod
    async def get_results(self) -> AsyncGenerator[ASRChunk, None]:
        """Yields interim and final ASR chunks as they become available."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Flushes and closes the stream."""
        pass

class ASRProvider(ABC):
    @abstractmethod
    async def transcribe_file(self, audio: AudioInput, options: ASROptions) -> ASRResult:
        """Transcribes complete audio input offline."""
        pass

    @abstractmethod
    async def start_stream(self, options: ASROptions) -> ASRStream:
        """Starts real-time live streaming ASR session."""
        pass
