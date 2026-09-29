"""
Rescue pass for short interjections the whole-file decode dropped.

The reported symptom: a user says "avunu", "yeah", "ah" -- 200-350 ms between two
longer turns -- and neither the diarisation nor the transcript shows it. The
offline pipeline runs the recogniser once over the whole file, which is right for
accuracy and speed but has one predictable blind spot: a short backchannel can be
swallowed, and one missing token removes the region entirely.
"""
import pytest

from backend.models.asr import ASRMode, ASROptions, ASRResult, ASRToken
from backend.models.diarization import DiarizationSegment
from backend.pipeline.backchannel_rescue import (
    CONTEXT_SEC,
    MAX_RESCUES,
    MAX_RESCUE_SEC,
    find_untranscribed_regions,
    rescue_backchannels,
)


def _token(start: float, end: float, text: str = "word") -> ASRToken:
    return ASRToken(id=f"t{start}", text=text, start=start, end=end, is_final=True)


# ── Region selection ───────────────────────────────────────────────────
def test_a_short_diarised_region_with_no_text_is_found():
    segments = [DiarizationSegment(speaker_id="speaker_0", start=1.0, end=1.3)]
    regions = find_untranscribed_regions(segments, [])

    assert len(regions) == 1
    start, end, speaker = regions[0]
    assert speaker == "speaker_0"
    # The region is padded with acoustic context on both sides.
    assert start == pytest.approx(1.0 - CONTEXT_SEC)
    assert end == pytest.approx(1.3 + CONTEXT_SEC)


def test_a_region_the_recogniser_already_covered_is_left_alone():
    segments = [DiarizationSegment(speaker_id="speaker_0", start=1.0, end=1.3)]
    regions = find_untranscribed_regions(segments, [_token(1.05, 1.25)])
    assert regions == []


def test_long_untranscribed_stretches_are_not_re_decoded():
    """A second full decode of a long gap is slow and adds nothing."""
    segments = [DiarizationSegment(speaker_id="speaker_0", start=0.0, end=MAX_RESCUE_SEC + 5)]
    assert find_untranscribed_regions(segments, []) == []


def test_sub_minimum_regions_are_ignored():
    segments = [DiarizationSegment(speaker_id="speaker_0", start=1.0, end=1.01)]
    assert find_untranscribed_regions(segments, []) == []


def test_regions_are_clamped_to_the_recording():
    segments = [DiarizationSegment(speaker_id="speaker_0", start=59.9, end=60.2)]
    regions = find_untranscribed_regions(segments, [], duration=60.0)
    assert regions and regions[0][1] <= 60.0


def test_nearby_regions_from_one_speaker_merge_into_one_decode():
    segments = [
        DiarizationSegment(speaker_id="speaker_0", start=1.0, end=1.2),
        DiarizationSegment(speaker_id="speaker_0", start=1.4, end=1.6),
    ]
    assert len(find_untranscribed_regions(segments, [])) == 1


def test_regions_from_different_speakers_stay_separate():
    segments = [
        DiarizationSegment(speaker_id="speaker_0", start=1.0, end=1.2),
        DiarizationSegment(speaker_id="speaker_1", start=1.25, end=1.4),
    ]
    assert len(find_untranscribed_regions(segments, [])) == 2


def test_the_number_of_rescues_is_capped():
    segments = [
        DiarizationSegment(speaker_id="speaker_0", start=i * 2.0, end=i * 2.0 + 0.2)
        for i in range(MAX_RESCUES + 20)
    ]
    assert len(find_untranscribed_regions(segments, [])) == MAX_RESCUES


def test_no_diarisation_means_nothing_to_rescue():
    assert find_untranscribed_regions([], []) == []


# ── The pass itself ────────────────────────────────────────────────────
class _StubProvider:
    """Records the intervals it was asked to decode and replies with fixed text."""

    def __init__(self, reply: str = "avunu", raises: Exception | None = None):
        self.calls: list[tuple[float, float]] = []
        self.reply = reply
        self.raises = raises

    async def transcribe_interval(self, path, start, end, options=None):
        self.calls.append((start, end))
        if self.raises:
            raise self.raises
        token = ASRToken(id="r1", text=self.reply, start=start, end=end, is_final=True)
        return ASRResult(transcript=self.reply, tokens=[token], chunks=[])


@pytest.mark.asyncio
async def test_a_recovered_backchannel_is_added_to_the_token_stream():
    segments = [DiarizationSegment(speaker_id="speaker_0", start=1.0, end=1.3)]
    provider = _StubProvider("avunu")
    original = [_token(0.0, 0.8, "hello")]

    tokens, rescued = await rescue_backchannels(
        provider, "audio.wav", segments, list(original), ASROptions(mode=ASRMode.CODEMIXED), duration=10.0
    )

    assert rescued == 1
    assert len(provider.calls) == 1
    assert [t.text for t in tokens] == ["hello", "avunu"], "recovered token joins the stream"
    assert tokens == sorted(tokens, key=lambda t: t.start), "stream stays in time order"


@pytest.mark.asyncio
async def test_a_region_that_decodes_to_nothing_changes_nothing():
    segments = [DiarizationSegment(speaker_id="speaker_0", start=1.0, end=1.3)]
    provider = _StubProvider(reply="")
    original = [_token(0.0, 0.8)]

    tokens, rescued = await rescue_backchannels(
        provider, "audio.wav", segments, original, ASROptions(), duration=10.0
    )

    assert rescued == 0
    assert tokens == original


@pytest.mark.asyncio
async def test_one_failing_region_does_not_abandon_the_rest():
    segments = [
        DiarizationSegment(speaker_id="speaker_0", start=1.0, end=1.2),
        DiarizationSegment(speaker_id="speaker_0", start=5.0, end=5.2),
    ]

    class Flaky(_StubProvider):
        async def transcribe_interval(self, path, start, end, options=None):
            if start < 2.0:
                raise RuntimeError("decoder hiccup")
            return await super().transcribe_interval(path, start, end, options)

    provider = Flaky("yeah")
    tokens, rescued = await rescue_backchannels(
        provider, "audio.wav", segments, [], ASROptions(), duration=10.0
    )

    assert rescued == 1
    assert [t.text for t in tokens] == ["yeah"]


@pytest.mark.asyncio
async def test_a_provider_that_cannot_decode_intervals_is_skipped_quietly():
    segments = [DiarizationSegment(speaker_id="speaker_0", start=1.0, end=1.3)]
    original = [_token(0.0, 0.8)]
    provider = _StubProvider(raises=NotImplementedError("offline only"))

    tokens, rescued = await rescue_backchannels(
        provider, "audio.wav", segments, original, ASROptions(), duration=10.0
    )

    assert rescued == 0
    assert tokens == original


@pytest.mark.asyncio
async def test_no_work_when_everything_was_already_transcribed():
    segments = [DiarizationSegment(speaker_id="speaker_0", start=1.0, end=1.3)]
    provider = _StubProvider()
    original = [_token(1.0, 1.3)]

    tokens, rescued = await rescue_backchannels(
        provider, "audio.wav", segments, original, ASROptions(), duration=10.0
    )

    assert rescued == 0
    assert provider.calls == [], "a fully covered file must not be re-decoded"
    assert tokens == original


# ── Alignment floor ────────────────────────────────────────────────────
class AlignedStub:
    def __init__(self, start: float, end: float):
        self.start = start
        self.end = end
        self.speaker_id = "speaker_0"
        self.is_speech_only = False


def test_a_substantial_uncovered_region_surfaces_as_speech_only():
    from backend.pipeline.alignment import AlignmentEngine

    segments = [DiarizationSegment(speaker_id="speaker_0", start=0.0, end=4.0)]
    units = AlignmentEngine()._uncovered_speech(segments, [AlignedStub(0.0, 1.0)])

    assert len(units) == 1
    assert units[0].start == pytest.approx(1.0)
    assert units[0].end == pytest.approx(4.0)
    assert units[0].is_speech_only
    assert units[0].speaker_id == "speaker_0"


def test_boundary_slivers_do_not_become_turns():
    """
    The edges of a diarisation segment are VAD padding and encoder frames, so a
    short sliver there is not evidence of anything.
    """
    from backend.pipeline.alignment import AlignmentEngine

    segments = [DiarizationSegment(speaker_id="speaker_0", start=0.0, end=2.4)]
    units = AlignmentEngine()._uncovered_speech(segments, [AlignedStub(0.2, 2.2)])
    assert units == []


def test_a_fully_untranscribed_segment_still_surfaces():
    """
    A backchannel the recogniser returned nothing for is a short segment with no
    text at all, and that is the case the timeline needs to show.
    """
    from backend.pipeline.alignment import AlignmentEngine

    segments = [DiarizationSegment(speaker_id="speaker_1", start=1.0, end=1.3)]
    units = AlignmentEngine()._uncovered_speech(segments, [])
    assert len(units) == 1
    assert units[0].is_speech_only and units[0].speaker_id == "speaker_1"


def test_the_floor_is_configurable():
    from backend.pipeline.alignment import AlignmentEngine

    segments = [DiarizationSegment(speaker_id="speaker_0", start=0.0, end=1.0)]
    # A 0.6s gap is above the 50%-of-segment coverage term, so on this segment the
    # absolute floor is what decides.
    assert AlignmentEngine(min_speech_only_duration=0.9)._uncovered_speech(segments, [AlignedStub(0.0, 0.4)]) == []
    assert len(AlignmentEngine(min_speech_only_duration=0.12)._uncovered_speech(segments, [AlignedStub(0.0, 0.4)])) == 1


def test_ordinary_pauses_are_not_turned_into_empty_turns():
    """
    A speech-only row carries no text, so a hesitation must not become one. This
    is why the real backchannel fix is the rescue pass, which measures the content
    of the region rather than guessing from its length.
    """
    from backend.pipeline.alignment import AlignmentEngine

    segments = [DiarizationSegment(speaker_id="speaker_0", start=0.0, end=5.0)]
    # Two words 600ms apart: a pause, not a missing interjection.
    units = AlignmentEngine()._uncovered_speech(segments, [AlignedStub(0.0, 2.0), AlignedStub(2.6, 5.0)])
    assert units == []
