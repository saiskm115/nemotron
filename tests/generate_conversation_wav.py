import asyncio
import io
import os
import edge_tts
import soundfile as sf
import numpy as np

OUTPUT_CONVERSATION_WAV = os.path.join(os.path.dirname(__file__), "fixtures", "telugu_english_conversation.wav")

async def generate_speech_audio(text: str, voice: str) -> np.ndarray:
    communicate = edge_tts.Communicate(text, voice)
    mp3_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_data += chunk["data"]
    
    # Read MP3 with soundfile
    data, sr = sf.read(io.BytesIO(mp3_data))
    if data.ndim > 1:
        data = data.mean(axis=1)
    
    # Resample to 16000 if needed
    if sr != 16000:
        # Simple resample using linear interpolation
        new_len = int(len(data) * 16000 / sr)
        data = np.interp(np.linspace(0, len(data), new_len, endpoint=False), np.arange(len(data)), data)
    return data.astype(np.float32)

async def build_conversation():
    print("Generating speech with edge-tts Mohan & Shruti...")
    # Mohan: turn 1
    t1 = await generate_speech_audio("నేను meeting కి 10 minutes late అవుతాను.", "te-IN-MohanNeural")
    # Priya: turn 2
    t2 = await generate_speech_audio("Okay, no problem. మీరు వచ్చిన తర్వాత start చేద్దాం.", "te-IN-ShrutiNeural")
    # Mohan: turn 3
    t3 = await generate_speech_audio("నాకు project deadline గురించి clarity లేదు.", "te-IN-MohanNeural")
    # Priya: turn 4
    t4 = await generate_speech_audio("Don't worry, Ramesh రేపు morning లో complete చేస్తాను అన్నారు.", "te-IN-ShrutiNeural")
    
    sr = 16000
    pause_0_5s = np.zeros(int(0.5 * sr), dtype=np.float32)
    pause_0_3s = np.zeros(int(0.3 * sr), dtype=np.float32)
    
    # Combine: 0.3s silence + t1 + 0.4s pause + t2 + 0.3s pause + t3 + 0.4s pause + t4 + 0.5s pause
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
    
    os.makedirs(os.path.dirname(OUTPUT_CONVERSATION_WAV), exist_ok=True)
    sf.write(OUTPUT_CONVERSATION_WAV, full_audio, sr, subtype='PCM_16')
    dur = len(full_audio) / sr
    print(f"Generated {OUTPUT_CONVERSATION_WAV} successfully! Duration: {dur:.2f}s")
    return OUTPUT_CONVERSATION_WAV, dur

if __name__ == "__main__":
    asyncio.run(build_conversation())
