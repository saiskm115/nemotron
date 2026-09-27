from datetime import datetime
from typing import Optional, List, Literal, Any, Dict
from pydantic import BaseModel, Field
from .speaker import Speaker
from .turn import Turn

class SessionSettings(BaseModel):
    asr_mode: str = "codemix" # normal, codemix, verbatim
    primary_language: str = "unknown" # te-IN, en-IN, unknown
    target_language: str = "en-IN"
    auto_translate: bool = False
    keyterms: List[str] = Field(default_factory=list)
    show_interim: bool = True
    display_mode: str = "both" # original, translation, both
    transliteration_mode: str = "script" # script, roman, codemix

class EditCommand(BaseModel):
    id: str
    type: str # text_edit, speaker_change, split, merge, delete, boundary_change
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    before: Any
    after: Any

class Session(BaseModel):
    id: str
    title: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    duration: float = 0.0
    audio_source: str = "file" # "file", "microphone", "stream"
    audio_file_path: Optional[str] = None
    source_languages: List[str] = Field(default_factory=lambda: ["te-IN", "en-IN"])
    target_language: Optional[str] = "en-IN"
    speakers: List[Speaker] = Field(default_factory=list)
    turns: List[Turn] = Field(default_factory=list)
    processing_status: Literal["uploading", "processing", "complete", "failed"] = "complete"
    error_message: Optional[str] = None
    mode: Literal["live", "offline"] = "offline"
    settings: SessionSettings = Field(default_factory=SessionSettings)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SessionCreate(BaseModel):
    title: str = "New DiarizeStudio Session"
    audio_source: str = "file"
    mode: Literal["live", "offline"] = "offline"
    target_language: Optional[str] = "en-IN"
    settings: Optional[SessionSettings] = None

class SessionUpdate(BaseModel):
    title: Optional[str] = None
    target_language: Optional[str] = None
    settings: Optional[SessionSettings] = None
