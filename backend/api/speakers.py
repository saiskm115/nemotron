from fastapi import APIRouter, HTTPException
from ..models.speaker import Speaker, SpeakerUpdate, SpeakerMergeRequest
from ..models.session import Session
from ..storage.session_store import session_store

router = APIRouter(prefix="/api/speakers", tags=["speakers"])

@router.patch("/{session_id}/{speaker_id}", response_model=Speaker)
async def update_speaker(session_id: str, speaker_id: str, update: SpeakerUpdate):
    spk = session_store.update_speaker(session_id, speaker_id, update)
    if not spk:
        raise HTTPException(status_code=404, detail="Speaker or session not found")
    return spk

@router.post("/{session_id}/merge", response_model=Session)
async def merge_speakers(session_id: str, req: SpeakerMergeRequest):
    session = session_store.merge_speakers(session_id, req.source_speaker_id, req.target_speaker_id)
    if not session:
        raise HTTPException(status_code=400, detail="Cannot merge speakers")
    return session
