import copy
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from ..models.session import Session, SessionCreate, SessionUpdate, EditCommand
from ..models.speaker import Speaker, SpeakerUpdate
from ..models.turn import Turn, TurnUpdate, TurnSplitRequest, TurnMergeRequest, LanguageSegment
from ..pipeline.alignment import parse_language_segments
from .edit_store import EditHistoryManager
from .audio_store import audio_store

class SessionStore:
    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._histories: Dict[str, EditHistoryManager] = {}

    def get_history(self, session_id: str) -> EditHistoryManager:
        if session_id not in self._histories:
            self._histories[session_id] = EditHistoryManager()
        return self._histories[session_id]

    def create_session(self, req: SessionCreate) -> Session:
        session_id = f"sess_{uuid.uuid4().hex[:10]}"
        session = Session(
            id=session_id,
            title=req.title,
            audio_source=req.audio_source,
            mode=req.mode,
            target_language=req.target_language or "en-IN",
            settings=req.settings or Session.model_fields['settings'].default_factory()
        )
        self._sessions[session_id] = session
        self.persist(session_id)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        if session_id in self._sessions:
            return self._sessions[session_id]
        
        # Try loading from disk
        s_dir = audio_store.get_session_dir(session_id)
        s_file = s_dir / "session.json"
        if s_file.exists():
            try:
                with open(s_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                session = Session(**data)
                self._sessions[session_id] = session
                return session
            except Exception:
                return None
        return None

    def list_sessions(self) -> List[Session]:
        # Discover sessions persisted on disk that aren't in memory yet
        if audio_store.base_path.exists():
            for p in audio_store.base_path.iterdir():
                if p.is_dir() and p.name.startswith("sess_") and p.name not in self._sessions:
                    s_file = p / "session.json"
                    if s_file.exists():
                        try:
                            with open(s_file, "r", encoding="utf-8") as f:
                                data = json.load(f)
                            self._sessions[p.name] = Session(**data)
                        except Exception:
                            pass
        return list(self._sessions.values())

    def update_session(self, session_id: str, update: SessionUpdate) -> Optional[Session]:
        session = self.get_session(session_id)
        if not session:
            return None
        if update.title is not None:
            session.title = update.title
        if update.target_language is not None:
            session.target_language = update.target_language
        if update.settings is not None:
            session.settings = update.settings
        self.persist(session_id)
        return session

    def delete_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
        audio_store.cleanup_session(session_id)
        return True

    # --- Turn Operations ---

    def update_turn(self, session_id: str, turn_id: str, update: TurnUpdate) -> Optional[Turn]:
        session = self.get_session(session_id)
        if not session:
            return None

        for t in session.turns:
            if t.id == turn_id:
                before_state = t.model_dump()

                if update.text is not None:
                    t.text = update.text
                    lang_segs, _ = parse_language_segments(update.text)
                    t.language_segments = lang_segs
                    t.source = "user_edit"
                    t.status = "edited"
                if update.speaker_id is not None:
                    t.speaker_id = update.speaker_id
                    t.source = "user_edit"
                    t.status = "edited"
                if update.start is not None:
                    t.start = update.start
                    t.source = "user_edit"
                if update.end is not None:
                    t.end = update.end
                    t.source = "user_edit"
                if update.translated_text is not None:
                    t.translated_text = update.translated_text
                    t.translation_status = "complete"

                after_state = t.model_dump()
                self.get_history(session_id).record_edit("turn_update", before_state, after_state)
                self._recalculate_speaker_stats(session)
                self.persist(session_id)
                return t
        return None

    def update_turn_retranscription(
        self,
        session_id: str,
        turn_id: str,
        start: float,
        end: float,
        text: str,
        confidence: float = 0.95,
        language_segments: Optional[List[LanguageSegment]] = None,
        translated_text: Optional[str] = None,
        speaker_id: Optional[str] = None
    ) -> Optional[Turn]:
        session = self.get_session(session_id)
        if not session:
            return None

        for t in session.turns:
            if t.id == turn_id:
                before_state = t.model_dump()
                t.start = round(start, 3)
                t.end = round(end, 3)
                t.text = text
                t.confidence = confidence
                if language_segments is not None:
                    t.language_segments = language_segments
                else:
                    segs, _ = parse_language_segments(text)
                    t.language_segments = segs

                if speaker_id is not None:
                    t.speaker_id = speaker_id

                if translated_text is not None:
                    t.translated_text = translated_text
                    t.translation_status = "complete"

                t.status = "edited"
                t.source = "user_edit"
                t.speech_only = False
                t.updated_at = datetime.utcnow().isoformat()

                after_state = t.model_dump()
                self.get_history(session_id).record_edit("turn_retranscribe", before_state, after_state)
                self._recalculate_speaker_stats(session)
                self.persist(session_id)
                return t
        return None

    def split_turn(self, session_id: str, req: TurnSplitRequest) -> Optional[List[Turn]]:
        session = self.get_session(session_id)
        if not session:
            return None

        idx = next((i for i, t in enumerate(session.turns) if t.id == req.turn_id), None)
        if idx is None:
            return None

        target = session.turns[idx]
        before_state = [t.model_dump() for t in session.turns]

        lang1, _ = parse_language_segments(req.text_before)
        lang2, _ = parse_language_segments(req.text_after)

        turn_1 = Turn(
            id=f"turn_{uuid.uuid4().hex[:8]}",
            speaker_id=target.speaker_id,
            start=target.start,
            end=round(req.split_timestamp, 3),
            text=req.text_before,
            language_segments=lang1,
            status="edited",
            source="user_edit",
            original_model_text=target.original_model_text,
            original_model_speaker_id=target.original_model_speaker_id,
            original_start=target.original_start,
            original_end=target.original_end
        )

        turn_2 = Turn(
            id=f"turn_{uuid.uuid4().hex[:8]}",
            speaker_id=target.speaker_id,
            start=round(req.split_timestamp, 3),
            end=target.end,
            text=req.text_after,
            language_segments=lang2,
            status="edited",
            source="user_edit",
            original_model_text=target.original_model_text,
            original_model_speaker_id=target.original_model_speaker_id,
            original_start=target.original_start,
            original_end=target.original_end
        )

        session.turns = session.turns[:idx] + [turn_1, turn_2] + session.turns[idx+1:]
        after_state = [t.model_dump() for t in session.turns]
        self.get_history(session_id).record_edit("split_turn", before_state, after_state)
        self._recalculate_speaker_stats(session)
        self.persist(session_id)
        return [turn_1, turn_2]

    def merge_turns(self, session_id: str, req: TurnMergeRequest) -> Optional[Turn]:
        session = self.get_session(session_id)
        if not session:
            return None

        t1_idx = next((i for i, t in enumerate(session.turns) if t.id == req.first_turn_id), None)
        t2_idx = next((i for i, t in enumerate(session.turns) if t.id == req.second_turn_id), None)

        if t1_idx is None or t2_idx is None or abs(t1_idx - t2_idx) != 1:
            return None

        t1 = session.turns[min(t1_idx, t2_idx)]
        t2 = session.turns[max(t1_idx, t2_idx)]
        before_state = [t.model_dump() for t in session.turns]

        merged_text = f"{t1.text} {t2.text}".strip()
        merged_lang, _ = parse_language_segments(merged_text)

        merged_turn = Turn(
            id=t1.id,
            speaker_id=t1.speaker_id,
            start=min(t1.start, t2.start),
            end=max(t1.end, t2.end),
            text=merged_text,
            language_segments=merged_lang,
            status="edited",
            source="user_edit",
            original_model_text=f"{t1.original_model_text or t1.text} {t2.original_model_text or t2.text}",
            original_model_speaker_id=t1.original_model_speaker_id or t1.speaker_id,
            original_start=t1.original_start or t1.start,
            original_end=t2.original_end or t2.end
        )

        first_pos = min(t1_idx, t2_idx)
        session.turns = session.turns[:first_pos] + [merged_turn] + session.turns[first_pos+2:]
        after_state = [t.model_dump() for t in session.turns]
        self.get_history(session_id).record_edit("merge_turns", before_state, after_state)
        self._recalculate_speaker_stats(session)
        self.persist(session_id)
        return merged_turn

    def delete_turn(self, session_id: str, turn_id: str) -> bool:
        session = self.get_session(session_id)
        if not session:
            return False
        before_state = [t.model_dump() for t in session.turns]
        session.turns = [t for t in session.turns if t.id != turn_id]
        after_state = [t.model_dump() for t in session.turns]
        self.get_history(session_id).record_edit("delete_turn", before_state, after_state)
        self._recalculate_speaker_stats(session)
        self.persist(session_id)
        return True

    def reset_turn(self, session_id: str, turn_id: str) -> Optional[Turn]:
        """Resets a turn back to raw model output without losing original model data (Section 13)."""
        session = self.get_session(session_id)
        if not session:
            return None
        for t in session.turns:
            if t.id == turn_id and t.original_model_text is not None:
                before_state = t.model_dump()
                t.text = t.original_model_text
                t.speaker_id = t.original_model_speaker_id or t.speaker_id
                if t.original_start is not None:
                    t.start = t.original_start
                if t.original_end is not None:
                    t.end = t.original_end
                t.status = "final"
                t.source = "model"
                lang_segs, _ = parse_language_segments(t.text)
                t.language_segments = lang_segs
                after_state = t.model_dump()
                self.get_history(session_id).record_edit("reset_turn", before_state, after_state)
                self._recalculate_speaker_stats(session)
                self.persist(session_id)
                return t
        return None

    def reset_session(self, session_id: str) -> Optional[Session]:
        """Resets all turns in the session to model output."""
        session = self.get_session(session_id)
        if not session:
            return None
        for t in session.turns:
            if t.original_model_text:
                t.text = t.original_model_text
                t.speaker_id = t.original_model_speaker_id or t.speaker_id
                if t.original_start is not None:
                    t.start = t.original_start
                if t.original_end is not None:
                    t.end = t.original_end
                t.status = "final"
                t.source = "model"
                lang_segs, _ = parse_language_segments(t.text)
                t.language_segments = lang_segs
        self._recalculate_speaker_stats(session)
        self.persist(session_id)
        return session

    # --- Speaker Operations ---

    def update_speaker(self, session_id: str, speaker_id: str, update: SpeakerUpdate) -> Optional[Speaker]:
        session = self.get_session(session_id)
        if not session:
            return None
        for s in session.speakers:
            if s.id == speaker_id:
                if update.display_name is not None:
                    s.display_name = update.display_name
                if update.color is not None:
                    s.color = update.color
                self.persist(session_id)
                return s
        return None

    def merge_speakers(self, session_id: str, source_id: str, target_id: str) -> Optional[Session]:
        """
        Merges source speaker into target speaker (Section 12: Speaker Merging).
        Updates all affected turns immediately.
        Preserves model speaker identity separately.
        """
        session = self.get_session(session_id)
        if not session or source_id == target_id:
            return session

        before_state = {
            "turns": [t.model_dump() for t in session.turns],
            "speakers": [s.model_dump() for s in session.speakers]
        }

        # Update turns
        for t in session.turns:
            if t.speaker_id == source_id:
                t.speaker_id = target_id
                t.source = "user_edit"
                t.status = "edited"

        # Remove source speaker
        session.speakers = [s for s in session.speakers if s.id != source_id]
        self._recalculate_speaker_stats(session)

        after_state = {
            "turns": [t.model_dump() for t in session.turns],
            "speakers": [s.model_dump() for s in session.speakers]
        }
        self.get_history(session_id).record_edit("merge_speakers", before_state, after_state)
        self.persist(session_id)
        return session

    # --- History (Undo / Redo) ---

    def undo(self, session_id: str) -> Optional[Session]:
        session = self.get_session(session_id)
        if not session:
            return None
        cmd = self.get_history(session_id).undo()
        if not cmd:
            return session
        
        # Apply before state
        if cmd.type in ("split_turn", "merge_turns", "delete_turn"):
            session.turns = [Turn(**t) for t in cmd.before]
        elif cmd.type == "turn_update":
            t_id = cmd.before["id"]
            for i, t in enumerate(session.turns):
                if t.id == t_id:
                    session.turns[i] = Turn(**cmd.before)
                    break
        elif cmd.type == "merge_speakers":
            session.turns = [Turn(**t) for t in cmd.before["turns"]]
            session.speakers = [Speaker(**s) for s in cmd.before["speakers"]]

        self._recalculate_speaker_stats(session)
        self.persist(session_id)
        return session

    def redo(self, session_id: str) -> Optional[Session]:
        session = self.get_session(session_id)
        if not session:
            return None
        cmd = self.get_history(session_id).redo()
        if not cmd:
            return session

        # Apply after state
        if cmd.type in ("split_turn", "merge_turns", "delete_turn"):
            session.turns = [Turn(**t) for t in cmd.after]
        elif cmd.type == "turn_update":
            t_id = cmd.after["id"]
            for i, t in enumerate(session.turns):
                if t.id == t_id:
                    session.turns[i] = Turn(**cmd.after)
                    break
        elif cmd.type == "merge_speakers":
            session.turns = [Turn(**t) for t in cmd.after["turns"]]
            session.speakers = [Speaker(**s) for s in cmd.after["speakers"]]

        self._recalculate_speaker_stats(session)
        self.persist(session_id)
        return session

    def _recalculate_speaker_stats(self, session: Session) -> None:
        stats: Dict[str, Dict[str, Any]] = {}
        for t in session.turns:
            dur = max(0.0, t.end - t.start)
            if t.speaker_id not in stats:
                stats[t.speaker_id] = {
                    "total_time": dur,
                    "turn_count": 1,
                    "first_seen": t.start,
                    "last_seen": t.end
                }
            else:
                stats[t.speaker_id]["total_time"] += dur
                stats[t.speaker_id]["turn_count"] += 1
                stats[t.speaker_id]["first_seen"] = min(stats[t.speaker_id]["first_seen"], t.start)
                stats[t.speaker_id]["last_seen"] = max(stats[t.speaker_id]["last_seen"], t.end)

        for s in session.speakers:
            if s.id in stats:
                s.total_speaking_time = round(stats[s.id]["total_time"], 3)
                s.turn_count = stats[s.id]["turn_count"]
                s.first_seen = round(stats[s.id]["first_seen"], 3)
                s.last_seen = round(stats[s.id]["last_seen"], 3)

    def persist(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if not session:
            return
        s_dir = audio_store.get_session_dir(session_id)
        # Save session.json
        with open(s_dir / "session.json", "w", encoding="utf-8") as f:
            json.dump(session.model_dump(), f, indent=2, ensure_ascii=False)
        # Save /processed/turns.json
        proc_dir = s_dir / "processed"
        proc_dir.mkdir(parents=True, exist_ok=True)
        with open(proc_dir / "turns.json", "w", encoding="utf-8") as f:
            json.dump([t.model_dump() for t in session.turns], f, indent=2, ensure_ascii=False)

session_store = SessionStore()
