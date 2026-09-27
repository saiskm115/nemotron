import pytest
from backend.storage.session_store import SessionStore
from backend.models.session import SessionCreate
from backend.models.speaker import Speaker, SpeakerUpdate
from backend.models.turn import Turn

def test_speaker_renaming_and_merging():
    store = SessionStore()
    sess = store.create_session(SessionCreate(title="Test Speaker Session"))

    # Add speakers
    sess.speakers = [
        Speaker(id="speaker_0", display_name="Mohan", color="#38bdf8", total_speaking_time=5.0, turn_count=1, first_seen=0.0, last_seen=5.0, model_label="speaker_0"),
        Speaker(id="speaker_1", display_name="Priya", color="#f43f5e", total_speaking_time=4.0, turn_count=1, first_seen=5.0, last_seen=9.0, model_label="speaker_1"),
        Speaker(id="speaker_2", display_name="Speaker 2", color="#10b981", total_speaking_time=3.0, turn_count=1, first_seen=9.0, last_seen=12.0, model_label="speaker_2")
    ]

    # Add turns
    sess.turns = [
        Turn(id="t1", speaker_id="speaker_0", start=0.0, end=5.0, text="Turn 1", original_model_speaker_id="speaker_0"),
        Turn(id="t2", speaker_id="speaker_1", start=5.0, end=9.0, text="Turn 2", original_model_speaker_id="speaker_1"),
        Turn(id="t3", speaker_id="speaker_2", start=9.0, end=12.0, text="Turn 3", original_model_speaker_id="speaker_2")
    ]
    store.persist(sess.id)

    # 1. Rename speaker_0 to "Mohan Kumar"
    updated_spk = store.update_speaker(sess.id, "speaker_0", SpeakerUpdate(display_name="Mohan Kumar", color="#0284c7"))
    assert updated_spk.display_name == "Mohan Kumar"
    assert updated_spk.color == "#0284c7"

    # 2. Merge speaker_2 into speaker_0
    updated_sess = store.merge_speakers(sess.id, source_id="speaker_2", target_id="speaker_0")
    
    # Speaker 2 should no longer exist in speakers list
    spk_ids = [s.id for s in updated_sess.speakers]
    assert "speaker_2" not in spk_ids
    assert "speaker_0" in spk_ids

    # Turn t3 must now be assigned to speaker_0
    t3 = next(t for t in updated_sess.turns if t.id == "t3")
    assert t3.speaker_id == "speaker_0"
    # But original model speaker ID must still be speaker_2!
    assert t3.original_model_speaker_id == "speaker_2"

    # 3. Test Undo
    undone_sess = store.undo(sess.id)
    t3_undone = next(t for t in undone_sess.turns if t.id == "t3")
    assert t3_undone.speaker_id == "speaker_2"
    assert any(s.id == "speaker_2" for s in undone_sess.speakers)
