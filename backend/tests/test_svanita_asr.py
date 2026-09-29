"""Svanita 0.6B transcription behaviour on real Telugu / Telugu-English audio."""
import pytest
import soundfile as sf

from backend.models.asr import ASRMode, ASROptions
from backend.models.audio import AudioInput
from backend.providers.asr.svanita import (
    SvanitaParakeetProvider,
    detect_output_language,
    resolve_script,
)

from .conftest_helpers import (
    EXPECTED_LATIN_WORDS,
    FIXTURE_PATH,
    has_telugu,
    latin_words,
    requires_fixture,
)


def test_script_lock_is_applied_only_for_known_languages():
    assert resolve_script("te-IN") == "telugu"
    assert resolve_script("te") == "telugu"
    assert resolve_script("hi-IN") == "hindi"
    # Auto-detect must not lock the decoder onto an Indic script.
    assert resolve_script("unknown") is None
    assert resolve_script("") is None
    assert resolve_script("en-IN") is None
    assert resolve_script(None) is None


def test_language_is_reported_from_the_script_actually_produced():
    assert detect_output_language("నమస్కారం")[0] == "te-IN"
    assert detect_output_language("documents submit")[0] == "en-IN"
    assert detect_output_language("मिलिएगा")[0] == "hi-IN"
    assert detect_output_language("home loan కావాలి")[0] == "te-IN"
    assert detect_output_language("")[0] is None


@requires_fixture
@pytest.mark.asyncio
async def test_telugu_audio_transcribes_into_telugu_script():
    provider = SvanitaParakeetProvider()
    result = await provider.transcribe_file(
        AudioInput(file_path=str(FIXTURE_PATH)),
        ASROptions(mode=ASRMode.CODEMIXED, language_code="te-IN"),
    )

    recording_seconds = sf.info(str(FIXTURE_PATH)).duration
    assert result.tokens, "Svanita produced no word tokens"
    assert has_telugu(result.transcript), "Telugu audio must not be forced into Latin script"
    assert all(t.end > t.start for t in result.tokens), "every token needs a real end time"
    assert result.tokens[-1].end <= recording_seconds + 0.05, (
        f"timestamps must stay inside the {recording_seconds:.2f}s recording"
    )
    assert result.latency_sec > 0


@requires_fixture
@pytest.mark.asyncio
async def test_code_mixed_english_stays_in_latin_script():
    provider = SvanitaParakeetProvider()
    result = await provider.transcribe_file(
        AudioInput(file_path=str(FIXTURE_PATH)),
        ASROptions(mode=ASRMode.CODEMIXED, language_code="te-IN"),
    )

    found = latin_words(result.transcript)
    assert found & EXPECTED_LATIN_WORDS, (
        f"English spoken inside Telugu must be written as English; got {sorted(found)}"
    )
    # Those words must not also be transliterated into Telugu script.
    for word in sorted(found & EXPECTED_LATIN_WORDS):
        assert not has_telugu(word), f"English word {word!r} was written in Telugu script"


@requires_fixture
@pytest.mark.asyncio
async def test_hindi_words_do_not_leak_into_telugu_output():
    provider = SvanitaParakeetProvider()
    result = await provider.transcribe_file(
        AudioInput(file_path=str(FIXTURE_PATH)),
        ASROptions(mode=ASRMode.CODEMIXED, language_code="te-IN"),
    )
    assert not any("\u0900" <= c <= "\u097F" for c in result.transcript), (
        "the Telugu script lock must remove Devanagari vocabulary pieces"
    )


@requires_fixture
@pytest.mark.asyncio
async def test_word_timestamps_track_speech_positions():
    provider = SvanitaParakeetProvider()
    result = await provider.transcribe_file(
        AudioInput(file_path=str(FIXTURE_PATH)),
        ASROptions(mode=ASRMode.CODEMIXED, language_code="te-IN"),
    )
    starts = [t.start for t in result.tokens]
    assert starts == sorted(starts), "tokens must come back in chronological order"
    # Tokens should span the whole recording, not bunch into the first second.
    assert result.tokens[-1].end > 20.0
    assert result.tokens[0].start < 2.0


@requires_fixture
@pytest.mark.asyncio
async def test_transcribing_an_interval_returns_only_that_window():
    provider = SvanitaParakeetProvider()
    start, end = 10.5, 15.0
    result = await provider.transcribe_interval(
        str(FIXTURE_PATH), start, end, ASROptions(mode=ASRMode.CODEMIXED, language_code="te-IN")
    )

    assert result.tokens, "the interval contains speech and must produce tokens"
    assert all(t.start >= start - 0.01 and t.end <= end + 0.01 for t in result.tokens), (
        "interval timestamps must be rebased onto the requested window"
    )
    assert all(t.end > t.start for t in result.tokens)


@requires_fixture
@pytest.mark.asyncio
async def test_missing_audio_is_reported_not_fabricated():
    provider = SvanitaParakeetProvider()
    with pytest.raises(ValueError):
        await provider.transcribe_interval(
            "does-not-exist.wav", 0.0, 1.0, ASROptions(language_code="te-IN")
        )


def test_streaming_is_refused_rather_than_faked():
    import asyncio

    provider = SvanitaParakeetProvider()
    with pytest.raises(NotImplementedError):
        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            provider.start_stream(ASROptions(language_code="te-IN"))
        )
