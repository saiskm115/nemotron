"""End-to-end pipeline behaviour on real two-speaker Telugu audio."""
import json

import pytest

from backend.models.session import Session, SessionSettings
from backend.pipeline.offline_pipeline import OfflinePipeline

from .conftest_helpers import FIXTURE_PATH, requires_fixture, truth_spans


@requires_fixture
@pytest.mark.asyncio
async def test_offline_pipeline_end_to_end(tmp_path):
    session = Session(
        id="sess_integration_test",
        title="Integration Test Session",
        settings=SessionSettings(
            asr_mode="codemix",
            asr_model="svanita_0_6b",
            primary_language="te-IN",
            auto_translate=False,
        ),
    )

    storage_dir = tmp_path / "storage_sess"
    storage_dir.mkdir(parents=True, exist_ok=True)

    updated = await OfflinePipeline().run(session, str(FIXTURE_PATH), storage_dir)

    assert updated.processing_status == "complete"
    assert updated.duration > 0
    assert updated.turns, "real speech must produce turns"
    assert len(updated.speakers) == 2, f"expected 2 speakers, got {[s.id for s in updated.speakers]}"
    assert "observability" in updated.metadata
    assert updated.metadata["observability"]["turn_count"] == len(updated.turns)
    assert updated.metadata["observability"]["asr_model"] == "svanita_0_6b"
    assert updated.metadata["observability"]["diarization_method"].startswith("acoustic_")

    # Raw model outputs are preserved for auditing (Section 13)
    raw_dir = storage_dir / "raw"
    diar = json.loads((raw_dir / "diarization.json").read_text(encoding="utf-8"))
    asr = json.loads((raw_dir / "asr.json").read_text(encoding="utf-8"))
    assert diar["segments"] and asr["tokens"]
    assert asr["language_code"] == "te-IN"

    # Every turn must sit inside the recording and carry a real duration.
    for turn in updated.turns:
        assert 0 <= turn.start < turn.end <= updated.duration + 0.2
        assert turn.source_language in {"te-IN", "en-IN", "hi-IN"}


@requires_fixture
@pytest.mark.asyncio
async def test_turns_follow_the_ground_truth_speakers(tmp_path):
    session = Session(
        id="sess_turn_alignment",
        title="Turn alignment",
        settings=SessionSettings(asr_model="svanita_0_6b", primary_language="te-IN"),
    )
    storage_dir = tmp_path / "storage_sess"
    storage_dir.mkdir(parents=True, exist_ok=True)

    updated = await OfflinePipeline().run(session, str(FIXTURE_PATH), storage_dir)

    truth = truth_spans()
    assert len(updated.turns) == len(truth), f"expected {len(truth)} turns, got {len(updated.turns)}"

    by_speaker = {"speaker_0": "speaker_0", "speaker_1": "speaker_1"}
    for turn, (truth_start, truth_end, truth_speaker) in zip(updated.turns, truth):
        assert by_speaker[turn.speaker_id] == truth_speaker, (
            f"{turn.start:.2f}-{turn.end:.2f} was assigned to {turn.speaker_id}, "
            f"ground truth is {truth_speaker}"
        )
        assert abs(turn.start - truth_start) < 0.8
        assert abs(turn.end - truth_end) < 0.8


@requires_fixture
@pytest.mark.asyncio
async def test_speaker_totals_add_up(tmp_path):
    session = Session(
        id="sess_speaker_totals",
        title="Speaker totals",
        settings=SessionSettings(asr_model="svanita_0_6b", primary_language="te-IN"),
    )
    storage_dir = tmp_path / "storage_sess"
    storage_dir.mkdir(parents=True, exist_ok=True)

    updated = await OfflinePipeline().run(session, str(FIXTURE_PATH), storage_dir)

    for speaker in updated.speakers:
        expected = sum(t.end - t.start for t in updated.turns if t.speaker_id == speaker.id)
        assert abs(speaker.total_speaking_time - expected) < 0.05
        assert speaker.turn_count == len([t for t in updated.turns if t.speaker_id == speaker.id])
        # Names must not invent a gender or an identity.
        assert speaker.display_name.startswith("Speaker")


@pytest.mark.asyncio
async def test_silence_produces_an_empty_timeline_rather_than_invented_turns(tmp_path):
    import numpy as np
    import soundfile as sf

    path = tmp_path / "silence.wav"
    sf.write(str(path), np.zeros(16000 * 3, dtype=np.float32), 16000)

    session = Session(
        id="sess_silence",
        title="Silence",
        settings=SessionSettings(asr_model="svanita_0_6b", primary_language="te-IN"),
    )
    storage_dir = tmp_path / "storage_sess"
    storage_dir.mkdir(parents=True, exist_ok=True)

    updated = await OfflinePipeline().run(session, str(path), storage_dir)

    assert updated.processing_status == "complete"
    assert updated.turns == [], "silence must not be turned into fabricated speaker turns"
    assert updated.speakers == []
