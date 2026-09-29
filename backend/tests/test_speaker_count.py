"""
Speaker-count estimation and over-split correction.

The regression these guard: a two-voice call coming out of diarisation as four
speakers. A power-set backend will activate every class it owns if the audio gives
it half a chance, and without a count estimate each phantom label becomes a
permanent timeline lane.
"""
import numpy as np
import pytest

from backend.models.diarization import DiarizationSegment
from backend.providers.diarization.speaker_count import (
    estimate_and_merge,
    estimate_speaker_count,
    scoring_sample,
)

DIM = 64


def _embeddings(count: int, offset: np.ndarray, jitter: float = 0.35, seed: int = 0) -> np.ndarray:
    """Unit-length embeddings scattered around one cluster centre."""
    rng = np.random.default_rng(seed)
    raw = rng.normal(size=(count, DIM)) * jitter + offset
    return raw / np.linalg.norm(raw, axis=1, keepdims=True)


def _centre(index: int, strength: float = 6.0) -> np.ndarray:
    vector = np.zeros(DIM)
    vector[index] = strength
    return vector


def _segments(labels, step: float = 1.5):
    out = []
    for i, label in enumerate(labels):
        start = round(i * step, 3)
        out.append(
            DiarizationSegment(speaker_id=f"speaker_{label}", start=start, end=round(start + step, 3))
        )
    return out


# ── The count itself ───────────────────────────────────────────────────
def test_one_voice_is_reported_as_one_speaker():
    embeddings = _embeddings(20, np.zeros(DIM))
    count, _scores = estimate_speaker_count(embeddings, max_speakers=8)
    assert count == 1


def test_two_voices_are_reported_as_two_speakers():
    embeddings = np.vstack([_embeddings(12, _centre(0)), _embeddings(12, _centre(1), seed=1)])
    count, _scores = estimate_speaker_count(embeddings, max_speakers=8)
    assert count == 2


def test_three_and_four_voices_are_reported_correctly():
    three = np.vstack([_embeddings(10, _centre(i), seed=i) for i in range(3)])
    four = np.vstack([_embeddings(10, _centre(i), seed=i) for i in range(4)])
    assert estimate_speaker_count(three, max_speakers=8)[0] == 3
    assert estimate_speaker_count(four, max_speakers=8)[0] == 4


# ── The reported bug ───────────────────────────────────────────────────
def test_two_voice_call_split_into_four_labels_collapses_to_two_speakers():
    """
    A backend already labelled a two-person recording speaker_0..speaker_3. The
    embeddings say two voices. The published result must be two speakers.
    """
    labels = [0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3]
    voice_of_label = {0: 0, 1: 1, 2: 0, 3: 1}  # two real voices, four labels
    segments = _segments(labels)
    embeddings = np.vstack(
        [_embeddings(1, _centre(voice_of_label[label]), jitter=0.3, seed=i)[0] for i, label in enumerate(labels)]
    )

    merged, count, scores = estimate_and_merge(segments, embeddings, max_speakers=8)

    assert count == 2, f"expected 2 speakers, got {count}"
    assert sorted({s.speaker_id for s in merged}) == ["speaker_0", "speaker_1"]
    # Every original segment survives, in time order.
    assert len(merged) == len(segments)
    assert [s.start for s in merged] == sorted(s.start for s in segments)
    assert scores, "the score trace is kept so a surprising count can be explained"


def test_segments_are_renumbered_by_first_appearance():
    # Speaker "speaker_2" is the first voice actually heard, so it becomes speaker_0.
    segments = _segments([2, 2, 1, 1, 2])
    embeddings = np.vstack(
        [_embeddings(1, _centre(0 if label == 2 else 1), jitter=0.3, seed=i)[0] for i, label in enumerate([2, 2, 1, 1, 2])]
    )
    merged, _count, _scores = estimate_and_merge(segments, embeddings, max_speakers=8)
    assert merged[0].speaker_id == "speaker_0"
    assert {s.speaker_id for s in merged} == {"speaker_0", "speaker_1"}


def test_overlap_speakers_are_remapped_with_their_segment():
    """
    Three real voices, four backend labels: speaker_0 and speaker_3 are the same
    person. The first segment genuinely overlaps speaker_1, and that reference must
    survive the merge while the merged-away label disappears.
    """
    segments = [
        DiarizationSegment(speaker_id="speaker_0", start=0.0, end=2.0, is_overlap=True,
                           overlap_speakers=["speaker_1"]),
        DiarizationSegment(speaker_id="speaker_1", start=0.0, end=2.0),
        DiarizationSegment(speaker_id="speaker_2", start=3.0, end=5.0),
        DiarizationSegment(speaker_id="speaker_3", start=6.0, end=8.0),
    ]
    embeddings = np.vstack([
        _embeddings(1, _centre(0), jitter=0.3, seed=0)[0],  # speaker_0 -> voice A
        _embeddings(1, _centre(1), jitter=0.3, seed=1)[0],  # speaker_1 -> voice B
        _embeddings(1, _centre(2), jitter=0.3, seed=2)[0],  # speaker_2 -> voice C
        _embeddings(1, _centre(0), jitter=0.3, seed=3)[0],  # speaker_3 -> voice A again
    ])
    merged, count, _scores = estimate_and_merge(segments, embeddings, max_speakers=8)

    assert count == 3
    overlapped = next(s for s in merged if s.is_overlap)
    assert overlapped.overlap_speakers == ["speaker_1"], "the real overlap must survive"
    assert overlapped.speaker_id not in overlapped.overlap_speakers


def test_overlap_is_dropped_when_the_other_voice_was_merged_away():
    """Two concurrent labels that turn out to be one voice are not an overlap."""
    segments = [
        DiarizationSegment(speaker_id="speaker_0", start=0.0, end=2.0, is_overlap=True,
                           overlap_speakers=["speaker_1"]),
        DiarizationSegment(speaker_id="speaker_1", start=0.0, end=2.0),
    ]
    embeddings = np.vstack([
        _embeddings(1, _centre(0), jitter=0.2, seed=0)[0],
        _embeddings(1, _centre(0), jitter=0.2, seed=1)[0],
    ])
    merged, count, _scores = estimate_and_merge(segments, embeddings, max_speakers=8)

    assert count == 1
    assert all(not s.is_overlap for s in merged)
    assert all(s.overlap_speakers == [] for s in merged)


# ── Bounds and guards ──────────────────────────────────────────────────
def test_max_speakers_is_never_exceeded():
    embeddings = np.vstack([_embeddings(10, _centre(i), seed=i) for i in range(6)])
    count, _scores = estimate_speaker_count(embeddings, max_speakers=3)
    assert count <= 3


def test_min_speakers_is_never_undercut():
    embeddings = _embeddings(20, np.zeros(DIM))
    count, _scores = estimate_speaker_count(embeddings, max_speakers=8, min_speakers=2)
    assert count >= 2


def test_too_few_segments_keeps_what_it_was_given():
    embeddings = np.vstack([_embeddings(1, _centre(0)), _embeddings(1, _centre(1))])
    count, _scores = estimate_speaker_count(embeddings, max_speakers=8)
    assert count == 1  # not enough evidence to claim anything


def test_mismatched_embedding_count_is_a_no_op():
    segments = _segments([0, 1, 0])
    merged, count, _scores = estimate_and_merge(segments, np.zeros((2, DIM)), max_speakers=8)
    assert merged == segments
    assert count == 2


def test_empty_input_is_handled():
    assert estimate_speaker_count(np.zeros((0, DIM)), max_speakers=8)[0] == 1
    assert estimate_and_merge([], np.zeros((0, DIM)), max_speakers=8) == ([], 0, {})


def test_scoring_sample_is_bounded_and_deterministic():
    embeddings = np.vstack([_embeddings(25, _centre(i % 4), seed=i) for i in range(16)])
    durations = [1.0] * embeddings.shape[0]
    first = scoring_sample(embeddings, durations)
    second = scoring_sample(embeddings, durations)

    assert embeddings.shape[0] > 240
    assert first.size <= 240
    assert np.array_equal(first, second), "the same file must always give the same answer"
    assert np.array_equal(first, np.sort(first)), "sample must stay in time order"
    # The estimate still works on the sample.
    assert estimate_speaker_count(embeddings[first], max_speakers=8)[0] == 4


@pytest.mark.parametrize("expected", [1, 2, 3, 4])
def test_count_is_stable_across_embedding_noise(expected):
    """Extra intra-speaker spread must not invent speakers or hide real ones."""
    embeddings = np.vstack([_embeddings(12, _centre(i), jitter=0.25, seed=i) for i in range(expected)])
    assert estimate_speaker_count(embeddings, max_speakers=8)[0] == expected
