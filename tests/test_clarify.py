"""Voice clarification loop: parser units + API safety (offline; Prisma/Timbre stubbed)."""
import os, tempfile, atexit, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

DIR = tempfile.TemporaryDirectory(); atexit.register(DIR.cleanup)
_prev = os.environ.get('CASE_DB_PATH')
os.environ['CASE_DB_PATH'] = os.path.join(DIR.name, 'clarify.sqlite3')
from app import main
from app import prisma
from app.clarify import parse_answer, spoken_digits, question_for, QUESTIONS
if _prev is None: os.environ.pop('CASE_DB_PATH', None)
else: os.environ['CASE_DB_PATH'] = _prev

WAV = b'RIFF' + (40).to_bytes(4, 'little') + b'WAVE' + b'0' * 36
MISSING_VILLAGE = 'Patient ID: TEST001, contact: 9876543210, reason: transport coordination requested'


class ParserTests(unittest.TestCase):
    def test_spoken_digits_hindi_english_and_repeat(self):
        self.assertEqual(spoken_digits('नौ आठ सात छह पांच चार तीन दो एक शून्य'), '9876543210')
        self.assertEqual(spoken_digits('nine eight double seven six five four three two one'), '9877654321')
        self.assertEqual(spoken_digits('९८७६५ ४३२१०'), '9876543210')
        self.assertEqual(spoken_digits('98765 डबल 4 3210'), '98765443210')
        self.assertEqual(spoken_digits('nau aath saat chhe paanch'), '98765')

    def test_ambiguous_romanised_words_ignored(self):
        # 'do' (give) and 'no' must not become digits in "number do" / "contact no".
        self.assertEqual(spoken_digits('contact no 98765 43210 do'), '9876543210')
        self.assertEqual(spoken_digits('do number'), '')

    def test_romanised_do_between_digits_is_two(self):
        self.assertEqual(spoken_digits('nau aath saat chhe paanch, chaar teen do ek shunya'), '9876543210')

    def test_contact_answer(self):
        self.assertEqual(parse_answer('contact', 'नंबर है 98765 43210'), '9876543210')
        self.assertEqual(parse_answer('contact', 'pata nahi'), '')

    def test_village_answer_strips_fillers(self):
        self.assertEqual(parse_answer('village', 'गाँव का नाम रामपुर है।'), 'रामपुर')
        self.assertEqual(parse_answer('village', 'रामपुर गांव'), 'रामपुर')
        self.assertEqual(parse_answer('village', 'village Rampur Kalan'), 'Rampur Kalan')
        self.assertEqual(parse_answer('village', '12345'), '')

    def test_patient_ref_answer(self):
        self.assertEqual(parse_answer('patient_ref', 'रेफरेंस नंबर 1024 है'), '1024')
        self.assertEqual(parse_answer('patient_ref', 'एक शून्य दो चार'), '1024')
        self.assertEqual(parse_answer('patient_ref', 'DEMO 001'), 'DEMO-001')

    def test_reason_answer(self):
        self.assertEqual(parse_answer('referral_reason', 'कारण है अस्पताल तक वाहन की व्यवस्था।'), 'अस्पताल तक वाहन की व्यवस्था')
        self.assertEqual(parse_answer('referral_reason', 'ok'), '')

    def test_unknown_field_rejected(self):
        self.assertEqual(parse_answer('diagnosis', 'anything'), '')

    def test_question_targets_first_invalid_field_only(self):
        q = question_for({'patient_ref': 'X1', 'village': '', 'contact': '123', 'referral_reason': 'transport'})
        self.assertEqual(q['field'], 'village')
        self.assertEqual(q['remaining'], ['village', 'contact'])
        self.assertEqual(q['question'], QUESTIONS['village'])
        self.assertIsNone(question_for({'patient_ref': 'X1', 'village': 'Rampur', 'contact': '9876543210', 'referral_reason': 'transport'}))

    def test_mobile_must_start_6_to_9(self):
        q = question_for({'patient_ref': 'X1', 'village': 'Rampur', 'contact': '1234567890', 'referral_reason': 'transport'})
        self.assertEqual(q['field'], 'contact')


class PrismaProfileTests(unittest.TestCase):
    def call(self, profile):
        seen = {}
        class R:
            def raise_for_status(self): pass
            def json(self): return {'transcript': ' रामपुर '}
        def post(url, **kw): seen.update(kw, url=url); return R()
        with patch.dict(os.environ, {'GNANI_STT_PROFILE': profile}):
            text = prisma.transcribe(b'x', 'a.wav', 'audio/wav', 'k', max_chars=100, transport=post)
        return text, seen

    def test_default_hindi_profile_unchanged(self):
        text, seen = self.call('hindi')
        self.assertEqual(text, 'रामपुर')
        self.assertEqual(seen['data']['format'], 'transcribe')
        self.assertEqual(seen['data']['language_code'], 'hi-IN')
        self.assertEqual(seen['headers'], {'X-API-Key-ID': 'k'})

    def test_codemix_profile_uses_v3(self):
        _, seen = self.call('codemix')
        self.assertEqual(seen['data'], {'model': 'prisma-v3.0', 'language_code': 'hi-IN,en-IN', 'format': 'codemix'})

    def test_bad_profile_rejected(self):
        with patch.dict(os.environ, {'GNANI_STT_PROFILE': 'klingon'}), self.assertRaises(prisma.PrismaError):
            prisma.profile_name()


class ClarifyApiTests(unittest.TestCase):
    def setUp(self):
        main.STORE.clear()
        self.client = TestClient(main.app)
        r = self.client.post('/api/cases/from-transcript', json={'transcript': MISSING_VILLAGE})
        self.assertEqual(r.status_code, 200, r.text)
        self.case = r.json()
        self.url = '/api/cases/' + self.case['id']

    def answer(self, field, version, text=None, audio=None):
        data = {'field': field, 'expected_version': str(version)}
        if text is not None: data['answer_text'] = text
        files = {'file': ('answer.wav', audio, 'audio/wav')} if audio is not None else None
        return self.client.post(self.url + '/clarify', data=data, files=files)

    def test_view_exposes_question_for_missing_field(self):
        q = self.case['clarification']
        self.assertEqual(q['field'], 'village')
        self.assertEqual(self.case['fields']['village'], '')

    def test_typed_answer_fills_only_asked_field_and_invalidates_review(self):
        before = dict(self.case['fields'])
        r = self.answer('village', 0, 'गाँव का नाम रामपुर है')
        self.assertEqual(r.status_code, 200, r.text)
        x = r.json()
        self.assertEqual(x['fields']['village'], 'रामपुर')
        for k in ('patient_ref', 'contact', 'referral_reason'):
            self.assertEqual(x['fields'][k], before[k])
        self.assertIsNone(x['clarification'])
        self.assertFalse(x['confirmed']); self.assertFalse(x['readback_ready'])
        self.assertEqual(x['version'], 1)
        self.assertTrue(any(e['event'] == 'voice_clarification_filled_village_typed' for e in x['events']))
        # Worker still has to read back + confirm; clarification never confirms.
        self.assertEqual(self.client.post(self.url + '/submit', json={'expected_version': 1, 'idempotency_key': 'clarify-key-01'}).status_code, 409)

    def test_answer_cannot_smuggle_other_fields(self):
        r = self.answer('village', 0, 'Rampur, contact: 9123456789')
        # The whole answer is not a clean village name -> rejected, contact untouched.
        self.assertEqual(r.status_code, 422)
        self.assertEqual(self.client.get(self.url).json()['fields']['contact'], '9876543210')

    def test_field_not_needing_clarification_rejected(self):
        self.assertEqual(self.answer('contact', 0, '9123456789').status_code, 409)
        self.assertEqual(self.answer('diagnosis', 0, 'x').status_code, 409)

    def test_stale_version_rejected(self):
        self.assertEqual(self.answer('village', 7, 'रामपुर').status_code, 409)

    def test_unusable_answer_keeps_case(self):
        r = self.answer('village', 0, '12345')
        self.assertEqual(r.status_code, 422)
        self.assertIn('12345', r.json()['detail'])
        self.assertEqual(self.client.get(self.url).json()['version'], 0)

    def test_empty_answer_rejected(self):
        self.assertEqual(self.answer('village', 0, '  ').status_code, 422)

    def test_audio_answer_needs_live_mode(self):
        with patch.object(main, 'MODE', 'mock'):
            self.assertEqual(self.answer('village', 0, audio=b'abc').status_code, 400)

    def test_audio_answer_uses_prisma_and_logs(self):
        seen = {}
        def stub(audio, file, key, previous_text=None):
            seen['audio'] = audio; seen['key'] = key; seen['prev'] = previous_text; return 'मेरे गाँव का नाम सोनपुर है'
        with patch.object(main, 'MODE', 'live'), patch.dict(os.environ, {'GNANI_API_KEY': 'secret-k'}), patch.object(main, 'prisma_text', stub):
            r = self.answer('village', 0, audio=b'RIFFfake')
        self.assertEqual(r.status_code, 200, r.text)
        x = r.json()
        self.assertEqual(x['fields']['village'], 'सोनपुर')
        self.assertEqual(x['clarified']['source'], 'prisma')
        self.assertEqual(seen['key'], 'secret-k')
        self.assertEqual(seen['prev'], QUESTIONS['village'])  # question passed as Prisma context
        self.assertTrue(any(e['event'] == 'voice_clarification_filled_village' for e in x['events']))
        self.assertEqual(x['clarification_count'], 1)
        self.assertNotIn('secret-k', repr(x))

    def test_question_audio_via_timbre(self):
        seen = {}
        def stub(text, key): seen['text'] = text; return WAV
        with patch.object(main, 'MODE', 'live'), patch.dict(os.environ, {'GNANI_API_KEY': 'k'}), patch.object(main, 'synthesize', stub):
            r = self.client.post(self.url + '/clarification/audio', json={'expected_version': 0, 'field': 'village'})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.content, WAV)
        self.assertEqual(seen['text'], QUESTIONS['village'])

    def test_question_audio_mock_and_wrong_field(self):
        with patch.object(main, 'MODE', 'mock'):
            self.assertEqual(self.client.post(self.url + '/clarification/audio', json={'expected_version': 0, 'field': 'village'}).status_code, 400)
        with patch.object(main, 'MODE', 'live'), patch.dict(os.environ, {'GNANI_API_KEY': 'k'}), patch.object(main, 'synthesize') as f:
            self.assertEqual(self.client.post(self.url + '/clarification/audio', json={'expected_version': 0, 'field': 'contact'}).status_code, 409)
        f.assert_not_called()

    def test_full_loop_then_existing_confirmation_flow(self):
        x = self.answer('village', 0, 'रामपुर').json()
        self.assertEqual(self.client.post(self.url + '/readback').status_code, 200)
        c = self.client.post(self.url + '/confirm', json={'expected_version': x['version'], 'acknowledged': True})
        self.assertEqual(c.status_code, 200, c.text)
        s = self.client.post(self.url + '/submit', json={'expected_version': x['version'], 'idempotency_key': 'clarify-key-02'})
        self.assertEqual(s.status_code, 200, s.text)
        self.assertTrue(s.json()['submitted'])
        self.assertIsNone(s.json()['clarification'])
        self.assertEqual(self.answer('village', x['version'], 'सोनपुर').status_code, 409)

    def test_readback_groups_contact_digits(self):
        self.answer('village', 0, 'रामपुर')
        text = self.client.post(self.url + '/readback').json()['text']
        self.assertIn('9 8 7 6 5, 4 3 2 1 0', text)


if __name__ == '__main__':
    unittest.main()
