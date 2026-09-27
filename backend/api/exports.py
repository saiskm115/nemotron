from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, PlainTextResponse
from ..storage.session_store import session_store
from ..exports.srt import export_srt
from ..exports.vtt import export_vtt
from ..exports.txt import export_txt
from ..exports.json_export import export_json
from ..exports.docx_export import export_docx

router = APIRouter(prefix="/api/exports", tags=["exports"])

@router.get("/{session_id}/srt", response_class=PlainTextResponse)
async def get_srt(session_id: str, include_translation: bool = Query(False)):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    content = export_srt(session.turns, session.speakers, include_translation=include_translation)
    headers = {"Content-Disposition": f'attachment; filename="{session.title}.srt"'}
    return PlainTextResponse(content, headers=headers)

@router.get("/{session_id}/vtt", response_class=PlainTextResponse)
async def get_vtt(session_id: str, include_translation: bool = Query(False)):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    content = export_vtt(session.turns, session.speakers, include_translation=include_translation)
    headers = {"Content-Disposition": f'attachment; filename="{session.title}.vtt"'}
    return PlainTextResponse(content, headers=headers)

@router.get("/{session_id}/txt", response_class=PlainTextResponse)
async def get_txt(session_id: str, include_translation: bool = Query(False)):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    content = export_txt(session.turns, session.speakers, include_translation=include_translation)
    headers = {"Content-Disposition": f'attachment; filename="{session.title}.txt"'}
    return PlainTextResponse(content, headers=headers)

@router.get("/{session_id}/json")
async def get_json(session_id: str):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    content = export_json(session)
    headers = {"Content-Disposition": f'attachment; filename="{session.title}.json"'}
    return Response(content=content, media_type="application/json", headers=headers)

@router.get("/{session_id}/docx")
async def get_docx(session_id: str, include_translation: bool = Query(True)):
    session = session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    content = export_docx(session, include_translation=include_translation)
    headers = {"Content-Disposition": f'attachment; filename="{session.title}.docx"'}
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers
    )
