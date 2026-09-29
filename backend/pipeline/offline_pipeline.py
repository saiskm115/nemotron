import os
import time
from pathlib import Path
from typing import Optional

from ..models.session import Session
from ..models.audio import AudioInput
from ..models.asr import ASROptions, ASRMode
from ..models.diarization import DiarizationOptions
from ..models.translation import TranslationRequest
from .audio_preprocessor import AudioPreprocessor
from .alignment import AlignmentEngine
from .backchannel_rescue import rescue_backchannels
from .turn_builder import TurnBuilder
from ..providers.asr.registry import get_asr_provider, primary_model_id
from ..providers.diarization.local_diarization import LocalDiarizationProvider
from ..providers.diarization.nemotron import NemotronDiarizationProvider
from ..providers.translation.sarvam import SarvamTranslationProvider
from ..providers.translation.mock_translation import MockTranslationProvider


def _env_int(name: str, fallback: int) -> int:
    """Reads a positive integer from the environment, ignoring anything unusable."""
    try:
        value = int(os.environ.get(name, "").strip())
    except (TypeError, ValueError):
        return fallback
    return value if value > 0 else fallback


class OfflinePipeline:
    def __init__(
        self,
        asr_provider=None,
        diarization_provider=None,
        translation_provider=None,
        audio_preprocessor=None
    ):
        self.preprocessor = audio_preprocessor or AudioPreprocessor(target_sample_rate=16000)
        self.alignment_engine = AlignmentEngine()
        self.turn_builder = TurnBuilder()

        # Determine providers based on env
        sarvam_key = os.environ.get("SARVAM_API_KEY", "")
        nemotron_endpoint = os.environ.get("NEMOTRON_ENDPOINT", "")

        # ASR model is resolved per session from session.settings.asr_model.
        self.default_asr_model = primary_model_id()
        self.asr_provider = asr_provider
        self.diarization_provider = diarization_provider or (
            NemotronDiarizationProvider(endpoint=nemotron_endpoint) if nemotron_endpoint else LocalDiarizationProvider()
        )
        self.translation_provider = translation_provider or (
            SarvamTranslationProvider(api_key=sarvam_key) if sarvam_key else MockTranslationProvider()
        )

    def _asr_for(self, model_id: Optional[str]):
        """Returns (provider, resolved_model_id) for the requested ASR model."""
        resolved = model_id if model_id else self.default_asr_model
        if self.asr_provider is not None:
            return self.asr_provider, resolved
        return get_asr_provider(resolved), resolved

    async def run(
        self,
        session: Session,
        audio_file_path: str,
        storage_session_dir: Path
    ) -> Session:
        start_total = time.time()
        session.processing_status = "processing"

        # 1. Preprocess audio
        out_wav_path = storage_session_dir / "audio_16k.wav"
        audio_input = AudioInput(file_path=audio_file_path)
        y, metadata, pcm_bytes = self.preprocessor.process(audio_input, output_path=out_wav_path)
        session.duration = metadata.duration_sec
        session.metadata["audio"] = metadata.model_dump()
        session.audio_file_path = str(out_wav_path)

        # 2. Run Diarization
        t0_diar = time.time()
        diar_options = DiarizationOptions(
            max_speakers=_env_int("DIARIZATION_MAX_SPEAKERS", 8),
            min_speakers=_env_int("DIARIZATION_MIN_SPEAKERS", 1),
        )
        prepared_input = AudioInput(
            file_path=str(out_wav_path),
            raw_bytes=pcm_bytes,
            metadata=metadata
        )
        diar_result = await self.diarization_provider.process_file(prepared_input, diar_options)
        diar_latency = time.time() - t0_diar

        # 3. Run ASR
        t0_asr = time.time()
        asr_mode_val = ASRMode.CODEMIXED
        if session.settings.asr_mode == "normal":
            asr_mode_val = ASRMode.NORMAL
        elif session.settings.asr_mode == "verbatim":
            asr_mode_val = ASRMode.VERBATIM

        asr_provider, asr_model_id = self._asr_for(session.settings.asr_model)
        asr_options = ASROptions(
            model=asr_model_id,
            mode=asr_mode_val,
            language_code=session.settings.primary_language,
            with_timestamps=True,
            keyterms=session.settings.keyterms
        )
        asr_result = await asr_provider.transcribe_file(prepared_input, asr_options)
        asr_latency = time.time() - t0_asr

        # 3b. Rescue pass for short interjections the whole-file decode dropped.
        # "avunu" / "yeah" / "ah" between two longer turns is a 200-350 ms
        # window, and a single missing token there removes the speech from the
        # transcript entirely. Re-decode just those regions, in isolation.
        t0_rescue = time.time()
        rescued_tokens, rescued_count = await rescue_backchannels(
            asr_provider,
            str(out_wav_path),
            diar_result.segments,
            list(asr_result.tokens),
            asr_options,
            duration=metadata.duration_sec,
        )
        if rescued_count:
            asr_result.tokens = rescued_tokens
            asr_result.transcript = " ".join(t.text for t in rescued_tokens if t.is_final)
        rescue_latency = time.time() - t0_rescue

        # 4. Alignment
        t0_align = time.time()
        aligned_units = self.alignment_engine.align(asr_result, diar_result)
        align_latency = time.time() - t0_align

        # 5. Build turns and speakers
        turns, speakers = self.turn_builder.build_turns(
            aligned_units,
            session.speakers,
            diar_result.segments,
            source_language=asr_result.language_code,
        )
        for t in turns:
            t.start = max(0.0, round(t.start, 3))
            t.end = min(round(max(t.start + 0.05, t.end), 3), round(session.duration, 3))
        session.turns = turns
        session.speakers = speakers

        # 6. Auto-translation if requested
        trans_latency = 0.0
        if session.settings.auto_translate:
            t0_trans = time.time()
            for turn in session.turns:
                # Skip speech-only turns — no ASR text to translate
                if turn.speech_only or not turn.text.strip():
                    continue
                try:
                    req = TranslationRequest(
                        text=turn.text,
                        source_language=turn.source_language or "te-IN",
                        target_language=session.settings.target_language or "en-IN"
                    )
                    trans_res = await self.translation_provider.translate(req)
                    turn.translated_text = trans_res.translated_text
                    turn.translation_status = "complete"
                except Exception:
                    turn.translation_status = "failed"
            trans_latency = time.time() - t0_trans

        # 7. Record observability metrics (Section 46)
        total_time = time.time() - start_total
        session.processing_status = "complete"
        session.metadata["observability"] = {
            "audio_duration_sec": metadata.duration_sec,
            "asr_model": asr_model_id,
            "asr_language": asr_result.language_code,
            "diarization_method": diar_result.method,
            "diarization_speaker_count": len(diar_result.speakers),
            "estimated_speaker_count": diar_result.metadata.get("estimated_speaker_count"),
            "speakers_before_consolidation": diar_result.metadata.get("speakers_before_consolidation"),
            "asr_latency_sec": round(asr_latency, 3),
            "diarization_latency_sec": round(diar_latency, 3),
            "alignment_latency_sec": round(align_latency, 3),
            "backchannel_rescue_latency_sec": round(rescue_latency, 3),
            "backchannel_tokens_recovered": rescued_count,
            "translation_latency_sec": round(trans_latency, 3),
            "total_processing_time_sec": round(total_time, 3),
            "speaker_count": len(speakers),
            "turn_count": len(turns),
            "overlap_count": diar_result.overlap_count,
            "raw_asr_tokens_count": len(asr_result.tokens)
        }

        # 8. Save raw outputs (Section 13: Raw Model Output)
        raw_dir = storage_session_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        import json
        with open(raw_dir / "diarization.json", "w", encoding="utf-8") as f:
            json.dump(diar_result.model_dump(), f, indent=2, ensure_ascii=False)
        with open(raw_dir / "asr.json", "w", encoding="utf-8") as f:
            json.dump(asr_result.model_dump(), f, indent=2, ensure_ascii=False)

        return session
