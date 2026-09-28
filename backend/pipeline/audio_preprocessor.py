import io
import math
import logging
from pathlib import Path
from typing import Tuple, List, Optional, Union
import numpy as np
import soundfile as sf
import librosa

try:
    import av
except ImportError:
    av = None

from ..models.audio import AudioMetadata, AudioInput

logger = logging.getLogger(__name__)

class AudioPreprocessor:
    def __init__(self, target_sample_rate: int = 16000):
        self.target_sample_rate = target_sample_rate

    def _decode_with_pyav(self, source: Union[str, Path, bytes, bytearray]) -> Optional[np.ndarray]:
        """
        Decodes any media container/codec supported by FFmpeg/PyAV
        (including call recording formats: AAC, M4A, MP4, AMR-NB, AMR-WB, 3GP,
        Opus, OGG, MP3, FLAC, WAV, WMA, WebM, CAF, AIFF, etc.) and resamples
        directly to target_sample_rate mono float32 array in memory.
        """
        if av is None:
            return None

        container = None
        try:
            if isinstance(source, (bytes, bytearray)):
                io_source = io.BytesIO(source)
            elif isinstance(source, Path):
                io_source = str(source)
            else:
                io_source = source

            container = av.open(io_source)
            # Find the primary audio stream
            audio_stream = next((s for s in container.streams if s.type == "audio"), None)
            if audio_stream is None:
                logger.warning("PyAV: No audio stream found in media container")
                return None

            # AudioResampler downmixes multichannel (stereo, dual-mic telephony) to mono
            # and resamples to target_sample_rate (16000 Hz)
            resampler = av.AudioResampler(
                format="fltp",
                layout="mono",
                rate=self.target_sample_rate
            )

            chunks: List[np.ndarray] = []
            for frame in container.decode(audio_stream):
                for resampled_frame in resampler.resample(frame):
                    chunks.append(resampled_frame.to_ndarray()[0])

            # Flush resampler buffer
            for resampled_frame in resampler.resample(None):
                chunks.append(resampled_frame.to_ndarray()[0])

            if not chunks:
                return np.zeros(0, dtype=np.float32)

            return np.concatenate(chunks).astype(np.float32)
        except Exception as e:
            logger.info(f"PyAV decode not applicable or failed ({e}); trying standard audio decoders...")
            return None
        finally:
            if container is not None:
                try:
                    container.close()
                except Exception:
                    pass

    def _decode_fallback(self, source: Union[str, Path, bytes, bytearray]) -> np.ndarray:
        """
        Fallback decoder using soundfile and librosa when PyAV is unavailable or fails.
        """
        if isinstance(source, (bytes, bytearray)):
            buf = io.BytesIO(source)
            y, sr = sf.read(buf)
        else:
            path_str = str(source)
            try:
                y, sr = sf.read(path_str)
            except Exception:
                # If soundfile fails, try librosa
                y, sr = librosa.load(path_str, sr=self.target_sample_rate, mono=True)
                return y.astype(np.float32)

        # Average multichannel to mono if needed
        if y.ndim > 1:
            y = np.mean(y, axis=1)

        # Resample if needed
        if sr != self.target_sample_rate:
            y = librosa.resample(y.astype(np.float32), orig_sr=sr, target_sr=self.target_sample_rate)

        return y.astype(np.float32)

    def load_audio(self, audio_input: AudioInput) -> np.ndarray:
        """
        Loads audio from file_path or raw_bytes, supporting all call recording formats.
        Returns a 1D float32 numpy array at target_sample_rate.
        """
        if audio_input.file_path and Path(audio_input.file_path).exists():
            source: Union[str, bytes] = str(audio_input.file_path)
        elif audio_input.raw_bytes:
            source = audio_input.raw_bytes
        else:
            raise ValueError("AudioInput must contain either valid file_path or raw_bytes")

        # 1. Try PyAV first (covers AAC, M4A, AMR, 3GP, OPUS, WAV, MP3, etc.)
        y = self._decode_with_pyav(source)

        # 2. If PyAV wasn't available or couldn't decode, use fallback
        if y is None:
            try:
                y = self._decode_fallback(source)
            except Exception as e:
                raise ValueError(
                    f"Failed to decode audio file. Supported formats include: "
                    f"Call recordings (.aac, .m4a, .amr, .3gp, .opus), "
                    f"Standard audio (.wav, .mp3, .ogg, .flac, .wma, .webm, .caf). "
                    f"Decoder error: {e}"
                )

        return y

    def process(self, audio_input: AudioInput, output_path: Optional[Path] = None) -> Tuple[np.ndarray, AudioMetadata, bytes]:
        """
        Decodes, converts to mono, resamples to target_sample_rate (16kHz),
        computes metadata & waveform peaks, and returns (float_array, metadata, pcm_bytes).
        """
        y = self.load_audio(audio_input)

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
