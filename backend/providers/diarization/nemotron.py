import logging
import os
import time
from typing import AsyncGenerator, List, Optional

import httpx
import numpy as np

from ...models.audio import AudioInput, AudioFrame
from ...models.diarization import DiarizationOptions, DiarizationResult, DiarizationSegment
from .base import DiarizationProvider, DiarizationStream
from .speaker_count import estimate_and_merge

logger = logging.getLogger(__name__)

# NVIDIA's canonical Sortformer diarisation checkpoints (powerset / multi-class
# labels, so they can report genuinely overlapped speech).
SORTFORMER_MODEL_ID = "nvidia/diar_sortformer_4spk-v1"
# The checkpoint is a four-class power-set model, so four is a *capacity*, not a
# prediction: it will activate all four classes for a two-voice call whenever the
# audio gives it enough excuse. Callers asking for fewer speakers get that
# ceiling passed through, and every result is re-clustered downstream against
# measured speaker embeddings so the published count is the evidence, not the
# model's capacity.
SORTFORMER_MAX_SPEAKERS = 4


class NemotronDiarizationStream(DiarizationStream):
    def __init__(self, options: DiarizationOptions):
        self.options = options
        self.closed = False

    async def push_audio(self, frame: AudioFrame) -> None:
        pass

    async def get_results(self) -> AsyncGenerator[DiarizationSegment, None]:
        return
        yield  # pragma: no cover - keeps this an async generator

    async def close(self) -> None:
        self.closed = True


class NemotronDiarizationProvider(DiarizationProvider):
    """
    NVIDIA neural diarisation.

    Two real backends:
      * a remote NIM/REST endpoint when ``NEMOTRON_ENDPOINT`` is configured;
      * local NVIDIA Sortformer (``nvidia_toolkit`` / ``nemo_toolkit``) otherwise.

    Unlike an acoustic heuristic this reports overlapped speech only where the
    model actually predicts it, and returns an empty segment list rather than
    fabricated turns when neither backend is usable.
    """

    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None):
        self.endpoint = (endpoint or os.environ.get("NEMOTRON_ENDPOINT", "")).strip()
        self.api_key = api_key or os.environ.get("NEMOTRON_API_KEY", "")
        self._sortformer = None
        self._sortformer_error: Optional[str] = None
        self._embedder = None

    async def process_file(self, audio: AudioInput, options: DiarizationOptions) -> DiarizationResult:
        started = time.time()

        if self.endpoint:
            result = await self._process_remote(audio, options, started)
        else:
            result = await self._process_sortformer(audio, options, started)

        if options.auto_speaker_count:
            result = self._consolidate(result, audio, options, started)
        return result

    # ── speaker-count consolidation ─────────────────────────────────────
    def _consolidate(
        self,
        result: DiarizationResult,
        audio: AudioInput,
        options: DiarizationOptions,
        started: float,
    ) -> DiarizationResult:
        """
        Re-clusters an over-split result to the number of voices actually heard.

        A power-set model and a remote endpoint both hand back a label per active
        class, and neither is a claim about how many people were on the call. The
        segment embeddings decide instead.
        """
        before = len(result.speakers)
        if len(result.segments) < 3 or before <= 1:
            return result

        try:
            embeddable = [s for s in result.segments if (s.end - s.start) > 0.05]
            if len(embeddable) < 3:
                return result
            embeddings = self._embed_segments(embeddable, audio)
            merged, count, scores = estimate_and_merge(
                embeddable,
                embeddings,
                max_speakers=options.max_speakers,
                min_speakers=options.min_speakers,
            )
        except Exception as exc:  # noqa: BLE001 - keep the raw result rather than fail
            logger.warning("Speaker consolidation skipped, embedding failed: %s", exc)
            return result

        if count == before:
            return result

        logger.info("Diarisation over-split: %d labels collapsed to %d speakers", before, count)

        # Unmeasurable slivers keep their original label, so nothing is lost when
        # a segment is too short to embed.
        remap = {old.speaker_id: new.speaker_id for old, new in zip(embeddable, merged)}
        segments: List[DiarizationSegment] = []
        for segment in result.segments:
            speaker = remap.get(segment.speaker_id, segment.speaker_id)
            # Two labels the backend marked as overlapping can turn out to be one
            # voice, which would leave the segment overlapping itself.
            others = sorted({
                remap.get(name, name) for name in segment.overlap_speakers if name != speaker
            })
            segments.append(
                DiarizationSegment(
                    speaker_id=speaker,
                    start=segment.start,
                    end=segment.end,
                    confidence=segment.confidence,
                    is_overlap=segment.is_overlap and bool(others),
                    overlap_speakers=others,
                )
            )
        segments.sort(key=lambda s: (s.start, s.end))

        result.segments = segments
        result.speakers = sorted({s.speaker_id for s in segments})
        result.overlap_count = sum(1 for s in segments if s.is_overlap)
        result.metadata = {
            **result.metadata,
            "speakers_before_consolidation": before,
            "estimated_speaker_count": count,
            "speaker_count_drops": scores,
        }
        result.latency_sec = round(time.time() - started, 3)
        return result

    def _embed_segments(self, segments: List[DiarizationSegment], audio: AudioInput) -> np.ndarray:
        from .embedding import SpeakerEmbedder

        if self._embedder is None:
            self._embedder = SpeakerEmbedder()
        y, sr = _mono_16k(audio)
        return np.stack(
            [self._embedder.embed(y[int(s.start * sr) : int(s.end * sr)], sr) for s in segments]
        )

    # ── remote endpoint ─────────────────────────────────────────────────
    async def _process_remote(
        self, audio: AudioInput, options: DiarizationOptions, started: float
    ) -> DiarizationResult:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        file_bytes = audio.raw_bytes
        file_name = "audio.wav"
        if audio.file_path and os.path.exists(audio.file_path):
            with open(audio.file_path, "rb") as f:
                file_bytes = f.read()
            file_name = os.path.basename(audio.file_path)

        if not file_bytes:
            raise ValueError("No audio content in AudioInput")

        files = {"file": (file_name, file_bytes, "audio/wav")}
        data = {
            "max_speakers": str(options.max_speakers),
            "threshold": str(options.threshold),
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            res = await client.post(f"{self.endpoint.rstrip('/')}/diarize", headers=headers, files=files, data=data)
            if res.status_code != 200:
                raise RuntimeError(f"Nemotron endpoint error ({res.status_code}): {res.text}")
            payload = res.json()

        segments = [
            DiarizationSegment(
                speaker_id=s["speaker_id"],
                start=round(float(s["start"]), 3),
                end=round(float(s["end"]), 3),
                confidence=s.get("confidence"),
                is_overlap=bool(s.get("is_overlap", False)),
                overlap_speakers=list(s.get("overlap_speakers", []) or []),
            )
            for s in payload.get("segments", [])
        ]
        segments.sort(key=lambda s: (s.start, s.end))
        return DiarizationResult(
            segments=segments,
            speakers=sorted({s.speaker_id for s in segments}),
            overlap_count=int(payload.get("overlap_count", 0)),
            method="nemotron_endpoint",
            latency_sec=round(time.time() - started, 3),
        )

    # ── local Sortformer ────────────────────────────────────────────────
    def _load_sortformer(self):
        if self._sortformer is not None:
            return self._sortformer
        if self._sortformer_error is not None:
            return None
        try:
            try:
                from nemo.collections.asr.models import SortformerEncLabelModel  # type: ignore
            except ImportError:
                from nemo_toolkit.collections.asr.models import SortformerEncLabelModel  # type: ignore

            self._sortformer = SortformerEncLabelModel.from_pretrained(SORTFORMER_MODEL_ID)
            self._sortformer_error = None
        except Exception as exc:  # noqa: BLE001
            self._sortformer_error = str(exc)
        return self._sortformer

    async def _process_sortformer(
        self, audio: AudioInput, options: DiarizationOptions, started: float
    ) -> DiarizationResult:
        model = self._load_sortformer()
        if model is None:
            raise RuntimeError(
                "NVIDIA neural diarisation needs either NEMOTRON_ENDPOINT or a local "
                f"Sortformer install ({SORTFORMER_MODEL_ID}). "
                f"Loader error: {self._sortformer_error}"
            )

        path = audio.file_path
        if not (path and os.path.exists(path)):
            raise ValueError("Sortformer diarisation requires a decoded audio file on disk")

        output = model.diarize(
            audio=[path],
            batch_size=1,
            # The caller's ceiling wins, clamped to what this checkpoint can do.
            max_speakers=max(1, min(int(options.max_speakers), SORTFORMER_MAX_SPEAKERS)),
        )

        segments: List[DiarizationSegment] = []
        transcript = output[0] if isinstance(output, (list, tuple)) else output
        rttm = getattr(transcript, "rttm", None)
        if rttm is None and isinstance(transcript, str):
            rttm = transcript

        for speaker, start, end in _parse_rttm(rttm or []):
            segments.append(
                DiarizationSegment(
                    speaker_id=speaker,
                    start=start,
                    end=end,
                    confidence=None,
                )
            )
        segments.sort(key=lambda s: (s.start, s.end))

        return DiarizationResult(
            segments=segments,
            speakers=sorted({s.speaker_id for s in segments}),
            overlap_count=0,
            method="sortformer",
            metadata={"model": SORTFORMER_MODEL_ID},
            latency_sec=round(time.time() - started, 3),
        )

    async def start_stream(self, options: DiarizationOptions) -> DiarizationStream:
        return NemotronDiarizationStream(options)


def _mono_16k(audio: AudioInput):
    """Loads ``audio`` as 16 kHz mono float32 for the speaker embedder."""
    import tempfile

    from ...pipeline.audio_preprocessor import preprocessor

    source = audio
    if not (audio.file_path and os.path.exists(audio.file_path)) and audio.raw_bytes:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.write(audio.raw_bytes)
        tmp.close()
        source = AudioInput(file_path=tmp.name, metadata=audio.metadata)

    y = preprocessor.load_audio(source)
    if len(y) == 0:
        raise ValueError("audio could not be decoded for speaker embedding")
    peak = float(np.max(np.abs(y)))
    if peak > 1.0:
        y = y / peak
    return np.asarray(y, dtype=np.float32), preprocessor.target_sample_rate


def _parse_rttm(lines) -> List[tuple]:
    """
    Parses RTTM ``SPEAKER <file> <chan> <start> <dur> <NA> <NA> <speaker> ...`` lines.

    Sortformer emits one entry per active class, so entries sharing a speaker label
    are merged and concurrent entries from different labels are kept as-is.
    """
    if isinstance(lines, str):
        lines = lines.splitlines()

    parsed: List[tuple] = []
    for line in lines:
        parts = line.split()
        if len(parts) < 8 or parts[0] != "SPEAKER":
            continue
        try:
            start = float(parts[3])
            duration = float(parts[4])
        except ValueError:
            continue
        if duration <= 0:
            continue
        parsed.append((parts[7], round(start, 3), round(start + duration, 3)))

    parsed.sort(key=lambda item: item[1])
    merged: List[tuple] = []
    for speaker, start, end in parsed:
        if merged and merged[-1][0] == speaker and start <= merged[-1][2]:
            merged[-1] = (speaker, merged[-1][1], max(merged[-1][2], end))
        else:
            merged.append((speaker, start, end))
    return merged
