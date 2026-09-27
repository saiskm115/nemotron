from typing import Optional, List
from pydantic import BaseModel, Field

class DiarizationSegment(BaseModel):
    speaker_id: str
    start: float
    end: float
    confidence: Optional[float] = None

class DiarizationOptions(BaseModel):
    max_speakers: int = 8
    latency_profile: str = "offline" # "offline" (30.4s), "low_latency" (0.32s), "ultra_low" (0.08s)
    threshold: float = 0.5

class DiarizationResult(BaseModel):
    segments: List[DiarizationSegment] = Field(default_factory=list)
    speakers: List[str] = Field(default_factory=list)
    overlap_count: int = 0
    latency_sec: float = 0.0
