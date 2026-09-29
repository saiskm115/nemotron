"""
Error-rate metrics for comparing speech-to-text engines.

Standard definitions:
  * WER  — Levenshtein distance over whitespace-delimited words, divided by the
           number of reference words.
  * CER  — the same over characters, which is the more informative number for
           languages the model segments poorly.

Both can be capped so a runaway hypothesis produces a finite score.
"""
import unicodedata
from typing import Dict, List, Tuple

# Combining marks (category M*) carry the vowel signs of Telugu, Devanagari and the
# other Brahmic scripts. Python's \w does not match them, so a regex-based punctuation
# strip deletes every matra and turns a Telugu word into a different word. Unicode
# categories are used instead: only punctuation, symbols, separators and control
# characters are dropped.
_DROPPED_CATEGORIES = ("P", "S", "Z", "C")


def normalize_text(text: str, lowercase_latin: bool = True) -> str:
    """NFC-normalises, removes invisible format characters and punctuation."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
    if lowercase_latin:
        text = "".join(c.lower() if "A" <= c <= "Z" else c for c in text)
    text = "".join(" " if unicodedata.category(ch)[0] in _DROPPED_CATEGORIES else ch for ch in text)
    return " ".join(text.split())


def edit_distance(reference: List[str], hypothesis: List[str]) -> int:
    """Levenshtein distance with a single rolling row."""
    if not reference:
        return len(hypothesis)
    if not hypothesis:
        return len(reference)

    previous = list(range(len(hypothesis) + 1))
    for i, ref_token in enumerate(reference, start=1):
        current = [i]
        for j, hyp_token in enumerate(hypothesis, start=1):
            insert = current[j - 1] + 1
            delete = previous[j] + 1
            substitute = previous[j - 1] + (ref_token != hyp_token)
            current.append(min(insert, delete, substitute))
        previous = current
    return previous[-1]


def wer(reference: str, hypothesis: str, max_rate: float = 10.0) -> float:
    ref = normalize_text(reference).split()
    hyp = normalize_text(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else max_rate
    return min(max_rate, edit_distance(ref, hyp) / len(ref))


def cer(reference: str, hypothesis: str, max_rate: float = 10.0) -> float:
    ref = normalize_text(reference).replace(" ", "")
    hyp = normalize_text(hypothesis).replace(" ", "")
    if not ref:
        return 0.0 if not hyp else max_rate
    return min(max_rate, edit_distance(list(ref), list(hyp)) / len(ref))


def error_counts(reference: str, hypothesis: str) -> Dict[str, int]:
    """Substitution / deletion / insertion breakdown for a word-level alignment."""
    ref = normalize_text(reference).split()
    hyp = normalize_text(hypothesis).split()

    rows, cols = len(ref), len(hyp)
    distances = [[0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(rows + 1):
        distances[i][0] = i
    for j in range(cols + 1):
        distances[0][j] = j

    for i in range(1, rows + 1):
        for j in range(1, cols + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            distances[i][j] = min(
                distances[i - 1][j] + 1,
                distances[i][j - 1] + 1,
                distances[i - 1][j - 1] + cost,
            )

    substitutions = deletions = insertions = 0
    i, j = rows, cols
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            if distances[i][j] == distances[i - 1][j - 1] + cost:
                if cost:
                    substitutions += 1
                i, j = i - 1, j - 1
                continue
        if i > 0 and distances[i][j] == distances[i - 1][j] + 1:
            deletions += 1
            i -= 1
            continue
        insertions += 1
        j -= 1

    return {
        "substitutions": substitutions,
        "deletions": deletions,
        "insertions": insertions,
        "reference_words": rows,
        "hypothesis_words": cols,
    }


def latin_word_ratio(text: str) -> Tuple[float, float]:
    """(latin words, total words) — how much of a transcript stayed in Latin script."""
    words = normalize_text(text, lowercase_latin=False).split()
    if not words:
        return 0.0, 0.0
    latin = sum(1 for w in words if any("a" <= c.lower() <= "z" for c in w))
    return latin, len(words)
