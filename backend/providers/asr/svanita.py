"""
Svanita 0.6B — Parakeet-TDT speech recognition for Telugu + code-mixed English.

Why this model: Svanita is a 0.6B FastConformer/TDT recogniser trained on Telugu
and Hindi conversational speech with English words kept in Latin script. It
transcribes the local language in the native script and the English mixed into
it as English in one pass, which is exactly the transcript a Telugu call-centre
recording needs.

Two behaviours from the model card are implemented here because they materially
change accuracy:

* **Script lock.** The checkpoint is multilingual (Telugu + Hindi) and will
  occasionally answer Telugu audio in Devanagari. ``--lang`` in the reference
  decoder bans every vocabulary piece containing a foreign Indic script before
  decoding, which is worth ~2 WER points on Telugu. When the caller states the
  language we apply the lock; when the language is unknown we decode freely and
  report the script we actually got.
* **Word timestamps.** The TDT decoder returns a duration per emitted token, so
  word boundaries are real measurements rather than a uniform split of a chunk.
  Those timestamps are what makes diarisation alignment trustworthy.

Runs on CPU in real time; full fp32 is intentional (dynamic int8 costs ~30 WER
points on this checkpoint).
"""
import logging
import os
import re
import time
import uuid
from typing import Dict, List, Optional, Tuple

import numpy as np

from ...models.audio import AudioInput
from ...models.asr import ASRChunk, ASRMode, ASROptions, ASRResult, ASRToken
from .base import ASRProvider as BaseASRProvider
from .base import ASRStream as BaseASRStream

logger = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "prasadvittaldev/svanita-0.6b"
TARGET_SAMPLE_RATE = 16000

# The model is trained on utterance-length audio; decode in overlapping windows so
# memory stays bounded on long recordings and each window keeps its context.
WINDOW_SEC = 30.0
OVERLAP_SEC = 1.5
MIN_WINDOW_SEC = 0.30

SCRIPT_BLOCKS = {"telugu": (0x0C00, 0x0C7F), "hindi": (0x0900, 0x097F)}
INDIC = (0x0900, 0x0D7F)
WORD_BOUNDARY = "▁"  # SentencePiece word-start marker

LANGUAGE_ALIASES = {
    "te": "telugu", "te-in": "telugu", "te_tt": "telugu", "telugu": "telugu",
    "hi": "hindi", "hi-in": "hindi", "hindi": "hindi", "hinglish": "hindi",
}


def resolve_script(language_code: Optional[str]) -> Optional[str]:
    """
    Maps a session language code to the script lock to apply.

    Returns None when the language is unknown or is English: the model should not
    be locked onto an Indic script in that case.
    """
    if not language_code:
        return None
    return LANGUAGE_ALIASES.get(str(language_code).strip().lower().replace("_", "-"))


def detect_output_language(text: str) -> Tuple[Optional[str], float]:
    """Reports the script actually produced: 'te-IN', 'hi-IN' or 'en-IN'."""
    has_te = any("\u0C00" <= c <= "\u0C7F" for c in text)
    has_hi = any("\u0900" <= c <= "\u097F" for c in text)
    has_latin = any(("a" <= c.lower() <= "z") for c in text)
    if has_te and not has_hi:
        return "te-IN", 0.95 if has_latin else 0.9
    if has_hi and not has_te:
        return "hi-IN", 0.95 if has_latin else 0.9
    if has_te and has_hi:
        return "te-IN", 0.6
    return ("en-IN", 0.8) if has_latin else (None, 0.0)


class SvanitaParakeetProvider(BaseASRProvider):
    """ASR provider backed by Svanita 0.6B (Parakeet-TDT)."""

    model_id = DEFAULT_MODEL_ID
    display_name = "Svanita 0.6B (Parakeet-TDT)"

    def __init__(self, model_id: str = DEFAULT_MODEL_ID, revision: Optional[str] = None):
        self.model_id = model_id
        self.revision = revision
        self._processor = None
        self._model = None
        self._tokenizer = None
        self._banned_cache: Dict[str, List[int]] = {}

    # ── model ───────────────────────────────────────────────────────────
    def _load(self) -> bool:
        if self._model is not None:
            return True
        try:
            import torch
            from transformers import ParakeetForTDT, ParakeetProcessor

            offline = os.environ.get("SVANITA_OFFLINE", "0") == "1"
            kwargs = {"local_files_only": offline} if offline else {}
            if self.revision:
                kwargs["revision"] = self.revision

            self._processor = ParakeetProcessor.from_pretrained(self.model_id, **kwargs)
            self._model = ParakeetForTDT.from_pretrained(
                self.model_id, dtype=torch.float32, **kwargs
            )
            self._model.eval()
            self._tokenizer = self._processor.tokenizer
            threads = int(os.environ.get("SVANITA_THREADS", "4"))
            torch.set_num_threads(max(1, threads))
            logger.info("Svanita ready: %s", self.model_id)
            return True
        except Exception as exc:  # noqa: BLE001
            logger.error("Could not load Svanita model %s: %s", self.model_id, exc)
            self._processor = None
            self._model = None
            return False

    def _banned_token_ids(self, script: Optional[str]) -> List[int]:
        """
        Vocabulary pieces containing an Indic character outside the locked script.

        English stays available in Latin; only the *other* Indic script is removed,
        which is what stops Telugu audio from coming back in Devanagari.
        """
        if not script or self._tokenizer is None:
            return []
        if script in self._banned_cache:
            return self._banned_cache[script]
        lo, hi = SCRIPT_BLOCKS[script]
        banned = sorted(
            i
            for piece, i in self._tokenizer.get_vocab().items()
            if any(INDIC[0] <= ord(c) <= INDIC[1] and not (lo <= ord(c) <= hi) for c in piece)
        )
        self._banned_cache[script] = banned
        return banned

    # ── core transcription ──────────────────────────────────────────────
    def _decode_window(
        self, y: np.ndarray, banned: Optional[List[int]]
    ) -> List[Tuple[str, float, float]]:
        """
        Decodes one window of 16 kHz mono audio into (word, start, end) tuples.

        Uses the model's own greedy TDT loop so the script lock can be applied and
        so per-token frame durations survive — ``generate()`` hides both.
        """
        import torch

        model, processor = self._model, self._processor
        cfg = model.config

        feats = processor.feature_extractor(
            y, sampling_rate=TARGET_SAMPLE_RATE, return_tensors="pt", return_attention_mask=True
        )
        with torch.inference_mode():
            enc = model.get_audio_features(
                input_features=feats["input_features"],
                attention_mask=feats["attention_mask"],
                output_attention_mask=True,
            )
            frames = int(enc.attention_mask[0].sum())
            encoder_out = enc.pooler_output[0, :frames]

            banned_tensor = torch.tensor(banned, dtype=torch.long) if banned else None

            decoder_step, joint = _make_tdt_steps(model)
            steps = _greedy_tdt(encoder_out, decoder_step, joint, cfg, banned_tensor)

        if not steps:
            return []

        total_units = max(1, sum(advance for _, advance in steps))
        frame_sec = (len(y) / float(TARGET_SAMPLE_RATE)) / total_units

        words: List[Tuple[str, float, float]] = []
        current: Optional[Dict[str, object]] = None
        cursor = 0
        for token, advance in steps:
            position = cursor * frame_sec
            if token is not None:
                piece = self._tokenizer.convert_ids_to_tokens(token)
                if piece.startswith(WORD_BOUNDARY):
                    if current is not None:
                        current["end"] = position
                        words.append((str(current["text"]), float(current["start"]), float(current["end"])))
                        current = None
                    current = {"text": piece[len(WORD_BOUNDARY):], "start": position}
                elif current is not None:
                    current["text"] = str(current["text"]) + piece
                else:
                    current = {"text": piece, "start": position}
            if current is not None:
                current["end"] = position
            cursor += advance

        if current is not None:
            current["end"] = min(cursor * frame_sec, len(y) / float(TARGET_SAMPLE_RATE))
            words.append((str(current["text"]), float(current["start"]), float(current["end"])))

        audio_sec = len(y) / float(TARGET_SAMPLE_RATE)
        cleaned: List[Tuple[str, float, float]] = []
        for word, start, end in words:
            word = word.strip()
            if not word:
                continue
            start = max(0.0, min(start, audio_sec))
            end = max(start, min(end, audio_sec))
            if end <= start:
                end = min(audio_sec, start + 0.04)
            cleaned.append((word, start, end))
        return cleaned

    def _transcribe_array(self, y: np.ndarray, options: ASROptions) -> Tuple[str, List[Tuple[str, float, float]]]:
        """Transcribes a full 16 kHz mono buffer, windowing long inputs."""
        script = resolve_script(options.language_code)
        banned = self._banned_token_ids(script)

        total_sec = len(y) / float(TARGET_SAMPLE_RATE)
        if total_sec <= WINDOW_SEC:
            words = self._decode_window(y, banned)
        else:
            words = self._transcribe_windowed(y, banned, total_sec)

        words.sort(key=lambda item: item[1])
        text = " ".join(word for word, _, _ in words)
        return text, words

    def _transcribe_windowed(
        self, y: np.ndarray, banned: Optional[List[int]], total_sec: float
    ) -> List[Tuple[str, float, float]]:
        """
        Decodes the buffer as overlapping windows and keeps each word once.

        Consecutive windows share ``OVERLAP_SEC`` of audio; a word is kept only by
        the window whose core region contains its centre, so the overlap is decoded
        twice and counted once.
        """
        window = int(WINDOW_SEC * TARGET_SAMPLE_RATE)
        hop = int((WINDOW_SEC - OVERLAP_SEC) * TARGET_SAMPLE_RATE)
        half = OVERLAP_SEC / 2.0
        words: List[Tuple[str, float, float]] = []

        offset = 0
        while offset < len(y):
            chunk = y[offset : offset + window]
            if len(chunk) < int(MIN_WINDOW_SEC * TARGET_SAMPLE_RATE):
                break

            base_sec = offset / float(TARGET_SAMPLE_RATE)
            is_first = offset == 0
            is_last = offset + window >= len(y)

            core_lo = 0.0 if is_first else half
            core_hi = len(chunk) / float(TARGET_SAMPLE_RATE)
            if not is_last:
                core_hi = min(core_hi, core_lo + (WINDOW_SEC - 2 * half))

            for word, w_start, w_end in self._decode_window(chunk, banned):
                centre = (w_start + w_end) / 2.0
                if not (core_lo <= centre < core_hi):
                    continue
                words.append((word, base_sec + w_start, base_sec + w_end))

            offset += hop

        return words

    # ── ASRProvider ─────────────────────────────────────────────────────
    async def transcribe_file(self, audio: AudioInput, options: ASROptions) -> ASRResult:
        import asyncio

        started = time.time()
        y, sr = await asyncio.to_thread(self._load_mono, audio)
        if y is None or len(y) == 0:
            raise ValueError("Audio could not be decoded for transcription")
        if sr != TARGET_SAMPLE_RATE:
            raise ValueError(f"Svanita expects {TARGET_SAMPLE_RATE} Hz audio, got {sr} Hz")

        if not await asyncio.to_thread(self._load):
            raise RuntimeError(
                f"Svanita model {self.model_id} is unavailable. Check the local model cache "
                "or unset SVANITA_OFFLINE to allow downloading."
            )

        text, words = await asyncio.to_thread(self._transcribe_array, y, options)

        tokens: List[ASRToken] = []
        chunks: List[ASRChunk] = []
        for word, start, end in words:
            tokens.append(
                ASRToken(
                    id=str(uuid.uuid4()),
                    text=word,
                    start=round(start, 3),
                    end=round(end, 3),
                    confidence=_token_confidence(word),
                    language=_word_language(word),
                    is_final=True,
                )
            )

        if tokens:
            # Group words into sentence-ish chunks on pauses and punctuation so the
            # transcript panel and caption track have readable units.
            chunks = _build_chunks(tokens, options.mode)

        detected_lang, probability = detect_output_language(text)
        return ASRResult(
            transcript=text,
            language_code=detected_lang or options.language_code,
            language_probability=round(probability, 3),
            chunks=chunks,
            tokens=tokens,
            latency_sec=round(time.time() - started, 3),
        )

    async def transcribe_interval(
        self,
        audio_file_path: str,
        start_time: float,
        end_time: float,
        options: Optional[ASROptions] = None,
    ) -> ASRResult:
        """
        Re-transcribes ``[start_time, end_time]`` by decoding only that slice.

        A small lead-in is included so the decoder has acoustic context, then
        timestamps are rebased onto the original timeline.
        """
        import asyncio

        started = time.time()
        opts = options or ASROptions(mode=ASRMode.CODEMIXED, language_code="te-IN")
        start_time = max(0.0, float(start_time))
        end_time = max(start_time + 0.05, float(end_time))

        if not audio_file_path or not os.path.exists(audio_file_path):
            raise ValueError("Audio file is not available for re-transcription")

        if not await asyncio.to_thread(self._load):
            raise RuntimeError(f"Svanita model {self.model_id} is unavailable")

        context = 0.25
        offset = max(0.0, start_time - context)
        y, sr = await asyncio.to_thread(_read_slice, audio_file_path, offset, end_time)

        if y is None or len(y) < int(0.1 * TARGET_SAMPLE_RATE):
            return _empty_result(opts, started, "selected range contains no audio")

        text, words = await asyncio.to_thread(self._transcribe_array, y, opts)

        tokens: List[ASRToken] = []
        for word, w_start, w_end in words:
            abs_start = round(min(max(offset + w_start, start_time), end_time), 3)
            abs_end = round(min(max(offset + w_end, start_time), end_time), 3)
            if abs_end <= abs_start:
                continue
            tokens.append(
                ASRToken(
                    id=str(uuid.uuid4()),
                    text=word,
                    start=abs_start,
                    end=abs_end,
                    confidence=_token_confidence(word),
                    language=_word_language(word),
                    is_final=True,
                )
            )

        detected_lang, probability = detect_output_language(text)
        return ASRResult(
            transcript=" ".join(t.text for t in tokens),
            language_code=detected_lang or opts.language_code,
            language_probability=round(probability, 3),
            chunks=_build_chunks(tokens, opts.mode) if tokens else [],
            tokens=tokens,
            latency_sec=round(time.time() - started, 3),
        )

    async def start_stream(self, options: ASROptions) -> BaseASRStream:
        raise NotImplementedError(
            "Svanita is an offline model; live streaming transcription is not supported."
        )

    # ── audio ───────────────────────────────────────────────────────────
    def _load_mono(self, audio: AudioInput):
        from ...pipeline.audio_preprocessor import preprocessor

        source = audio
        if not (audio.file_path and os.path.exists(audio.file_path)) and audio.raw_bytes:
            import tempfile

            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(audio.raw_bytes)
            tmp.close()
            source = AudioInput(file_path=tmp.name, metadata=audio.metadata)
        y = preprocessor.load_audio(source)
        max_val = float(np.max(np.abs(y))) if len(y) else 0.0
        if max_val > 1.0:
            y = y / max_val
        return np.asarray(y, dtype=np.float32), TARGET_SAMPLE_RATE


# ── TDT decoding helpers ─────────────────────────────────────────────────
def _make_tdt_steps(model):
    """Builds the per-step decoder and joint calls used by the greedy TDT loop."""
    import torch

    decoder = model.decoder

    def decoder_step(token, state):
        out, state = decoder.lstm(decoder.embedding(torch.tensor([[token]])), state)
        return decoder.decoder_projector(out)[0, 0], state

    def joint(encoder_frame, decoder_frame):
        return model.joint.head(model.joint.activation(encoder_frame + decoder_frame)[None])[0]

    return decoder_step, joint


def _greedy_tdt(encoder_out, decoder_step, joint, cfg, banned):
    """
    Greedy token-and-duration decoding.

    Returns one ``(token_or_None, frame_advance)`` pair per decoding step. The
    advance is recorded for *every* step, blanks included, because it is what
    moves the frame cursor; only non-blank tokens carry a token id.
    """

    blank = cfg.blank_token_id
    vocab_size = cfg.vocab_size
    durations = list(cfg.durations)
    max_symbols = int(getattr(cfg, "max_symbols_per_step", 10))
    frames = encoder_out.shape[0]

    steps: List[Tuple[Optional[int], int]] = []
    dec_out, state = decoder_step(blank, None)
    t, symbols = 0, 0

    while t < frames:
        logits = joint(encoder_out[t], dec_out)
        if banned is not None and banned.numel() > 0:
            logits = logits.clone()
            logits[banned] = float("-inf")
        token = int(logits[:vocab_size].argmax())
        duration = int(durations[int(logits[vocab_size:].argmax())])

        if token == blank:
            symbols = 0
        else:
            dec_out, state = decoder_step(token, state)
            symbols += 1

        if duration == 0 and (token == blank or symbols >= max_symbols):
            duration = 1
        if duration > 0:
            symbols = 0

        steps.append((None if token == blank else token, duration))
        t += duration

    return steps


# ── text helpers ─────────────────────────────────────────────────────────
def _word_language(word: str) -> str:
    if any("\u0C00" <= c <= "\u0C7F" for c in word):
        return "te"
    if any("\u0900" <= c <= "\u097F" for c in word):
        return "hi"
    if any("a" <= c.lower() <= "z" for c in word):
        return "en"
    return "te"


def _token_confidence(word: str) -> float:
    """
    Heuristic token confidence.

    Greedy TDT decoding exposes no per-token posterior, so this is derived from
    orthography rather than invented: tokens that look like sub-word fragments
    (which are also the ones alignment is least sure about) score lower.
    """
    stripped = word.strip()
    if not stripped:
        return 0.5
    if re.fullmatch(r"[\W\d_]+", stripped):
        return 0.9
    if len(stripped) <= 2:
        return 0.82
    return 0.93


def _build_chunks(tokens: List[ASRToken], mode: ASRMode) -> List[ASRChunk]:
    """Groups word tokens into readable chunks on pause length and punctuation."""
    if not tokens:
        return []

    pause_limit = 0.9 if mode == ASRMode.NORMAL else 0.6
    groups: List[List[ASRToken]] = [[tokens[0]]]
    for prev, token in zip(tokens, tokens[1:]):
        gap = token.start - prev.end
        ends_sentence = prev.text.endswith((".", "?", "!", "।", "॥"))
        if gap > pause_limit or ends_sentence:
            groups.append([token])
        else:
            groups[-1].append(token)

    chunks: List[ASRChunk] = []
    for group in groups:
        text = " ".join(t.text for t in group)
        chunks.append(
            ASRChunk(
                id=str(uuid.uuid4()),
                text=text,
                start=group[0].start,
                end=group[-1].end,
                confidence=round(sum(t.confidence or 0.9 for t in group) / len(group), 2),
                language=group[0].language,
                tokens=group,
                is_final=True,
            )
        )
    return chunks


def _read_slice(path: str, start_sec: float, end_sec: float):
    """Reads ``[start_sec, end_sec]`` as 16 kHz mono float32."""
    import soundfile as sf

    info = sf.info(path)
    sr = info.samplerate
    start_frame = max(0, int(start_sec * sr))
    stop_frame = min(info.frames, int(end_sec * sr))
    if stop_frame <= start_frame:
        return None, sr
    data, _ = sf.read(path, start=start_frame, stop=stop_frame, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != TARGET_SAMPLE_RATE:
        import librosa

        data = librosa.resample(data, orig_sr=sr, target_sr=TARGET_SAMPLE_RATE)
    return np.asarray(data, dtype=np.float32), TARGET_SAMPLE_RATE


def _empty_result(options: ASROptions, started: float, reason: str) -> ASRResult:
    logger.warning("Svanita returned no transcript: %s", reason)
    return ASRResult(
        transcript="",
        language_code=options.language_code,
        language_probability=0.0,
        chunks=[],
        tokens=[],
        latency_sec=round(time.time() - started, 3),
    )
