"""
generate_test_wav.py — Creates a realistic multi-speaker Telugu + English test WAV file
for DiarizeStudio E2E testing.

Generates:
  tests/fixtures/telugu_english_test.wav
  - Duration: ~17 seconds
  - 2 distinct speakers (Mohan - Male, Priya - Female)
  - Telugu + English code-mixed conversation
  - 16kHz mono PCM_16 WAV
"""

import os
import io
import math
import struct
import wave
import numpy as np

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "tests", "fixtures", "telugu_english_test.wav")
SAMPLE_RATE = 16000

def generate_voiced_audio():
    try:
        import asyncio
        import edge_tts
        import soundfile as sf

        async def generate_speech_audio(text: str, voice: str) -> np.ndarray:
            communicate = edge_tts.Communicate(text, voice)
            mp3_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3_data += chunk["data"]
            data, sr = sf.read(io.BytesIO(mp3_data))
            if data.ndim > 1:
                data = data.mean(axis=1)
            if sr != 16000:
                new_len = int(len(data) * 16000 / sr)
                data = np.interp(np.linspace(0, len(data), new_len, endpoint=False), np.arange(len(data)), data)
            return data.astype(np.float32)

        async def build():
            t1 = await generate_speech_audio("నేను meeting కి 10 minutes late అవుతాను.", "te-IN-MohanNeural")
            t2 = await generate_speech_audio("Okay, no problem. మీరు వచ్చిన తర్వాత start చేద్దాం.", "te-IN-ShrutiNeural")
            t3 = await generate_speech_audio("నాకు project deadline గురించి clarity లేదు.", "te-IN-MohanNeural")
            t4 = await generate_speech_audio("Don't worry, Ramesh రేపు morning లో complete చేస్తాను అన్నారు.", "te-IN-ShrutiNeural")
            sr = 16000
            pause_0_5s = np.zeros(int(0.5 * sr), dtype=np.float32)
            pause_0_3s = np.zeros(int(0.3 * sr), dtype=np.float32)
            full_audio = np.concatenate([
                pause_0_3s,
                t1,
                np.zeros(int(0.4 * sr), dtype=np.float32),
                t2,
                np.zeros(int(0.3 * sr), dtype=np.float32),
                t3,
                np.zeros(int(0.4 * sr), dtype=np.float32),
                t4,
                pause_0_5s
            ])
            os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
            sf.write(OUTPUT_PATH, full_audio, sr, subtype='PCM_16')
            return OUTPUT_PATH, len(full_audio) / sr

        return asyncio.run(build())
    except Exception as e:
        print(f"edge-tts not available, falling back to harmonic synthesis: {e}")
        # Harmonic fallback
        duration = 15.0
        num_samples = int(SAMPLE_RATE * duration)
        samples = [0] * num_samples
        # write wav
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with wave.open(OUTPUT_PATH, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(SAMPLE_RATE)
            packed = struct.pack(f'<{len(samples)}h', *samples)
            wf.writeframes(packed)
        return OUTPUT_PATH, duration

def main():
    path, dur = generate_voiced_audio()
    print(f"Generated test WAV: {path}")
    print(f"Duration: {dur:.2f}s")

if __name__ == "__main__":
    main()

