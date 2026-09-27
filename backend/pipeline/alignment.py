import re
from typing import List, Dict, Optional, Tuple
from ..models.asr import ASRToken, ASRChunk, ASRResult
from ..models.diarization import DiarizationSegment, DiarizationResult
from ..models.turn import LanguageSegment

def parse_language_segments(text: str) -> Tuple[List[LanguageSegment], bool]:
    """
    Analyzes text to detect code-mixing between Telugu and English/Latin scripts.
    Returns (segments, is_code_mixed).
    Conforms strictly to Section 4:
    {
      "language": "te-IN",
      "is_code_mixed": true,
      "segments": [
        {"text": "నాకు", "language": "te"},
        {"text": "project deadline", "language": "en"},
        {"text": "గురించి", "language": "te"}
      ]
    }
    """
    words = text.strip().split()
    if not words:
        return [], False

    def get_word_lang(w: str) -> str:
        clean = re.sub(r'[^\w\s]', '', w)
        if any('\u0C00' <= c <= '\u0C7F' for c in clean):
            return "te"
        elif any('a' <= c.lower() <= 'z' for c in clean):
            return "en"
        return "neutral"

    segments: List[LanguageSegment] = []
    current_lang: Optional[str] = None
    current_words: List[str] = []

    for w in words:
        w_lang = get_word_lang(w)
        if w_lang == "neutral":
            # Append neutral punctuation/numbers to current segment
            current_words.append(w)
            continue

        if current_lang is None:
            current_lang = w_lang
            current_words.append(w)
        elif current_lang == w_lang:
            current_words.append(w)
        else:
            # Language changed: flush previous segment
            segments.append(LanguageSegment(text=" ".join(current_words), language=current_lang))
            current_lang = w_lang
            current_words = [w]

    if current_words:
        segments.append(LanguageSegment(text=" ".join(current_words), language=current_lang or "te"))

    has_te = any(s.language == "te" for s in segments)
    has_en = any(s.language == "en" for s in segments)
    is_code_mixed = has_te and has_en

    return segments, is_code_mixed

class AlignedUnit:
    def __init__(
        self,
        text: str,
        start: float,
        end: float,
        speaker_id: str,
        confidence: Optional[float] = None,
        is_final: bool = True,
        is_overlap: bool = False,
        overlap_speakers: Optional[List[str]] = None,
        source_token: Optional[ASRToken] = None
    ):
        self.text = text
        self.start = start
        self.end = end
        self.speaker_id = speaker_id
        self.confidence = confidence
        self.is_final = is_final
        self.is_overlap = is_overlap
        self.overlap_speakers = overlap_speakers or []
        self.source_token = source_token

class AlignmentEngine:
    def __init__(self, overlap_threshold: float = 0.05, merge_gap: float = 0.45):
        self.overlap_threshold = overlap_threshold
        self.merge_gap = merge_gap

    def align(
        self,
        asr_result: ASRResult,
        diarization_result: DiarizationResult
    ) -> List[AlignedUnit]:
        """
        Aligns ASR units (word tokens if available, else chunks) against diarization intervals
        using temporal overlap calculations.
        Detects overlapping speech (barge-ins).
        """
        # Determine whether to align on word tokens or chunk level
        units_to_align: List[Tuple[str, float, float, Optional[float], bool, Optional[ASRToken]]] = []

        if asr_result.tokens:
            for t in asr_result.tokens:
                units_to_align.append((t.text, t.start, t.end, t.confidence, t.is_final, t))
        elif asr_result.chunks:
            for c in asr_result.chunks:
                units_to_align.append((c.text, c.start, c.end, c.confidence, c.is_final, None))
        else:
            return []

        diar_segments = diarization_result.segments
        aligned_units: List[AlignedUnit] = []
        last_assigned_speaker: str = diar_segments[0].speaker_id if diar_segments else "speaker_0"

        for text, u_start, u_end, conf, is_final, src_token in units_to_align:
            u_duration = max(0.001, u_end - u_start)
            speaker_overlaps: Dict[str, float] = {}

            # Calculate exact temporal overlap with every diarization segment
            for d in diar_segments:
                overlap = max(0.0, min(u_end, d.end) - max(u_start, d.start))
                if overlap > 0:
                    speaker_overlaps[d.speaker_id] = speaker_overlaps.get(d.speaker_id, 0.0) + overlap

            if speaker_overlaps:
                # Find speaker with maximum overlap
                best_speaker = max(speaker_overlaps.items(), key=lambda kv: kv[1])[0]
                max_overlap = speaker_overlaps[best_speaker]

                # Check for concurrent overlapping speech (barge-in)
                # If a second speaker has significant overlap (> 20% of unit duration or > 0.08s)
                overlapping_speakers = [
                    spk for spk, ov in speaker_overlaps.items()
                    if ov >= max(0.08, 0.20 * u_duration)
                ]
                is_overlap = len(overlapping_speakers) > 1
                last_assigned_speaker = best_speaker

                aligned_units.append(
                    AlignedUnit(
                        text=text,
                        start=u_start,
                        end=u_end,
                        speaker_id=best_speaker,
                        confidence=conf,
                        is_final=is_final,
                        is_overlap=is_overlap,
                        overlap_speakers=overlapping_speakers if is_overlap else [],
                        source_token=src_token
                    )
                )
            else:
                # No direct temporal overlap found (pause or gap in diarization)
                # Find closest diarization segment
                closest_seg = None
                min_dist = float("inf")
                for d in diar_segments:
                    dist = min(abs(u_start - d.end), abs(d.start - u_end))
                    if dist < min_dist:
                        min_dist = dist
                        closest_seg = d

                # If closest segment is within 0.8s, assign to that speaker, else keep last speaker
                assigned_speaker = closest_seg.speaker_id if (closest_seg and min_dist < 0.8) else last_assigned_speaker
                last_assigned_speaker = assigned_speaker

                aligned_units.append(
                    AlignedUnit(
                        text=text,
                        start=u_start,
                        end=u_end,
                        speaker_id=assigned_speaker,
                        confidence=conf,
                        is_final=is_final,
                        is_overlap=False,
                        overlap_speakers=[],
                        source_token=src_token
                    )
                )

        return aligned_units
