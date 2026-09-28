import uuid
from typing import List, Tuple, Optional
from ..models.turn import Turn, LanguageSegment
from ..models.speaker import Speaker
from ..models.diarization import DiarizationSegment
from .alignment import AlignedUnit, parse_language_segments

class TurnBuilder:
    def __init__(self, max_turn_pause_sec: float = 1.0):
        self.max_turn_pause_sec = max_turn_pause_sec

    def build_turns(
        self,
        aligned_units: List[AlignedUnit],
        existing_speakers: List[Speaker] = None,
        diarization_segments: Optional[List[DiarizationSegment]] = None
    ) -> Tuple[List[Turn], List[Speaker]]:
        """
        Groups aligned units into conversational Turn objects and updates Speaker registry.
        Snaps turn boundaries to Nemotron Diarization segments so that audio is completely covered.
        """
        if not aligned_units:
            return [], existing_speakers or []

        turns: List[Turn] = []
        current_speaker: str = aligned_units[0].speaker_id
        current_units: List[AlignedUnit] = []

        def flush_turn(units: List[AlignedUnit]) -> None:
            if not units:
                return
            t_start = units[0].start
            t_end = units[-1].end
            combined_text = " ".join(u.text for u in units if not u.is_speech_only).strip()

            # Determine if this is a pure speech-only turn (no ASR text at all)
            is_speech_only_turn = all(getattr(u, 'is_speech_only', False) for u in units)

            # Snap turn boundary to encompass matching Nemotron diarization segment
            if diarization_segments:
                for d in diarization_segments:
                    if d.speaker_id == units[0].speaker_id:
                        ov = max(0.0, min(t_end, d.end) - max(t_start, d.start))
                        if ov > 0.15:
                            t_start = min(t_start, d.start)
                            t_end = max(t_end, d.end)
            
            # Detect overlap across units in this turn
            any_overlap = any(u.is_overlap for u in units)
            overlap_spks = sorted(list(set(
                spk for u in units for spk in u.overlap_speakers if spk != units[0].speaker_id
            )))
            all_final = all(u.is_final for u in units)

            # Language segments (only for turns with actual text)
            lang_segs, _ = parse_language_segments(combined_text) if combined_text else ([], False)

            turn_id = f"turn_{uuid.uuid4().hex[:8]}"
            turns.append(
                Turn(
                    id=turn_id,
                    speaker_id=units[0].speaker_id,
                    start=round(t_start, 3),
                    end=round(t_end, 3),
                    text=combined_text,
                    source_language="te-IN",
                    language_segments=lang_segs,
                    confidence=0.94,
                    status="final" if all_final else "interim",
                    overlap=any_overlap,
                    overlap_speakers=overlap_spks,
                    source="model",
                    original_model_text=combined_text,
                    original_model_speaker_id=units[0].speaker_id,
                    original_start=round(t_start, 3),
                    original_end=round(t_end, 3),
                    translation_status="not_requested",
                    speech_only=is_speech_only_turn
                )
            )

        for unit in aligned_units:
            # Check speaker change or significant pause
            if current_units:
                pause = unit.start - current_units[-1].end
                if unit.speaker_id != current_speaker or pause > self.max_turn_pause_sec:
                    flush_turn(current_units)
                    current_units = []
                    current_speaker = unit.speaker_id

            current_units.append(unit)

        if current_units:
            flush_turn(current_units)

        # Cross-turn overlap check (e.g. barge-ins between turns)
        for i, t1 in enumerate(turns):
            for j, t2 in enumerate(turns):
                if i != j and t1.speaker_id != t2.speaker_id:
                    if t1.start < t2.end and t2.start < t1.end:
                        t1.overlap = True
                        if t2.speaker_id not in t1.overlap_speakers:
                            t1.overlap_speakers.append(t2.speaker_id)

        # Update or construct Speaker list
        speakers_dict = {s.id: s for s in (existing_speakers or [])}
        DEFAULT_COLORS = ["#38bdf8", "#f43f5e", "#10b981", "#a855f7", "#f59e0b", "#06b6d4", "#ec4899", "#84cc16"]

        for turn in turns:
            spk_id = turn.speaker_id
            turn_dur = max(0.0, turn.end - turn.start)
            if spk_id not in speakers_dict:
                color_idx = len(speakers_dict) % len(DEFAULT_COLORS)
                disp_num = len(speakers_dict)
                disp_names = ["Mohan", "Priya", "Ramesh", "Ananya", "Kavya", "Suresh", "Vikram", "Deepa"]
                disp_name = disp_names[disp_num] if disp_num < len(disp_names) else f"Speaker {disp_num + 1}"

                speakers_dict[spk_id] = Speaker(
                    id=spk_id,
                    display_name=disp_name,
                    color=DEFAULT_COLORS[color_idx],
                    total_speaking_time=round(turn_dur, 3),
                    turn_count=1,
                    first_seen=turn.start,
                    last_seen=turn.end,
                    model_label=spk_id
                )
            else:
                s = speakers_dict[spk_id]
                s.total_speaking_time = round(s.total_speaking_time + turn_dur, 3)
                s.turn_count += 1
                s.first_seen = min(s.first_seen, turn.start)
                s.last_seen = max(s.last_seen, turn.end)

        return turns, list(speakers_dict.values())
