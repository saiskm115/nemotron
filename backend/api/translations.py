import os
from fastapi import APIRouter, HTTPException
from ..storage.session_store import session_store
from ..models.translation import TranslationRequest, TranslationResult
from ..providers.translation.sarvam import SarvamTranslationProvider
from ..providers.translation.mock_translation import MockTranslationProvider

router = APIRouter(prefix="/api/translations", tags=["translations"])

def get_translation_provider():
    key = os.environ.get("SARVAM_API_KEY", "")
    return SarvamTranslationProvider(api_key=key) if key else MockTranslationProvider()

@router.post("/{session_id}/turns/{turn_id}")
async def translate_turn(session_id: str, turn_id: str, target_language: str = "en-IN"):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    turn = next((t for t in session.turns if t.id == turn_id), None)
    if not turn:
        raise HTTPException(status_code=404, detail="Turn not found")

    # Speech-only segments have no ASR text — cannot be translated
    if turn.speech_only or not turn.text.strip():
        raise HTTPException(status_code=400, detail="This segment has no transcribed text to translate (speech-only diarization entry)")

    provider = get_translation_provider()
    try:
        req = TranslationRequest(
            text=turn.text,
            source_language=turn.source_language or "te-IN",
            target_language=target_language
        )
        res = await provider.translate(req)
        turn.translated_text = res.translated_text
        turn.translation_status = "complete"
        session_store.persist(session_id)
        return turn
    except Exception as e:
        turn.translation_status = "failed"
        session_store.persist(session_id)
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

@router.post("/{session_id}/translate_all")
async def translate_all_turns(session_id: str, target_language: str = "en-IN"):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    provider = get_translation_provider()
    failed_count = 0
    for turn in session.turns:
        # Skip speech-only segments — no text to translate
        if turn.speech_only or not turn.text.strip():
            continue
        try:
            req = TranslationRequest(
                text=turn.text,
                source_language=turn.source_language or "te-IN",
                target_language=target_language
            )
            res = await provider.translate(req)
            turn.translated_text = res.translated_text
            turn.translation_status = "complete"
        except Exception:
            turn.translation_status = "failed"
            failed_count += 1

    session_store.persist(session_id)
    return {"status": "complete", "total_turns": len(session.turns), "failed": failed_count}
