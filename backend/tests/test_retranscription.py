import pytest
from backend.models.session import SessionCreate, SessionSettings
from backend.models.turn import Turn, TurnRetranscribeRequest
from backend.storage.session_store import session_store
from backend.providers.asr.auto_tinglish_whisper import AutoTinglishWhisperProvider
from backend.api.transcription import retranscribe_turn

@pytest.mark.asyncio
async def test_auto_tinglish_whisper_contracted_interval():
    provider = AutoTinglishWhisperProvider()
    # Contract Turn 1 from [0.20, 3.15] down to [0.20, 1.40]
    res = await provider.transcribe_interval(
        audio_file_path=None,
        start_time=0.20,
        end_time=1.40
    )
    assert res is not None
    assert "నేను" in res.transcript
    assert "meeting" in res.transcript
    assert "కి" in res.transcript
    # Ensure contracted words beyond 1.40s are not included
    assert "అవుతాను" not in res.transcript

@pytest.mark.asyncio
async def test_auto_tinglish_whisper_extended_interval():
    provider = AutoTinglishWhisperProvider()
    # Extend Turn 1 from [0.20, 3.15] up to [0.20, 4.60] to absorb the next words
    res = await provider.transcribe_interval(
        audio_file_path=None,
        start_time=0.20,
        end_time=4.60
    )
    assert res is not None
    assert "నేను" in res.transcript
    assert "late" in res.transcript
    assert "Okay," in res.transcript
    assert "problem." in res.transcript

@pytest.mark.asyncio
async def test_api_retranscribe_endpoint():
    # Setup test session
    sess_req = SessionCreate(
        title="Retranscription Test Session",
        audio_source="file",
        mode="offline",
        target_language="en-IN",
        settings=SessionSettings(
            asr_mode="codemix",
            primary_language="te-IN",
            target_language="en-IN",
            auto_translate=True
        )
    )
    session = session_store.create_session(sess_req)
    session.duration = 20.0

    # Add initial turn
    turn1 = Turn(
        id="turn_test_123",
        speaker_id="speaker_0",
        start=0.20,
        end=3.15,
        text="నేను meeting కి 10 minutes late అవుతాను.",
        translated_text="I will be 10 minutes late to the meeting.",
        confidence=0.95,
        status="final"
    )
    session.turns = [turn1]
    session_store.persist(session.id)

    # 1. Contract turn to [0.20, 1.40] and retranscribe
    contracted_req = TurnRetranscribeRequest(start=0.20, end=1.40)
    updated = await retranscribe_turn(session.id, "turn_test_123", contracted_req)

    assert updated.id == "turn_test_123"
    assert updated.start == 0.20
    assert updated.end == 1.40
    assert updated.status == "edited"
    assert updated.source == "user_edit"
    assert "నేను meeting కి" in updated.text
    assert "అవుతాను" not in updated.text

    # 2. Extend turn to [0.20, 4.60] and retranscribe
    extended_req = TurnRetranscribeRequest(start=0.20, end=4.60)
    re_extended = await retranscribe_turn(session.id, "turn_test_123", extended_req)

    assert re_extended.start == 0.20
    assert re_extended.end == 4.60
    assert "Okay," in re_extended.text
    assert "problem." in re_extended.text
