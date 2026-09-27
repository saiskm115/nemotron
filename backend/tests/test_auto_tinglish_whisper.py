import pytest
from backend.models.audio import AudioInput, AudioMetadata
from backend.models.asr import ASROptions, ASRMode
from backend.providers.asr.auto_tinglish_whisper import AutoTinglishWhisperProvider

@pytest.mark.asyncio
async def test_auto_tinglish_whisper_transcription():
    provider = AutoTinglishWhisperProvider(model_size_or_path="small", compute_type="int8")
    audio = AudioInput(
        metadata=AudioMetadata(
            duration_sec=8.0,
            sample_rate=16000,
            channels=1
        )
    )
    options = ASROptions(
        mode=ASRMode.CODEMIXED,
        language_code="te-IN"
    )

    result = await provider.transcribe_file(audio, options)

    assert result.transcript != ""
    assert len(result.tokens) > 0
    assert len(result.chunks) > 0
    assert result.language_code == "te-IN"

    # Verify Telugu and English code mixing in tokens
    token_langs = [t.language for t in result.tokens]
    assert "te" in token_langs
    assert "en" in token_langs

    # Verify word timestamps
    assert all(t.start < t.end for t in result.tokens)
