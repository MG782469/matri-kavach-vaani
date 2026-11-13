"""One-command LIVE check of the whole voice-agent flow against real Gnani Prisma + Timbre.

Gnani Timbre plays the "worker" (it speaks "हाँ", "दूसरा", "रामपुर" ...) and those clips are sent
through the real app endpoints, exactly like browser recordings. A temporary database is used;
your saved cases are not touched.

    CMD:        set GNANI_API_KEY=<key>      then   py scripts\\live_smoke_test.py
    PowerShell: $env:GNANI_API_KEY="<key>"   then   py scripts\\live_smoke_test.py

Cost: about 9 Timbre calls + 5 Prisma calls. Prints PASS/FAIL per check and what Prisma heard.
"""
import io
import math
import os
import struct
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding='utf-8')

key = (os.getenv('GNANI_API_KEY') or '').strip().strip('"\'').strip()
if not key or key.lower() in {'yahan_key_paste_karo', 'yahan_asli_key', '<yahan asli key>'}:
    print('Set your real GNANI_API_KEY in this terminal first (see the docstring).'); raise SystemExit(2)
os.environ['GNANI_MODE'] = 'live'
os.environ['CASE_DB_PATH'] = str(Path(tempfile.mkdtemp()) / 'smoke.sqlite3')
os.environ.pop('DEMO_PUBLIC', None)

import requests  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app import main  # noqa: E402

client = TestClient(main.app)
results = []


def check(name, ok, detail=''):
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f'  — {detail}' if detail else ''))


def worker_says(text):
    """Timbre voice standing in for the health worker's microphone (16 kHz WAV)."""
    r = requests.post('https://api.vachana.ai/api/v1/tts/inference',
                      headers={'X-API-Key-ID': key, 'Content-Type': 'application/json'},
                      json={'text': text, 'model': 'timbre-v2.5', 'voice': 'Bhavna', 'language': 'hi-IN', 'speed': 0.9,
                            'audio_config': {'sample_rate': 16000, 'num_channels': 1, 'sample_width': 2,
                                             'encoding': 'linear_pcm', 'container': 'wav'}}, timeout=60)
    if r.status_code != 200:
        raise SystemExit(f'Timbre failed (HTTP {r.status_code}): {r.text[:200]} — run scripts\\check_gnani.py')
    return r.content


def silence(seconds=1.5):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b''.join(struct.pack('<h', int(30 * math.sin(i))) for i in range(int(16000 * seconds))))
    return buf.getvalue()


def answer(case, field, audio, path='/clarify'):
    return client.post(f"/api/cases/{case['id']}{path}", data={'field': field, 'expected_version': str(case['version'])},
                       files={'file': ('answer.wav', audio, 'audio/wav')})


def heard(r):
    j = r.json()
    if isinstance(j.get('detail'), str):
        return j['detail'][:110]
    return (j.get('clarified') or j.get('correction') or {}).get('heard', '')


print('Prisma profile:', main.profile_name(), '| Timbre model:', main.model_and_voice()[0], '\n')

# 1. Conflict: Timbre asks, "हाँ" is rejected, "दूसरा" picks the second number.
conflict_text = ('Patient ID: SMOKE-1, village: Rampur, contact: 9876543210, reason: transport coordination. '
                 'Sorry, contact number 9123456789.')
c = client.post('/api/cases/from-transcript', json={'transcript': conflict_text}).json()
check('conflict detected', c['conflicts'].get('contact') == ['9876543210', '9123456789'])
q = client.post(f"/api/cases/{c['id']}/clarification/audio", json={'expected_version': c['version'], 'field': 'contact'})
check('Timbre speaks the conflict question', q.status_code == 200 and q.content[:4] == b'RIFF',
      f'HTTP {q.status_code}, {len(q.content)} bytes')
r = answer(c, 'contact', worker_says('हाँ'))
check('"हाँ" is rejected and conflict stays open', r.status_code == 422, f'Prisma heard: {heard(r)}')
r = answer(c, 'contact', worker_says('दूसरा'))
ok = r.status_code == 200 and r.json()['fields']['contact'] == '9123456789'
check('"दूसरा" resolves to the second number', ok, f'Prisma heard: {heard(r)}')
if ok:
    x = r.json()
    check('both original numbers kept in history', x['resolutions'][0]['candidates'] == ['9876543210', '9123456789'])
    rb = client.post(f"/api/cases/{c['id']}/readback/audio", json={'expected_version': x['version']})
    check('Timbre read-back audio', rb.status_code == 200 and rb.content[:4] == b'RIFF', f'HTTP {rb.status_code}')
    cf = client.post(f"/api/cases/{c['id']}/confirm", json={'expected_version': x['version'], 'acknowledged': True})
    sb = client.post(f"/api/cases/{c['id']}/submit", json={'expected_version': x['version'], 'idempotency_key': 'smoke-test-0001'})
    check('confirm + simulated submit', cf.status_code == 200 and sb.status_code == 200 and sb.json()['submitted'])
    ev = sb.json()['evidence']
    check('evidence passport complete', ev['conflicts_resolved'] == 1 and ev['readback_current_version']
          and ev['timbre_audio_generated'] and ev['worker_confirmed_version'] == x['version'])

# 2. Missing village: the spoken answer fills ONLY the village.
m = client.post('/api/cases/from-transcript', json={'transcript': 'Patient ID: SMOKE-2, contact: 9876543210, reason: transport coordination'}).json()
check('missing village asked first', (m['clarification'] or {}).get('field') == 'village')
r = answer(m, 'village', worker_says('गाँव का नाम रामपुर है'))
ok = r.status_code == 200 and r.json()['fields']['village'] in ('रामपुर', 'Rampur')
check('spoken village fills only that field', ok and r.json()['fields']['contact'] == '9876543210', f'Prisma heard: {heard(r)}')

# 3. Silence never changes a case.
s = client.post('/api/cases/from-transcript', json={'transcript': 'Patient ID: SMOKE-3, contact: 9876543210, reason: transport coordination'}).json()
r = answer(s, 'village', silence())
check('silence -> "nothing heard", case unchanged', r.status_code == 422 and client.get(f"/api/cases/{s['id']}").json()['version'] == 0,
      f'HTTP {r.status_code}: {heard(r)}')

# 4. Voice correction is never applied silently.
v = client.post('/api/cases/from-transcript', json={'transcript': 'Patient ID: SMOKE-4, village: Rampur, contact: 9876543210, reason: transport coordination'}).json()
r = answer(v, 'village', worker_says('रामपुर नहीं, सोनपुर'), path='/correct')
ok = r.status_code == 200 and 'village' in r.json()['conflicts'] and r.json()['fields']['village'] == 'Rampur'
check('spoken correction becomes a conflict, not an overwrite', ok, f'Prisma heard: {heard(r)}')

print(f'\n{sum(results)}/{len(results)} checks passed.')
raise SystemExit(0 if all(results) else 1)
