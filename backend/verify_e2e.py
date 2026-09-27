import urllib.request
import json

def verify():
    # 1. Health check
    res = urllib.request.urlopen("http://127.0.0.1:8000/api/health")
    data = json.loads(res.read().decode("utf-8"))
    print("[1] Health check OK:", data)

    # 2. List sessions
    res2 = urllib.request.urlopen("http://127.0.0.1:8000/api/sessions")
    sessions = json.loads(res2.read().decode("utf-8"))
    print(f"[2] Found {len(sessions)} active sessions.")

    # 3. Create a test session
    create_payload = json.dumps({
        "title": "Verification Standup",
        "audio_source": "file",
        "mode": "offline",
        "target_language": "en-IN"
    }).encode("utf-8")
    
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/sessions",
        data=create_payload,
        headers={"Content-Type": "application/json"}
    )
    sess_res = urllib.request.urlopen(req)
    new_sess = json.loads(sess_res.read().decode("utf-8"))
    sess_id = new_sess["id"]
    print(f"[3] Created new session ID: {sess_id}")

    # 4. Update turn
    # Add a mock turn to session
    from backend.storage.session_store import session_store
    from backend.models.turn import Turn
    from backend.models.speaker import Speaker

    sess_obj = session_store.get_session(sess_id)
    sess_obj.speakers = [
        Speaker(id="speaker_0", display_name="Mohan", color="#38bdf8", total_speaking_time=3.1, turn_count=1, first_seen=0.2, last_seen=3.1, model_label="speaker_0"),
        Speaker(id="speaker_1", display_name="Priya", color="#f43f5e", total_speaking_time=3.5, turn_count=1, first_seen=3.5, last_seen=7.0, model_label="speaker_1")
    ]
    sess_obj.turns = [
        Turn(id="t1", speaker_id="speaker_0", start=0.2, end=3.1, text="నేను meeting కి 10 minutes late అవుతాను.", translated_text="I will be 10 minutes late to the meeting."),
        Turn(id="t2", speaker_id="speaker_1", start=3.5, end=7.0, text="Okay, no problem. మీరు వచ్చిన తర్వాత start చేద్దాం.", translated_text="Okay, no problem. Let's start after you arrive.")
    ]
    session_store.persist(sess_id)

    # 5. Test SRT Export
    srt_res = urllib.request.urlopen(f"http://127.0.0.1:8000/api/exports/{sess_id}/srt?include_translation=true")
    srt_text = srt_res.read().decode("utf-8")
    print("[4] SRT Export Preview:\n" + srt_text.strip())

    # 6. Test DOCX Export
    docx_res = urllib.request.urlopen(f"http://127.0.0.1:8000/api/exports/{sess_id}/docx?include_translation=true")
    docx_bytes = docx_res.read()
    print(f"[5] DOCX Export OK, size: {len(docx_bytes)} bytes (ZIP header: {docx_bytes[:2]})")

    print("\nALL BACKEND API VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    verify()
