"""Diagnose Gnani key / scope problems without printing the key.

Run in the SAME terminal where GNANI_API_KEY is set:
    py scripts\\check_gnani.py
Makes 1 tiny Prisma request (1 s tone) and up to 2 tiny Timbre requests ("नमस्ते").
Prints only HTTP status codes and Gnani's error message, never the key.
"""
import io
import math
import os
import struct
import sys
import wave

import requests

sys.stdout.reconfigure(encoding='utf-8')
raw = os.getenv('GNANI_API_KEY')
print('GNANI_MODE         :', os.getenv('GNANI_MODE'))
if not raw:
    print('GNANI_API_KEY      : NOT SET in this terminal'); raise SystemExit(1)
key = raw.strip().strip('"\'').strip()
print('Key length         :', len(raw), '->', len(key), 'after cleaning')
print('Had quotes/spaces  :', raw != key)
print('Looks like template:', key.lower() in {'yahan_key_paste_karo', '<tumhari key>', 'your-key', 'changeme'})


def show(name, r):
    body = r.content[:300]
    ctype = r.headers.get('content-type', '')
    text = body.decode('utf-8', 'replace') if ('json' in ctype or 'text' in ctype) else f'<{len(r.content)} bytes {ctype}>'
    print(f'{name:<19}: HTTP {r.status_code}  {text}')
    return r.status_code


buf = io.BytesIO()
with wave.open(buf, 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(b''.join(struct.pack('<h', int(8000 * math.sin(2 * math.pi * 440 * i / 16000))) for i in range(16000)))
try:
    r = requests.post('https://api.vachana.ai/stt/v3', headers={'X-API-Key-ID': key},
                      data={'language_code': 'hi-IN', 'format': 'transcribe'},
                      files={'audio_file': ('tone.wav', buf.getvalue(), 'audio/wav')}, timeout=30)
    show('Prisma STT', r)
except requests.RequestException as e:
    print('Prisma STT         : network error', type(e).__name__)

for model, voice in (('timbre-v2.5', 'Nalini'), ('timbre-v3.0', 'Shivani')):
    try:
        r = requests.post('https://api.vachana.ai/api/v1/tts/inference',
                          headers={'X-API-Key-ID': key, 'Content-Type': 'application/json'},
                          json={'text': 'नमस्ते', 'model': model, 'voice': voice, 'language': 'hi-IN',
                                'audio_config': {'sample_rate': 24000, 'num_channels': 1, 'sample_width': 2,
                                                 'encoding': 'linear_pcm', 'container': 'wav'}}, timeout=30)
        if show(f'Timbre {model}', r) == 200:
            break
    except requests.RequestException as e:
        print(f'Timbre {model:<12}: network error', type(e).__name__)
