import urllib.request
import io
import json
import soundfile as sf
import numpy as np

def run_test():
    sr = 16000
    t = np.linspace(0, 3.5, int(3.5 * sr), endpoint=False)
    sig = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, sig, sr, format='WAV', subtype='PCM_16')
    wav_bytes = buf.getvalue()

    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="meeting.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode('utf-8'),
        wav_bytes,
        f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\nTelugu + English Standup\r\n'.encode('utf-8'),
        f'--{boundary}\r\nContent-Disposition: form-data; name="asr_mode"\r\n\r\ncodemix\r\n'.encode('utf-8'),
        f'--{boundary}\r\nContent-Disposition: form-data; name="auto_translate"\r\n\r\ntrue\r\n'.encode('utf-8'),
        f'--{boundary}--\r\n'.encode('utf-8')
    ]
    body = b''.join(parts)

    req = urllib.request.Request(
        'http://127.0.0.1:8000/api/audio/upload',
        data=body,
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
    )

    print("Uploading audio to live FastAPI server...")
    res = urllib.request.urlopen(req)
    sess = json.loads(res.read().decode('utf-8'))
    print('SUCCESS! Upload processed.')
    print('Session ID:', sess['id'])
    print('Duration:', sess['duration'], 'seconds')
    print('Speakers attributed:', len(sess['speakers']))
    print('Turns built:', len(sess['turns']))

    for idx, t in enumerate(sess['turns'], 1):
        spk = next((s['display_name'] for s in sess['speakers'] if s['id'] == t['speaker_id']), t['speaker_id'])
        t_text = t['text'].encode('ascii', 'backslashreplace').decode('ascii')
        print(f"Turn {idx} [{spk}] ({t['start']}s - {t['end']}s): {t_text}")
        if t.get('translated_text'):
            print(f"   --> Translation: {t['translated_text']}")

    # Test SRT Export
    srt_url = f"http://127.0.0.1:8000/api/exports/{sess['id']}/srt?include_translation=true"
    srt_res = urllib.request.urlopen(srt_url)
    srt_data = srt_res.read().decode('utf-8')
    print("\n--- SRT EXPORT OUTPUT ---")
    print(srt_data.encode('ascii', 'backslashreplace').decode('ascii').strip())

    # Test DOCX Export
    docx_url = f"http://127.0.0.1:8000/api/exports/{sess['id']}/docx?include_translation=true"
    docx_res = urllib.request.urlopen(docx_url)
    docx_data = docx_res.read()
    print(f"\n--- DOCX EXPORT OK (Size: {len(docx_data)} bytes) ---")

if __name__ == '__main__':
    run_test()
