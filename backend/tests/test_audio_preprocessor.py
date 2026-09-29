import numpy as np
from backend.models.audio import AudioInput
from backend.pipeline.audio_preprocessor import (
    PEAK_MAX_BUCKETS,
    AudioPreprocessor,
)


def assert_valid_peak_pyramid(metadata):
    """The peak pyramid must be ordered coarse-to-fine, bounded and non-empty."""
    levels = metadata.peak_levels
    assert levels, "a waveform pyramid is required for the timeline"
    assert metadata.peaks == levels[0]
    counts = [len(level) for level in levels]
    assert counts == sorted(counts), f"levels must run coarse to fine, got {counts}"
    assert counts[0] <= PEAK_MAX_BUCKETS, "the payload must stay bounded regardless of length"
    assert all(count > 0 for count in counts)
    assert all(0.0 <= v <= 1.0 for level in levels for v in level)

def test_audio_preprocessor_synthetic_sine(tmp_path):
    # Generate 1 second 44.1kHz stereo audio
    sr_orig = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sr_orig * duration), endpoint=False)
    sine_wave = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    stereo_wave = np.column_stack([sine_wave, sine_wave * 0.8])

    import soundfile as sf
    test_wav = tmp_path / "test_orig.wav"
    sf.write(str(test_wav), stereo_wave, sr_orig)

    preprocessor = AudioPreprocessor(target_sample_rate=16000)
    audio_in = AudioInput(file_path=str(test_wav))
    out_wav = tmp_path / "test_16k.wav"

    y, metadata, pcm_bytes = preprocessor.process(audio_in, output_path=out_wav)

    # Assertions
    assert metadata.sample_rate == 16000
    assert metadata.channels == 1
    assert abs(metadata.duration_sec - 1.0) < 0.05
    assert len(y) == 16000
    assert len(pcm_bytes) == 16000 * 2 # 16-bit PCM = 2 bytes per sample
    assert_valid_peak_pyramid(metadata)
    assert out_wav.exists()

def test_stereo_is_downmixed_to_mono(tmp_path):
    # Left channel silent, right channel full scale: a downmix must average them,
    # not silently pick one channel.
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    right = (0.8 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    stereo = np.column_stack([np.zeros_like(right), right])

    import soundfile as sf
    path = tmp_path / "stereo.wav"
    sf.write(str(path), stereo, sr)

    y, metadata, _ = AudioPreprocessor().process(AudioInput(file_path=str(path)))
    assert metadata.channels == 1
    assert abs(float(np.max(np.abs(y))) - 0.4) < 0.02, "stereo must be averaged, not selected"

def test_dc_offset_is_removed(tmp_path):
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    biased = (0.3 * np.sin(2 * np.pi * 440 * t) + 0.25).astype(np.float32)

    import soundfile as sf
    path = tmp_path / "dc.wav"
    sf.write(str(path), biased, sr)

    y, metadata, _ = AudioPreprocessor().process(AudioInput(file_path=str(path)))
    assert abs(float(np.mean(y))) < 1e-3, "DC offset must be removed before the models see it"

def test_clipping_input_is_normalised(tmp_path):
    sr = 16000
    t = np.linspace(0, 1.0, sr, endpoint=False)
    loud = (4.0 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    import soundfile as sf
    path = tmp_path / "loud.wav"
    sf.write(str(path), loud, sr)

    y, metadata, _ = AudioPreprocessor().process(AudioInput(file_path=str(path)))
    assert float(np.max(np.abs(y))) <= 1.0, "out-of-range samples must be scaled, not wrapped"
    assert metadata.peak_db <= 0.1

def test_audio_preprocessor_aac_format(tmp_path):
    # Create an AAC audio file using PyAV
    import av
    sr = 16000
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    sine_wave = (0.4 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    test_aac = tmp_path / "call_recording.aac"
    with av.open(str(test_aac), mode='w', format='adts') as container:
        stream = container.add_stream('aac', rate=sr)
        stream.layout = 'mono'
        stream.format = 'fltp'
        frame = av.AudioFrame.from_ndarray(sine_wave.reshape(1, -1), format='fltp', layout='mono')
        frame.rate = sr
        for p in stream.encode(frame):
            container.mux(p)
        for p in stream.encode():
            container.mux(p)

    assert test_aac.exists()

    preprocessor = AudioPreprocessor(target_sample_rate=16000)
    audio_in = AudioInput(file_path=str(test_aac))
    out_wav = tmp_path / "call_recording_16k.wav"

    y, metadata, pcm_bytes = preprocessor.process(audio_in, output_path=out_wav)

    assert metadata.sample_rate == 16000
    assert metadata.channels == 1
    assert metadata.duration_sec > 0.9 and metadata.duration_sec < 1.2
    assert_valid_peak_pyramid(metadata)
    assert out_wav.exists()

def test_peak_pyramid_size_is_bounded_for_long_recordings():
    sr = 16000
    rng = np.random.default_rng(3)
    # 10 minutes of audio
    long_audio = (0.2 * rng.standard_normal(sr * 600)).astype(np.float32)
    levels = AudioPreprocessor()._compute_peak_levels(long_audio)
    counts = [len(level) for level in levels]
    assert counts[0] <= PEAK_MAX_BUCKETS
    assert sum(counts) <= PEAK_MAX_BUCKETS * 8, f"payload must stay bounded, got {sum(counts)} points"

def test_audio_preprocessor_raw_bytes(tmp_path):
    sr = 16000
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False, dtype=np.float32)
    sine = (0.5 * np.sin(2 * np.pi * 500 * t)).astype(np.float32)

    import io
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, sine, sr, format='WAV')
    wav_bytes = buf.getvalue()

    preprocessor = AudioPreprocessor(target_sample_rate=16000)
    audio_in = AudioInput(raw_bytes=wav_bytes)

    y, metadata, pcm_bytes = preprocessor.process(audio_in)

    assert metadata.sample_rate == 16000
    assert metadata.channels == 1
    assert abs(metadata.duration_sec - 0.5) < 0.05
    assert len(pcm_bytes) == len(y) * 2

