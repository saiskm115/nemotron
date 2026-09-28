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
from .turn_builder import TurnBuilder
from ..providers.asr.auto_tinglish_whisper import AutoTinglishWhisperProvider
from ..providers.asr.sarvam_saaras import SarvamSaarasProvider
from ..providers.diarization.nemotron import NemotronDiarizationProvider
from ..providers.diarization.mock_nemotron import MockNemotronProvider
from ..providers.translation.sarvam import SarvamTranslationProvider
from ..providers.translation.mock_translation import MockTranslationProvider

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

        # AutoTinglishSub Whisper Telugu Small/Quantized is primary ASR
        self.asr_provider = asr_provider or AutoTinglishWhisperProvider(model_size_or_path="small", compute_type="int8")
        self.diarization_provider = diarization_provider or (
            NemotronDiarizationProvider(endpoint=nemotron_endpoint) if nemotron_endpoint else MockNemotronProvider()
        )
        self.translation_provider = translation_provider or (
            SarvamTranslationProvider(api_key=sarvam_key) if sarvam_key else MockTranslationProvider()
        )

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
        diar_options = DiarizationOptions(max_speakers=8)
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

        asr_options = ASROptions(
            mode=asr_mode_val,
            language_code=session.settings.primary_language,
            with_timestamps=True,
            keyterms=session.settings.keyterms
        )
        asr_result = await self.asr_provider.transcribe_file(prepared_input, asr_options)
        asr_latency = time.time() - t0_asr

        # 4. Alignment
        t0_align = time.time()
        aligned_units = self.alignment_engine.align(asr_result, diar_result)
        align_latency = time.time() - t0_align

        # 5. Build turns and speakers
        turns, speakers = self.turn_builder.build_turns(aligned_units, session.speakers, diar_result.segments)
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
                except Exception as ex:
                    turn.translation_status = "failed"
            trans_latency = time.time() - t0_trans

        # 7. Record observability metrics (Section 46)
        total_time = time.time() - start_total
        session.processing_status = "complete"
        session.metadata["observability"] = {
            "audio_duration_sec": metadata.duration_sec,
            "asr_latency_sec": round(asr_latency, 3),
            "diarization_latency_sec": round(diar_latency, 3),
            "alignment_latency_sec": round(align_latency, 3),
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
