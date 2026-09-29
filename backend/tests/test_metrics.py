"""Error-rate scoring used by the benchmark."""
from backend.metrics import cer, edit_distance, error_counts, latin_word_ratio, normalize_text, wer


def test_identical_text_scores_zero():
    text = "నమస్కారం home loan కావాలి"
    assert wer(text, text) == 0.0
    assert cer(text, text) == 0.0


def test_punctuation_and_case_are_ignored():
    assert wer("Hello, world!", "hello world") == 0.0
    assert cer("Hello, world!", "hello world") == 0.0


def test_word_errors_are_counted():
    # "a b c" -> "a x c": one substitution out of three reference words.
    assert abs(wer("a b c", "a x c") - 1 / 3) < 1e-9
    counts = error_counts("a b c", "a x c")
    assert counts["substitutions"] == 1
    assert counts["deletions"] == 0
    assert counts["insertions"] == 0


def test_deletions_and_insertions_are_separated():
    # WER is normalised by the reference length, so a deletion out of three reference
    # words costs 1/3 while the matching insertion costs 1/2 against two words.
    assert abs(wer("a b c", "a c") - 1 / 3) < 1e-9
    assert abs(wer("a c", "a b c") - 1 / 2) < 1e-9
    counts = error_counts("a b c", "a c")
    assert counts["deletions"] == 1
    assert error_counts("a c", "a b c")["insertions"] == 1


def test_empty_hypothesis_is_full_deletion_not_a_crash():
    assert abs(wer("a b c", "") - 1.0) < 1e-9
    assert error_counts("a b c", "")["deletions"] == 3


def test_extra_words_in_the_hypothesis_raise_wer_above_one():
    # Whisper emitting Telugu audio in Devanagari: every reference word is replaced
    # and extra words are added, so the score exceeds 100%. That has to be visible.
    assert wer("హలో వర్డ్", "नमस्ते शब्द अधिक") > 1.0


def test_a_wrong_script_scores_as_wrong_words():
    # Same words in the wrong script: every word is a substitution.
    assert wer("నమస్కారం రమేష్", "नमस्कारम रमेश") == 1.0
    assert error_counts("నమస్కారం రమేష్", "नमस्कारम रमेश")["substitutions"] == 2


def test_vowel_signs_survive_normalisation():
    # Telugu matras are Unicode category Mn, which \w does not match; stripping them
    # would silently turn one Telugu word into a different word.
    assert normalize_text("అప్లికేషన్") == "అప్లికేషన్"
    assert normalize_text("కావాలి,") == "కావాలి"


def test_edit_distance_is_symmetric():
    assert edit_distance(list("kitten"), list("sitting")) == 3
    assert edit_distance(list("sitting"), list("kitten")) == 3


def test_cer_is_more_forgiving_than_wer_on_partial_words():
    assert cer("అప్లికేషన్", "అప్లికేషన") < wer("అప్లికేషన్", "అప్లికేషన")


def test_normalisation_strips_zero_width_marks():
    assert normalize_text("హ\u200bలో") == "హలో"


def test_latin_ratio_marks_code_mixed_transcripts():
    latin, total = latin_word_ratio("మీకు home loan కావాలి")
    assert total == 4
    assert latin == 2
