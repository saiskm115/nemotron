import os
from pathlib import Path
from typing import Dict, Any, List
import yaml
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "config" / "providers.yaml"

class AudioConfig(BaseModel):
    sample_rate: int = 16000
    channels: int = 1
    format: str = "wav"
    chunk_duration_sec: float = 1.0

class AlignmentConfig(BaseModel):
    overlap_threshold_sec: float = 0.15
    ambiguity_delta_sec: float = 0.05
    merge_turn_gap_sec: float = 0.45

class AppConfig(BaseModel):
    asr_primary: str = "auto_tinglish_whisper_telugu"
    diarization_primary: str = "nemotron_3_diarization"
    translation_primary: str = "sarvam"
    audio: AudioConfig = Field(default_factory=AudioConfig)
    alignment: AlignmentConfig = Field(default_factory=AlignmentConfig)
    
    # Environment variables
    sarvam_api_key: str = ""
    nemotron_endpoint: str = ""
    nemotron_api_key: str = ""
    translation_provider: str = "sarvam"
    translation_api_key: str = ""
    storage_path: Path = BASE_DIR / "data" / "storage"
    database_url: str = "sqlite:///./data/diarizestudio.db"

def load_config() -> AppConfig:
    data: Dict[str, Any] = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

    asr_data = data.get("asr", {})
    diar_data = data.get("diarization", {})
    trans_data = data.get("translation", {})
    audio_data = data.get("audio", {})
    align_data = data.get("alignment", {})

    cfg = AppConfig(
        asr_primary=asr_data.get("primary", "auto_tinglish_whisper_telugu"),
        diarization_primary=diar_data.get("primary", "nemotron_3_diarization"),
        translation_primary=trans_data.get("primary", "sarvam"),
        audio=AudioConfig(**audio_data) if audio_data else AudioConfig(),
        alignment=AlignmentConfig(**align_data) if align_data else AlignmentConfig(),
        sarvam_api_key=os.environ.get("SARVAM_API_KEY", ""),
        nemotron_endpoint=os.environ.get("NEMOTRON_ENDPOINT", ""),
        nemotron_api_key=os.environ.get("NEMOTRON_API_KEY", ""),
        translation_provider=os.environ.get("TRANSLATION_PROVIDER", "sarvam"),
        translation_api_key=os.environ.get("TRANSLATION_API_KEY", ""),
        storage_path=Path(os.environ.get("STORAGE_PATH", str(BASE_DIR / "data" / "storage"))),
        database_url=os.environ.get("DATABASE_URL", "sqlite:///./data/diarizestudio.db")
    )
    
    cfg.storage_path.mkdir(parents=True, exist_ok=True)
    return cfg

settings = load_config()
