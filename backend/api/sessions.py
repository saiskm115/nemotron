from typing import List
from fastapi import APIRouter, HTTPException
from ..models.session import Session, SessionCreate, SessionUpdate
from ..storage.session_store import session_store

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

@router.get("", response_model=List[Session])
async def list_sessions():
    return session_store.list_sessions()

@router.post("", response_model=Session)
async def create_session(req: SessionCreate):
    return session_store.create_session(req)

@router.get("/{session_id}", response_model=Session)
async def get_session(session_id: str):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.patch("/{session_id}", response_model=Session)
async def update_session(session_id: str, update: SessionUpdate):
    session = session_store.update_session(session_id, update)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.delete("/{session_id}")
async def delete_session(session_id: str):
    success = session_store.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}

@router.post("/{session_id}/reset", response_model=Session)
async def reset_session(session_id: str):
    session = session_store.reset_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/{session_id}/undo", response_model=Session)
async def undo_session(session_id: str):
    session = session_store.undo(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/{session_id}/redo", response_model=Session)
async def redo_session(session_id: str):
    session = session_store.redo(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
