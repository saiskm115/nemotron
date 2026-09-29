"""
IndicConformer 600M multilingual — AI4Bharat's IndicConformers for 22 languages.

Why this model: it is the only recogniser in the catalogue that covers the whole
Indic set in one pass, so a multilingual call centre recording does not need a
per-language model. It is a Conformer-CTC with per-language token sets, and the
official checkpoint is a ``.nemo`` archive that needs the full NeMo training
stack. This deployment runs the INT8 ONNX export instead: the same weights, the
same 22 language heads, executed through onnxruntime, which already ships with
the app and needs about 1.1 GB of RAM on CPU instead of the fp32 checkpoint's
2.6 GB.

Two behaviours are implemented here that matter for a diarised timeline:

* **Per-language vocabulary masking.** The checkpoint shares one 5633-token
  output space across all 22 languages. Decoding without a mask lets Telugu audio
  come back as whichever language happened to score highest in a space it was
  never meant to use, so the caller states the language and the head is
  restricted to that language's 257 tokens.
* **Real word timestamps from the CTC frame path.** CTC emits one label per
  80 ms encoder frame, so collapsing the path gives genuine per-word boundaries
  rather than a uniform split of a chunk. That is what makes the diarisation
  alignment trustworthy, and it is also what lets a 200 ms backchannel carry a
  real timestamp instead of borrowing its neighbour's.

CTC greedy decoding is the default because it is a single pass over the encoder
output and yields the frame path that timestamps come from. The RNNT head is
also wired up for callers that want it.
"""
import glob
import json
import logging
import os
import time
import uuid
from typing import Dict, List, Optional, Tuple

import numpy as np

from ...models.audio import AudioInput
from ...models.asr import ASRChunk, ASRMode, ASROptions, ASRResult, ASRToken
from .base import ASRProvider as BaseASRProvider
from .base import ASRStream as BaseASRStream

logger = logging.getLogger(__name__)

DEFAULT_MODEL_ID = "livinNector/indic-conformer-600m-int8-onnx"
TARGET_SAMPLE_RATE = 16000
WORD_BOUNDARY = "▁"

# The 22 official Indian languages, and the model id prefix that keys their
# per-language token set and prediction head.
LANGUAGES = (
    "as", "bn", "brx", "doi", "gu", "hi", "kn", "kok", "ks", "mai", "ml",
    "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta", "te", "ur",
)

# Session language codes ("te-IN", "hinglish", ...) to a model language.
LANGUAGE_ALIASES = {
    "te": "te", "te-in": "te", "te_tt": "te", "telugu": "te",
    "hi": "hi", "hi-in": "hi", "hi_tt": "hi", "hindi": "hi", "hinglish": "hi",
    "as": "as", "assamese": "as",
    "bn": "bn", "bangla": "bn", "bengali": "bn",
    "brx": "brx", "bodo": "brx",
    "doi": "doi", "dogri": "doi",
    "gu": "gu", "gujarati": "gu",
    "kn": "kn", "kannada": "kn",
    "kok": "kok", "konkani": "kok",
    "ks": "ks", "kashmiri": "ks",
    "mai": "mai", "maithili": "mai",
    "ml": "ml", "malayalam": "ml",
    "mni": "mni", "manipuri": "mni",
    "mr": "mr", "marathi": "mr",
    "ne": "ne", "nepali": "ne",
    "or": "or", "odia": "or", "oriya": "or",
    "pa": "pa", "punjabi": "pa", "panjabi": "pa",
    "sa": "sa", "sanskrit": "sa",
    "sat": "sat", "santali": "sat",
    "sd": "sd", "sindhi": "sd",
    "ta": "ta", "tamil": "ta",
    "ur": "ur", "urdu": "ur",
}

# Unicode block per language, used to report the script actually produced.
SCRIPT_BLOCKS = {
    "te": (0x0C00, 0x0C7F), "hi": (0x0900, 0x097F), "as": (0x0980, 0x09FF),
    "bn": (0x0980, 0x09FF), "brx": (0x1C50, 0x1C7F), "doi": (0x0900, 0x097F),
    "gu": (0x0A80, 0x0AFF), "kn": (0x0C80, 0x0CFF), "kok": (0x0900, 0x097F),
    "ks": (0x0900, 0x097F), "mai": (0x0900, 0x097F), "ml": (0x0D00, 0x0D7F),
    "mni": (0x0900, 0x097F), "mr": (0x0900, 0x097F), "ne": (0x0900, 0x097F),
    "or": (0x0B00, 0x0B7F), "pa": (0x0A00, 0x0A7F), "sa": (0x0900, 0x097F),
    "sat": (0x1C50, 0x1C7F), "sd": (0x0900, 0x097F), "ta": (0x0B80, 0x0BFF),
    "ur": (0x0600, 0x06FF),
}

# The model is trained on utterance-length audio, so it is decoded in overlapping
# windows: memory stays bounded on long recordings and each window keeps context.
#
# The window is 10 s rather than the 30 s a NeMo FastConformer would take, and that
# is not a performance choice. Measured on a 71 s Telugu call, the INT8 encoder
# emits a non-blank CTC path 47-79% of the time over 10 s windows but collapses to
# an all-blank path on 30 s windows (0.0% at offset 0, 9.0% at offset 15) -- the
# quantised encoder loses the utterance as the sequence grows. A silently blank
# window reads as "nobody spoke", which is exactly the failure this model exists
# to avoid, so the window stays inside what the encoder handles.
WINDOW_SEC = 10.0
OVERLAP_SEC = 1.5
MIN_WINDOW_SEC = 0.20

SCRIPT_LOCK_THRESHOLD = 0.5


def resolve_language(language_code: Optional[str], default: str = "te") -> str:
    """
    Maps a session language code to one of the 22 model languages.

    An unrecognised code falls back to the default rather than to "no mask",
    because an unmasked decode picks a language at random from the shared space.
    """
    if not language_code:
        return default
    key = str(language_code).strip().lower().replace("_", "-")
    if key in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[key]
    base = key.split("-")[0]
    return LANGUAGE_ALIASES.get(base, default)


def detect_output_language(text: str) -> Tuple[Optional[str], float]:
    """Reports the script actually produced, mapped back to a model language."""
    if not text:
        return None, 0.0
    counts = {lang: 0 for lang in SCRIPT_BLOCKS}
    latin = 0
    for char in text:
        point = ord(char)
        if ("a" <= char.lower() <= "z"):
            latin += 1
            continue
        for lang, (lo, hi) in SCRIPT_BLOCKS.items():
            if lo <= point <= hi:
                counts[lang] += 1
                break
    best = max(counts, key=lambda k: counts[k])
    total = sum(counts.values())
    if total == 0:
        return ("en" if latin else None, 0.8 if latin else 0.0)
    return best, round(counts[best] / total, 3)


class IndicConformerProvider(BaseASRProvider):
    """ASR provider backed by IndicConformer 600M multilingual (INT8 ONNX)."""

    model_id = DEFAULT_MODEL_ID
    display_name = "IndicConformer 600M multilingual (INT8 ONNX)"

    def __init__(self, model_id: str = DEFAULT_MODEL_ID):
        self.model_id = model_id
        self._root: Optional[str] = None
        self._load_error: Optional[str] = None
        self._loaded = False
        self._preprocessor = None
        self._sessions: Dict[str, object] = {}
        self._vocab: Dict[str, List[str]] = {}
        self._masks: Dict[str, np.ndarray] = {}
        self._blank_id = 256
        self._frame_sec = 0.08

    # ── model ───────────────────────────────────────────────────────────
    def _assets_dir(self) -> str:
        if self._root is not None:
            return os.path.join(self._root, "assets")

        override = os.environ.get("INDIC_CONFORMER_PATH", "").strip()
        if override and os.path.isdir(override):
            candidate = override if override.endswith("assets") else os.path.join(override, "assets")
            if os.path.exists(os.path.join(candidate, "encoder.onnx")):
                self._root = os.path.dirname(candidate.rstrip("/\\"))
                return candidate

        from huggingface_hub import snapshot_download

        offline = os.environ.get("INDIC_CONFORMER_OFFLINE", "0") == "1"
        self._root = snapshot_download(self.model_id, local_files_only=offline)
        return os.path.join(self._root, "assets")

    def _load(self) -> bool:
        if self._loaded:
            return True
        if self._load_error is not None:
            return False
        try:
            import onnxruntime as ort
            import torch

            assets = self._assets_dir()
            providers = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if torch.cuda.is_available()
                else ["CPUExecutionProvider"]
            )
            options = ort.SessionOptions()
            threads = int(os.environ.get("INDIC_CONFORMER_THREADS", "4"))
            options.intra_op_num_threads = max(1, threads)
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            def session(name: str):
                path = os.path.join(assets, f"{name}.onnx")
                return ort.InferenceSession(path, options, providers=providers)

            for name in ("encoder", "ctc_decoder", "joint_enc", "rnnt_decoder",
                         "joint_pred", "joint_pre_net"):
                self._sessions[name] = session(name)

            self._preprocessor = torch.jit.load(
                os.path.join(assets, "preprocessor.ts"),
                map_location=torch.device("cuda" if torch.cuda.is_available() else "cpu"),
            )

            with open(os.path.join(assets, "vocab.json"), encoding="utf-8") as handle:
                self._vocab = json.load(handle)
            with open(os.path.join(assets, "language_masks.json"), encoding="utf-8") as handle:
                masks = json.load(handle)
            self._masks = {lang: np.asarray(m, dtype=bool) for lang, m in masks.items()}

            self._loaded = True
            self._load_error = None
            logger.info("IndicConformer ready: %s", self.model_id)
            return True
        except Exception as exc:  # noqa: BLE001
            self._load_error = str(exc)
            self._preprocessor = None
            self._sessions.clear()
            logger.error("Could not load IndicConformer %s: %s", self.model_id, exc)
            return False

    def _head(self, language: str):
        """The per-language prediction head, loaded on first use."""
        if language not in self._sessions:
            import onnxruntime as ort

            assets = self._assets_dir()
            providers = list(self._sessions["encoder"].get_providers())
            options = ort.SessionOptions()
            options.intra_op_num_threads = max(1, int(os.environ.get("INDIC_CONFORMER_THREADS", "4")))
            self._sessions[f"joint_post_net_{language}"] = ort.InferenceSession(
                os.path.join(assets, f"joint_post_net_{language}.onnx"),
                options,
                providers=providers,
            )
        return self._sessions[f"joint_post_net_{language}"]

    def _vocab_for(self, language: str) -> List[str]:
        vocab = self._vocab.get(language) or self._vocab.get("te")
        if vocab is None:
            raise RuntimeError(f"IndicConformer has no vocabulary for '{language}'")
        return vocab

    def _mask_for(self, language: str) -> np.ndarray:
        mask = self._masks.get(language)
        if mask is None:
            raise RuntimeError(f"IndicConformer has no token mask for '{language}'")
        return mask

    # ── encoding ────────────────────────────────────────────────────────
    def _encode(self, y: np.ndarray):
        """
        Runs the mel preprocessor and encoder.

        Returns the encoder frames as ``(batch, time, 1024)`` and the number of
        valid frames. The frame count is used to trim padded output back down, so
        timestamps do not drift into padding on a window shorter than 30 s.
        """
        import torch

        # The exported preprocessor slices axis 1 to build the pre-emphasis
        # filter, so it takes (batch, samples) rather than a bare waveform.
        signal = torch.from_numpy(np.asarray(y, dtype=np.float32)).unsqueeze(0)
        features, length = self._preprocessor(
            input_signal=signal, length=torch.tensor([signal.shape[-1]])
        )
        outputs, encoded_lengths = self._sessions["encoder"].run(
            ["outputs", "encoded_lengths"],
            {"audio_signal": features.cpu().numpy(), "length": length.cpu().numpy()},
        )
        frames = int(np.asarray(encoded_lengths).reshape(-1)[0])
        return np.asarray(outputs, dtype=np.float32), min(frames, np.asarray(outputs).shape[1])

    def _decode_ctc(self, encoder_output: np.ndarray, frames: int, language: str) -> np.ndarray:
        """
        Greedy CTC decode restricted to one language's tokens.

        The decoder takes the encoder's native ``(batch, 1024, time)`` and returns
        ``(batch, time, 5633)``. Returns the per-frame path with blank frames
        included, because the frame path is what word timestamps come from.
        """
        logprobs = self._sessions["ctc_decoder"].run(
            ["logprobs"], {"encoder_output": encoder_output}
        )[0][0, :frames, :]
        masked = logprobs[:, self._mask_for(language)]
        # The masked slice is the language's own token set, so argmax over it is
        # an index into that language's vocabulary.
        return masked.argmax(axis=-1).astype(np.int64)

    def _word_spans(
        self, path: np.ndarray, language: str, audio_sec: float
    ) -> List[Tuple[str, float, float]]:
        """
        Collapses a CTC frame path into ``(word, start, end)`` with real times.

        A word starts at the piece carrying the word-boundary marker and ends when
        the next one starts, so a sub-word split across several frames is one
        timestamped word rather than several fragments.
        """
        vocab = self._vocab_for(language)
        blank = self._blank_id
        frame_sec = self._frame_sec if path.size else 0.0
        if path.size and path.size * frame_sec > 0:
            # Keep timestamps honest if the encoder's frame rate is not the
            # documented 80 ms: scale so the last frame lands on the audio end.
            frame_sec = min(frame_sec, audio_sec / float(path.size))

        words: List[Tuple[str, float, float]] = []
        current: Optional[str] = None
        start = 0.0
        previous_token: Optional[int] = None

        def flush(end_time: float) -> None:
            nonlocal current
            if current and current.strip():
                words.append((current.strip(), start, end_time))
            current = None

        for index, token in enumerate(path.tolist()):
            position = index * frame_sec
            if token != previous_token and token != blank:
                piece = vocab[token] if token < len(vocab) else ""
                if WORD_BOUNDARY in piece:
                    flush(position)
                    current = piece.replace(WORD_BOUNDARY, " ").strip()
                    start = position
                elif current is not None:
                    current += piece
            previous_token = token
        flush(min(audio_sec, path.size * frame_sec))

        return [
            (word, max(0.0, min(lo, audio_sec)), max(0.0, min(hi, audio_sec)))
            for word, lo, hi in words
            if max(0.0, min(hi, audio_sec)) > max(0.0, min(lo, audio_sec))
        ]

    def _decode_rnnt(self, encoder_output: np.ndarray, language: str) -> str:
        """Greedy RNNT decode through the per-language prediction head."""
        joint = self._sessions["joint_enc"].run(
            ["output"], {"input": np.ascontiguousarray(np.transpose(encoder_output, (0, 2, 1)))}
        )[0]
        steps, hidden = joint.shape[1], joint.shape[2]
        vocab = self._vocab_for(language)
        head = self._head(language)

        hypothesis = [256]
        state_h = np.zeros((2, 1, 640), dtype=np.float32)
        state_c = np.zeros((2, 1, 640), dtype=np.float32)
        limit = int(os.environ.get("INDIC_CONFORMER_RNNT_MAX_SYMBOLS", "10"))

        for step in range(steps):
            frame = joint[:, step, :].reshape(1, 1, hidden)
            not_blank, symbols = True, 0
            while not_blank and symbols < limit:
                targets = np.array([[hypothesis[-1]]], dtype=np.int32)
                decoder_out, _, next_h, next_c = self._sessions["rnnt_decoder"].run(
                    ["outputs", "prednet_lengths", "states", "162"],
                    {
                        "targets": targets,
                        "target_length": np.array([1], dtype=np.int32),
                        "states.1": state_h,
                        "onnx::Slice_3": state_c,
                    },
                )
                prediction = self._sessions["joint_pred"].run(
                    ["output"], {"input": np.ascontiguousarray(np.transpose(decoder_out, (0, 2, 1)))}
                )[0]
                joint_out = self._sessions["joint_pre_net"].run(
                    ["output"], {"input": (frame + prediction).astype(np.float32)}
                )[0]
                logits = head.run(["output"], {"input": joint_out})[0].reshape(-1)
                token = int(np.argmax(logits))
                if token == self._blank_id:
                    not_blank = False
                else:
                    hypothesis.append(token)
                    state_h, state_c = next_h, next_c
                symbols += 1

        return "".join(
            vocab[t] for t in hypothesis[1:] if t < len(vocab)
        ).replace(WORD_BOUNDARY, " ").strip()

    # ── transcription ───────────────────────────────────────────────────
    def _transcribe_array(
        self, y: np.ndarray, language: str, decoding: str
    ) -> Tuple[str, List[Tuple[str, float, float]]]:
        total_sec = len(y) / float(TARGET_SAMPLE_RATE)
        if total_sec <= WINDOW_SEC:
            return self._transcribe_window(y, language, decoding)

        words: List[Tuple[str, float, float]] = []
        window = int(WINDOW_SEC * TARGET_SAMPLE_RATE)
        hop = int((WINDOW_SEC - OVERLAP_SEC) * TARGET_SAMPLE_RATE)
        half = OVERLAP_SEC / 2.0
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

            _, window_words = self._transcribe_window(chunk, language, decoding)
            for word, start, end in window_words:
                centre = (start + end) / 2.0
                if core_lo <= centre < core_hi:
                    words.append((word, base_sec + start, base_sec + end))
            offset += hop

        words.sort(key=lambda item: item[1])
        return " ".join(word for word, _, _ in words), words

    def _transcribe_window(
        self, y: np.ndarray, language: str, decoding: str
    ) -> Tuple[str, List[Tuple[str, float, float]]]:
        audio_sec = len(y) / float(TARGET_SAMPLE_RATE)
        encoder_output, frames = self._encode(y)
        if frames <= 0:
            return "", []

        if decoding == "rnnt":
            return self._decode_rnnt(encoder_output, language), []

        path = self._decode_ctc(encoder_output, frames, language)
        words = self._word_spans(path, language, audio_sec)
        return " ".join(word for word, _, _ in words), words

    def _decoding(self, options: ASROptions) -> str:
        return "rnnt" if os.environ.get("INDIC_CONFORMER_DECODER", "ctc") == "rnnt" else "ctc"

    # ── ASRProvider ─────────────────────────────────────────────────────
    async def transcribe_file(self, audio: AudioInput, options: ASROptions) -> ASRResult:
        import asyncio

        started = time.time()
        y, sr = await asyncio.to_thread(self._load_mono, audio)
        if y is None or len(y) == 0:
            raise ValueError("Audio could not be decoded for transcription")
        if sr != TARGET_SAMPLE_RATE:
            raise ValueError(f"IndicConformer expects {TARGET_SAMPLE_RATE} Hz audio, got {sr} Hz")
        if not await asyncio.to_thread(self._load):
            raise RuntimeError(
                f"IndicConformer model {self.model_id} is unavailable: {self._load_error}. "
                "Set INDIC_CONFORMER_PATH to a local copy, or unset INDIC_CONFORMER_OFFLINE "
                "to allow the download."
            )

        language = resolve_language(options.language_code)
        text, words = await asyncio.to_thread(
            self._transcribe_array, y, language, self._decoding(options)
        )
        return self._result(text, words, language, options, started)

    async def transcribe_interval(
        self,
        audio_file_path: str,
        start_time: float,
        end_time: float,
        options: Optional[ASROptions] = None,
    ) -> ASRResult:
        """
        Re-decodes ``[start_time, end_time]`` on its own.

        This is the path the backchannel rescue pass uses. A 300 ms "yeah" is a
        much easier thing to decode on its own than to find between two long
        utterances, so the region is given a lead-in of context, decoded, and the
        timestamps are rebased onto the original timeline.
        """
        import asyncio

        started = time.time()
        opts = options or ASROptions(mode=ASRMode.CODEMIXED, language_code="te")
        start_time = max(0.0, float(start_time))
        end_time = max(start_time + 0.05, float(end_time))

        if not audio_file_path or not os.path.exists(audio_file_path):
            raise ValueError("Audio file is not available for re-transcription")
        if not await asyncio.to_thread(self._load):
            raise RuntimeError(f"IndicConformer model {self.model_id} is unavailable")

        context = 0.25
        offset = max(0.0, start_time - context)
        y, sr = await asyncio.to_thread(_read_slice, audio_file_path, offset, end_time)
        if y is None or len(y) < int(0.08 * TARGET_SAMPLE_RATE):
            return _empty_result(opts, started)

        language = resolve_language(opts.language_code)
        _, words = await asyncio.to_thread(
            self._transcribe_array, y, language, self._decoding(opts)
        )

        rebased: List[Tuple[str, float, float]] = []
        for word, w_start, w_end in words:
            absolute_start = min(max(offset + w_start, start_time), end_time)
            absolute_end = min(max(offset + w_end, start_time), end_time)
            if absolute_end > absolute_start:
                rebased.append((word, absolute_start, absolute_end))

        return self._result(
            " ".join(word for word, _, _ in rebased), rebased, language, opts, started
        )

    async def start_stream(self, options: ASROptions) -> BaseASRStream:
        raise NotImplementedError(
            "IndicConformer is an offline model; live streaming transcription is not supported."
        )

    # ── helpers ─────────────────────────────────────────────────────────
    def _result(
        self,
        text: str,
        words: List[Tuple[str, float, float]],
        language: str,
        options: ASROptions,
        started: float,
    ) -> ASRResult:
        tokens = [
            ASRToken(
                id=str(uuid.uuid4()),
                text=word,
                start=round(start, 3),
                end=round(end, 3),
                confidence=_token_confidence(word),
                language=_word_language(word, language),
                is_final=True,
            )
            for word, start, end in words
        ]
        detected, probability = detect_output_language(text)
        return ASRResult(
            transcript=text,
            language_code=f"{detected or language}-IN",
            language_probability=round(probability, 3),
            chunks=_build_chunks(tokens, options.mode) if tokens else [],
            tokens=tokens,
            latency_sec=round(time.time() - started, 3),
        )

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
        peak = float(np.max(np.abs(y))) if len(y) else 0.0
        if peak > 1.0:
            y = y / peak
        return np.asarray(y, dtype=np.float32), TARGET_SAMPLE_RATE


# ── text helpers ─────────────────────────────────────────────────────────
def _word_language(word: str, fallback: str) -> str:
    if not word:
        return fallback
    lo, hi = SCRIPT_BLOCKS.get(fallback, (0, 0))
    if lo <= ord(word[0]) <= hi:
        return fallback
    for lang, (block_lo, block_hi) in SCRIPT_BLOCKS.items():
        if any(block_lo <= ord(c) <= block_hi for c in word):
            return lang
    return "en" if any("a" <= c.lower() <= "z" for c in word) else fallback


def _token_confidence(word: str) -> float:
    """
    Greedy CTC decoding exposes no per-token posterior, so confidence is derived
    from orthography rather than invented: the sub-word fragments alignment is
    least sure about score lower.
    """
    stripped = word.strip()
    if not stripped:
        return 0.5
    if len(stripped) <= 2:
        return 0.80
    return 0.92


def _build_chunks(tokens: List[ASRToken], mode: ASRMode) -> List[ASRChunk]:
    """Groups word tokens into readable chunks on pause length and punctuation."""
    if not tokens:
        return []

    pause_limit = 0.9 if mode == ASRMode.NORMAL else 0.6
    groups: List[List[ASRToken]] = [[tokens[0]]]
    for previous, token in zip(tokens, tokens[1:]):
        gap = token.start - previous.end
        if gap > pause_limit or previous.text.endswith((".", "?", "!", "।", "॥")):
            groups.append([token])
        else:
            groups[-1].append(token)

    chunks: List[ASRChunk] = []
    for group in groups:
        chunks.append(
            ASRChunk(
                id=str(uuid.uuid4()),
                text=" ".join(t.text for t in group),
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
    start_frame = max(0, int(start_sec * info.samplerate))
    stop_frame = min(info.frames, int(end_sec * info.samplerate))
    if stop_frame <= start_frame:
        return None, info.samplerate
    data, _ = sf.read(path, start=start_frame, stop=stop_frame, dtype="float32")
    if data.ndim > 1:
        data = data.mean(axis=1)
    if info.samplerate != TARGET_SAMPLE_RATE:
        import librosa

        data = librosa.resample(data, orig_sr=info.samplerate, target_sr=TARGET_SAMPLE_RATE)
    return np.asarray(data, dtype=np.float32), TARGET_SAMPLE_RATE


def _empty_result(options: ASROptions, started: float) -> ASRResult:
    return ASRResult(
        transcript="",
        language_code=options.language_code,
        language_probability=0.0,
        chunks=[],
        tokens=[],
        latency_sec=round(time.time() - started, 3),
    )


def model_available() -> bool:
    """True when the checkpoint is on disk, without paying for a model load."""
    if os.environ.get("INDIC_CONFORMER_PATH"):
        return True
    pattern = os.path.join(
        os.path.expanduser("~"),
        ".cache/huggingface/hub",
        f"models--{DEFAULT_MODEL_ID.replace('/', '--')}",
        "snapshots", "*", "assets", "encoder.onnx",
    )
    return bool(glob.glob(pattern))
