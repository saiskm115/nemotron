import uuid
from typing import List, Optional, Tuple

from ..models.turn import Turn
from ..models.speaker import Speaker
from ..models.diarization import DiarizationSegment
from .alignment import AlignedUnit, parse_language_segments

DEFAULT_SPEAKER_COLORS = [
    "#38bdf8", "#f43f5e", "#10b981", "#a855f7",
    "#f59e0b", "#06b6d4", "#ec4899", "#84cc16",
]

# Neutral placeholders only. Invented human names imply a gender and an identity the
# diarisation model has no way of knowing.
DEFAULT_SPEAKER_LABELS = [
    "Speaker 1", "Speaker 2", "Speaker 3", "Speaker 4",
    "Speaker 5", "Speaker 6", "Speaker 7", "Speaker 8",
]


def infer_source_language(text: str, fallback: Optional[str] = None) -> str:
    """
    Language actually produced by the recogniser for this text.

    Telugu/Hindi script presence wins over Latin, so a code-mixed line is reported
    as the language the speaker was actually using.
    """
    has_te = any("\u0C00" <= c <= "\u0C7F" for c in text)
    has_hi = any("\u0900" <= c <= "\u097F" for c in text)
    has_latin = any(("a" <= c.lower() <= "z") for c in text)
    if has_te:
        return "te-IN"
    if has_hi:
        return "hi-IN"
    if has_latin:
        return "en-IN"
    return fallback or "te-IN"


class TurnBuilder:
    def __init__(self, max_turn_pause_sec: float = 1.0):
        self.max_turn_pause_sec = max_turn_pause_sec

    def build_turns(
        self,
        aligned_units: List[AlignedUnit],
        existing_speakers: Optional[List[Speaker]] = None,
        diarization_segments: Optional[List[DiarizationSegment]] = None,
        source_language: Optional[str] = None,
    ) -> Tuple[List[Turn], List[Speaker]]:
        """
        Groups aligned units into conversational Turn objects and updates the Speaker registry.

        Turn boundaries follow the diarisation segments so audio coverage is exact:
        a turn spans the diarisation segments that the units it contains overlap,
        and stops at the first segment a different speaker owns.
        """
        if not aligned_units:
            return [], existing_speakers or []

        turns: List[Turn] = []
        current_units: List[AlignedUnit] = []

        def flush(units: List[AlignedUnit]) -> None:
            if not units:
                return
            speaker_id = units[0].speaker_id
            text_units = [u for u in units if not u.is_speech_only]
            combined_text = " ".join(u.text for u in text_units).strip()
            is_speech_only_turn = not text_units

            t_start = min(u.start for u in units)
            t_end = max(u.end for u in units)

            # Extend the turn to fully cover the diarisation segments it touches,
            # but never across a segment owned by another speaker.
            if diarization_segments:
                for d in diarization_segments:
                    if d.speaker_id != speaker_id:
                        continue
                    if max(0.0, min(t_end, d.end) - max(t_start, d.start)) <= 0.15:
                        continue
                    blocked = any(
                        other.speaker_id != speaker_id
                        and max(0.0, min(d.end, other.end) - max(d.start, other.start)) > 0.05
                        for other in diarization_segments
                    )
                    if blocked:
                        continue
                    t_start = min(t_start, d.start)
                    t_end = max(t_end, d.end)

            if t_end <= t_start:
                t_end = t_start + 0.05

            any_overlap = any(u.is_overlap for u in units)
            overlap_spks = sorted(
                {
                    spk
                    for u in units
                    for spk in u.overlap_speakers
                    if spk != speaker_id
                }
            )
            all_final = all(u.is_final for u in units)

            lang_segs, _ = parse_language_segments(combined_text) if combined_text else ([], False)
            confidences = [u.confidence for u in units if u.confidence is not None]

            turns.append(
                Turn(
                    id=f"turn_{uuid.uuid4().hex[:8]}",
                    speaker_id=speaker_id,
                    start=round(t_start, 3),
                    end=round(t_end, 3),
                    text=combined_text,
                    source_language=infer_source_language(combined_text, source_language),
                    language_segments=lang_segs,
                    confidence=round(sum(confidences) / len(confidences), 3) if confidences else None,
                    status="final" if all_final else "interim",
                    overlap=any_overlap,
                    overlap_speakers=overlap_spks,
                    source="model",
                    original_model_text=combined_text,
                    original_model_speaker_id=speaker_id,
                    original_start=round(t_start, 3),
                    original_end=round(t_end, 3),
                    translation_status="not_requested",
                    speech_only=is_speech_only_turn,
                )
            )

        current_speaker: Optional[str] = None
        for unit in aligned_units:
            if current_units:
                pause = unit.start - current_units[-1].end
                if unit.speaker_id != current_speaker or pause > self.max_turn_pause_sec:
                    flush(current_units)
                    current_units = []
            current_units.append(unit)
            current_speaker = unit.speaker_id

        if current_units:
            flush(current_units)

        # Cross-turn overlap check (e.g. barge-ins between turns)
        for i, t1 in enumerate(turns):
            for j, t2 in enumerate(turns):
                if i == j or t1.speaker_id == t2.speaker_id:
                    continue
                if t1.start < t2.end and t2.start < t1.end:
                    t1.overlap = True
                    if t2.speaker_id not in t1.overlap_speakers:
                        t1.overlap_speakers.append(t2.speaker_id)

        speakers_dict = {s.id: s for s in (existing_speakers or [])}
        order = list(speakers_dict.keys())
        for turn in turns:
            if turn.speaker_id in speakers_dict:
                continue
            index = len(speakers_dict)
            speakers_dict[turn.speaker_id] = Speaker(
                id=turn.speaker_id,
                display_name=(
                    DEFAULT_SPEAKER_LABELS[index]
                    if index < len(DEFAULT_SPEAKER_LABELS)
                    else f"Speaker {index + 1}"
                ),
                color=DEFAULT_SPEAKER_COLORS[index % len(DEFAULT_SPEAKER_COLORS)],
                total_speaking_time=0.0,
                turn_count=0,
                first_seen=turn.start,
                last_seen=turn.end,
                model_label=turn.speaker_id,
            )
            order.append(turn.speaker_id)

        for turn in turns:
            speaker = speakers_dict[turn.speaker_id]
            speaker.total_speaking_time = round(
                speaker.total_speaking_time + max(0.0, turn.end - turn.start), 3
            )
            speaker.turn_count += 1
            speaker.first_seen = min(speaker.first_seen, turn.start)
            speaker.last_seen = max(speaker.last_seen, turn.end)

        return turns, [speakers_dict[key] for key in order]
