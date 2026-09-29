"""
Manual annotations: a reviewer's own labels on the timeline.

These are the human corrections the model cannot make for itself -- most
importantly, saying who is actually speaking in a region when diarisation split
one person into four or merged two into one.
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.session import SessionCreate
from backend.models.turn import Turn
from backend.storage.session_store import session_store

client = TestClient(app)


@pytest.fixture
def session_id():
    session = session_store.create_session(SessionCreate(title="annotation test", mode="offline"))
    session.duration = 60.0
    session.turns = [
        Turn(id="t1", speaker_id="speaker_0", start=1.0, end=5.0, text="one"),
        Turn(id="t2", speaker_id="speaker_1", start=6.0, end=9.0, text="two"),
        Turn(id="t3", speaker_id="speaker_2", start=10.0, end=14.0, text="three"),
    ]
    session_store.persist(session.id)
    yield session.id
    session_store.delete_session(session.id)


# ── CRUD ───────────────────────────────────────────────────────────────
def test_creating_an_annotation_returns_it(session_id):
    res = client.post(f"/api/annotations/{session_id}", json={
        "start": 6.0, "end": 9.0, "text": "wrong speaker", "label": "speaker_label",
        "speaker_id": "speaker_0", "author": "admin",
    })
    assert res.status_code == 201
    body = res.json()
    assert body["text"] == "wrong speaker"
    assert body["label"] == "speaker_label"
    assert body["source"] == "manual"
    assert body["author"] == "admin"


def test_annotations_are_listed_in_time_order(session_id):
    for start in (20.0, 2.0, 11.0):
        client.post(f"/api/annotations/{session_id}", json={"start": start, "end": start + 0.5, "text": "x"})
    body = client.get(f"/api/annotations/{session_id}").json()
    assert [a["start"] for a in body] == sorted(a["start"] for a in body)


def test_a_region_running_off_the_end_is_clamped_not_rejected(session_id):
    res = client.post(f"/api/annotations/{session_id}", json={"start": 55.0, "end": 999.0, "text": "tail"})
    assert res.status_code == 201
    assert res.json()["end"] <= 60.0


def test_a_backwards_drag_is_repaired(session_id):
    res = client.post(f"/api/annotations/{session_id}", json={"start": 12.0, "end": 11.0, "text": "backwards"})
    assert res.status_code == 201
    assert res.json()["start"] <= res.json()["end"]


def test_a_tiny_region_is_given_a_usable_length(session_id):
    res = client.post(f"/api/annotations/{session_id}", json={"start": 5.0, "end": 5.0, "text": "click"})
    assert res.status_code == 201
    assert res.json()["end"] > res.json()["start"]


def test_updating_an_annotation(session_id):
    created = client.post(
        f"/api/annotations/{session_id}", json={"start": 1.0, "end": 2.0, "text": "before"}
    ).json()
    res = client.patch(f"/api/annotations/{session_id}/{created['id']}",
                       json={"text": "after", "label": "review"})
    assert res.status_code == 200
    assert res.json()["text"] == "after"
    assert res.json()["label"] == "review"


def test_deleting_an_annotation(session_id):
    created = client.post(f"/api/annotations/{session_id}", json={"start": 1.0, "end": 2.0}).json()
    assert client.delete(f"/api/annotations/{session_id}/{created['id']}").status_code == 204
    assert client.get(f"/api/annotations/{session_id}").json() == []


def test_unknown_ids_are_reported_not_silently_ignored(session_id):
    assert client.get("/api/annotations/sess_missing").status_code == 404
    assert client.patch(f"/api/annotations/{session_id}/ann_missing", json={"text": "x"}).status_code == 404
    assert client.delete(f"/api/annotations/{session_id}/ann_missing").status_code == 404


# ── Applying a manual speaker label ─────────────────────────────────────
def test_applying_a_speaker_label_reassigns_the_turns_it_covers(session_id):
    created = client.post(f"/api/annotations/{session_id}", json={
        "start": 6.0, "end": 9.0, "label": "speaker_label", "speaker_id": "speaker_0",
    }).json()

    res = client.post(f"/api/annotations/{session_id}/{created['id']}/apply")
    assert res.status_code == 200
    assert res.json()["turns_updated"] == 1

    speakers = {t.id: t.speaker_id for t in session_store.get_session(session_id).turns}
    assert speakers["t2"] == "speaker_0", "the covered turn must move"
    assert speakers["t1"] == "speaker_0", "an already-correct turn is untouched"
    assert speakers["t3"] == "speaker_2", "a turn outside the region must not move"


def test_applying_a_label_is_undoable(session_id):
    created = client.post(f"/api/annotations/{session_id}", json={
        "start": 6.0, "end": 9.0, "label": "speaker_label", "speaker_id": "speaker_0",
    }).json()
    client.post(f"/api/annotations/{session_id}/{created['id']}/apply")
    assert session_store.get_session(session_id).turns[1].speaker_id == "speaker_0"

    client.post(f"/api/sessions/{session_id}/undo")
    assert session_store.get_session(session_id).turns[1].speaker_id == "speaker_1", "undo must restore the model label"

    client.post(f"/api/sessions/{session_id}/redo")
    assert session_store.get_session(session_id).turns[1].speaker_id == "speaker_0", "redo must reapply it"


def test_a_partial_overlap_is_not_enough_to_move_a_turn(session_id):
    """A 0.5s label inside a 4s turn must not drag the whole turn with it."""
    created = client.post(f"/api/annotations/{session_id}", json={
        "start": 6.0, "end": 6.5, "label": "speaker_label", "speaker_id": "speaker_0",
    }).json()
    res = client.post(f"/api/annotations/{session_id}/{created['id']}/apply")
    assert res.status_code == 400
    assert session_store.get_session(session_id).turns[1].speaker_id == "speaker_1"


def test_applying_a_label_with_no_speaker_is_refused(session_id):
    created = client.post(f"/api/annotations/{session_id}", json={
        "start": 6.0, "end": 9.0, "label": "note",
    }).json()
    assert client.post(f"/api/annotations/{session_id}/{created['id']}/apply").status_code == 400


# ── Persistence ────────────────────────────────────────────────────────
def test_annotations_survive_a_reload(session_id):
    client.post(f"/api/annotations/{session_id}", json={
        "start": 6.0, "end": 9.0, "text": "keep me", "label": "important",
    })
    body = client.get(f"/api/sessions/{session_id}").json()
    saved = [a for a in body["annotations"] if a["text"] == "keep me"]
    assert len(saved) == 1
    assert saved[0]["label"] == "important"


def test_speaker_stats_are_recomputed_after_a_label_is_applied(session_id):
    created = client.post(f"/api/annotations/{session_id}", json={
        "start": 6.0, "end": 9.0, "label": "speaker_label", "speaker_id": "speaker_0",
    }).json()
    client.post(f"/api/annotations/{session_id}/{created['id']}/apply")

    session = session_store.get_session(session_id)
    for speaker in session.speakers:
        expected = sum(t.end - t.start for t in session.turns if t.speaker_id == speaker.id)
        assert abs(speaker.total_speaking_time - expected) < 0.05
