import os
import time
import uuid
import httpx
from typing import Optional, List, AsyncGenerator
from ...models.audio import AudioInput, AudioFrame
from ...models.asr import ASROptions, ASRResult, ASRChunk, ASRToken, ASRMode
from .base import ASRProvider, ASRStream

SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_STREAM_URL = "wss://api.sarvam.ai/speech-to-text/ws"

class SarvamSaarasStream(ASRStream):
    def __init__(self, options: ASROptions, api_key: str):
        self.options = options
        self.api_key = api_key
        self.closed = False
        self._buffer: List[AudioFrame] = []

    async def push_audio(self, frame: AudioFrame) -> None:
        self._buffer.append(frame)

    async def get_results(self) -> AsyncGenerator[ASRChunk, None]:
        # WebSocket streaming yield mechanism
        while not self.closed:
            await httpx.AsyncClient().get("http://localhost:8000/api/health") # Keep event loop alive
            break
        yield ASRChunk(
            id=str(uuid.uuid4()),
            text="",
            start=0.0,
            end=0.0,
            is_final=True
        )

    async def close(self) -> None:
        self.closed = True

class SarvamSaarasProvider(ASRProvider):
    api_model = "saaras:v4"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SARVAM_API_KEY", "")

    async def transcribe_file(self, audio: AudioInput, options: ASROptions) -> ASRResult:
        if not self.api_key:
            raise ValueError(
                "SARVAM_API_KEY is not configured. Please set SARVAM_API_KEY in environment or .env file."
            )

        start_time = time.time()
        
        # Determine mode string for Sarvam API
        mode_str = "codemix"
        if options.mode == ASRMode.NORMAL:
            mode_str = "transcribe"
        elif options.mode == ASRMode.VERBATIM:
            mode_str = "verbatim"
        elif options.mode == ASRMode.CODEMIXED:
            mode_str = "codemix"

        headers = {
            "api-subscription-key": self.api_key
        }

        # Prepare audio file payload
        file_bytes = audio.raw_bytes
        file_name = "audio.wav"
        if audio.file_path and os.path.exists(audio.file_path):
            with open(audio.file_path, "rb") as f:
                file_bytes = f.read()
            file_name = os.path.basename(audio.file_path)

        if not file_bytes:
            raise ValueError("No audio data provided in AudioInput")

        files = {
            "file": (file_name, file_bytes, "audio/wav")
        }

        # ASROptions.model carries the *registry* id (e.g. "sarvam_saaras_v4"), so only
        # forward it when it is actually a Sarvam API model name.
        api_model = options.model if str(options.model or "").startswith("saaras") else self.api_model

        data = {
            "model": api_model,
            "mode": mode_str,
            "with_timestamps": "true" if options.with_timestamps else "false"
        }

        if options.language_code and options.language_code != "unknown":
            data["language_code"] = options.language_code

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                SARVAM_STT_URL,
                headers=headers,
                files=files,
                data=data
            )

            if response.status_code != 200:
                raise RuntimeError(
                    f"Sarvam API error (status {response.status_code}): {response.text}"
                )

            res_json = response.json()

        latency = time.time() - start_time
        transcript = res_json.get("transcript", "")
        detected_lang = res_json.get("language_code", "te-IN")
        lang_prob = res_json.get("language_probability")

        # Parse word timestamps
        tokens: List[ASRToken] = []
        timestamps_data = res_json.get("timestamps", {})
        words = timestamps_data.get("words", [])
        starts = timestamps_data.get("start_time_seconds", [])
        ends = timestamps_data.get("end_time_seconds", [])

        if words and len(words) == len(starts) and len(words) == len(ends):
            for w, s, e in zip(words, starts, ends):
                # Detect word language (Telugu script vs English Latin script)
                is_telugu = any('\u0C00' <= char <= '\u0C7F' for char in w)
                w_lang = "te" if is_telugu else ("en" if any('a' <= char.lower() <= 'z' for char in w) else detected_lang)
                tokens.append(
                    ASRToken(
                        id=str(uuid.uuid4()),
                        text=w,
                        start=round(float(s), 3),
                        end=round(float(e), 3),
                        language=w_lang,
                        is_final=True
                    )
                )

        # Build chunks: if word timestamps exist, chunk by pauses or sentences; else single chunk
        chunks: List[ASRChunk] = []
        if tokens:
            current_tokens: List[ASRToken] = []
            for token in tokens:
                if current_tokens and (token.start - current_tokens[-1].end > 0.6 or token.text.endswith(('.', '?', '!'))):
                    chunk_text = " ".join(t.text for t in current_tokens)
                    chunks.append(
                        ASRChunk(
                            id=str(uuid.uuid4()),
                            text=chunk_text,
                            start=current_tokens[0].start,
                            end=current_tokens[-1].end,
                            tokens=list(current_tokens),
                            language=detected_lang,
                            is_final=True
                        )
                    )
                    current_tokens = []
                current_tokens.append(token)
            if current_tokens:
                chunk_text = " ".join(t.text for t in current_tokens)
                chunks.append(
                    ASRChunk(
                        id=str(uuid.uuid4()),
                        text=chunk_text,
                        start=current_tokens[0].start,
                        end=current_tokens[-1].end,
                        tokens=list(current_tokens),
                        language=detected_lang,
                        is_final=True
                    )
                )
        else:
            # Fallback if provider only returned whole transcript without words
            chunks.append(
                ASRChunk(
                    id=str(uuid.uuid4()),
                    text=transcript,
                    start=0.0,
                    end=audio.metadata.duration_sec if audio.metadata else 0.0,
                    tokens=[],
                    language=detected_lang,
                    is_final=True
                )
            )

        return ASRResult(
            transcript=transcript,
            language_code=detected_lang,
            language_probability=lang_prob,
            chunks=chunks,
            tokens=tokens,
            latency_sec=round(latency, 3)
        )

    async def transcribe_interval(
        self,
        audio_file_path: str,
        start_time: float,
        end_time: float,
        options: Optional[ASROptions] = None
    ) -> ASRResult:
        """
        Uploads only the requested slice, with a little lead-in for context.

        Sarvam reports absolute timestamps for the audio it was given, so the slice
        offset is added back on before returning.
        """
        import os as _os
        import tempfile

        import numpy as np
        import soundfile as sf

        if not audio_file_path or not _os.path.exists(audio_file_path):
            raise ValueError("Audio file is not available for re-transcription")

        context = 0.25
        offset = max(0.0, float(start_time) - context)
        info = sf.info(audio_file_path)
        data, sr = sf.read(
            audio_file_path,
            start=int(offset * info.samplerate),
            stop=int(float(end_time) * info.samplerate),
            dtype="float32",
        )
        if data.ndim > 1:
            data = data.mean(axis=1)
        if len(data) == 0:
            return ASRResult(transcript="", chunks=[], tokens=[], latency_sec=0.0)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            slice_path = tmp.name
        try:
            sf.write(slice_path, np.asarray(data, dtype="float32"), sr, subtype="PCM_16")
            result = await self.transcribe_file(AudioInput(file_path=slice_path), options)
        finally:
            try:
                _os.remove(slice_path)
            except OSError:
                pass

        upper = float(end_time)
        for token in result.tokens:
            token.start = round(min(max(offset + token.start, float(start_time)), upper), 3)
            token.end = round(min(max(offset + token.end, token.start), upper), 3)
        for chunk in result.chunks:
            chunk.start = round(min(max(offset + chunk.start, float(start_time)), upper), 3)
            chunk.end = round(min(max(offset + chunk.end, chunk.start), upper), 3)
        return result

    async def start_stream(self, options: ASROptions) -> ASRStream:
        return SarvamSaarasStream(options, self.api_key)
