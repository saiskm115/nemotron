"""
Generates a real two-speaker Telugu (+ English code-mixed) call recording.

The tests validate diarisation and transcription against what was actually said,
so they need genuine speech rather than synthesised tone fixtures. Each turn is
rendered with a different neural voice, so the two speakers are acoustically
distinct the way two people are.

The renderer writes a JSON sidecar next to the WAV holding the exact turn
boundaries it used. Ground truth is therefore read from the same run that produced
the audio and can never drift out of step with it.

    python -m backend.tests.make_telugu_fixture [output.wav]
"""
import asyncio
import json
import tempfile
from pathlib import Path
from typing import List, Tuple

import numpy as np
import soundfile as sf

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUT = BASE_DIR / "data" / "fixtures" / "telugu_call_2spk.wav"
SAMPLE_RATE = 16000
LEAD_IN_SEC = 0.25

# Two distinct Telugu voices (male / female), each speaking the way people actually
# do in Indian call centres: Telugu with English product terms left in English.
SCRIPT: List[Tuple[str, str, float]] = [
    ("te-IN-MohanNeural", "నమస్కారం, నా పేరు రమేష్. మీకు home loan గురించి ఎంత వస్తుంది?", 0.30),
    ("te-IN-ShrutiNeural", "తెలుగు తెలుగు అయితే, డాక్యుమెంట్స్ submit చేయాల్సి ఉంటుంది.", 0.55),
    ("te-IN-MohanNeural", "అవును, salary slip మరియు bank statement కావాలి.", 0.45),
    ("te-IN-ShrutiNeural", "ఇంటి నుండి వచ్చేవాడు. ఇప్పుడే application చేస్తాను.", 0.40),
    ("te-IN-MohanNeural", "ధన్యవాదాలు, ఆంటోపేయిడ్ కావాలి.", 0.35),
    ("te-IN-ShrutiNeural", "కాదు, bank వచ్చి కలవడం మరో option.", 0.30),
]


async def _synthesize(tmp_dir: Path) -> List[Tuple[Path, str, float]]:
    import edge_tts

    parts = []
    for idx, (voice, text, gap) in enumerate(SCRIPT):
        out = tmp_dir / f"part_{idx:02d}.mp3"
        await edge_tts.Communicate(text, voice).save(str(out))
        parts.append((out, voice, gap))
    return parts


def _decode(path: Path) -> np.ndarray:
    """Decode an edge-tts output to 16 kHz mono float32 via PyAV."""
    import av

    container = av.open(str(path))
    stream = next(s for s in container.streams if s.type == "audio")
    resampler = av.AudioResampler(format="fltp", layout="mono", rate=SAMPLE_RATE)
    chunks = []
    for frame in container.decode(stream):
        for rf in resampler.resample(frame):
            chunks.append(rf.to_ndarray()[0])
    for rf in resampler.resample(None):
        chunks.append(rf.to_ndarray()[0])
    container.close()
    return np.concatenate(chunks).astype(np.float32) if chunks else np.zeros(0, np.float32)


def build(out_path: Path = DEFAULT_OUT) -> Tuple[Path, List[dict]]:
    """Renders the call and returns (wav_path, turns) from a single pass."""
    with tempfile.TemporaryDirectory() as td:
        parts = asyncio.run(_synthesize(Path(td)))

        gap_samples = lambda seconds: np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32)

        audio = gap_samples(LEAD_IN_SEC)
        turns: List[dict] = []
        cursor = LEAD_IN_SEC

        for (mp3, voice, gap), (script_voice, text, script_gap) in zip(parts, SCRIPT):
            assert voice == script_voice, "synthesised voices must match the script"
            y = _decode(Path(mp3))
            duration = len(y) / SAMPLE_RATE
            turns.append(
                {
                    "start": round(cursor, 3),
                    "end": round(cursor + duration, 3),
                    "speaker": "speaker_0" if voice == "te-IN-MohanNeural" else "speaker_1",
                    "voice": voice,
                    "text": text,
                }
            )
            audio = np.concatenate([audio, y, gap_samples(gap)])
            cursor += duration + gap

    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        audio = audio / peak * 0.89

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), audio, SAMPLE_RATE, subtype="PCM_16")
    out_path.with_suffix(".truth.json").write_text(
        json.dumps(turns, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_path, turns


def ground_truth(out_path: Path = DEFAULT_OUT) -> List[dict]:
    """
    Exact turn boundaries of the rendered audio.

    Read from the sidecar written by the same pass that produced the WAV, so the
    labels can never describe a different rendering than the audio.
    """
    sidecar = out_path.with_suffix(".truth.json")
    if out_path.exists() and sidecar.exists():
        return json.loads(sidecar.read_text(encoding="utf-8"))
    _, turns = build(out_path)
    return turns


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    path, truth = build(target)
    info = sf.info(str(path))
    print(f"Wrote {path} ({info.duration:.2f}s @ {info.samplerate}Hz {info.subtype})")
    for turn in truth:
        print(f"  {turn['speaker']}  {turn['start']:6.2f} - {turn['end']:6.2f}  {turn['text']}")
