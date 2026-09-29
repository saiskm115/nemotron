"""
Energy-based voice activity detection with an adaptive noise floor.

Frame length 25 ms / hop 10 ms (the same framing convention used by WebRTC VAD),
noise floor estimated from the quietest decile of frames, and a hysteresis pair of
thresholds so a single loud consonant does not chop a word in half. Speech runs are
then closed with an explicit minimum-silence duration and a hangover tail, which is
what makes the resulting regions usable for both embedding extraction and ASR
alignment.
"""
import logging
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

FRAME_SEC = 0.025
HOP_SEC = 0.010
# Extra dB a frame must clear the noise floor by to count as speech.
SPEECH_MARGIN_DB = 6.0
# Hysteresis: once speaking, stay speaking until the frame drops this far.
EXIT_MARGIN_DB = 3.0
# Below this much dynamic range the file is treated as constant-level (no reliable VAD).
MIN_DYNAMIC_RANGE_DB = 6.0


def _frame_rms_db(y: np.ndarray, frame: int, hop: int) -> np.ndarray:
    if len(y) < frame:
        return np.zeros(0, dtype=np.float32)
    n_frames = 1 + (len(y) - frame) // hop
    # Strided view is far cheaper than a Python loop over hundreds of thousands of frames.
    shape = (n_frames, frame)
    strides = (y.strides[0] * hop, y.strides[0])
    frames = np.lib.stride_tricks.as_strided(y, shape=shape, strides=strides)
    rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
    return (20 * np.log10(rms + 1e-10)).astype(np.float32)


def detect_speech(
    y: np.ndarray,
    sr: int,
    min_speech_duration: float = 0.25,
    min_silence_duration: float = 0.20,
    pad: float = 0.10,
) -> List[Tuple[float, float]]:
    """Returns speech regions as (start_sec, end_sec) tuples."""
    frame = max(1, int(FRAME_SEC * sr))
    hop = max(1, int(HOP_SEC * sr))
    db = _frame_rms_db(np.asarray(y, dtype=np.float32), frame, hop)
    if db.size == 0:
        return []

    noise_floor = float(np.percentile(db, 10))
    peak_db = float(np.percentile(db, 95))
    if peak_db - noise_floor < MIN_DYNAMIC_RANGE_DB:
        # Uniform level (synthetic tone, heavy noise bed): treat the upper half as speech.
        enter_db = float(np.percentile(db, 50))
        exit_db = enter_db
    else:
        enter_db = noise_floor + SPEECH_MARGIN_DB
        exit_db = max(noise_floor + EXIT_MARGIN_DB, enter_db - EXIT_MARGIN_DB)

    active = np.zeros(db.shape, dtype=bool)
    speaking = False
    for i, value in enumerate(db):
        if speaking:
            speaking = value > exit_db
        else:
            speaking = value > enter_db
        active[i] = speaking

    min_speech_frames = max(1, int(round(min_speech_duration / HOP_SEC)))
    min_silence_frames = max(1, int(round(min_silence_duration / HOP_SEC)))

    regions: List[Tuple[float, float]] = []
    start: Optional[int] = None
    silence_run = 0

    for i, is_active in enumerate(active):
        if is_active:
            if start is None:
                start = i
            silence_run = 0
            continue
        if start is None:
            continue
        silence_run += 1
        if silence_run >= min_silence_frames:
            end = i - silence_run + 1
            if end - start >= min_speech_frames:
                regions.append((start, end))
            start = None
            silence_run = 0

    if start is not None:
        end = len(active)
        if end - start >= min_speech_frames:
            regions.append((start, end))

    pad_frames = int(round(pad / HOP_SEC))
    n_frames_total = max(len(y), 1)
    total_frames = 1 + (n_frames_total - frame) // hop if n_frames_total >= frame else 0
    total_sec = total_frames * HOP_SEC
    padded: List[Tuple[float, float]] = []
    for s, e in regions:
        s2 = max(0, s - pad_frames)
        e2 = min(total_frames, e + pad_frames)
        if e2 > s2:
            padded.append((s2 * HOP_SEC, min(e2 * HOP_SEC, total_sec)))
    return padded
