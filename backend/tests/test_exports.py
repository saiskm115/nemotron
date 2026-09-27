import json
import pytest
from backend.models.session import Session, SessionSettings
from backend.models.speaker import Speaker
from backend.models.turn import Turn
from backend.exports.srt import export_srt
from backend.exports.vtt import export_vtt
from backend.exports.txt import export_txt
from backend.exports.json_export import export_json
from backend.exports.docx_export import export_docx

@pytest.fixture
def sample_session():
    speakers = [
        Speaker(id="speaker_0", display_name="Mohan", color="#38bdf8", total_speaking_time=3.1, turn_count=1, first_seen=0.2, last_seen=3.1, model_label="speaker_0"),
        Speaker(id="speaker_1", display_name="Priya", color="#f43f5e", total_speaking_time=3.5, turn_count=1, first_seen=3.5, last_seen=7.0, model_label="speaker_1")
    ]
    turns = [
        Turn(
            id="t1",
            speaker_id="speaker_0",
            start=0.2,
            end=3.1,
            text="నేను meeting కి 10 minutes late అవుతాను.",
            translated_text="I will be 10 minutes late to the meeting."
        ),
        Turn(
            id="t2",
            speaker_id="speaker_1",
            start=3.5,
            end=7.0,
            text="Okay, no problem. మీరు వచ్చిన తర్వాత start చేద్దాం.",
            translated_text="Okay, no problem. Let's start after you arrive."
        )
    ]
    return Session(
        id="sess_test_123",
        title="Telugu English Meeting",
        duration=7.0,
        speakers=speakers,
        turns=turns,
        settings=SessionSettings()
    )

def test_export_srt(sample_session):
    srt = export_srt(sample_session.turns, sample_session.speakers, include_translation=True)
    assert "1" in srt
    assert "00:00:00,200 --> 00:00:03,100" in srt
    assert "[Mohan] నేను meeting కి 10 minutes late అవుతాను." in srt
    assert "(I will be 10 minutes late to the meeting.)" in srt

def test_export_vtt(sample_session):
    vtt = export_vtt(sample_session.turns, sample_session.speakers, include_translation=True)
    assert "WEBVTT" in vtt
    assert "00:00:00.200 --> 00:00:03.100" in vtt
    assert "<v Mohan>" in vtt

def test_export_txt(sample_session):
    txt = export_txt(sample_session.turns, sample_session.speakers, include_translation=True)
    assert "[Mohan] [00:00:00]" in txt
    assert "నేను meeting కి 10 minutes late అవుతాను." in txt
    assert "Translation:" in txt

def test_export_json(sample_session):
    json_str = export_json(sample_session)
    data = json.loads(json_str)
    assert data["id"] == "sess_test_123"
    assert len(data["turns"]) == 2
    assert len(data["speakers"]) == 2

def test_export_docx(sample_session):
    docx_bytes = export_docx(sample_session, include_translation=True)
    assert len(docx_bytes) > 1000 # Valid docx file binary
    assert docx_bytes[:2] == b"PK" # Zip header for .docx
