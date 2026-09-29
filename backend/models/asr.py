from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

class ASRMode(str, Enum):
    NORMAL = "normal"          # MODE A: Readable transcript
    CODEMIXED = "codemix"      # MODE B: Preserves actual spoken language without unwanted transliteration
    VERBATIM = "verbatim"      # MODE C: Preserves fillers, repetitions, false starts

class ASRToken(BaseModel):
    id: str
    text: str
    start: float
    end: float
    confidence: Optional[float] = None
    language: Optional[str] = None
    is_final: bool = True

class ASRChunk(BaseModel):
    id: str
    text: str
    start: float
    end: float
    confidence: Optional[float] = None
    language: Optional[str] = None
    is_final: bool = True
    tokens: List[ASRToken] = Field(default_factory=list)

class ASROptions(BaseModel):
    # Registry id of the model to run (see providers/asr/registry.py).
    model: str = ""
    mode: ASRMode = ASRMode.CODEMIXED
    language_code: Optional[str] = "unknown" # "unknown", "te-IN", "en-IN"
    with_timestamps: bool = True
    keyterms: List[str] = Field(default_factory=list) # Custom vocabulary prompting

class ASRResult(BaseModel):
    transcript: str
    language_code: Optional[str] = None
    language_probability: Optional[float] = None
    chunks: List[ASRChunk] = Field(default_factory=list)
    tokens: List[ASRToken] = Field(default_factory=list)
    latency_sec: float = 0.0
