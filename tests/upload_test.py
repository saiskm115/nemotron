import urllib.request, json

wav_path = 'tests/fixtures/telugu_english_conversation.wav'
with open(wav_path, 'rb') as f:
    wav_bytes = f.read()

boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
parts = [
    f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="telugu_english_conversation.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode('utf-8'),
    wav_bytes,
    f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\nTelugu + English Conversation Standup\r\n'.encode('utf-8'),
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
res = urllib.request.urlopen(req)
sess = json.loads(res.read().decode('utf-8'))
print('SUCCESS! Session ID:', sess['id'])
print('Duration:', sess['duration'])
print('Speakers:', len(sess['speakers']))
for s in sess['speakers']:
    print(f"  Speaker: {s['id']} ({s['display_name']}) - {s['total_speaking_time']}s")
print('Turns:', len(sess['turns']))
for t in sess['turns']:
    print(f"  [{t['start']} -> {t['end']}] {t['speaker_id']}: {t['text']}")
