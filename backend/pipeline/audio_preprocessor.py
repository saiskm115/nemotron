import io
import math
from pathlib import Path
from typing import Tuple, List, Optional
import numpy as np
import soundfile as sf
import librosa
from ..models.audio import AudioMetadata, AudioInput

class AudioPreprocessor:
    def __init__(self, target_sample_rate: int = 16000):
        self.target_sample_rate = target_sample_rate

    def process(self, audio_input: AudioInput, output_path: Optional[Path] = None) -> Tuple[np.ndarray, AudioMetadata, bytes]:
        """
        Decodes, converts to mono, resamples to target_sample_rate (16kHz),
        computes metadata & waveform peaks, and returns (float_array, metadata, pcm_bytes).
        """
        if audio_input.file_path and Path(audio_input.file_path).exists():
            y, sr = librosa.load(audio_input.file_path, sr=self.target_sample_rate, mono=True)
        elif audio_input.raw_bytes:
            # Read from memory buffer
            buf = io.BytesIO(audio_input.raw_bytes)
            y, sr = sf.read(buf)
            # If multichannel, average to mono
            if y.ndim > 1:
                y = np.mean(y, axis=1)
            # Resample if needed
            if sr != self.target_sample_rate:
                y = librosa.resample(y, orig_sr=sr, target_sr=self.target_sample_rate)
        else:
            raise ValueError("AudioInput must contain either valid file_path or raw_bytes")

        # Ensure float32 normalized in [-1.0, 1.0]
        y = np.asarray(y, dtype=np.float32)
        max_val = np.max(np.abs(y)) if len(y) > 0 else 0
        if max_val > 1.0:
            y = y / max_val

        sample_count = len(y)
        duration_sec = sample_count / float(self.target_sample_rate) if self.target_sample_rate > 0 else 0.0

        # Compute RMS in dB
        rms = np.sqrt(np.mean(y ** 2)) if sample_count > 0 else 0.0
        rms_db = 20 * math.log10(rms + 1e-9)

        # Compute downsampled visual peaks for waveform UI (approx 800 buckets)
        peaks = self._compute_peaks(y, num_peaks=800)

        # Convert to 16-bit PCM (signed little-endian int16)
        y_int16 = (y * 32767.0).astype(np.int16)
        pcm_bytes = y_int16.tobytes()

        # If output_path provided, save standardized 16kHz mono WAV file
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output_path), y, self.target_sample_rate, subtype="PCM_16", format="WAV")

        metadata = AudioMetadata(
            duration_sec=round(duration_sec, 3),
            sample_rate=self.target_sample_rate,
            channels=1,
            sample_count=sample_count,
            rms_db=round(rms_db, 2),
            peaks=peaks
        )

        return y, metadata, pcm_bytes

    def _compute_peaks(self, y: np.ndarray, num_peaks: int = 800) -> List[float]:
        """Calculates normalized peak envelopes for responsive waveform UI rendering."""
        if len(y) == 0:
            return []
        if len(y) <= num_peaks:
            return [round(float(abs(v)), 3) for v in y]
        
        step = len(y) / float(num_peaks)
        peaks = []
        for i in range(num_peaks):
            start = int(i * step)
            end = int((i + 1) * step)
            chunk = y[start:end]
            if len(chunk) > 0:
                peaks.append(round(float(np.max(np.abs(chunk))), 3))
            else:
                peaks.append(0.0)
        return peaks

preprocessor = AudioPreprocessor(target_sample_rate=16000)
