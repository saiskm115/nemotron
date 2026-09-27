import numpy as np
import pytest
import soundfile as sf
from backend.models.session import Session, SessionSettings
from backend.models.audio import AudioInput
from backend.pipeline.offline_pipeline import OfflinePipeline

@pytest.mark.asyncio
async def test_offline_pipeline_end_to_end(tmp_path):
    # Create 4 second synthetic test audio file
    sr = 16000
    t = np.linspace(0, 4.0, int(sr * 4.0), endpoint=False)
    sig = (0.3 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    test_audio_file = tmp_path / "meeting_sample.wav"
    sf.write(str(test_audio_file), sig, sr)

    session = Session(
        id="sess_integration_test",
        title="Integration Test Session",
        settings=SessionSettings(
            asr_mode="codemix",
            auto_translate=True
        )
    )

    storage_dir = tmp_path / "storage_sess"
    storage_dir.mkdir(parents=True, exist_ok=True)

    pipeline = OfflinePipeline()
    updated_session = await pipeline.run(session, str(test_audio_file), storage_dir)

    assert updated_session.processing_status == "complete"
    assert updated_session.duration > 0
    assert len(updated_session.turns) > 0
    assert len(updated_session.speakers) > 0
    assert "observability" in updated_session.metadata
    assert updated_session.metadata["observability"]["turn_count"] == len(updated_session.turns)
    
    # Check that raw outputs were preserved on disk (Section 13)
    raw_dir = storage_dir / "raw"
    assert (raw_dir / "diarization.json").exists()
    assert (raw_dir / "asr.json").exists()

    # Check that translations were populated
    assert any(t.translated_text for t in updated_session.turns)
