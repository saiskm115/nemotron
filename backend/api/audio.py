import os
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from ..storage.session_store import session_store
from ..storage.audio_store import audio_store
from ..models.session import SessionCreate, SessionSettings
from ..pipeline.offline_pipeline import OfflinePipeline

router = APIRouter(prefix="/api/audio", tags=["audio"])
pipeline = OfflinePipeline()

@router.post("/upload")
async def upload_audio(
    file: UploadFile = File(...),
    title: str = Form("Uploaded Audio Session"),
    asr_mode: str = Form("codemix"),
    primary_language: str = Form("unknown"),
    target_language: str = Form("en-IN"),
    auto_translate: bool = Form(False)
):
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    
    ext = Path(file.filename).suffix.lower()
    valid_exts = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma"}
    if ext not in valid_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format '{ext}'. Supported formats: {', '.join(valid_exts)}"
        )

    # 1. Create session
    settings = SessionSettings(
        asr_mode=asr_mode,
        primary_language=primary_language,
        target_language=target_language,
        auto_translate=auto_translate
    )
    sess_req = SessionCreate(
        title=title,
        audio_source="file",
        mode="offline",
        target_language=target_language,
        settings=settings
    )
    session = session_store.create_session(sess_req)

    # 2. Save file
    file_bytes = await file.read()
    raw_path = audio_store.save_upload(session.id, file.filename, file_bytes)

    # 3. Run Pipeline
    session_dir = audio_store.get_session_dir(session.id)
    try:
        updated_session = await pipeline.run(session, str(raw_path), session_dir)
        session_store.persist(session.id)
        return updated_session
    except Exception as e:
        session.processing_status = "failed"
        session.error_message = str(e)
        session_store.persist(session.id)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@router.get("/{session_id}/stream")
async def stream_audio(session_id: str):
    session = session_store.get_session(session_id)
    if not session or not session.audio_file_path or not os.path.exists(session.audio_file_path):
        raise HTTPException(status_code=404, detail="Audio file not found for session")
    return FileResponse(session.audio_file_path, media_type="audio/wav")
