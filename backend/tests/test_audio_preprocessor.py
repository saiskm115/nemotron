import numpy as np
import pytest
from backend.models.audio import AudioInput
from backend.pipeline.audio_preprocessor import AudioPreprocessor

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
    assert len(metadata.peaks) == 800
    assert out_wav.exists()

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
    assert len(metadata.peaks) == 800
    assert out_wav.exists()

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

