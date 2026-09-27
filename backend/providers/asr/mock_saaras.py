import time
import uuid
from typing import List, AsyncGenerator
from ...models.audio import AudioInput, AudioFrame
from ...models.asr import ASROptions, ASRResult, ASRChunk, ASRToken, ASRMode
from .base import ASRProvider, ASRStream

TELUGU_ENGLISH_SAMPLE_TURNS = [
    {
        "text": "నేను meeting కి 10 minutes late అవుతాను.",
        "tokens": [
            ("నేను", 0.20, 0.70, "te"),
            ("meeting", 0.75, 1.15, "en"),
            ("కి", 1.20, 1.40, "te"),
            ("10", 1.45, 1.70, "en"),
            ("minutes", 1.75, 2.10, "en"),
            ("late", 2.15, 2.50, "en"),
            ("అవుతాను.", 2.55, 3.10, "te")
        ]
    },
    {
        "text": "Okay, no problem. మీరు వచ్చిన తర్వాత start చేద్దాం.",
        "tokens": [
            ("Okay,", 3.50, 3.85, "en"),
            ("no", 3.90, 4.10, "en"),
            ("problem.", 4.15, 4.60, "en"),
            ("మీరు", 4.70, 5.05, "te"),
            ("వచ్చిన", 5.10, 5.50, "te"),
            ("తర్వాత", 5.55, 5.95, "te"),
            ("start", 6.00, 6.35, "en"),
            ("చేద్దాం.", 6.40, 6.95, "te")
        ]
    },
    {
        "text": "నాకు project deadline గురించి clarity లేదు.",
        "tokens": [
            ("నాకు", 7.20, 7.60, "te"),
            ("project", 7.65, 8.05, "en"),
            ("deadline", 8.10, 8.55, "en"),
            ("గురించి", 8.60, 9.05, "te"),
            ("clarity", 9.10, 9.50, "en"),
            ("లేదు.", 9.55, 9.95, "te")
        ]
    },
    {
        "text": "Don't worry, Ramesh రేపు morning లో complete చేస్తాను అన్నారు.",
        "tokens": [
            ("Don't", 10.30, 10.60, "en"),
            ("worry,", 10.65, 11.00, "en"),
            ("Ramesh", 11.10, 11.55, "en"),
            ("రేపు", 11.60, 11.95, "te"),
            ("morning", 12.00, 12.45, "en"),
            ("లో", 12.50, 12.70, "te"),
            ("complete", 12.75, 13.20, "en"),
            ("చేస్తాను", 13.25, 13.70, "te"),
            ("అన్నారు.", 13.75, 14.20, "te")
        ]
    }
]

class MockASRStream(ASRStream):
    def __init__(self, options: ASROptions):
        self.options = options
        self.closed = False
        self._sent = False

    async def push_audio(self, frame: AudioFrame) -> None:
        pass

    async def get_results(self) -> AsyncGenerator[ASRChunk, None]:
        # Yield interim then final turn
        yield ASRChunk(
            id=str(uuid.uuid4()),
            text="నేను meeting కి...",
            start=0.2,
            end=1.4,
            is_final=False
        )
        yield ASRChunk(
            id=str(uuid.uuid4()),
            text="నేను meeting కి 10 minutes late అవుతాను.",
            start=0.2,
            end=3.1,
            is_final=True
        )

    async def close(self) -> None:
        self.closed = True

class MockSaarasProvider(ASRProvider):
    def __init__(self):
        pass

    async def transcribe_file(self, audio: AudioInput, options: ASROptions) -> ASRResult:
        start_time = time.time()
        
        all_tokens: List[ASRToken] = []
        all_chunks: List[ASRChunk] = []

        # If audio duration is provided, adapt sample turns
        duration = audio.metadata.duration_sec if audio.metadata else 15.0

        for sample in TELUGU_ENGLISH_SAMPLE_TURNS:
            # Check if within duration
            if sample["tokens"][0][1] > duration and len(all_chunks) > 0:
                break

            chunk_tokens: List[ASRToken] = []
            for word, s, e, lang in sample["tokens"]:
                token = ASRToken(
                    id=str(uuid.uuid4()),
                    text=word,
                    start=s,
                    end=e,
                    language=lang,
                    is_final=True
                )
                chunk_tokens.append(token)
                all_tokens.append(token)

            chunk = ASRChunk(
                id=str(uuid.uuid4()),
                text=sample["text"],
                start=sample["tokens"][0][1],
                end=sample["tokens"][-1][2],
                tokens=chunk_tokens,
                language="te-IN",
                is_final=True
            )
            all_chunks.append(chunk)

        full_transcript = " ".join(c.text for c in all_chunks)
        latency = round(time.time() - start_time + 0.12, 3)

        return ASRResult(
            transcript=full_transcript,
            language_code="te-IN",
            language_probability=0.96,
            chunks=all_chunks,
            tokens=all_tokens,
            latency_sec=latency
        )

    async def start_stream(self, options: ASROptions) -> ASRStream:
        return MockASRStream(options)
