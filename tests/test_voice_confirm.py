"""Hands-free spoken confirmation: strict phrase, only after the Timbre read-back of THIS version."""
import os, tempfile, atexit, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

DIR = tempfile.TemporaryDirectory(); atexit.register(DIR.cleanup)
_prev = os.environ.get('CASE_DB_PATH')
os.environ['CASE_DB_PATH'] = os.path.join(DIR.name, 'voiceconfirm.sqlite3')
from app import main
from app.clarify import parse_confirmation, CONFIRM_QUESTION
if _prev is None: os.environ.pop('CASE_DB_PATH', None)
else: os.environ['CASE_DB_PATH'] = _prev

WAV = b'RIFF' + (40).to_bytes(4, 'little') + b'WAVE' + b'0' * 36
COMPLETE = 'Patient ID: DEMO-001, village: Rampur, contact: 9876543210, reason: transport coordination requested'


class PhraseTests(unittest.TestCase):
    def test_clear_approvals(self):
        for t in ('हाँ, सब सही है', 'हां सब सही है', 'जी, सही है', 'सब ठीक है', 'haan sab sahi hai', 'yes correct', 'confirm', 'पुष्टि करती हूँ', 'बिल्कुल सही'):
            self.assertEqual(parse_confirmation(t), 'yes', t)

    def test_any_negative_never_confirms(self):
        for t in ('नहीं', 'नहीं, नंबर गलत है', 'हाँ सही है, नहीं रुकिए', 'galat hai', 'no', 'mat karo confirm', 'sab sahi nahi hai'):
            self.assertEqual(parse_confirmation(t), 'no', t)

    def test_ambiguous_is_neither(self):
        for t in ('हाँ', 'haan', 'ठीक है', 'सही', 'ok', 'hello', '', 'रामपुर'):
            self.assertEqual(parse_confirmation(t), '', t)


class VoiceConfirmApiTests(unittest.TestCase):
    def setUp(self):
        main.STORE.clear()
        self.client = TestClient(main.app)
        self.case = self.client.post('/api/cases/from-transcript', json={'transcript': COMPLETE}).json()
        self.url = '/api/cases/' + self.case['id']

    def live(self):
        return [patch.object(main, 'MODE', 'live'), patch.dict(os.environ, {'GNANI_API_KEY': 'k'}),
                patch.object(main, 'synthesize', lambda t, k: WAV)]

    def audio_readback(self, version=0):
        ctx = self.live()
        for c in ctx: c.start()
        try:
            r = self.client.post(self.url + '/readback/audio', json={'expected_version': version})
        finally:
            for c in reversed(ctx): c.stop()
        self.assertEqual(r.status_code, 200, r.text)

    def say(self, text, version=0):
        return self.client.post(self.url + '/confirm/voice', data={'expected_version': str(version), 'answer_text': text})

    def test_requires_timbre_readback_audio_not_just_text(self):
        self.client.post(self.url + '/readback')                      # text read-back only
        r = self.say('हाँ, सब सही है')
        self.assertEqual(r.status_code, 409)
        self.assertIn('Timbre read-back', r.json()['detail'])

    def test_voice_yes_confirms_this_version(self):
        self.audio_readback()
        r = self.say('हाँ, सब सही है')
        self.assertEqual(r.status_code, 200, r.text)
        x = r.json()
        self.assertTrue(x['confirmed'])
        self.assertEqual(x['evidence']['confirmed_by'], 'voice')
        self.assertTrue(any(e['event'] == 'worker_confirmed_by_voice' for e in x['events']))
        s = self.client.post(self.url + '/submit', json={'expected_version': 0, 'idempotency_key': 'voice-ok-0001'})
        self.assertEqual(s.status_code, 200)

    def test_bare_haan_and_unclear_change_nothing(self):
        self.audio_readback()
        for t in ('हाँ', 'ठीक है', 'रामपुर'):
            r = self.say(t)
            self.assertEqual(r.status_code, 422, t)
        x = self.client.get(self.url).json()
        self.assertFalse(x['confirmed']); self.assertEqual(x['version'], 0)

    def test_voice_no_logs_and_does_not_confirm(self):
        self.audio_readback()
        r = self.say('नहीं, नंबर गलत है')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['voice_confirmation']['decision'], 'no')
        self.assertFalse(r.json()['confirmed'])
        self.assertTrue(any(e['event'] == 'worker_rejected_readback_by_voice' for e in r.json()['events']))

    def test_edit_after_audio_requires_new_audio(self):
        self.audio_readback()
        f = dict(self.case['fields']); f['village'] = 'Sonpur'
        self.client.put(self.url + '/fields', json={'fields': f, 'expected_version': 0})
        self.client.post(self.url + '/readback')                      # text read-back of v1, but no audio of v1
        self.assertEqual(self.say('हाँ, सब सही है', version=1).status_code, 409)
        self.assertEqual(self.say('हाँ, सब सही है', version=0).status_code, 409)   # stale version

    def test_open_conflict_blocks_voice_confirm(self):
        self.audio_readback()
        self.client.post(self.url + '/correct', data={'field': 'village', 'expected_version': '0', 'answer_text': 'Sonpur'})
        self.assertEqual(self.say('हाँ, सब सही है', version=1).status_code, 409)

    def test_spoken_answer_goes_through_prisma_with_question_context(self):
        self.audio_readback()
        seen = {}
        def stub(audio, file, key, previous_text=None): seen['prev'] = previous_text; return 'हाँ सब सही है'
        with patch.object(main, 'MODE', 'live'), patch.dict(os.environ, {'GNANI_API_KEY': 'k'}), patch.object(main, 'prisma_text', stub):
            r = self.client.post(self.url + '/confirm/voice', data={'expected_version': '0'}, files={'file': ('a.wav', b'RIFF', 'audio/wav')})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['voice_confirmation']['source'], 'prisma')
        self.assertEqual(seen['prev'], CONFIRM_QUESTION)

    def test_question_audio(self):
        with patch.object(main, 'MODE', 'mock'):
            self.assertEqual(self.client.post(self.url + '/confirm/question-audio', json={'expected_version': 0}).status_code, 400)
        self.audio_readback()
        seen = {}
        with patch.object(main, 'MODE', 'live'), patch.dict(os.environ, {'GNANI_API_KEY': 'k'}), \
             patch.object(main, 'synthesize', lambda t, k: seen.setdefault('t', t) and WAV):
            r = self.client.post(self.url + '/confirm/question-audio', json={'expected_version': 0})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(seen['t'], CONFIRM_QUESTION)

    def test_checkbox_confirmation_still_works_and_is_labelled(self):
        self.client.post(self.url + '/readback')
        x = self.client.post(self.url + '/confirm', json={'expected_version': 0, 'acknowledged': True}).json()
        self.assertEqual(x['evidence']['confirmed_by'], 'checkbox')


if __name__ == '__main__':
    unittest.main()
