"""
Shared helpers for pipeline tests.

The tests need genuine two-speaker Telugu speech rather than synthesised tone
fixtures, because the whole point of these suites is that diarisation and
transcription agree with what was actually said. ``make_telugu_fixture.py``
renders that audio once; tests that need it are skipped when it is missing.
"""
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

from .make_telugu_fixture import DEFAULT_OUT, ground_truth

FIXTURE_PATH = DEFAULT_OUT

# Text each speaker actually says, in order.
FIXTURE_LINES = [
    "నమస్కారం, నా పేరు రమేష్. మీకు home loan గురించి ఎంత వస్తుంది?",
    "తెలుగు తెలుగు అయితే, డాక్యుమెంట్స్ submit చేయాల్సి ఉంటుంది.",
    "అవును, salary slip మరియు bank statement కావాలి.",
    "ఇంటి నుండి వచ్చేవాడు. ఇప్పుడే application చేస్తాను.",
    "ధన్యవాదాలు, ఆంటోపేయిడ్ కావాలి.",
    "కాదు, bank వచ్చి కలవడం మరో option.",
]
# English words that must survive as Latin script, not be transliterated.
EXPECTED_LATIN_WORDS = {"home", "loan", "documents", "submit", "salary", "bank", "application", "option"}


def _fixture_available() -> bool:
    return Path(FIXTURE_PATH).exists() and Path(FIXTURE_PATH).with_suffix(".truth.json").exists()


def truth_turns() -> List[dict]:
    return ground_truth(FIXTURE_PATH)


def truth_spans() -> List[Tuple[float, float, str]]:
    return [(t["start"], t["end"], t["speaker"]) for t in truth_turns()]


requires_fixture = pytest.mark.skipif(
    not _fixture_available(),
    reason=(
        "Telugu two-speaker fixture is missing. Generate it with "
        "`python -m backend.tests.make_telugu_fixture` (needs network access)."
    ),
)


def has_telugu(text: str) -> bool:
    return any("\u0C00" <= c <= "\u0C7F" for c in text)


def has_devanagari(text: str) -> bool:
    return any("\u0900" <= c <= "\u097F" for c in text)


def latin_words(text: str) -> set:
    return {w.strip(".,!?;:").lower() for w in text.split() if w[:1].isascii() and w[:1].isalpha()}


def speaker_sequence(segments, tolerance: float = 0.6) -> List[str]:
    """
    Ground-truth speaker for each segment, matched by best time overlap.

    A wrong label (speaker A's audio assigned to B) must fail; a boundary that is
    off by a few hundred milliseconds must not.
    """
    labels: List[str] = []
    for segment in segments:
        best_overlap = 0.0
        best_label: Optional[str] = None
        for truth_start, truth_end, truth_label in truth_spans():
            overlap = min(segment.end, truth_end + tolerance) - max(segment.start, truth_start - tolerance)
            if overlap > best_overlap:
                best_overlap = overlap
                best_label = truth_label
        labels.append(best_label or "unknown")
    return labels
