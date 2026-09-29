from backend.models.asr import ASRResult, ASRToken
from backend.models.diarization import DiarizationResult, DiarizationSegment
from backend.pipeline.alignment import AlignmentEngine

def test_alignment_two_speakers_clean_boundary():
    """
    Diarization:
    0.0 -> 2.4 speaker_0
    2.4 -> 4.8 speaker_1
    ASR:
    0.2 -> 1.1 "నమస్కారం"
    1.2 -> 2.2 "ఎలా ఉన్నారు"
    2.5 -> 3.4 "I am fine"
    3.6 -> 4.5 "thank you"
    """
    diar = DiarizationResult(
        segments=[
            DiarizationSegment(speaker_id="speaker_0", start=0.0, end=2.4),
            DiarizationSegment(speaker_id="speaker_1", start=2.4, end=4.8)
        ],
        speakers=["speaker_0", "speaker_1"]
    )

    tokens = [
        ASRToken(id="t1", text="నమస్కారం", start=0.2, end=1.1, is_final=True),
        ASRToken(id="t2", text="ఎలా ఉన్నారు", start=1.2, end=2.2, is_final=True),
        ASRToken(id="t3", text="I am fine", start=2.5, end=3.4, is_final=True),
        ASRToken(id="t4", text="thank you", start=3.6, end=4.5, is_final=True)
    ]
    asr = ASRResult(transcript="నమస్కారం ఎలా ఉన్నారు I am fine thank you", tokens=tokens)

    engine = AlignmentEngine()
    aligned = engine.align(asr, diar)

    assert len(aligned) == 4
    assert aligned[0].speaker_id == "speaker_0"
    assert aligned[1].speaker_id == "speaker_0"
    assert aligned[2].speaker_id == "speaker_1"
    assert aligned[3].speaker_id == "speaker_1"
    assert not any(u.is_overlap for u in aligned)

def test_alignment_overlapping_speech_barge_in():
    """
    Diarization:
    0.0 -> 3.0 speaker_0
    2.5 -> 5.0 speaker_1  (overlap between 2.5 and 3.0)
    ASR token at 2.6 -> 2.9 should be detected as overlapping speech!
    """
    diar = DiarizationResult(
        segments=[
            DiarizationSegment(speaker_id="speaker_0", start=0.0, end=3.0),
            DiarizationSegment(speaker_id="speaker_1", start=2.5, end=5.0)
        ],
        speakers=["speaker_0", "speaker_1"]
    )

    tokens = [
        ASRToken(id="t1", text="Mohan speaking", start=0.5, end=2.0, is_final=True),
        ASRToken(id="t2", text="Barge-in overlap word", start=2.6, end=2.9, is_final=True),
        ASRToken(id="t3", text="Priya continues", start=3.5, end=4.8, is_final=True)
    ]
    asr = ASRResult(transcript="Mohan speaking Barge-in overlap word Priya continues", tokens=tokens)

    engine = AlignmentEngine()
    aligned = engine.align(asr, diar)

    assert len(aligned) == 3
    assert aligned[0].speaker_id == "speaker_0"
    assert not aligned[0].is_overlap
    
    # Overlapping token must have is_overlap = True
    assert aligned[1].is_overlap
    assert len(aligned[1].overlap_speakers) >= 2
    assert "speaker_0" in aligned[1].overlap_speakers
    assert "speaker_1" in aligned[1].overlap_speakers

    assert aligned[2].speaker_id == "speaker_1"
    assert not aligned[2].is_overlap
