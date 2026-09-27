from typing import Optional, List
from pydantic import BaseModel, Field

class AudioMetadata(BaseModel):
    duration_sec: float = 0.0
    sample_rate: int = 16000
    channels: int = 1
    sample_count: int = 0
    rms_db: float = 0.0
    peaks: List[float] = Field(default_factory=list) # Downsampled waveform peaks for fast UI rendering

class AudioInput(BaseModel):
    file_path: Optional[str] = None
    raw_bytes: Optional[bytes] = None
    metadata: Optional[AudioMetadata] = None

class AudioFrame(BaseModel):
    timestamp_ms: float
    data: bytes
    is_last: bool = False
