import os
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from ..models.turn import Turn, TurnUpdate, TurnSplitRequest, TurnMergeRequest, TurnRetranscribeRequest
from ..storage.session_store import session_store, parse_language_segments
from ..providers.asr.registry import get_asr_provider
from ..models.asr import ASROptions, ASRMode
from ..models.translation import TranslationRequest
from ..api.translations import get_translation_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/transcription", tags=["transcription"])

async def _perform_turn_retranscription(
    session_id: str,
    turn_id: str,
    start: float,
    end: float,
    speaker_id: Optional[str] = None
) -> Turn:
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    turn = next((t for t in session.turns if t.id == turn_id), None)
    if not turn:
        raise HTTPException(status_code=404, detail="Turn not found")

    duration = session.duration or 60.0
    start = max(0.0, float(start))
    end = min(round(float(end), 3), round(duration, 3))
    if end <= start + 0.05:
        raise HTTPException(status_code=400, detail="Turn duration too short (minimum 0.05s)")

    asr_mode_val = ASRMode.CODEMIXED
    if session.settings.asr_mode == "normal":
        asr_mode_val = ASRMode.NORMAL
    elif session.settings.asr_mode == "verbatim":
        asr_mode_val = ASRMode.VERBATIM

    asr_options = ASROptions(
        model=session.settings.asr_model,
        mode=asr_mode_val,
        language_code=session.settings.primary_language,
        with_timestamps=True,
        keyterms=session.settings.keyterms
    )

    audio_file_path = session.audio_file_path if (session.audio_file_path and os.path.exists(session.audio_file_path)) else None

    asr_engine = get_asr_provider(session.settings.asr_model)
    asr_res = await asr_engine.transcribe_interval(
        audio_file_path=audio_file_path,
        start_time=start,
        end_time=end,
        options=asr_options
    )

    new_text = asr_res.transcript.strip()
    confidences = [t.confidence for t in asr_res.tokens if t.confidence is not None]
    conf = round(sum(confidences) / len(confidences), 2) if confidences else None

    lang_segs, _ = parse_language_segments(new_text)
    source_language = (
        asr_res.language_code
        or turn.source_language
        or session.settings.primary_language
        or "te-IN"
    )

    # Auto-translate if enabled or turn previously had translation
    new_translation = None
    if (session.settings.auto_translate or turn.translated_text) and new_text:
        try:
            trans_provider = get_translation_provider()
            req = TranslationRequest(
                text=new_text,
                source_language=turn.source_language or "te-IN",
                target_language=session.settings.target_language or "en-IN"
            )
            trans_res = await trans_provider.translate(req)
            new_translation = trans_res.translated_text
        except Exception as e:
            logger.warning(f"Translation failed during retranscription: {e}")

    updated_turn = session_store.update_turn_retranscription(
        session_id=session_id,
        turn_id=turn_id,
        start=start,
        end=end,
        text=new_text,
        confidence=conf,
        language_segments=lang_segs,
        translated_text=new_translation,
        speaker_id=speaker_id,
        source_language=source_language
    )

    if not updated_turn:
        raise HTTPException(status_code=500, detail="Failed to persist retranscribed turn")

    return updated_turn

@router.patch("/{session_id}/turns/{turn_id}", response_model=Turn)
async def update_turn(session_id: str, turn_id: str, update: TurnUpdate):
    if update.retranscribe and (update.start is not None or update.end is not None):
        session = session_store.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        turn = next((t for t in session.turns if t.id == turn_id), None)
        if not turn:
            raise HTTPException(status_code=404, detail="Turn not found")
        start = update.start if update.start is not None else turn.start
        end = update.end if update.end is not None else turn.end
        return await _perform_turn_retranscription(
            session_id=session_id,
            turn_id=turn_id,
            start=start,
            end=end,
            speaker_id=update.speaker_id
        )

    turn = session_store.update_turn(session_id, turn_id, update)
    if not turn:
        raise HTTPException(status_code=404, detail="Turn or session not found")
    return turn

@router.post("/{session_id}/turns/{turn_id}/retranscribe", response_model=Turn)
async def retranscribe_turn(session_id: str, turn_id: str, req: TurnRetranscribeRequest):
    return await _perform_turn_retranscription(
        session_id=session_id,
        turn_id=turn_id,
        start=req.start,
        end=req.end,
        speaker_id=req.speaker_id
    )

@router.post("/{session_id}/turns/split")
async def split_turn(session_id: str, req: TurnSplitRequest):
    result = session_store.split_turn(session_id, req)
    if not result:
        raise HTTPException(status_code=400, detail="Cannot split turn with provided parameters")
    return {"status": "split", "turns": result}

@router.post("/{session_id}/turns/merge", response_model=Turn)
async def merge_turns(session_id: str, req: TurnMergeRequest):
    turn = session_store.merge_turns(session_id, req)
    if not turn:
        raise HTTPException(status_code=400, detail="Cannot merge turns; they must be consecutive and valid")
    return turn

@router.delete("/{session_id}/turns/{turn_id}")
async def delete_turn(session_id: str, turn_id: str):
    success = session_store.delete_turn(session_id, turn_id)
    if not success:
        raise HTTPException(status_code=404, detail="Turn or session not found")
    return {"status": "deleted", "turn_id": turn_id}

@router.post("/{session_id}/turns/{turn_id}/reset", response_model=Turn)
async def reset_turn(session_id: str, turn_id: str):
    turn = session_store.reset_turn(session_id, turn_id)
    if not turn:
        raise HTTPException(status_code=404, detail="Turn or session not found")
    return turn
