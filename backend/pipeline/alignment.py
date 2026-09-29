import re
from typing import Dict, List, Optional, Tuple

from ..models.asr import ASRResult, ASRToken
from ..models.diarization import DiarizationResult, DiarizationSegment
from ..models.turn import LanguageSegment

# Script ranges used to label each recognised word.
SCRIPT_RANGES = (
    ("te", 0x0C00, 0x0C7F),
    ("hi", 0x0900, 0x097F),
    ("kn", 0x0C80, 0x0CFF),
    ("ta", 0x0B80, 0x0BFF),
    ("ml", 0x0D00, 0x0D7F),
    ("bn", 0x0980, 0x09FF),
    ("gu", 0x0A80, 0x0AFF),
    ("pa", 0x0A00, 0x0A7F),
)

INDIC_LANGUAGES = {lang for lang, _, _ in SCRIPT_RANGES}


def detect_word_language(word: str) -> str:
    """
    Labels a single word by the script it is written in.

    Returns ``"en"`` for Latin words, the matching language tag for an Indic
    script, or ``"neutral"`` for punctuation and numbers.
    """
    clean = re.sub(r"[^\w\s]", "", word or "", flags=re.UNICODE)
    if not clean:
        return "neutral"
    for lang, lo, hi in SCRIPT_RANGES:
        if any(lo <= ord(c) <= hi for c in clean):
            return lang
    if any("a" <= c.lower() <= "z" for c in clean):
        return "en"
    return "neutral"


def parse_language_segments(text: str) -> Tuple[List[LanguageSegment], bool]:
    """
    Splits text into runs of the same language and reports whether it is code-mixed.

    A Telugu sentence with English words written in Latin comes back as alternating
    ``te``/``en`` segments with ``is_code_mixed=True``; a pure Telugu sentence comes
    back as a single ``te`` segment.
    """
    words = text.strip().split()
    if not words:
        return [], False

    segments: List[LanguageSegment] = []
    current_lang: Optional[str] = None
    current_words: List[str] = []

    for word in words:
        lang = detect_word_language(word)
        if lang == "neutral":
            if current_words:
                current_words.append(word)
            continue

        if current_lang is None or lang == current_lang:
            current_lang = lang
            current_words.append(word)
        else:
            segments.append(LanguageSegment(text=" ".join(current_words), language=current_lang))
            current_lang = lang
            current_words = [word]

    if current_words:
        segments.append(LanguageSegment(text=" ".join(current_words), language=current_lang or "te"))

    languages = {segment.language for segment in segments}
    is_code_mixed = bool(languages & INDIC_LANGUAGES) and "en" in languages
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
        source_token: Optional[ASRToken] = None,
        is_speech_only: bool = False
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
        self.is_speech_only = is_speech_only


class AlignmentEngine:
    def __init__(
        self,
        overlap_threshold: float = 0.05,
        merge_gap: float = 0.45,
        max_unattributed_gap: float = 0.40,
        min_speech_only_coverage: float = 0.50,
        min_speech_only_duration: float = 0.40,
    ):
        self.overlap_threshold = overlap_threshold
        self.merge_gap = merge_gap
        self.max_unattributed_gap = max_unattributed_gap
        self.min_speech_only_coverage = min_speech_only_coverage
        self.min_speech_only_duration = min_speech_only_duration

    def _uncovered_speech(
        self, diar_segments: List[DiarizationSegment], aligned: List[AlignedUnit]
    ) -> List[AlignedUnit]:
        """
        Emits a timeline-only unit for diarised speech the recogniser produced no text for.

        This is a *timeline hint*, not a transcript. It says "the diariser heard
        someone here and the recogniser returned nothing", which is useful for
        showing audio coverage, but it carries no text.

        The floor is deliberately conservative, and the reason matters: a gap
        between two words is either a missed interjection or an ordinary pause, and
        the duration alone cannot tell them apart. A 250 ms "ah" and a 600 ms
        hesitation look identical here, so a low enough floor to catch the first
        would turn every pause in the conversation into an empty row. At 0.40 s a
        bare pause stays out of the transcript.

        Recovering the actual interjection is the job of
        :mod:`backend.pipeline.backchannel_rescue`, which re-decodes the region in
        isolation and only produces a token if there really is speech in it. That
        measures the content instead of guessing from the length, which is the only
        way to tell "avunu" from silence.
        """
        gaps: List[Tuple[float, float, DiarizationSegment]] = []
        for segment in diar_segments:
            duration = max(0.0, segment.end - segment.start)
            if duration <= 0:
                continue
            cursor = segment.start
            for unit in aligned:
                if unit.end <= cursor or unit.start >= segment.end:
                    continue
                if unit.speaker_id != segment.speaker_id:
                    continue
                if unit.start > cursor:
                    gaps.append((cursor, unit.start, segment))
                cursor = max(cursor, unit.end)
            if cursor < segment.end:
                gaps.append((cursor, segment.end, segment))

        units: List[AlignedUnit] = []
        for start, end, segment in gaps:
            floor = min(
                max(self.min_speech_only_duration, self.min_speech_only_coverage * (segment.end - segment.start)),
                segment.end - segment.start,
            )
            if end - start < floor:
                continue
            units.append(
                AlignedUnit(
                    text="",
                    start=start,
                    end=end,
                    speaker_id=segment.speaker_id,
                    confidence=segment.confidence,
                    is_final=True,
                    is_speech_only=True,
                )
            )
        return units

    def align(
        self,
        asr_result: ASRResult,
        diarization_result: DiarizationResult
    ) -> List[AlignedUnit]:
        """
        Assigns each recognised word to the diarisation segment it overlaps most.

        Words falling in a genuine gap keep the previous speaker when the gap is
        short (normal within-turn hesitation) and are left to the speech-only pass
        when it is not.
        """
        units: List[Tuple[str, float, float, Optional[float], bool, Optional[ASRToken]]] = []
        if asr_result.tokens:
            units = [
                (t.text, t.start, t.end, t.confidence, t.is_final, t)
                for t in asr_result.tokens
            ]
        elif asr_result.chunks:
            units = [
                (c.text, c.start, c.end, c.confidence, c.is_final, None)
                for c in asr_result.chunks
            ]

        diar_segments = sorted(diarization_result.segments, key=lambda d: d.start)
        aligned: List[AlignedUnit] = []
        last_speaker = diar_segments[0].speaker_id if diar_segments else "speaker_0"

        for text, u_start, u_end, conf, is_final, src_token in units:
            duration = max(0.001, u_end - u_start)
            overlaps: Dict[str, float] = {}
            for segment in diar_segments:
                overlap = max(0.0, min(u_end, segment.end) - max(u_start, segment.start))
                if overlap > 0:
                    overlaps[segment.speaker_id] = overlaps.get(segment.speaker_id, 0.0) + overlap

            if overlaps:
                best_speaker = max(overlaps.items(), key=lambda kv: kv[1])[0]
                concurrent = [
                    spk
                    for spk, ov in overlaps.items()
                    if ov >= max(0.08, 0.20 * duration)
                ]
                is_overlap = len(concurrent) > 1
                last_speaker = best_speaker
                aligned.append(
                    AlignedUnit(
                        text=text,
                        start=u_start,
                        end=u_end,
                        speaker_id=best_speaker,
                        confidence=conf,
                        is_final=is_final,
                        is_overlap=is_overlap,
                        overlap_speakers=concurrent if is_overlap else [],
                        source_token=src_token,
                    )
                )
            else:
                gap_distance = float("inf")
                nearest = None
                for segment in diar_segments:
                    distance = min(abs(u_start - segment.end), abs(segment.start - u_end))
                    if distance < gap_distance:
                        gap_distance = distance
                        nearest = segment
                assigned = (
                    nearest.speaker_id
                    if nearest is not None and gap_distance <= self.max_unattributed_gap
                    else last_speaker
                )
                last_speaker = assigned
                aligned.append(
                    AlignedUnit(
                        text=text,
                        start=u_start,
                        end=u_end,
                        speaker_id=assigned,
                        confidence=conf,
                        is_final=is_final,
                        source_token=src_token,
                    )
                )

        aligned.extend(self._uncovered_speech(diar_segments, aligned))
        aligned.sort(key=lambda unit: (unit.start, unit.end))
        return aligned
