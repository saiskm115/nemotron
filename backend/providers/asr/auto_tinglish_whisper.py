"""
Whisper-based ASR (local, offline).

Two flavours share this provider:

* **CTranslate2 / faster-whisper** (``model_size_or_path``) — quantized Whisper for
  general multilingual and code-mixed audio.
* **Fine-tuned Whisper checkpoint** (``hf_model_id``) — e.g. a Telugu fine-tune,
  run through ``transformers`` with real word timestamps.

Language handling: the language requested for the session is honoured verbatim.
When the language is unknown the decoder is left to detect it instead of being
forced into Telugu, so an English or Hindi recording is not transliterated into the
wrong script.
"""
import logging
import os
import re
import time
import uuid
from typing import AsyncGenerator, List, Optional

import numpy as np

from ...models.asr import ASRChunk, ASRMode, ASROptions, ASRResult, ASRToken
from ...models.audio import AudioFrame, AudioInput, AudioMetadata
from .base import ASRProvider, ASRStream

logger = logging.getLogger(__name__)

DEFAULT_MODEL_SIZE = "small"

# Session language codes -> Whisper language tags. Anything absent is passed to
# Whisper as "auto-detect" (None).
LANGUAGE_MAP = {
    "te": "te", "te-in": "te", "te_tt": "te", "telugu": "te",
    "hi": "hi", "hi-in": "hi", "hindi": "hi", "hinglish": "hi",
    "en": "en", "en-in": "en", "en-us": "en", "en-gb": "en", "english": "en",
    "kn": "kn", "ta": "ta", "ml": "ml", "mr": "mr", "bn": "bn", "gu": "gu",
    "ur": "ur", "pa": "pa", "or": "or", "as": "as", "mr_d": "mr",
}


def resolve_whisper_language(language_code: Optional[str]) -> Optional[str]:
    """Returns a Whisper language tag, or None to let Whisper detect it."""
    if not language_code:
        return None
    key = str(language_code).strip().lower().replace("_", "-")
    if key in ("unknown", "auto", ""):
        return None
    return LANGUAGE_MAP.get(key)


def _strip_special_tokens(text: str) -> str:
    return re.sub(r"<\|[^|]*\|>", "", text).strip()


def _word_language(word: str) -> str:
    if any("\u0C00" <= c <= "\u0C7F" for c in word):
        return "te"
    if any("\u0900" <= c <= "\u097F" for c in word):
        return "hi"
    if any("a" <= c.lower() <= "z" for c in word):
        return "en"
    return "te"


class WhisperStream(ASRStream):
    """Placeholder stream; Whisper transcription in this app is offline-only."""

    def __init__(self, options: ASROptions):
        self.options = options
        self.closed = False

    async def push_audio(self, frame: AudioFrame) -> None:
        pass

    async def get_results(self) -> AsyncGenerator[ASRChunk, None]:
        return
        yield  # pragma: no cover - keeps this an async generator

    async def close(self) -> None:
        self.closed = True


class WhisperASRProvider(ASRProvider):
    """Local Whisper provider (faster-whisper or a fine-tuned HF checkpoint)."""

    def __init__(
        self,
        model_size_or_path: str = DEFAULT_MODEL_SIZE,
        compute_type: str = "int8",
        hf_model_id: Optional[str] = None,
    ):
        self.model_size_or_path = model_size_or_path
        self.compute_type = compute_type
        self.hf_model_id = hf_model_id
        self._model = None
        self._hf_model = None
        self._hf_processor = None

    # ── backends ─────────────────────────────────────────────────────────
    def _get_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel

            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:  # noqa: BLE001
                device = "cpu"
            comp_type = "float16" if device == "cuda" else self.compute_type

            offline = os.environ.get("WHISPER_DOWNLOAD_ONLINE") != "1"
            self._model = WhisperModel(
                self.model_size_or_path,
                device=device,
                compute_type=comp_type,
                cpu_threads=int(os.environ.get("WHISPER_THREADS", "4")),
                local_files_only=offline,
            )
            return self._model
        except Exception as exc:  # noqa: BLE001
            logger.error("faster-whisper model unavailable: %s", exc)
            return None

    def _get_hf_model(self):
        if self._hf_model is not None and self._hf_processor is not None:
            return self._hf_model, self._hf_processor
        if not self.hf_model_id:
            return None, None
        try:
            import torch
            from transformers import WhisperForConditionalGeneration, WhisperProcessor

            offline = os.environ.get("WHISPER_DOWNLOAD_ONLINE") != "1"
            kwargs = {"local_files_only": offline} if offline else {}
            processor = WhisperProcessor.from_pretrained(self.hf_model_id, **kwargs)
            model = WhisperForConditionalGeneration.from_pretrained(self.hf_model_id, **kwargs)
            model.eval()
            self._hf_model, self._hf_processor = model, processor
            torch.set_num_threads(max(1, int(os.environ.get("WHISPER_THREADS", "4"))))
            return model, processor
        except Exception as exc:  # noqa: BLE001
            logger.error("Fine-tuned Whisper %s unavailable: %s", self.hf_model_id, exc)
            self._hf_model, self._hf_processor = None, None
            return None, None

    # ── transcription ────────────────────────────────────────────────────
    async def transcribe_file(self, audio: AudioInput, options: ASROptions) -> ASRResult:
        import asyncio

        started = time.time()
        if not self.hf_model_id:
            return await asyncio.to_thread(self._transcribe_ct2, audio, options, started)
        return await asyncio.to_thread(self._transcribe_hf, audio, options, started)

    async def transcribe_interval(
        self,
        audio_file_path: str,
        start_time: float,
        end_time: float,
        options: Optional[ASROptions] = None,
    ) -> ASRResult:
        """Decodes only ``[start_time, end_time]`` and rebases the timestamps."""
        import asyncio

        started = time.time()
        opts = options or ASROptions(mode=ASRMode.CODEMIXED, language_code="unknown")
        start_time = max(0.0, float(start_time))
        end_time = max(start_time + 0.05, float(end_time))

        if not audio_file_path or not os.path.exists(audio_file_path):
            raise ValueError("Audio file is not available for re-transcription")

        if not self.hf_model_id:
            return await asyncio.to_thread(
                self._transcribe_ct2_interval, audio_file_path, start_time, end_time, opts, started
            )
        return await asyncio.to_thread(
            self._transcribe_hf_interval, audio_file_path, start_time, end_time, opts, started
        )

    async def start_stream(self, options: ASROptions) -> ASRStream:
        raise NotImplementedError(
            "This Whisper provider runs offline transcription only; live streaming is not supported."
        )

    # ── CTranslate2 ─────────────────────────────────────────────────────
    def _transcribe_ct2(self, audio: AudioInput, options: ASROptions, started: float) -> ASRResult:
        path = audio.file_path
        if not (path and os.path.exists(path)):
            raise ValueError("Audio file is not available for transcription")

        model = self._get_model()
        if model is None:
            raise RuntimeError(
                f"faster-whisper model {self.model_size_or_path!r} is unavailable. "
                "Pre-download it or set WHISPER_DOWNLOAD_ONLINE=1."
            )

        duration = audio.metadata.duration_sec if audio.metadata else 0.0
        language = resolve_whisper_language(options.language_code)

        prompt = _build_prompt(options)
        segments, info = model.transcribe(
            path,
            language=language,
            task="transcribe",
            word_timestamps=True,
            initial_prompt=prompt,
            # Whisper's own VAD chunks the stream, which on code-mixed Indian speech
            # pushes it into repetition loops; decoding the 30 s window in one pass is
            # measurably more faithful. Opt in with WHISPER_VAD_FILTER=1.
            vad_filter=os.environ.get("WHISPER_VAD_FILTER", "0") == "1",
            condition_on_previous_text=False,
            beam_size=int(os.environ.get("WHISPER_BEAM_SIZE", "5")),
            # Greedy decoding. Temperature fallback accepts high-entropy garbage on
            # hard audio, which is strictly worse than a repetition loop that the
            # degenerate-segment filter below can remove.
            temperature=0.0,
            compression_ratio_threshold=2.4,
            no_speech_threshold=0.6,
        )

        tokens: List[ASRToken] = []
        chunks: List[ASRChunk] = []
        for seg in segments:
            if duration and seg.start >= duration:
                break
            text = (seg.text or "").strip()
            if not text or is_degenerate(text):
                continue
            chunk_tokens: List[ASRToken] = []
            for word in seg.words or []:
                token_text = (word.word or "").strip()
                if not token_text or is_degenerate(token_text):
                    continue
                start = max(0.0, round(word.start, 3))
                end = round(max(word.end, start + 0.02), 3)
                if duration:
                    end = min(end, round(duration, 3))
                if end <= start:
                    continue
                token = ASRToken(
                    id=str(uuid.uuid4()),
                    text=token_text,
                    start=start,
                    end=end,
                    confidence=round(float(getattr(word, "probability", 0.0) or 0.0), 2) or None,
                    language=_word_language(token_text),
                    is_final=True,
                )
                tokens.append(token)
                chunk_tokens.append(token)
            if text and chunk_tokens:
                chunks.append(
                    ASRChunk(
                        id=str(uuid.uuid4()),
                        text=text,
                        start=chunk_tokens[0].start,
                        end=chunk_tokens[-1].end,
                        language=chunk_tokens[0].language,
                        tokens=chunk_tokens,
                        is_final=True,
                    )
                )

        return _result(
            tokens, chunks, getattr(info, "language", language), getattr(info, "language_probability", None), started
        )

    def _transcribe_ct2_interval(
        self, path: str, start: float, end: float, options: ASROptions, started: float
    ) -> ASRResult:
        import tempfile

        from ...pipeline.audio_preprocessor import preprocessor

        y, sr = _read_slice(preprocessor, path, start, end)
        if y is None or len(y) == 0:
            return _empty(options, started)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            import soundfile as sf

            sf.write(tmp_path, y, sr, subtype="PCM_16")
            slice_input = AudioInput(
                file_path=tmp_path,
                metadata=AudioMetadata(
                    duration_sec=round(len(y) / float(sr), 3),
                    sample_rate=sr,
                    channels=1,
                    sample_count=len(y),
                ),
            )
            result = self._transcribe_ct2(slice_input, options, started)
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

        _rebase(result, start, end)
        return result

    # ── fine-tuned Hugging Face checkpoint ───────────────────────────────
    def _transcribe_hf(self, audio: AudioInput, options: ASROptions, started: float) -> ASRResult:
        path = audio.file_path
        if not (path and os.path.exists(path)):
            raise ValueError("Audio file is not available for transcription")

        model, processor = self._get_hf_model()
        if model is None:
            raise RuntimeError(f"Fine-tuned Whisper checkpoint {self.hf_model_id} is unavailable.")

        from ...pipeline.audio_preprocessor import preprocessor

        y = preprocessor.load_audio(audio)
        sr = preprocessor.target_sample_rate
        duration = len(y) / float(sr)
        words = _hf_words(model, processor, y, sr, options)
        return _from_words(words, options, duration, started)

    def _transcribe_hf_interval(
        self, path: str, start: float, end: float, options: ASROptions, started: float
    ) -> ASRResult:
        from ...pipeline.audio_preprocessor import preprocessor

        model, processor = self._get_hf_model()
        if model is None:
            raise RuntimeError(f"Fine-tuned Whisper checkpoint {self.hf_model_id} is unavailable.")

        y, sr = _read_slice(preprocessor, path, start, end)
        if y is None or len(y) == 0:
            return _empty(options, started)

        words = _hf_words(model, processor, y, sr, options)
        result = _from_words(words, options, len(y) / float(sr), started)
        _rebase(result, start, end)
        return result


# ── helpers ──────────────────────────────────────────────────────────────
def _read_slice(preprocessor, path: str, start: float, end: float):
    """Reads [start, end] from any decodable audio file as 16 kHz mono."""
    import soundfile as sf

    try:
        info = sf.info(path)
        data, sr = sf.read(
            path,
            start=max(0, int(start * info.samplerate)),
            stop=max(0, int(end * info.samplerate)),
            dtype="float32",
        )
    except Exception:  # noqa: BLE001 - compressed container, decode the whole thing
        full = preprocessor.load_audio(AudioInput(file_path=path))
        sr = preprocessor.target_sample_rate
        data = full[int(start * sr) : int(end * sr)]

    if data is None or len(data) == 0:
        return None, sr
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != preprocessor.target_sample_rate:
        import librosa

        data = librosa.resample(data, orig_sr=sr, target_sr=preprocessor.target_sample_rate)
        sr = preprocessor.target_sample_rate
    return np.asarray(data, dtype=np.float32), sr


def _build_prompt(options: ASROptions) -> Optional[str]:
    """
    Conditioning prompt: custom vocabulary only.

    Deliberately never language-specific. Whisper follows a prompt very strongly,
    so conditioning it on Telugu makes it emit Telugu script for English recordings —
    and, measured on this codebase's corpus, a Telugu-script prompt makes it fall
    straight into a repetition loop.
    """
    if not options.keyterms:
        return None
    return "Vocabulary: " + ", ".join(options.keyterms)


def is_degenerate(text: str) -> bool:
    """
    True when a decoded span is a repetition loop rather than speech.

    Whisper's most common failure on code-mixed Indian audio is emitting the same
    syllable until the segment ends. The share of whitespace tokens that are unique
    collapses toward zero in a loop and stays high in ordinary speech, which repeats
    real words. Only spans of four tokens or more are tested, so a legitimately
    repeated two-word phrase is never dropped.
    """
    stripped = text.strip()
    if not stripped:
        return True
    words = stripped.split()
    if len(words) >= 4 and len(set(words)) / len(words) < 0.34:
        return True
    return False


def _repair_generation_config(model, processor) -> None:
    """
    Rebuilds the language/task tables on an outdated Whisper generation config.

    Many fine-tuned checkpoints predate the ``lang_to_id`` / ``is_multilingual``
    fields. Passing ``language`` or ``task`` then raises, and decoding without them
    emits the wrong token sequence entirely. The tokens are all still present in the
    tokenizer, so the tables can simply be reconstructed from it.
    """
    generation_config = getattr(model, "generation_config", None)
    if generation_config is None:
        return

    if not getattr(generation_config, "lang_to_id", None):
        import re

        lang_to_id = {}
        for token, token_id in processor.tokenizer.get_vocab().items():
            match = re.fullmatch(r"<\|([a-z]{2,3})\|>", token)
            if match:
                lang_to_id[match.group(1)] = token_id
        if lang_to_id:
            generation_config.lang_to_id = lang_to_id
            generation_config.is_multilingual = True
            logger.info(
                "Rebuilt lang_to_id (%d languages) on the generation config of %s",
                len(lang_to_id),
                getattr(model.config, "_name_or_path", "checkpoint"),
            )

    if not getattr(generation_config, "task_to_id", None):
        task_to_id = {}
        for task_name in ("transcribe", "translate"):
            token_id = processor.tokenizer.convert_tokens_to_ids(f"<|{task_name}|>")
            if isinstance(token_id, int) and token_id >= 0:
                task_to_id[task_name] = token_id
        if len(task_to_id) == 2:
            generation_config.task_to_id = task_to_id

    if getattr(generation_config, "no_timestamps_token_id", None) is None:
        token_id = processor.tokenizer.convert_tokens_to_ids("<|notimestamps|>")
        if isinstance(token_id, int) and token_id >= 0:
            generation_config.no_timestamps_token_id = token_id

    if getattr(generation_config, "max_length", None) in (None, 20, 448):
        generation_config.max_length = 225


def _hf_words(model, processor, y: np.ndarray, sr: int, options: ASROptions) -> List[dict]:
    """
    Runs the HF checkpoint and returns word timings.

    Timestamps are requested when the checkpoint supports them; fine-tunes often ship
    a generation config without ``no_timestamps_token_id`` or alignment heads, so each
    step degrades to the next best instead of failing the transcription.
    """
    import torch

    language = resolve_whisper_language(options.language_code)
    generate_kwargs = {"task": "transcribe", "condition_on_prev_tokens": False}
    if language:
        generate_kwargs["language"] = language

    prompt = _build_prompt(options)
    if prompt:
        generate_kwargs["prompt_ids"] = processor.get_prompt_ids(prompt)

    inputs = processor(y, sampling_rate=sr, return_tensors="pt")

    _repair_generation_config(model, processor)

    has_alignment_heads = bool(getattr(model.config, "alignment_heads", None))

    def run(extra: dict):
        with torch.inference_mode():
            return model.generate(
                inputs.input_features,
                attention_mask=getattr(inputs, "attention_mask", None),
                **{**generate_kwargs, **extra},
            )

    if has_alignment_heads:
        attempts = [{"return_timestamps": "word"}, {"return_timestamps": True}]
    else:
        attempts = [{"return_timestamps": True}, {}]

    generated = None
    for extra in attempts:
        try:
            generated = run(extra)
            break
        except Exception as exc:  # noqa: BLE001 - try the next timestamp mode
            logger.warning("Whisper generation with %s failed: %s", extra, exc)

    if generated is None:
        return []

    text = _strip_special_tokens(processor.batch_decode(generated, skip_special_tokens=True)[0])
    if not text or is_degenerate(text):
        return []

    pieces = getattr(generated, "segments", None)
    audio_sec = len(y) / float(sr)
    if not pieces:
        # No segment timings at all: spread the words across the clip. This is an
        # estimate and is only reached for checkpoints with no timestamp support.
        words = text.split()
        step = audio_sec / max(1, len(words))
        return [
            {"text": w, "start": i * step, "end": (i + 1) * step, "word_aligned": False}
            for i, w in enumerate(words)
        ]

    words: List[dict] = []
    for piece in pieces:
        start = float(getattr(piece, "start", 0.0) or 0.0)
        end = float(getattr(piece, "end", 0.0) or 0.0)
        tokens = list(getattr(piece, "tokens", None) or [])
        if tokens and end > start:
            step = (end - start) / len(tokens)
            for offset, token_id in enumerate(tokens):
                word = _strip_special_tokens(processor.tokenizer.decode([token_id]))
                if not word:
                    continue
                words.append(
                    {
                        "text": word,
                        "start": start + offset * step,
                        "end": start + (offset + 1) * step,
                        "word_aligned": True,
                    }
                )
        else:
            chunk = _strip_special_tokens(getattr(piece, "text", "") or "")
            if chunk:
                words.append({"text": chunk, "start": start, "end": end, "word_aligned": False})
    return words


def _from_words(
    words: List[dict], options: ASROptions, duration: float, started: float
) -> ASRResult:
    tokens: List[ASRToken] = []
    chunks: List[ASRChunk] = []
    for word in words:
        text = str(word["text"]).strip()
        if not text or is_degenerate(text):
            continue
        start = max(0.0, round(float(word["start"]), 3))
        end = round(max(float(word["end"]), start + 0.02), 3)
        if duration:
            end = min(end, round(duration, 3))
        if end <= start:
            continue
        tokens.append(
            ASRToken(
                id=str(uuid.uuid4()),
                text=text,
                start=start,
                end=end,
                confidence=None,
                language=_word_language(text),
                is_final=True,
            )
        )
    if tokens:
        chunks = _chunk_tokens(tokens, options.mode)
    return _result(tokens, chunks, resolve_whisper_language(options.language_code), None, started)


def _chunk_tokens(tokens: List[ASRToken], mode: ASRMode) -> List[ASRChunk]:
    pause_limit = 0.9 if mode == ASRMode.NORMAL else 0.6
    groups: List[List[ASRToken]] = [[tokens[0]]]
    for prev, token in zip(tokens, tokens[1:]):
        if (token.start - prev.end) > pause_limit or prev.text.endswith((".", "?", "!", "।", "॥")):
            groups.append([token])
        else:
            groups[-1].append(token)
    return [
        ASRChunk(
            id=str(uuid.uuid4()),
            text=" ".join(t.text for t in group),
            start=group[0].start,
            end=group[-1].end,
            language=group[0].language,
            tokens=group,
            is_final=True,
        )
        for group in groups
    ]


def _result(
    tokens: List[ASRToken],
    chunks: List[ASRChunk],
    language: Optional[str],
    probability: Optional[float],
    started: float,
) -> ASRResult:
    from .svanita import detect_output_language

    text = " ".join(t.text for t in tokens)
    detected, confidence = detect_output_language(text)
    return ASRResult(
        transcript=text,
        language_code=detected or (f"{language}-IN" if language else None),
        language_probability=round(probability, 3) if probability is not None else round(confidence, 3),
        chunks=chunks,
        tokens=tokens,
        latency_sec=round(time.time() - started, 3),
    )


def _rebase(result: ASRResult, start: float, end: float) -> None:
    for token in result.tokens:
        token.start = round(min(max(start + token.start, start), end), 3)
        token.end = round(min(max(start + token.end, token.start), end), 3)
    for chunk in result.chunks:
        chunk.start = round(min(max(start + chunk.start, start), end), 3)
        chunk.end = round(min(max(start + chunk.end, chunk.start), end), 3)


def _empty(options: ASROptions, started: float) -> ASRResult:
    return ASRResult(
        transcript="",
        language_code=resolve_whisper_language(options.language_code),
        language_probability=0.0,
        chunks=[],
        tokens=[],
        latency_sec=round(time.time() - started, 3),
    )
