import io
import logging
import math
from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np
import soundfile as sf
import librosa

try:
    import av
except ImportError:
    av = None

from ..models.audio import AudioInput, AudioMetadata

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16000

# Peaks are stored as a small pyramid: level 0 is the coarse overview the timeline
# draws first and each following level doubles the resolution. The waveform view
# picks the level that matches its zoom, so zooming in reveals real detail instead
# of magnifying an 800-point envelope.
#
# Levels are capped so the payload stays small regardless of recording length. A
# production deployment that needs detail finer than ~2048 points across the visible
# window should serve peaks from a range endpoint (start/duration/width) instead.
PEAK_MIN_BUCKETS = 512
PEAK_MAX_BUCKETS = 2048


class AudioPreprocessor:
    def __init__(self, target_sample_rate: int = TARGET_SAMPLE_RATE):
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
            audio_stream = next((s for s in container.streams if s.type == "audio"), None)
            if audio_stream is None:
                logger.warning("PyAV: No audio stream found in media container")
                return None

            # Resample in the source's own channel layout and average the channels
            # explicitly. Asking PyAV for a mono output instead applies libswresample's
            # default stereo->mono matrix of [0.707, 0.707], which preserves RMS: a
            # dual-mic call recording with speech on one channel comes out 3 dB quiet
            # and an out-of-phase stereo pair is summed, not cancelled.
            resampler = av.AudioResampler(format="fltp", rate=self.target_sample_rate)

            chunks: List[np.ndarray] = []
            for frame in container.decode(audio_stream):
                for resampled_frame in resampler.resample(frame):
                    chunks.append(_to_mono(resampled_frame))

            for resampled_frame in resampler.resample(None):
                chunks.append(_to_mono(resampled_frame))

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
                # If soundfile fails, try librosa (audioread/ffmpeg backend)
                y, sr = librosa.load(path_str, sr=self.target_sample_rate, mono=True)
                return np.asarray(y, dtype=np.float32)

        if y.ndim > 1:
            y = np.mean(y, axis=1)

        if sr != self.target_sample_rate:
            y = librosa.resample(y.astype(np.float32), orig_sr=sr, target_sr=self.target_sample_rate)

        return np.asarray(y, dtype=np.float32)

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

        y = self._decode_with_pyav(source)

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

        return self._condition(y)

    def _condition(self, y: np.ndarray) -> np.ndarray:
        """
        Sample conditioning applied to every signal before it reaches a model.

        Removes DC offset, clips defensively and peak-normalises anything that would
        otherwise clip. Speech recognition quality on telephone audio degrades badly
        without this, and it is also what keeps the RMS dBFS reported to the UI honest.
        """
        y = np.asarray(y, dtype=np.float32)
        if y.size == 0:
            return y

        dc = float(np.mean(y))
        if abs(dc) > 1e-4:
            y = y - dc

        peak = float(np.max(np.abs(y)))
        if peak > 1.0:
            y = y / peak

        return np.ascontiguousarray(y, dtype=np.float32)

    def process(self, audio_input: AudioInput, output_path: Optional[Path] = None) -> Tuple[np.ndarray, AudioMetadata, bytes]:
        """
        Decodes, converts to mono, resamples to target_sample_rate (16kHz),
        computes metadata & waveform peaks, and returns (float_array, metadata, pcm_bytes).
        """
        y = self.load_audio(audio_input)

        sample_count = len(y)
        duration_sec = sample_count / float(self.target_sample_rate) if self.target_sample_rate > 0 else 0.0

        rms = float(np.sqrt(np.mean(y.astype(np.float64) ** 2))) if sample_count else 0.0
        rms_db = 20 * math.log10(rms + 1e-9)
        peak = float(np.max(np.abs(y))) if sample_count else 0.0
        peak_db = 20 * math.log10(peak + 1e-9)

        peak_levels = self._compute_peak_levels(y)

        y_int16 = np.clip(y * 32767.0, -32768, 32767).astype(np.int16)
        pcm_bytes = y_int16.tobytes()

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output_path), y, self.target_sample_rate, subtype="PCM_16", format="WAV")

        metadata = AudioMetadata(
            duration_sec=round(duration_sec, 3),
            sample_rate=self.target_sample_rate,
            channels=1,
            sample_count=sample_count,
            rms_db=round(rms_db, 2),
            peaks=peak_levels[0],
            peak_levels=peak_levels,
            peak_db=round(peak_db, 2),
        )

        return y, metadata, pcm_bytes

    def _compute_peak_levels(self, y: np.ndarray) -> List[List[float]]:
        """
        Builds a mip-mapped peak pyramid, coarsest first.

        Each level doubles the bucket count up to ``PEAK_MAX_BUCKETS``, so the total
        payload is bounded no matter how long the recording is.
        """
        if len(y) == 0:
            return []

        magnitudes = np.abs(y.astype(np.float32))
        buckets = min(PEAK_MIN_BUCKETS, max(1, len(magnitudes)))
        levels: List[List[float]] = []

        while True:
            bucket_size = max(1, -(-len(magnitudes) // buckets))  # ceil division
            levels.append(_downsample_peaks(magnitudes, bucket_size))
            if buckets >= PEAK_MAX_BUCKETS or buckets >= len(magnitudes):
                break
            buckets = min(buckets * 2, PEAK_MAX_BUCKETS)

        return levels


def _to_mono(frame) -> np.ndarray:
    """
    One resampled frame as mono float32.

    ``to_ndarray`` returns planar ``(channels, samples)`` for float formats and a
    flat interleaved ``(1, channels * samples)`` for packed ones, so both shapes are
    handled before averaging.
    """
    data = frame.to_ndarray()
    if data.shape[0] == 1:
        if frame.layout.nb_channels > 1:
            data = data.reshape(-1, frame.layout.nb_channels).T
        else:
            return data[0].astype(np.float32, copy=False)
    return data.mean(axis=0).astype(np.float32, copy=False)


def _downsample_peaks(values: np.ndarray, bucket: int) -> List[float]:
    if values.size == 0:
        return []
    if bucket <= 1:
        return [round(float(v), 3) for v in values]
    usable = (values.size // bucket) * bucket
    if usable == 0:
        return [round(float(values.max()), 3)]
    folded = values[:usable].reshape(-1, bucket).max(axis=1)
    return [round(float(v), 3) for v in folded]


preprocessor = AudioPreprocessor(target_sample_rate=TARGET_SAMPLE_RATE)
