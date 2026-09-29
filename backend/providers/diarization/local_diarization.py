"""
Offline speaker diarisation that runs on CPU with no extra services.

Pipeline (the standard offline recipe used by pyannote and friends):

    VAD  ->  speaker embeddings per region  ->  within-region change detection
         ->  agglomerative clustering on cosine distance  ->  speaker labels

It never invents speech. If no voice activity is found, the result is an empty
segment list rather than fabricated alternating blocks, and overlaps are only
reported when a model that actually models overlapped speech produced them.
"""
import logging
import os
import time
from typing import List, Optional, Tuple

import numpy as np

from ...models.audio import AudioInput, AudioFrame
from ...models.diarization import DiarizationOptions, DiarizationResult, DiarizationSegment
from .base import DiarizationProvider, DiarizationStream
from .embedding import SpeakerEmbedder
from .speaker_count import estimate_and_merge
from .vad import detect_speech

logger = logging.getLogger(__name__)

CHANGE_WINDOW_SEC = 1.5
CHANGE_HOP_SEC = 0.5
MIN_SPLIT_SIDE_SEC = 1.5
# Floor on the automatically detected cluster boundary, as a share of the
# configured threshold. See auto_cluster_threshold for why it is not lower.
OTSU_LOWER_BOUND = 0.70


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity of two embeddings, safe for the zero vector."""
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denominator < 1e-8:
        return 0.0
    return float(np.dot(a, b)) / denominator


def mean_normalize(embeddings: np.ndarray) -> np.ndarray:
    """
    Removes the corpus mean and re-normalises.

    Self-supervised x-vectors share a large common component that inflates every
    cosine similarity; subtracting the mean of the file's own segments isolates the
    speaker-discriminative directions. This is the same normalisation standard
    offline diarisation pipelines apply before clustering.
    """
    if embeddings.shape[0] == 0:
        return embeddings
    centred = embeddings - embeddings.mean(axis=0, keepdims=True)
    norms = np.linalg.norm(centred, axis=1, keepdims=True)
    norms[norms < 1e-8] = 1.0
    return centred / norms


def auto_cluster_threshold(embeddings: np.ndarray, fallback: float) -> float:
    """
    Picks the speech/speech decision boundary from the distance distribution.

    Otsu's method on the off-diagonal cosine distances finds the natural gap
    between "same speaker" and "different speaker" clusters, then the result is
    bounded so a degenerate distribution can never run away.

    The lower bound is deliberately tight (70% of the configured threshold).
    Halving it, as an earlier version did, let the boundary fall to 0.45 cosine
    distance on a two-voice call -- far enough that ordinary variation in one
    person's voice, their handset, their mood, the channel balance between
    handsets, turned into extra clusters. An over-split is much more damaging
    than a slightly loose threshold, because every phantom cluster becomes its
    own speaker lane that the user then has to merge by hand.
    """
    n = embeddings.shape[0]
    fallback = float(fallback)
    if n < 3:
        return fallback

    normed = embeddings / np.maximum(np.linalg.norm(embeddings, axis=1, keepdims=True), 1e-8)
    distance = 1.0 - np.clip(normed @ normed.T, -1.0, 1.0)
    upper = distance[np.triu_indices(n, 1)]
    upper = upper[np.isfinite(upper)]
    if upper.size < 3 or float(upper.max() - upper.min()) < 1e-6:
        return fallback

    hist, edges = np.histogram(upper, bins=64)
    p = hist.astype(np.float64) / max(hist.sum(), 1)
    centers = (edges[:-1] + edges[1:]) / 2.0
    w0 = np.cumsum(p)
    w1 = 1.0 - w0
    mu0 = np.cumsum(p * centers)
    mu1 = (mu0[-1] - mu0) / np.maximum(w1, 1e-12)
    between = w0 * w1 * (mu0 / np.maximum(w0, 1e-12) - mu1) ** 2
    estimate = float(centers[int(np.argmax(between))])

    return float(np.clip(estimate, OTSU_LOWER_BOUND * fallback, 1.5 * fallback))



def agglomerative_cosine(
    embeddings: np.ndarray,
    threshold: float,
    max_clusters: int,
) -> np.ndarray:
    """
    Average-linkage agglomerative clustering with cosine distance.

    Merges the closest pair while its distance is within ``threshold`` (the
    speech/speech decision boundary), then keeps merging if the cap in
    ``max_clusters`` still has to be enforced. Returns one label per row.
    """
    n = embeddings.shape[0]
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    if n == 1:
        return np.zeros(1, dtype=np.int64)

    max_clusters = max(1, min(int(max_clusters), n))

    try:
        from sklearn.cluster import AgglomerativeClustering

        labels = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=threshold,
            metric="cosine",
            linkage="average",
        ).fit_predict(embeddings)
        labels = np.asarray(labels, dtype=np.int64)
        if len(set(labels.tolist())) <= max_clusters:
            return labels
        # Too many clusters for the requested cap — re-run with a fixed cluster count.
        return np.asarray(
            AgglomerativeClustering(
                n_clusters=max_clusters,
                metric="cosine",
                linkage="average",
            ).fit_predict(embeddings),
            dtype=np.int64,
        )
    except Exception as exc:  # noqa: BLE001 - degrade to the built-in implementation
        logger.info("scikit-learn clustering unavailable (%s); using built-in AHC", exc)
        return _average_linkage(embeddings, threshold, max_clusters)


def _average_linkage(embeddings: np.ndarray, threshold: float, max_clusters: int) -> np.ndarray:
    n = embeddings.shape[0]
    normed = embeddings / np.maximum(np.linalg.norm(embeddings, axis=1, keepdims=True), 1e-8)
    similarity = np.clip(normed @ normed.T, -1.0, 1.0)
    distance = 1.0 - similarity

    active = {i: [i] for i in range(n)}
    while len(active) > 1:
        keys = sorted(active)
        best_d, best_a, best_b = float("inf"), None, None
        for ai in range(len(keys)):
            for bi in range(ai + 1, len(keys)):
                ka, kb = keys[ai], keys[bi]
                d = float(distance[ka, active[kb]].mean())
                if d < best_d:
                    best_d, best_a, best_b = d, ka, kb
        if best_a is None:
            break
        if best_d > threshold and len(active) <= max_clusters:
            break
        active[best_a].extend(active[best_b])
        del active[best_b]

    labels = np.zeros(n, dtype=np.int64)
    for idx, members in enumerate(sorted(active.values(), key=lambda m: m[0])):
        for m in members:
            labels[m] = idx
    return labels


class LocalSpeakerDiarizer:
    """VAD + speaker embeddings + clustering over a 16 kHz mono buffer."""

    def __init__(self, embedder: Optional[SpeakerEmbedder] = None):
        self._embedder = embedder or SpeakerEmbedder()

    def diarize(
        self,
        y: np.ndarray,
        sr: int,
        options: DiarizationOptions,
        duration: Optional[float] = None,
    ) -> DiarizationResult:
        started = time.time()

        def empty(reason: str) -> DiarizationResult:
            return DiarizationResult(
                segments=[],
                speakers=[],
                method="acoustic",
                metadata={"reason": reason},
                latency_sec=round(time.time() - started, 3),
            )

        if y is None or sr <= 0 or len(y) < int(0.2 * sr):
            return empty("audio too short to analyse")

        if not duration or duration <= 0:
            duration = len(y) / float(sr)

        regions = [
            (s, e)
            for s, e in detect_speech(
                y,
                sr,
                min_speech_duration=options.min_speech_duration,
                min_silence_duration=options.min_silence_duration,
                pad=options.speech_pad,
            )
            if e - s >= options.min_speech_duration
        ]
        if not regions:
            return empty("no voice activity detected")

        regions = self._split_long_regions(y, sr, regions, options)
        if not regions:
            return empty("no regions left after change detection")

        embeddings = np.stack(
            [self._embedder.embed(y[int(s * sr) : int(e * sr)], sr) for s, e in regions]
        )
        embeddings = mean_normalize(embeddings)

        max_clusters = max(1, min(int(options.max_speakers), len(regions)))
        threshold = auto_cluster_threshold(embeddings, options.cluster_threshold)
        labels = agglomerative_cosine(embeddings, threshold, max_clusters)

        segments = self._to_segments(regions, embeddings, labels, options, duration)

        estimated_count = None
        count_scores: dict = {}
        speakers_before = len({s.speaker_id for s in segments})
        if options.auto_speaker_count:
            segments, estimated_count, count_scores = estimate_and_merge(
                segments,
                self._embed_for(segments, y, sr),
                max_speakers=options.max_speakers,
                min_speakers=options.min_speakers,
            )

        speakers = sorted({seg.speaker_id for seg in segments})
        return DiarizationResult(
            segments=segments,
            speakers=speakers,
            overlap_count=0,
            method=f"acoustic_{self._embedder.backend or 'mfcc'}",
            metadata={
                "num_speakers": len(speakers),
                "speech_duration_sec": round(sum(e - s for s, e in regions), 3),
                "embedding_model": self._embedder.model_id if self._embedder.backend else "mfcc_statistics",
                "num_regions": len(regions),
                "cluster_threshold": round(threshold, 3),
                "speakers_before_consolidation": speakers_before,
                "estimated_speaker_count": estimated_count,
                "speaker_count_drops": count_scores,
            },
            latency_sec=round(time.time() - started, 3),
        )

    def _embed_for(
        self, segments: List[DiarizationSegment], y: np.ndarray, sr: int
    ) -> np.ndarray:
        """Speaker embedding per already-built segment, for the re-clustering pass."""
        return np.stack(
            [
                self._embedder.embed(y[int(s.start * sr) : int(s.end * sr)], sr)
                for s in segments
            ]
        )

    # ── internals ────────────────────────────────────────────────────────
    def _absorb_short_runs(self, items: List[dict], options: DiarizationOptions) -> List[dict]:
        """
        Folds runs too short to be a real turn into the run before them.

        "Too short" is not on its own a reason to relabel. A 200 ms "yeah" from
        the other person is a short run *and* a genuine speaker change, and the
        previous implementation discarded its label and its embedding together,
        so an interjection was silently relabelled to whoever spoke before it.
        The run is only absorbed when its embedding actually looks like the
        previous speaker; otherwise it is left standing as its own short turn,
        which is what puts "avunu" back on the right lane.
        """
        cleaned: List[dict] = []
        for item in items:
            duration = item["end"] - item["start"]
            if not cleaned or duration >= options.min_turn_duration:
                cleaned.append(item)
                continue

            prev = cleaned[-1]
            similarity = _cosine(prev["emb"], item["emb"])
            if similarity >= options.short_turn_similarity:
                prev["end"] = max(prev["end"], item["end"])
                prev["emb"] = item["emb"]
            else:
                cleaned.append(item)
        return cleaned

    @staticmethod
    def _merge_same_label_runs(cleaned: List[dict]) -> List[dict]:
        """Collapses adjacent runs the clustering already gave the same label."""
        merged: List[dict] = []
        for item in cleaned:
            if merged and merged[-1]["label"] == item["label"]:
                previous = merged[-1]
                previous["end"] = max(previous["end"], item["end"])
                previous["emb"] = item["emb"]
            else:
                merged.append(item)
        return merged

    def _split_long_regions(
        self,
        y: np.ndarray,
        sr: int,
        regions: List[Tuple[float, float]],
        options: DiarizationOptions,
    ) -> List[Tuple[float, float]]:
        """Splits regions longer than max_segment_duration at the strongest speaker change."""
        out: List[Tuple[float, float]] = []
        for start, end in regions:
            if end - start <= options.max_segment_duration:
                out.append((start, end))
            else:
                out.extend(self._split_by_speaker_change(y, sr, start, end))
        return out

    def _split_by_speaker_change(
        self, y: np.ndarray, sr: int, start: float, end: float
    ) -> List[Tuple[float, float]]:
        win = int(CHANGE_WINDOW_SEC * sr)
        hop = int(CHANGE_HOP_SEC * sr)
        span = int((end - start) * sr)
        offsets = list(range(0, max(1, span - win + 1), hop))
        if len(offsets) < 2:
            return [(start, end)]

        base = int(start * sr)
        mat = np.stack([self._embedder.embed(y[base + o : base + o + win], sr) for o in offsets])
        normed = mat / np.maximum(np.linalg.norm(mat, axis=1, keepdims=True), 1e-8)
        similarity = np.sum(normed[:-1] * normed[1:], axis=1)

        cut = int(np.argmin(similarity))
        boundary = start + (offsets[cut + 1] + win / 2.0) / float(sr)
        if boundary - start < MIN_SPLIT_SIDE_SEC or end - boundary < MIN_SPLIT_SIDE_SEC:
            return [(start, end)]
        return self._split_by_speaker_change(y, sr, start, boundary) + self._split_by_speaker_change(
            y, sr, boundary, end
        )

    def _to_segments(
        self,
        regions: List[Tuple[float, float]],
        embeddings: np.ndarray,
        labels: np.ndarray,
        options: DiarizationOptions,
        duration: float,
    ) -> List[DiarizationSegment]:
        items = [
            {"start": s, "end": e, "label": int(labels[i]), "emb": embeddings[i]}
            for i, (s, e) in enumerate(regions)
        ]

        cleaned: List[dict] = self._absorb_short_runs(items, options)
        cleaned = self._merge_same_label_runs(cleaned)

        # Stable numbering by first appearance: "speaker_0" is the first voice heard.
        order: List[int] = []
        for item in cleaned:
            if item["label"] not in order:
                order.append(item["label"])
        remap = {label: f"speaker_{i}" for i, label in enumerate(order)}

        centroids: dict = {}
        for label in order:
            members = [it["emb"] for it in cleaned if it["label"] == label]
            centroid = np.mean(np.stack(members), axis=0)
            norm = float(np.linalg.norm(centroid))
            centroids[label] = centroid / norm if norm > 1e-8 else centroid

        segments: List[DiarizationSegment] = []
        for item in cleaned:
            sim = float(np.dot(item["emb"], centroids[item["label"]]))
            start = round(max(0.0, item["start"]), 3)
            end = round(min(item["end"], duration), 3)
            if end - start <= 0.05:
                continue
            segments.append(
                DiarizationSegment(
                    speaker_id=remap[item["label"]],
                    start=start,
                    end=end,
                    confidence=round(min(0.99, max(0.5, (sim + 1.0) / 2.0)), 3),
                )
            )
        return segments


class LocalDiarizationStream(DiarizationStream):
    def __init__(self, options: DiarizationOptions):
        self.options = options
        self.closed = False

    async def push_audio(self, frame: AudioFrame) -> None:
        pass

    async def get_results(self):
        return
        yield  # pragma: no cover - keeps this an async generator

    async def close(self) -> None:
        self.closed = True


class LocalDiarizationProvider(DiarizationProvider):
    """
    CPU speaker diarisation used when no remote Nemotron endpoint is configured.

    Wraps :class:`LocalSpeakerDiarizer` behind the same ``AudioInput`` contract as
    the remote Nemotron provider so the pipeline is provider-agnostic.
    """

    def __init__(self, preprocessor=None, diarizer: Optional[LocalSpeakerDiarizer] = None):
        self.preprocessor = preprocessor
        self.diarizer = diarizer or LocalSpeakerDiarizer()

    async def process_file(self, audio: AudioInput, options: DiarizationOptions) -> DiarizationResult:
        started = time.time()
        y, sr = self._load_mono(audio)
        duration = (
            audio.metadata.duration_sec if audio.metadata else (len(y) / float(sr) if sr else 0.0)
        )

        if y is None or len(y) == 0:
            return DiarizationResult(
                segments=[],
                speakers=[],
                method="acoustic",
                metadata={"reason": "audio could not be decoded"},
                latency_sec=round(time.time() - started, 3),
            )

        result = self.diarizer.diarize(y, sr, options, duration=duration)
        result.latency_sec = round(time.time() - started, 3)
        return result

    async def start_stream(self, options: DiarizationOptions) -> DiarizationStream:
        return LocalDiarizationStream(options)

    # ── audio ────────────────────────────────────────────────────────────
    def _load_mono(self, audio: AudioInput) -> Tuple[Optional[np.ndarray], int]:
        from ...pipeline.audio_preprocessor import preprocessor as shared_preprocessor

        pre = self.preprocessor or shared_preprocessor
        source = audio
        if not (audio.file_path and os.path.exists(audio.file_path)) and audio.raw_bytes:
            import tempfile

            tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp.write(audio.raw_bytes)
            tmp.close()
            source = AudioInput(file_path=tmp.name, metadata=audio.metadata)

        y = pre.load_audio(source)
        if len(y) == 0:
            return None, pre.target_sample_rate

        max_val = float(np.max(np.abs(y)))
        if max_val > 1.0:
            y = y / max_val
        return y.astype(np.float32), pre.target_sample_rate
