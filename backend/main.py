import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import settings
from .api import (
    sessions_router,
    audio_router,
    transcription_router,
    speakers_router,
    translations_router,
    exports_router,
    live_router
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure storage paths exist
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    yield

app = FastAPI(
    title="DiarizeStudio API",
    description="Enterprise Speech Diarization, Telugu-English Code-Mixed ASR & Translation Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware (allows frontend on Vite dev port 5173 / localhost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(sessions_router)
app.include_router(audio_router)
app.include_router(transcription_router)
app.include_router(speakers_router)
app.include_router(translations_router)
app.include_router(exports_router)
app.include_router(live_router)

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "DiarizeStudio Backend",
        "asr_provider": settings.asr_primary,
        "diarization_provider": settings.diarization_primary,
        "has_sarvam_key": bool(settings.sarvam_api_key),
        "has_nemotron_endpoint": bool(settings.nemotron_endpoint)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
