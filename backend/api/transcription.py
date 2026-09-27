from fastapi import APIRouter, HTTPException
from ..models.turn import Turn, TurnUpdate, TurnSplitRequest, TurnMergeRequest
from ..storage.session_store import session_store

router = APIRouter(prefix="/api/transcription", tags=["transcription"])

@router.patch("/{session_id}/turns/{turn_id}", response_model=Turn)
async def update_turn(session_id: str, turn_id: str, update: TurnUpdate):
    turn = session_store.update_turn(session_id, turn_id, update)
    if not turn:
        raise HTTPException(status_code=404, detail="Turn or session not found")
    return turn

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
