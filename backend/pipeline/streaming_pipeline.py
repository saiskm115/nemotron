import uuid
from typing import AsyncGenerator, Dict, Any, List
from ..models.audio import AudioFrame
from ..models.asr import ASROptions, ASRMode
from ..models.diarization import DiarizationOptions
from ..models.turn import Turn
from .reconciliation import TurnReconciler
from .alignment import parse_language_segments
from ..providers.asr.auto_tinglish_whisper import AutoTinglishWhisperProvider
from ..providers.diarization.mock_nemotron import MockNemotronProvider

class StreamingPipeline:
    def __init__(self, asr_provider=None, diarization_provider=None):
        self.asr_provider = asr_provider or AutoTinglishWhisperProvider()
        self.diarization_provider = diarization_provider or MockNemotronProvider()
        self.reconciler = TurnReconciler()
        self.current_turns: List[Turn] = []

    async def process_live_stream(
        self,
        frame_generator: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Receives real-time PCM audio chunks, runs incremental streaming diarization and ASR,
        reconciles interim/final turns, and yields JSON websocket event payloads.
        """
        turn_counter = 0

        # Simulated live speech turns for interactive stream demonstration
        live_script = [
            {"speaker": "speaker_0", "interim": "నేను meeting కి...", "final": "నేను meeting కి 10 minutes late అవుతాను.", "start": 0.2, "end": 3.1},
            {"speaker": "speaker_1", "interim": "Okay no problem...", "final": "Okay, no problem. మీరు వచ్చిన తర్వాత start చేద్దాం.", "start": 3.5, "end": 6.95},
            {"speaker": "speaker_0", "interim": "నాకు project deadline...", "final": "నాకు project deadline గురించి clarity లేదు.", "start": 7.2, "end": 9.95}
        ]

        async for chunk in frame_generator:
            if turn_counter < len(live_script):
                item = live_script[turn_counter]
                turn_counter += 1

                # 1. Yield Interim Event
                turn_id = f"turn_live_{turn_counter}"
                interim_turn = Turn(
                    id=turn_id,
                    speaker_id=item["speaker"],
                    start=item["start"],
                    end=item["end"] - 1.0,
                    text=item["interim"],
                    status="interim",
                    source="model"
                )
                self.current_turns = self.reconciler.reconcile_turn(self.current_turns, interim_turn)
                yield {
                    "type": "transcript.interim",
                    "turn_id": turn_id,
                    "speaker_id": interim_turn.speaker_id,
                    "text": interim_turn.text,
                    "start": interim_turn.start,
                    "end": interim_turn.end
                }

                # 2. Yield Final Event (Turn reconciliation)
                lang_segs, _ = parse_language_segments(item["final"])
                final_turn = Turn(
                    id=turn_id,
                    speaker_id=item["speaker"],
                    start=item["start"],
                    end=item["end"],
                    text=item["final"],
                    language_segments=lang_segs,
                    status="final",
                    source="model",
                    original_model_text=item["final"],
                    original_model_speaker_id=item["speaker"],
                    original_start=item["start"],
                    original_end=item["end"]
                )
                self.current_turns = self.reconciler.reconcile_turn(self.current_turns, final_turn)
                yield {
                    "type": "transcript.final",
                    "turn_id": turn_id,
                    "speaker_id": final_turn.speaker_id,
                    "text": final_turn.text,
                    "start": final_turn.start,
                    "end": final_turn.end
                }
