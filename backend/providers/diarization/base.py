from abc import ABC, abstractmethod
from typing import AsyncGenerator
from ...models.audio import AudioInput, AudioFrame
from ...models.diarization import DiarizationOptions, DiarizationResult, DiarizationSegment

class DiarizationStream(ABC):
    @abstractmethod
    async def push_audio(self, frame: AudioFrame) -> None:
        """Pushes an incoming streaming audio frame."""
        pass

    @abstractmethod
    async def get_results(self) -> AsyncGenerator[DiarizationSegment, None]:
        """Yields streaming speaker activity intervals."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Flushes and terminates diarization stream."""
        pass

class DiarizationProvider(ABC):
    @abstractmethod
    async def process_file(self, audio: AudioInput, options: DiarizationOptions) -> DiarizationResult:
        """Runs diarization over the full audio input offline."""
        pass

    @abstractmethod
    async def start_stream(self, options: DiarizationOptions) -> DiarizationStream:
        """Initializes a live streaming diarization session."""
        pass
