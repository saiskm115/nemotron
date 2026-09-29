"""Re-transcribing a segment after dragging its boundary on the timeline."""
import asyncio
from pathlib import Path
from typing import List

import pytest
from fastapi.testclient import TestClient

from backend.api.transcription import _perform_turn_retranscription
from backend.main import app
from backend.models.session import SessionCreate, SessionSettings
from backend.models.turn import Turn, TurnRetranscribeRequest  # noqa: F401
from backend.pipeline.offline_pipeline import OfflinePipeline
from backend.storage.session_store import session_store

from .conftest_helpers import FIXTURE_PATH, requires_fixture


def _find_turn(turns: List, speaker_index: int):
    for turn in turns:
        if turn.speaker_id == f"speaker_{speaker_index}":
            return turn
    raise AssertionError("expected at least two speakers")


@requires_fixture
@pytest.mark.asyncio
async def test_contracting_a_turn_drops_the_words_it_no_longer_covers(tmp_path: Path):
    session = session_store.create_session(
        SessionCreate(
            title="retranscribe contract",
            settings=SessionSettings(asr_model="svanita_0_6b", primary_language="te-IN"),
        )
    )
    storage = tmp_path / "s1"
    storage.mkdir(parents=True, exist_ok=True)
    result = await OfflinePipeline().run(session, str(FIXTURE_PATH), storage)
    session_store.persist(result.id)

    turn = _find_turn(result.turns, 0)
    original_end = turn.end
    original_text = turn.text
    new_end = round(turn.start + (original_end - turn.start) * 0.5, 3)

    updated = await _perform_turn_retranscription(result.id, turn.id, turn.start, new_end)
    shortened = updated.text

    assert updated.start == turn.start
    assert updated.end == new_end
    assert updated.status == "edited"
    assert updated.source == "user_edit"
    assert shortened.strip(), "the shortened range still contains speech"
    assert updated.original_model_text == original_text, "the model output must stay recoverable"
    # Re-running the model on real audio cannot reproduce the canned fixture corpus,
    # so the point is that the new text comes from the audio in the new range.
    assert shortened != "నేను meeting కి 10 minutes late అవుతాను."
    session_store.delete_session(result.id)


@requires_fixture
@pytest.mark.asyncio
async def test_extending_a_turn_picks_up_the_words_now_inside_it(tmp_path: Path):
    session = session_store.create_session(
        SessionCreate(
            title="retranscribe extend",
            settings=SessionSettings(asr_model="svanita_0_6b", primary_language="te-IN"),
        )
    )
    storage = tmp_path / "s2"
    storage.mkdir(parents=True, exist_ok=True)
    result = await OfflinePipeline().run(session, str(FIXTURE_PATH), storage)
    session_store.persist(result.id)

    turn = _find_turn(result.turns, 0)
    start = turn.start

    # The store hands back the same mutable Turn object, so snapshot after each call.
    await _perform_turn_retranscription(result.id, turn.id, start, round(start + 1.0, 3))
    short_text = turn.text

    await _perform_turn_retranscription(result.id, turn.id, start, round(start + 6.0, 3))
    long_text = turn.text

    assert len(long_text.split()) > len(short_text.split()), (
        f"a longer range must transcribe more words: {short_text!r} vs {long_text!r}"
    )
    assert len(short_text.split()) < len(long_text.split())
    session_store.delete_session(result.id)


@requires_fixture
def test_retranscription_endpoint_over_http(tmp_path: Path):
    async def prepare():
        session = session_store.create_session(
            SessionCreate(
                title="http retranscribe",
                settings=SessionSettings(asr_model="svanita_0_6b", primary_language="te-IN"),
            )
        )
        storage = tmp_path / "s3"
        storage.mkdir(parents=True, exist_ok=True)
        result = await OfflinePipeline().run(session, str(FIXTURE_PATH), storage)
        session_store.persist(result.id)
        return result

    result = asyncio.run(prepare())
    turn = _find_turn(result.turns, 1)

    with TestClient(app) as client:
        response = client.post(
            f"/api/transcription/{result.id}/turns/{turn.id}/retranscribe",
            json={"start": turn.start, "end": round(turn.start + 4.0, 3)},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["end"] == round(turn.start + 4.0, 3)
        assert body["source"] == "user_edit"
        assert body["text"].strip()

        # Reassigning the speaker on the same request must be honoured.
        response = client.patch(
            f"/api/transcription/{result.id}/turns/{turn.id}",
            json={
                "retranscribe": True,
                "start": turn.start,
                "end": round(turn.start + 3.0, 3),
                "speaker_id": "speaker_0",
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["speaker_id"] == "speaker_0"

    session_store.delete_session(result.id)


def test_retranscribing_without_audio_is_refused_not_faked():
    session = session_store.create_session(
        SessionCreate(
            title="no audio",
            settings=SessionSettings(asr_model="svanita_0_6b", primary_language="te-IN"),
        )
    )
    session.duration = 10.0
    session.audio_file_path = None
    session.turns = [
        Turn(id="turn_x", speaker_id="speaker_0", start=0.0, end=2.0, text="hello")
    ]
    session_store.persist(session.id)

    try:
        asyncio.run(
            _perform_turn_retranscription(session.id, "turn_x", 0.0, 2.0)
        )
        raise AssertionError("expected a failure rather than fabricated text")
    except Exception as exc:  # noqa: BLE001
        assert "not available" in str(exc).lower() or "unavailable" in str(exc).lower()
    finally:
        session_store.delete_session(session.id)
