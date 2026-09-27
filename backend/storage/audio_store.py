import shutil
from pathlib import Path
from typing import Optional
from ..config import settings

class AudioStore:
    def __init__(self, base_path: Optional[Path] = None):
        self.base_path = base_path or settings.storage_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def get_session_dir(self, session_id: str) -> Path:
        p = self.base_path / session_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    def save_upload(self, session_id: str, file_name: str, file_bytes: bytes) -> Path:
        session_dir = self.get_session_dir(session_id)
        raw_path = session_dir / file_name
        with open(raw_path, "wb") as f:
            f.write(file_bytes)
        return raw_path

    def cleanup_session(self, session_id: str) -> None:
        session_dir = self.base_path / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)

audio_store = AudioStore()
