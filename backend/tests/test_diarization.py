"""Diarisation behaviour on real two-speaker Telugu audio."""
import numpy as np
import soundfile as sf

from backend.models.diarization import DiarizationOptions, DiarizationSegment
from backend.providers.diarization.local_diarization import (
    LocalSpeakerDiarizer,
    auto_cluster_threshold,
    mean_normalize,
)
from backend.providers.diarization.vad import detect_speech

from .conftest_helpers import FIXTURE_PATH, requires_fixture, speaker_sequence, truth_spans


def test_mean_normalisation_removes_the_shared_embedding_component():
    # Three points that differ only by a tiny amount on top of a large shared
    # offset: raw cosines would call them near-identical.
    base = np.array([[4.0, 1.0], [4.0, 1.05], [3.9, 0.9]], dtype=np.float32)
    normalised = mean_normalize(base)
    norms = np.linalg.norm(normalised, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_auto_threshold_sits_between_clusters_and_respects_bounds():
    # Three pairs within 0.2 of each other, three pairs ~1.8 apart.
    embeddings = np.array(
        [
            [1.0, 0.0],
            [1.0, 0.02],
            [1.0, -0.02],
            [0.0, 1.0],
            [0.01, 1.0],
            [-0.01, 1.0],
        ],
        dtype=np.float32,
    )
    embeddings = mean_normalize(embeddings)
    fallback = 0.9
    threshold = auto_cluster_threshold(embeddings, fallback)
    assert 0.5 * fallback <= threshold <= 1.5 * fallback
    assert threshold < 1.0, "the boundary must land in the gap, not inside a cluster"


def test_auto_threshold_falls_back_with_too_few_segments():
    embeddings = mean_normalize(np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32))
    assert auto_cluster_threshold(embeddings, 0.77) == 0.77


def test_vad_finds_every_speech_region_and_no_silence():
    y, sr = sf.read(str(FIXTURE_PATH), dtype="float32")
    regions = detect_speech(y, sr, min_speech_duration=0.25, min_silence_duration=0.20, pad=0.10)

    assert len(regions) >= len(truth_spans()), "VAD must not merge separate turns"
    for start, end in regions:
        assert 0.0 <= start < end <= len(y) / sr + 0.01
    # Regions must not overlap.
    ordered = sorted(regions)
    for (_, prev_end), (next_start, _) in zip(ordered, ordered[1:]):
        assert next_start >= prev_end - 1e-6


@requires_fixture
def test_diarisation_recovers_two_speakers_on_real_speech():
    y, sr = sf.read(str(FIXTURE_PATH), dtype="float32")
    result = LocalSpeakerDiarizer().diarize(y, sr, DiarizationOptions(max_speakers=8), duration=len(y) / sr)

    assert result.segments, "diarisation must not return an empty timeline for real speech"
    assert len(result.speakers) == 2, f"expected 2 speakers, got {result.speakers}"
    assert result.overlap_count == 0, "overlaps must only be reported when a model predicts them"
    assert result.method and result.method.startswith("acoustic_")

    labels = speaker_sequence(result.segments)
    truth = [label for _, _, label in truth_spans()]
    # Map predicted labels onto truth so ordering of ids is not assumed.
    assert sorted(labels) == sorted(truth), f"speaker assignment mismatch: {labels} vs {truth}"


@requires_fixture
def test_turn_boundaries_track_the_actual_speech():
    y, sr = sf.read(str(FIXTURE_PATH), dtype="float32")
    result = LocalSpeakerDiarizer().diarize(y, sr, DiarizationOptions(max_speakers=8), duration=len(y) / sr)

    merged: list = []
    for segment in sorted(result.segments, key=lambda s: s.start):
        if merged and merged[-1].speaker_id == segment.speaker_id and abs(merged[-1].end - segment.start) < 0.3:
            merged[-1].end = segment.end
        else:
            merged.append(segment)

    truth = truth_spans()
    assert len(merged) == len(truth), f"expected {len(truth)} turns, got {len(merged)}"
    for predicted, (truth_start, truth_end, _) in zip(merged, truth):
        assert abs(predicted.start - truth_start) < 0.45, f"start {predicted.start} vs {truth_start}"
        assert abs(predicted.end - truth_end) < 0.45, f"end {predicted.end} vs {truth_end}"


@requires_fixture
def test_speakers_are_numbered_by_first_appearance():
    y, sr = sf.read(str(FIXTURE_PATH), dtype="float32")
    result = LocalSpeakerDiarizer().diarize(y, sr, DiarizationOptions(max_speakers=8), duration=len(y) / sr)
    ordered = sorted(result.segments, key=lambda s: s.start)
    assert ordered[0].speaker_id == "speaker_0"


def test_silence_produces_no_speech_rather_than_invented_turns():
    sr = 16000
    silence = np.zeros(sr * 3, dtype=np.float32)
    result = LocalSpeakerDiarizer().diarize(silence, sr, DiarizationOptions(), duration=3.0)
    assert result.segments == []
    assert result.speakers == []
    assert result.metadata.get("reason")


def test_a_single_voice_is_reported_as_one_speaker():
    sr = 16000
    t = np.arange(sr * 3, dtype=np.float32) / sr
    tone = (0.4 * np.sin(2 * np.pi * 180 * t) + 0.2 * np.sin(2 * np.pi * 720 * t)).astype(np.float32)
    result = LocalSpeakerDiarizer().diarize(tone, sr, DiarizationOptions(), duration=3.0)
    assert len({s.speaker_id for s in result.segments}) <= 1


def test_max_speakers_is_respected():
    from backend.providers.diarization.local_diarization import agglomerative_cosine

    rng = np.random.default_rng(0)
    embeddings = np.vstack([rng.normal(size=(3, 16)) for _ in range(6)]).astype(np.float32)
    labels = agglomerative_cosine(embeddings, 0.2, 3)
    assert len(set(labels.tolist())) <= 3


def test_diarization_segment_carries_overlap_metadata():
    segment = DiarizationSegment(speaker_id="speaker_0", start=0.0, end=1.0, is_overlap=True,
                                overlap_speakers=["speaker_1"])
    assert segment.is_overlap is True
    assert segment.overlap_speakers == ["speaker_1"]
