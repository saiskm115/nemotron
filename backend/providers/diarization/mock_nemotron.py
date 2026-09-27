import time
from typing import List, AsyncGenerator
from ...models.audio import AudioInput, AudioFrame
from ...models.diarization import DiarizationOptions, DiarizationResult, DiarizationSegment
from .base import DiarizationProvider, DiarizationStream

SAMPLE_DIARIZATION_SEGMENTS = [
    # Speaker 0 (e.g. Mohan)
    DiarizationSegment(speaker_id="speaker_0", start=0.15, end=3.25, confidence=0.95),
    # Speaker 1 (e.g. Priya)
    DiarizationSegment(speaker_id="speaker_1", start=3.40, end=7.05, confidence=0.94),
    # Overlapping speech segment: Speaker 0 barges in slightly before Priya finishes
    DiarizationSegment(speaker_id="speaker_0", start=6.80, end=10.05, confidence=0.91),
    # Speaker 1 responds
    DiarizationSegment(speaker_id="speaker_1", start=10.20, end=14.30, confidence=0.96)
]

class MockDiarizationStream(DiarizationStream):
    def __init__(self, options: DiarizationOptions):
        self.options = options
        self.closed = False

    async def push_audio(self, frame: AudioFrame) -> None:
        pass

    async def get_results(self) -> AsyncGenerator[DiarizationSegment, None]:
        for seg in SAMPLE_DIARIZATION_SEGMENTS:
            yield seg

    async def close(self) -> None:
        self.closed = True

class MockNemotronProvider(DiarizationProvider):
    def __init__(self):
        pass

    async def process_file(self, audio: AudioInput, options: DiarizationOptions) -> DiarizationResult:
        start_time = time.time()
        duration = audio.metadata.duration_sec if audio.metadata else 15.0

        segments: List[DiarizationSegment] = []
        for s in SAMPLE_DIARIZATION_SEGMENTS:
            if s.start <= duration:
                end_time = min(s.end, duration)
                segments.append(
                    DiarizationSegment(
                        speaker_id=s.speaker_id,
                        start=s.start,
                        end=end_time,
                        confidence=s.confidence
                    )
                )

        speakers = sorted(list(set(s.speaker_id for s in segments)))
        # Count overlaps
        overlap_count = 1 if len(segments) >= 3 else 0

        return DiarizationResult(
            segments=segments,
            speakers=speakers,
            overlap_count=overlap_count,
            latency_sec=round(time.time() - start_time + 0.1, 3)
        )

    async def start_stream(self, options: DiarizationOptions) -> DiarizationStream:
        return MockDiarizationStream(options)
