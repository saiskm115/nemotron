"""
Speaker-count estimation and over-split correction.

Every diarisation backend has a ceiling, not a promise. Sortformer is a power-set
model that will happily activate all four of its classes for a two-voice call, a
remote endpoint will echo whatever cluster count it felt like returning, and
embedding clustering with a generous cosine threshold will happily split one
person across two clusters when their handset, channel balance or mood moves the
embedding. Left alone, every one of those phantom labels becomes a permanent
timeline lane, and a two-party call renders as a four-party call.

This module is the single place that decides how many voices the recording
actually contains, and it works from measured evidence rather than from whatever
label the backend happened to emit.

The criterion is the relative-drop elbow test, a standard way to recover the
number of clusters when it is unknown. Let ``S(k)`` be the within-cluster scatter
when the segments are cut into ``k`` clusters, and let the cut that produces the
k-th cluster remove ``d(k) = S(k-1) - S(k)`` of it:

    cut      = max(ELBOW_RATIO * max(d), MIN_ABS_FRACTION * S(1))
    k*       = the largest k whose d(k) clears the cut, or 1 if none do

Two distinct voices collapse the scatter hard on the first cut and then leave
nothing for the rest, so the first cut clears the bar and nothing after it does.
Cutting one voice a second time only rearranges noise, so its drop stays under
the bar. The ``MIN_ABS_FRACTION`` term is what stops a single-voice recording
from being carved up: on one voice every cut removes about the same modest
amount, so no cut ever explains a quarter of the total scatter and the answer
stays at one speaker.

A two-party call that the backend split four ways therefore lands on k=2, and the
phantom clusters are merged instead of being published.
"""
import logging
from typing import Dict, List, Sequence, Tuple

import numpy as np

from ...models.diarization import DiarizationSegment

logger = logging.getLogger(__name__)

# Above this many segments the scatter test runs on a duration-weighted sample.
# Speaker count is a property of the voices, not of how many turn boundaries
# exist, so a few seconds of each segment carries the same evidence as all of it.
MAX_SEGMENTS_FOR_SCORING = 240
# Below this there is not enough evidence to estimate anything; keep what we have.
MIN_SEGMENTS_FOR_ESTIMATION = 3
EPS = 1e-9
SAMPLE_SEED = 1234
# A cut has to remove at least this share of the largest cut to count, so one
# dominant boundary is not diluted by a long tail of negligible ones.
ELBOW_RATIO = 0.35
# ...and it has to explain at least this share of the *total* scatter, which is
# what keeps a single voice from being carved into every cluster on offer.
MIN_ABS_FRACTION = 0.25


def cosine_distance_matrix(embeddings: np.ndarray) -> np.ndarray:
    """Pairwise cosine distance between L2-normalised rows."""
    normed = embeddings / np.maximum(np.linalg.norm(embeddings, axis=1, keepdims=True), 1e-8)
    return 1.0 - np.clip(normed @ normed.T, -1.0, 1.0)


def cluster_to_k(embeddings: np.ndarray, k: int) -> np.ndarray:
    """
    Assigns one label per embedding using average-linkage cosine clustering.

    Forcing exactly ``k`` clusters is what turns an over-split labelling back into
    the number of voices the recording actually contains.
    """
    n = embeddings.shape[0]
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    k = max(1, min(int(k), n))
    if k == 1:
        return np.zeros(n, dtype=np.int64)

    try:
        from sklearn.cluster import AgglomerativeClustering

        return np.asarray(
            AgglomerativeClustering(
                n_clusters=k, metric="cosine", linkage="average"
            ).fit_predict(embeddings),
            dtype=np.int64,
        )
    except Exception as exc:  # noqa: BLE001 - degrade to the built-in implementation
        logger.info("scikit-learn clustering unavailable (%s); using built-in AHC", exc)
        return _average_linkage(embeddings, k)


def _average_linkage(embeddings: np.ndarray, k: int) -> np.ndarray:
    """Average-linkage agglomeration to exactly ``k`` clusters, no sklearn needed."""
    n = embeddings.shape[0]
    distances = cosine_distance_matrix(embeddings)
    active: Dict[int, List[int]] = {i: [i] for i in range(n)}

    while len(active) > k:
        keys = sorted(active)
        best, pair = float("inf"), None
        for i, a in enumerate(keys):
            for b in keys[i + 1 :]:
                d = float(distances[np.ix_(active[a], active[b])].mean())
                if d < best:
                    best, pair = d, (a, b)
        if pair is None:
            break
        a, b = pair
        active[a].extend(active[b])
        del active[b]

    lookup = {cluster_id: idx for idx, cluster_id in enumerate(sorted(active))}
    return np.asarray([lookup[min(active[i])] for i in range(n)], dtype=np.int64)


def _within_cluster_scatter(embeddings: np.ndarray, labels: np.ndarray) -> float:
    """Sum of squared distances of each row to its cluster centroid."""
    scatter = 0.0
    for label in np.unique(labels):
        members = embeddings[labels == label]
        if members.shape[0] <= 1:
            continue
        centroid = members.mean(axis=0, keepdims=True)
        scatter += float(((members - centroid) ** 2).sum())
    return scatter


def scoring_sample(embeddings: np.ndarray, durations: Sequence[float]) -> np.ndarray:
    """
    Row indices of the duration-weighted subsample the scatter test runs on.

    Deterministic for a given file, so the same audio always yields the same
    speaker count.
    """
    n = embeddings.shape[0]
    if n <= MAX_SEGMENTS_FOR_SCORING:
        return np.arange(n, dtype=np.int64)

    weights = np.asarray(durations, dtype=np.float64)
    if not np.all(np.isfinite(weights)) or weights.sum() <= 0:
        weights = np.ones(n, dtype=np.float64)
    rng = np.random.default_rng(SAMPLE_SEED)
    picked = rng.choice(n, size=MAX_SEGMENTS_FOR_SCORING, replace=False, p=weights / weights.sum())
    return np.sort(picked)


def estimate_speaker_count(
    embeddings: np.ndarray,
    max_speakers: int = 8,
    min_speakers: int = 1,
) -> Tuple[int, Dict[str, float]]:
    """
    Estimates how many distinct voices the embeddings contain.

    Returns the chosen count and the score trace, which is kept in the diarisation
    metadata so a surprising speaker count can be explained after the fact instead
    of being guessed at.
    """
    n = embeddings.shape[0]
    scores: Dict[str, float] = {}

    if n < MIN_SEGMENTS_FOR_ESTIMATION:
        return max(1, min(n, max(int(min_speakers), 1))), scores

    upper = max(1, min(int(max_speakers), n))
    lower = max(1, min(int(min_speakers), upper))
    if upper == 1:
        return 1, {"1": 1.0}

    scatters = {k: _within_cluster_scatter(embeddings, cluster_to_k(embeddings, k)) for k in range(1, upper + 1)}

    # How much scatter each additional cluster removes. Agglomerative clustering
    # always reduces scatter, so the magnitude of the reduction is the only
    # evidence that a particular cut found a real boundary.
    drops = {k: scatters[k - 1] - scatters[k] for k in range(2, upper + 1)}
    largest = max(drops.values())
    if largest <= EPS:
        return max(1, min(lower, upper)), {"1": 1.0}

    cut = max(ELBOW_RATIO * largest, MIN_ABS_FRACTION * scatters[1])
    accepted = [k for k in range(2, upper + 1) if drops[k] >= cut]
    best_k = max(accepted) if accepted else 1

    # A caller that insists on a minimum ("this file definitely has two handsets")
    # is never overruled; a caller that sets a ceiling is never exceeded.
    return max(lower, min(best_k, upper)), {str(k): round(v, 4) for k, v in drops.items()}


def estimate_and_merge(
    segments: List[DiarizationSegment],
    embeddings: np.ndarray,
    max_speakers: int,
    min_speakers: int = 1,
) -> Tuple[List[DiarizationSegment], int, Dict[str, float]]:
    """
    Re-clusters diarised segments to the number of voices actually present.

    ``embeddings`` must hold one row per segment, in the same order. Returns the
    relabelled segments, the resulting speaker count, and the score trace.
    """
    if not segments or embeddings.shape[0] != len(segments):
        return segments, len({s.speaker_id for s in segments}), {}

    durations = [max(0.0, s.end - s.start) for s in segments]
    sample_rows = scoring_sample(embeddings, durations)
    count, scores = estimate_speaker_count(
        embeddings[sample_rows], max_speakers=max_speakers, min_speakers=min_speakers
    )

    # The chosen count is applied to *every* segment, not just the scored sample,
    # so a short backchannel is re-clustered on the same footing as a long turn.
    labels = cluster_to_k(embeddings, count)

    # Renumber by first appearance so ``speaker_0`` is the first voice heard,
    # matching the local pipeline's numbering and keeping the UI stable.
    order: List[int] = []
    for label in labels:
        if int(label) not in order:
            order.append(int(label))
    name_for_cluster = {label: f"speaker_{position}" for position, label in enumerate(order)}

    # Original speaker label -> the name that voice now carries. Overlap
    # references are stored as original labels, so they need this map, not the
    # cluster-index map.
    by_original: Dict[str, str] = {}
    for segment, label in zip(segments, labels):
        by_original.setdefault(segment.speaker_id, name_for_cluster[int(label)])

    merged = []
    for segment, label in zip(segments, labels):
        speaker = name_for_cluster[int(label)]
        # Two labels the backend marked as overlapping can turn out to be the same
        # voice, which would leave the segment claiming to overlap with itself.
        others = sorted({
            by_original.get(name, name)
            for name in segment.overlap_speakers
            if by_original.get(name, name) != speaker
        })
        merged.append(
            DiarizationSegment(
                speaker_id=speaker,
                start=segment.start,
                end=segment.end,
                confidence=segment.confidence,
                is_overlap=segment.is_overlap and bool(others),
                overlap_speakers=others,
            )
        )
    merged.sort(key=lambda s: (s.start, s.end))
    return merged, len(order), scores
