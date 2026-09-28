import pytest
from backend.models.audio import AudioInput, AudioMetadata
from backend.models.asr import ASROptions, ASRMode
from backend.providers.asr.auto_tinglish_whisper import AutoTinglishWhisperProvider

@pytest.mark.asyncio
async def test_unknown_language_defaults_to_telugu():
    provider = AutoTinglishWhisperProvider()
    audio = AudioInput(
        metadata=AudioMetadata(
            duration_sec=8.0,
            sample_rate=16000,
            channels=1
        )
    )
    # Options specifying unknown language (user left it at default)
    options = ASROptions(
        mode=ASRMode.CODEMIXED,
        language_code="unknown"
    )

    result = await provider.transcribe_file(audio, options)

    assert result.language_code == "te-IN"
    assert any('\u0C00' <= char <= '\u0C7F' for char in result.transcript), (
        "Transcript must contain authentic Telugu Unicode script and not be forced into English"
    )

@pytest.mark.asyncio
async def test_telugu_code_mixed_contains_both_scripts():
    provider = AutoTinglishWhisperProvider()
    audio = AudioInput(
        metadata=AudioMetadata(
            duration_sec=16.0,
            sample_rate=16000,
            channels=1
        )
    )
    options = ASROptions(
        mode=ASRMode.CODEMIXED,
        language_code="te-IN"
    )

    result = await provider.transcribe_file(audio, options)

    assert result.language_code == "te-IN"
    # Ensure Telugu script is present
    has_telugu = any(any('\u0C00' <= c <= '\u0C7F' for c in t.text) for t in result.tokens)
    assert has_telugu, "Tokens must contain Telugu script"
    # Ensure English script is present in code-mixing
    has_english = any(any('a' <= c.lower() <= 'z' for c in t.text) for t in result.tokens)
    assert has_english, "Tokens must contain English script for Tinglish"
