from typing import Optional
from pydantic import BaseModel, Field

class Speaker(BaseModel):
    id: str = Field(..., description="Unique session speaker ID, e.g. speaker_0")
    display_name: str = Field(..., description="User-assigned or default name, e.g. Mohan")
    color: str = Field(default="#38bdf8", description="Hex color for timeline visualization")
    total_speaking_time: float = Field(default=0.0, description="Total speaking time in seconds")
    turn_count: int = Field(default=0, description="Total number of turns for speaker")
    first_seen: float = Field(default=0.0, description="Timestamp of first appearance in seconds")
    last_seen: float = Field(default=0.0, description="Timestamp of last appearance in seconds")
    model_label: str = Field(default="", description="Original model-assigned label, e.g. speaker_0")

class SpeakerUpdate(BaseModel):
    display_name: Optional[str] = None
    color: Optional[str] = None

class SpeakerMergeRequest(BaseModel):
    source_speaker_id: str
    target_speaker_id: str
