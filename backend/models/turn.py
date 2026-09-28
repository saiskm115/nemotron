from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field

class LanguageSegment(BaseModel):
    text: str
    language: str # "te", "en", etc.

class Turn(BaseModel):
    id: str
    speaker_id: str
    start: float
    end: float
    text: str
    translated_text: Optional[str] = None
    source_language: Optional[str] = None
    language_segments: Optional[List[LanguageSegment]] = Field(default_factory=list)
    confidence: Optional[float] = None
    status: Literal["interim", "final", "edited"] = "final"
    overlap: bool = False
    overlap_speakers: List[str] = Field(default_factory=list)
    source: Literal["model", "user_edit"] = "model"
    original_model_text: Optional[str] = None
    original_model_speaker_id: Optional[str] = None
    original_start: Optional[float] = None
    original_end: Optional[float] = None
    translation_status: Literal["not_requested", "pending", "complete", "failed"] = "not_requested"
    speech_only: bool = False  # True when Nemotron detected speech but ASR has no coverage
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class TurnUpdate(BaseModel):
    text: Optional[str] = None
    speaker_id: Optional[str] = None
    start: Optional[float] = None
    end: Optional[float] = None
    translated_text: Optional[str] = None
    retranscribe: Optional[bool] = False

class TurnRetranscribeRequest(BaseModel):
    start: float
    end: float
    speaker_id: Optional[str] = None

class TurnSplitRequest(BaseModel):
    turn_id: str
    split_timestamp: float
    text_before: str
    text_after: str

class TurnMergeRequest(BaseModel):
    first_turn_id: str
    second_turn_id: str
