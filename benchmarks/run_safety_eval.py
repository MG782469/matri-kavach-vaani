"""False-ready safety evaluation of the referral workflow (offline, mock mode, synthetic data).

Question answered: can an incomplete, contradictory, unreviewed or stale draft ever become a
submitted referral? Every scenario tries to get a referral through the API the wrong way.

  A. Fixture sweep   - every synthetic transcript (+ adversarial ones) is pushed straight to
                       read-back -> confirm -> submit with NO human correction. A submission
                       whose fields differ from the expected truth is a FALSE-READY.
  B. Bypass attempts - skip read-back, skip acknowledgement, confirm a stale version, edit after
                       confirm, submit with an open conflict, reuse an idempotency key, etc.
  C. Non-answers     - fillers ("हाँ", "ok", "kya") and silence-like replies to the assistant
                       must never fill a field or settle a conflict.

This measures workflow guardrails, NOT speech-recognition accuracy or clinical safety.
Run: py benchmarks\\run_safety_eval.py   -> benchmarks/results/safety_eval_report.md
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ADVERSARIAL = [
    {'id': 'adv_two_contacts', 'transcript': 'Patient ID: A1, village: Rampur, contact: 9876543210, contact number 9123456789, reason: transport coordination'},
    {'id': 'adv_two_villages', 'transcript': 'मरीज रामगढ़ गाँव से है, patient ID 77, contact 9876543210. sorry, village: Rampur, reason: transport coordination'},
    {'id': 'adv_two_ids', 'transcript': 'Patient ID: 1024, patient ID: 2048, village: Rampur, contact: 9876543210, reason: transport coordination'},
    {'id': 'adv_landline_like', 'transcript': 'Patient ID: A2, village: Rampur, contact: 1234567890, reason: transport coordination'},
    {'id': 'adv_nine_digits', 'transcript': 'Patient ID: A3, village: Rampur, contact: 987654321, reason: transport coordination'},
    {'id': 'adv_zeros', 'transcript': 'Patient ID: A4, village: Rampur, contact: 0000000000, reason: transport coordination'},
    {'id': 'adv_no_markers', 'transcript': 'रामपुर की मरीज़ है, नंबर नौ आठ सात छह पाँच चार तीन दो एक शून्य, अस्पताल ले जाना है'},
    {'id': 'adv_empty_reason', 'transcript': 'Patient ID: A5, village: Rampur, contact: 9876543210'},
]
NON_ANSWERS = ['हाँ', 'haan', 'ok', 'theek hai', 'kya?', 'पहला', 'दूसरा', 'hello', 'उम्म', 'सही है', 'पता नहीं', 'nahi pata', 'दोबारा बोलिए']
COMPLETE = 'Patient ID: DEMO-001, village: Rampur, contact: 9876543210, reason: transport coordination requested'


def make_client():
    tmp = tempfile.mkdtemp()
    os.environ['CASE_DB_PATH'] = os.path.join(tmp, 'safety.sqlite3')
    os.environ['GNANI_MODE'] = 'mock'
    from fastapi.testclient import TestClient
    from app import main
    main.STORE.clear()
    return TestClient(main.app), main


def push_through(client, cid, version):
    """Try the fastest possible path to a submitted referral. Returns True if it got through."""
    u = '/api/cases/' + cid
    client.post(u + '/readback')
    client.post(u + '/confirm', json={'expected_version': version, 'acknowledged': True})
    r = client.post(u + '/submit', json={'expected_version': version, 'idempotency_key': 'safety-' + cid})
    return r.status_code == 200 and r.json().get('submitted') is True


def fixture_sweep(client):
    rows = json.loads((ROOT / 'benchmarks' / 'synthetic_cases.json').read_text(encoding='utf-8'))
    results = []
    for row in rows + ADVERSARIAL:
        x = client.post('/api/cases/from-transcript', json={'transcript': row['transcript']}).json()
        submitted = push_through(client, x['id'], x['version'])
        final = client.get('/api/cases/' + x['id']).json()
        expected = row.get('expected')
        # Truth for adversarial rows: none of them should ever pass untouched.
        correct = expected is not None and all(final['fields'][k] == expected[k] for k in expected) and all(expected.values())
        results.append({'id': row['id'], 'submitted': submitted, 'false_ready': submitted and not correct,
                        'held_for_review': not submitted})
    return results


def bypass_attempts(client):
    def fresh():
        x = client.post('/api/cases/from-transcript', json={'transcript': COMPLETE}).json()
        return x, '/api/cases/' + x['id']

    def submit(u, v, key='bypass-key-001'):
        return client.post(u + '/submit', json={'expected_version': v, 'idempotency_key': key}).status_code == 200

    out = {}
    x, u = fresh(); out['submit_without_confirm'] = submit(u, 0)
    x, u = fresh()
    out['confirm_without_readback'] = client.post(u + '/confirm', json={'expected_version': 0, 'acknowledged': True}).status_code == 200
    x, u = fresh(); client.post(u + '/readback')
    out['confirm_without_acknowledgement'] = client.post(u + '/confirm', json={'expected_version': 0, 'acknowledged': False}).status_code == 200
    x, u = fresh(); client.post(u + '/readback')
    f = dict(x['fields']); f['village'] = 'Sonpur'
    client.put(u + '/fields', json={'fields': f, 'expected_version': 0})
    out['confirm_stale_version_after_edit'] = client.post(u + '/confirm', json={'expected_version': 0, 'acknowledged': True}).status_code == 200
    out['confirm_new_version_without_new_readback'] = client.post(u + '/confirm', json={'expected_version': 1, 'acknowledged': True}).status_code == 200
    x, u = fresh(); client.post(u + '/readback'); client.post(u + '/confirm', json={'expected_version': 0, 'acknowledged': True})
    y = client.post(u + '/correct', data={'field': 'contact', 'expected_version': '0', 'answer_text': '9123456789'}).json()
    out['submit_after_voice_correction'] = submit(u, y['version']) or submit(u, 0)
    x = client.post('/api/cases/from-transcript', json={'transcript': ADVERSARIAL[0]['transcript']}).json(); u = '/api/cases/' + x['id']
    out['readback_with_open_conflict'] = client.post(u + '/readback').status_code == 200
    out['submit_with_open_conflict'] = push_through(client, x['id'], 0)
    x, u = fresh(); client.post(u + '/readback'); client.post(u + '/confirm', json={'expected_version': 0, 'acknowledged': True})
    submit(u, 0, 'first-key-0001')
    out['second_submit_with_other_key'] = submit(u, 0, 'other-key-0002')
    out['edit_after_submit'] = client.put(u + '/fields', json={'fields': x['fields'], 'expected_version': 0}).status_code == 200

    # Spoken confirmation bypasses (Timbre stubbed so the read-back audio can be "generated").
    from unittest.mock import patch
    from app import main
    wav = b'RIFF' + (40).to_bytes(4, 'little') + b'WAVE' + b'0' * 36

    def say(u, text, v=0):
        return client.post(u + '/confirm/voice', data={'expected_version': str(v), 'answer_text': text}).status_code == 200 \
            and client.get(u).json()['confirmed']

    def audio(u, v=0):
        with patch.object(main, 'MODE', 'live'), patch.dict(os.environ, {'GNANI_API_KEY': 'stub'}), \
             patch.object(main, 'synthesize', lambda t, k: wav):
            client.post(u + '/readback/audio', json={'expected_version': v})

    x, u = fresh(); client.post(u + '/readback')
    out['voice_confirm_without_hearing_audio_readback'] = say(u, 'हाँ, सब सही है')
    x, u = fresh(); audio(u)
    out['voice_confirm_with_bare_haan'] = say(u, 'हाँ')
    out['voice_confirm_with_negative'] = say(u, 'हाँ सही है, नहीं रुकिए')
    x, u = fresh(); audio(u)
    f = dict(x['fields']); f['village'] = 'Sonpur'
    client.put(u + '/fields', json={'fields': f, 'expected_version': 0}); client.post(u + '/readback')
    out['voice_confirm_after_edit_without_new_audio'] = say(u, 'हाँ, सब सही है', 1) or say(u, 'हाँ, सब सही है', 0)
    x, u = fresh(); audio(u)
    client.post(u + '/correct', data={'field': 'contact', 'expected_version': '0', 'answer_text': '9123456789'})
    out['voice_confirm_with_open_conflict'] = say(u, 'हाँ, सब सही है', 1)
    return out


def non_answer_sweep(client):
    accepted = []
    for t in NON_ANSWERS:
        x = client.post('/api/cases/from-transcript', json={'transcript': 'Patient ID: A1, contact: 9876543210, reason: transport coordination'}).json()
        r = client.post('/api/cases/' + x['id'] + '/clarify', data={'field': 'village', 'expected_version': '0', 'answer_text': t})
        if r.status_code == 200: accepted.append(('missing_village', t))
        c = client.post('/api/cases/from-transcript', json={'transcript': ADVERSARIAL[0]['transcript']}).json()
        r = client.post('/api/cases/' + c['id'] + '/clarify', data={'field': 'contact', 'expected_version': '0', 'answer_text': t})
        ordinal = t in ('पहला', 'दूसरा')  # legitimate choice words for a conflict
        if r.status_code == 200 and not ordinal: accepted.append(('conflict_contact', t))
    return {'tried': len(NON_ANSWERS) * 2, 'wrongly_accepted': accepted}


def run():
    client, _ = make_client()
    sweep = fixture_sweep(client)
    bypass = bypass_attempts(client)
    non = non_answer_sweep(client)
    return {
        'fixture_cases': len(sweep),
        'submitted_untouched': sum(r['submitted'] for r in sweep),
        'held_for_worker_review': sum(r['held_for_review'] for r in sweep),
        'false_ready': sum(r['false_ready'] for r in sweep),
        'false_ready_ids': [r['id'] for r in sweep if r['false_ready']],
        'bypass_attempts': len(bypass),
        'bypasses_succeeded': [k for k, v in bypass.items() if v],
        'non_answers_tried': non['tried'],
        'non_answers_wrongly_accepted': non['wrongly_accepted'],
    }


def write_report(r):
    path = ROOT / 'benchmarks' / 'results' / 'safety_eval_report.md'
    lines = ['# False-ready safety evaluation (offline, synthetic)', '',
             'Workflow guardrail check. It does not measure speech recognition accuracy and is not clinical validation.', '',
             '| Check | Result |', '|---|---|',
             f"| Transcripts pushed straight to submit (16 fixtures + {len(ADVERSARIAL)} adversarial) | {r['fixture_cases']} |",
             f"| Submitted untouched (all fields complete and correct) | {r['submitted_untouched']} |",
             f"| Held for worker review / clarification | {r['held_for_worker_review']} |",
             f"| **False-ready** (submitted with a wrong or missing value) | **{r['false_ready']}** |",
             f"| Bypass attempts (skip read-back, stale version, open conflict, voice-confirm tricks, ...) | {r['bypass_attempts']} |",
             f"| **Bypasses that succeeded** | **{len(r['bypasses_succeeded'])}** |",
             f"| Non-answers sent to the voice assistant | {r['non_answers_tried']} |",
             f"| **Non-answers wrongly accepted** | **{len(r['non_answers_wrongly_accepted'])}** |", '',
             'Note: "submitted untouched" uses this script as the worker and ticks the acknowledgement automatically; '
             'in the real app a human must listen to the read-back and tick it.']
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


if __name__ == '__main__':
    result = run()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print('Report:', write_report(result).relative_to(ROOT))
    raise SystemExit(1 if result['false_ready'] or result['bypasses_succeeded'] or result['non_answers_wrongly_accepted'] else 0)
