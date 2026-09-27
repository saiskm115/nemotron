import pytest
from backend.pipeline.alignment import parse_language_segments

def test_pure_telugu():
    text = "మీరు ఎక్కడికి వెళ్తున్నారు?"
    segments, is_code_mixed = parse_language_segments(text)
    assert not is_code_mixed
    assert len(segments) == 1
    assert segments[0].language == "te"

def test_code_mixed_telugu_english():
    text = "నాకు project deadline గురించి clarity లేదు."
    segments, is_code_mixed = parse_language_segments(text)
    assert is_code_mixed
    
    # Verify segments correctly separate Telugu and English
    languages = [s.language for s in segments]
    assert "te" in languages
    assert "en" in languages

    # "project deadline" should be categorized as en
    en_segs = [s.text for s in segments if s.language == "en"]
    assert any("project" in s for s in en_segs)

def test_telugu_with_english_fillers_and_numbers():
    text = "నేను meeting కి 10 minutes late అవుతాను."
    segments, is_code_mixed = parse_language_segments(text)
    assert is_code_mixed
    # Verify both Telugu and English tokens are identified
    assert any(s.language == "te" for s in segments)
    assert any(s.language == "en" for s in segments)

def test_verbatim_sentence_with_hesitation():
    text = "అది... actually నేను... అంటే రేపు office కి వస్తాను."
    segments, is_code_mixed = parse_language_segments(text)
    assert is_code_mixed
    assert any("actually" in s.text for s in segments)
