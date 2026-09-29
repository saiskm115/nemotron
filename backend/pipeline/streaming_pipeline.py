"""
Live streaming pipeline.

Streaming ASR and streaming diarisation are not implemented: Svanita is an offline
recogniser and the local diariser works on complete recordings. Rather than emit a
scripted transcript, this pipeline reports the limitation to the client and stops.
Live capture is therefore unusable today, and the UI says so instead of showing
plausible-looking invented turns.
"""
import logging
from typing import Any, AsyncGenerator, Dict, List

from ..models.turn import Turn
from .reconciliation import TurnReconciler

logger = logging.getLogger(__name__)

UNSUPPORTED_MESSAGE = (
    "Live streaming transcription is not available: the configured speech recognition "
    "models are offline-only. Upload a recording to run the pipeline."
)


class StreamingPipeline:
    def __init__(self, asr_provider=None, diarization_provider=None):
        self.asr_provider = asr_provider
        self.diarization_provider = diarization_provider
        self.reconciler = TurnReconciler()
        self.current_turns: List[Turn] = []

    async def process_live_stream(
        self, frame_generator: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Consumes PCM chunks and emits transcript events.

        Emits a single ``unsupported`` event and returns. No turns are fabricated.
        """
        async for _chunk in frame_generator:
            break

        logger.info(UNSUPPORTED_MESSAGE)
        yield {
            "type": "unsupported",
            "message": UNSUPPORTED_MESSAGE,
        }
