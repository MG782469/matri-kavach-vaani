"""Contradiction-aware clarification, voice correction, field states and evidence passport (offline)."""
import os, tempfile, atexit, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

DIR = tempfile.TemporaryDirectory(); atexit.register(DIR.cleanup)
_prev = os.environ.get('CASE_DB_PATH')
os.environ['CASE_DB_PATH'] = os.path.join(DIR.name, 'conflicts.sqlite3')
from app import main, prisma
from app.extraction import find_conflicts, parse_transcript
from app.clarify import resolve_choice, parse_answer, question_for
if _prev is None: os.environ.pop('CASE_DB_PATH', None)
else: os.environ['CASE_DB_PATH'] = _prev

TWO_NUMBERS = 'Patient ID: A1, contact: 9876543210, contact number 9123456789, village Rampur, reason: transport coordination'
TWO_VILLAGES = 'मरीज रामगढ़ गाँव से है, patient ID 77, contact 9876543210. sorry, village: Rampur, reason: transport coordination'
COMPLETE = 'Patient ID: DEMO-001, village: Rampur, contact: 9876543210, reason: transport coordination requested'


class ConflictUnitTests(unittest.TestCase):
    def test_conflicting_contacts_detected_and_not_picked(self):
        self.assertEqual(find_conflicts(TWO_NUMBERS), {'contact': ['9876543210', '9123456789']})
        self.assertEqual(parse_transcript(TWO_NUMBERS)['contact'], '')

    def test_conflicting_villages_ignore_filler_words(self):
        self.assertEqual(sorted(find_conflicts(TWO_VILLAGES)['village']), sorted(['Rampur', 'रामगढ़']))

    def test_no_conflict_for_clean_transcript(self):
        self.assertEqual(find_conflicts(COMPLETE), {})
        self.assertEqual(find_conflicts('village Rampur Kalan, contact 9876543210'), {})

    def test_conflict_asked_before_missing(self):
        q = question_for({'patient_ref': '', 'village': '', 'contact': '9876543210', 'referral_reason': 'x y z'},
                         {'village': ['रामगढ़', 'Rampur']})
        self.assertEqual(q['kind'], 'conflict')
        self.assertEqual(q['field'], 'village')
        self.assertIn('पहला रामगढ़', q['question'])
        self.assertEqual(q['remaining'], ['patient_ref', 'village'])

    def test_contact_conflict_question_reads_digits(self):
        q = question_for({'patient_ref': 'A1', 'village': 'R', 'contact': '', 'referral_reason': 'abc'},
                         {'contact': ['9876543210', '9123456789']})
        self.assertIn('9 8 7 6 5, 4 3 2 1 0', q['question'])

    def test_resolve_by_ordinal_name_or_new_value(self):
        c = ['रामगढ़', 'Rampur']
        self.assertEqual(resolve_choice('village', 'दूसरा वाला', c), 'Rampur')
        self.assertEqual(resolve_choice('village', 'pehla', c), 'रामगढ़')
        self.assertEqual(resolve_choice('village', 'rampur', c), 'Rampur')
        self.assertEqual(resolve_choice('village', 'सोनपुर', c), 'सोनपुर')
        # 'pehle' means "earlier", not "first": must not pick candidate 0.
        self.assertEqual(resolve_choice('village', 'pehle Ramgarh bola, ab Rampur', c), '')

    def test_negation_correction_keeps_value_after_nahi(self):
        self.assertEqual(parse_answer('village', 'रामगढ़ नहीं, रामपुर है'), 'रामपुर')
        self.assertEqual(parse_answer('contact', '9876543210 nahi, 9123456789'), '9123456789')

    def test_negation_in_reason_is_preserved(self):
        self.assertEqual(parse_answer('referral_reason', 'मरीज़ को साँस नहीं आ रही'), 'मरीज़ को साँस नहीं आ रही')

    def test_acknowledgements_and_fillers_are_not_values(self):
        bad = ['हाँ', 'haan', 'ok', 'theek hai', 'ठीक है', 'kya?', 'क्या', 'पहला', 'दूसरा', 'hello', 'उम्म',
               'नमस्ते', 'yes', 'sahi hai', 'सही है', 'दोबारा बोलिए', 'से']
        for f in ('village', 'patient_ref', 'referral_reason', 'contact'):
            for t in bad:
                self.assertEqual(parse_answer(f, t), '', (f, t))

    def test_prisma_itn_ordinals_pick_candidate(self):
        # Live Prisma returned "१st" when the worker said "पहला".
        c = ['9876543210', '9123456789']
        for t, want in (('१st', c[0]), ('1st', c[0]), ('1 st', c[0]), ('१ला', c[0]),
                        ('2nd', c[1]), ('२nd', c[1]), ('२रा', c[1]), ('2nd wala', c[1])):
            self.assertEqual(resolve_choice('contact', t, c), want, t)

    def test_partial_value_cannot_settle_conflict(self):
        c = ['9876543210', '9123456789']
        for t in ('1', '98765', '1234567890', '१'):
            self.assertEqual(resolve_choice('contact', t, c), '', t)
        self.assertEqual(resolve_choice('contact', '9000000001', c), '9000000001')   # full valid new number is allowed

    def test_unclear_reply_never_settles_conflict(self):
        for t in ('हाँ', 'sahi hai', 'ok', 'दोनों', 'kya'):
            self.assertEqual(resolve_choice('village', t, ['रामगढ़', 'Rampur']), '', t)

    def test_leading_acknowledgement_is_stripped(self):
        self.assertEqual(parse_answer('village', 'जी, सोनपुर'), 'सोनपुर')
        self.assertEqual(parse_answer('patient_ref', 'haan, 1024'), '1024')

    def test_dont_know_is_not_a_value(self):
        for t in ('पता नहीं', 'pata nahi', 'nahi pata', "don't know"):
            self.assertEqual(parse_answer('village', t), '', t)


class PrismaStyleExtractionTests(unittest.TestCase):
    """Prisma hi-IN writes spoken English markers in Devanagari ("विलेज", "कॉन्टैक्ट", "रीज़न")."""
    def test_devanagari_english_markers(self):
        x = parse_transcript('पेशेंट रेफरेंस १०२४ है विलेज रामपुर कॉन्टैक्ट नंबर ९८७६५४३२१० रेफरल रीज़न हॉस्पिटल चेकअप')
        self.assertEqual(x, {'patient_ref': '1024', 'village': 'रामपुर', 'contact': '9876543210', 'referral_reason': 'हॉस्पिटल चेकअप'})

    def test_spoken_digit_words_and_grouped_numbers(self):
        x = parse_transcript('संपर्क नंबर नौ आठ सात छह पाँच, चार तीन दो एक शून्य है।')
        self.assertEqual(x['contact'], '9876543210')
        self.assertEqual(parse_transcript('contact number 9 8 7 6 5, 4 3 2 1 0')['contact'], '9876543210')
        # Ordinary words like "एक मरीज़" are not digit runs.
        self.assertEqual(parse_transcript('एक मरीज़ है, संपर्क नंबर 9876543210')['contact'], '9876543210')

    def test_reference_with_or_without_nukta(self):
        for t in ('मरीज़ का रेफ़रेंस नंबर 1024 है', 'मरीज़ का रेफरेंस नंबर 1024 है', 'रामपुर की मरीज़ है, रेफ़रेंस 1024'):
            self.assertEqual(parse_transcript(t)['patient_ref'], '1024', t)

    def test_reason_without_colon(self):
        self.assertEqual(parse_transcript('referral reason hospital checkup.')['referral_reason'], 'hospital checkup')

    def test_village_then_se_hai_with_danda(self):
        x = parse_transcript('मरीज़ का रेफरेंस नंबर 1024 है। मरीज़ रामपुर गाँव से है। संपर्क नंबर 9876543210 है।')
        self.assertEqual(x['village'], 'रामपुर')
        self.assertEqual(find_conflicts('मरीज़ रामपुर गाँव से है।'), {})


class ConflictApiTests(unittest.TestCase):
    def setUp(self):
        main.STORE.clear()
        self.client = TestClient(main.app)

    def create(self, transcript):
        r = self.client.post('/api/cases/from-transcript', json={'transcript': transcript})
        self.assertEqual(r.status_code, 200, r.text)
        self.url = '/api/cases/' + r.json()['id']
        return r.json()

    def post(self, path, field, version, text):
        return self.client.post(self.url + path, data={'field': field, 'expected_version': str(version), 'answer_text': text})

    def test_transcript_conflict_blocks_readback_until_resolved(self):
        x = self.create(TWO_NUMBERS)
        self.assertEqual(x['conflicts'], {'contact': ['9876543210', '9123456789']})
        self.assertEqual(x['clarification']['kind'], 'conflict')
        self.assertEqual(x['field_states']['contact']['state'], 'conflict')
        self.assertTrue(any(e['event'] == 'conflicting_values_detected' for e in x['events']))
        self.assertEqual(self.client.post(self.url + '/readback').status_code, 422)
        r = self.post('/clarify', 'contact', 0, 'दूसरा')
        self.assertEqual(r.status_code, 200, r.text)
        y = r.json()
        self.assertEqual(y['fields']['contact'], '9123456789')
        self.assertEqual(y['conflicts'], {})
        self.assertEqual(y['resolutions'][0]['candidates'], ['9876543210', '9123456789'])
        self.assertEqual(y['resolutions'][0]['chosen'], '9123456789')
        self.assertTrue(y['clarified']['resolved_conflict'])
        self.assertTrue(y['field_states']['contact']['resolved_conflict'])
        self.assertEqual(y['evidence']['conflicts_resolved'], 1)
        self.assertEqual(self.client.post(self.url + '/readback').status_code, 200)

    def test_unclear_conflict_answer_rejected(self):
        self.create(TWO_NUMBERS)
        r = self.post('/clarify', 'contact', 0, 'haan')
        self.assertEqual(r.status_code, 422)
        self.assertIn('दूसरा', r.json()['detail'])

    def test_voice_correction_creates_conflict_not_silent_overwrite(self):
        self.create(COMPLETE)
        r = self.post('/correct', 'village', 0, 'Rampur nahi, Sonpur')
        self.assertEqual(r.status_code, 200, r.text)
        x = r.json()
        self.assertEqual(x['fields']['village'], 'Rampur')            # not overwritten
        self.assertEqual(x['conflicts'], {'village': ['Rampur', 'Sonpur']})
        self.assertEqual(x['version'], 1)
        self.assertIn('आपने पहले', x['clarification']['question'])
        self.assertFalse(x['readback_ready'])
        y = self.post('/clarify', 'village', 1, 'नया वाला').json()
        self.assertEqual(y['fields']['village'], 'Sonpur')
        self.assertEqual(y['resolutions'][0]['how'], 'typed')

    def test_partial_voice_correction_rejected(self):
        self.create(COMPLETE)
        r = self.post('/correct', 'contact', 0, '98765')
        self.assertEqual(r.status_code, 422)
        self.assertIn('incomplete or invalid', r.json()['detail'])
        x = self.client.get(self.url).json()
        self.assertEqual(x['conflicts'], {}); self.assertEqual(x['version'], 0)

    def test_voice_correction_same_value_only_logs(self):
        self.create(COMPLETE)
        x = self.post('/correct', 'village', 0, 'village Rampur').json()
        self.assertTrue(x['correction']['matches_existing'])
        self.assertEqual(x['conflicts'], {})
        self.assertEqual(x['version'], 0)

    def test_correction_invalidates_confirmation(self):
        self.create(COMPLETE)
        self.client.post(self.url + '/readback')
        self.assertEqual(self.client.post(self.url + '/confirm', json={'expected_version': 0, 'acknowledged': True}).status_code, 200)
        x = self.post('/correct', 'contact', 0, '9123456789').json()
        self.assertFalse(x['confirmed'])
        self.assertEqual(self.client.post(self.url + '/submit', json={'expected_version': x['version'], 'idempotency_key': 'conf-key-001'}).status_code, 409)

    def test_correct_rejects_empty_or_unknown_field(self):
        self.create(TWO_NUMBERS)
        self.assertEqual(self.post('/correct', 'contact', 0, '9000000001').status_code, 409)
        self.assertEqual(self.post('/correct', 'diagnosis', 0, 'x').status_code, 422)

    def test_manual_edit_of_other_field_does_not_settle_conflict(self):
        x = self.create(TWO_NUMBERS)
        f = dict(x['fields']); f['referral_reason'] = 'new reason text'
        y = self.client.put(self.url + '/fields', json={'fields': f, 'expected_version': 0}).json()
        self.assertIn('contact', y['conflicts'])
        self.assertEqual(y['field_states']['referral_reason']['source'], 'manual edit')
        f['contact'] = '9123456789'
        z = self.client.put(self.url + '/fields', json={'fields': f, 'expected_version': 1}).json()
        self.assertEqual(z['conflicts'], {})
        self.assertEqual(z['resolutions'][0]['how'], 'manual edit')

    def test_field_states_progress_to_confirmed(self):
        x = self.create(COMPLETE)
        self.assertEqual({v['state'] for v in x['field_states'].values()}, {'needs_readback'})
        self.assertEqual(x['field_states']['village']['source'], 'typed transcript')
        self.client.post(self.url + '/readback')
        self.assertEqual({v['state'] for v in self.client.get(self.url).json()['field_states'].values()}, {'read_back'})
        y = self.client.post(self.url + '/confirm', json={'expected_version': 0, 'acknowledged': True}).json()
        self.assertEqual({v['state'] for v in y['field_states'].values()}, {'confirmed'})
        self.assertEqual(y['evidence']['worker_confirmed_version'], 0)
        self.assertTrue(y['evidence']['readback_current_version'])

    def test_evidence_passport_has_no_patient_values(self):
        x = self.create(TWO_NUMBERS)
        # case_ref is a random hex id that can contain "A1" by chance, so leave it out of the scan.
        blob = repr({k: v for k, v in x['evidence'].items() if k != 'case_ref'})
        for value in ('9876543210', '9123456789', 'Rampur', 'A1'):
            self.assertNotIn(value, blob)
        self.assertTrue(x['evidence']['synthetic_only'])
        self.assertEqual(x['evidence']['conflicts_detected'], 1)

    def test_conflicts_survive_storage_roundtrip(self):
        x = self.create(TWO_NUMBERS)
        stored = main.STORE.get(x['id'])
        self.assertEqual(stored.conflicts, {'contact': ['9876543210', '9123456789']})
        self.assertEqual(stored.sources['village'], 'typed transcript')

    def test_old_rows_without_new_columns_still_load(self):
        from app.core import Case
        import json
        raw = json.dumps({'id': 'legacy', 'transcript': 't', 'fields': {}, 'version': 0, 'confirmation_digest': None,
                          'confirmed_version': None, 'submitted': False, 'referral_id': None, 'events': [],
                          'reviewed_digest': None, 'reviewed_version': None, 'submission_key': None})
        self.assertEqual(main.STORE._decode(raw).conflicts, {})


class SilenceTests(unittest.TestCase):
    def test_empty_prisma_transcript_is_422_and_changes_nothing(self):
        main.STORE.clear()
        client = TestClient(main.app)
        x = client.post('/api/cases/from-transcript', json={'transcript': 'Patient ID: A1, contact: 9876543210, reason: transport coordination'}).json()
        class R:
            def raise_for_status(self): pass
            def json(self): return {'transcript': '   '}
        with patch.object(main, 'MODE', 'live'), patch.dict(os.environ, {'GNANI_API_KEY': 'k', 'GNANI_STT_PROFILE': 'hindi'}), \
             patch.object(main.requests, 'post', lambda *a, **k: R()):
            r = client.post('/api/cases/' + x['id'] + '/clarify', data={'field': 'village', 'expected_version': '0'},
                            files={'file': ('a.wav', b'RIFF', 'audio/wav')})
        self.assertEqual(r.status_code, 422)
        self.assertIn('nothing was heard', r.json()['detail'])
        self.assertEqual(client.get('/api/cases/' + x['id']).json()['version'], 0)


class KeyHygieneTests(unittest.TestCase):
    def test_quotes_and_spaces_removed_from_key(self):
        for raw in ('"abc123"', " 'abc123' ", 'abc123 \r\n', '  "abc123" '):
            with patch.dict(os.environ, {'GNANI_API_KEY': raw}):
                self.assertEqual(main.gnani_key(), 'abc123', repr(raw))
        with patch.dict(os.environ, {'GNANI_API_KEY': '""'}):
            self.assertEqual(main.gnani_key(), '')


class PrismaContextTests(unittest.TestCase):
    def test_previous_text_only_sent_on_codemix(self):
        seen = {}
        class R:
            def raise_for_status(self): pass
            def json(self): return {'transcript': 'x'}
        def post(url, **kw): seen.update(kw); return R()
        with patch.dict(os.environ, {'GNANI_STT_PROFILE': 'hindi'}):
            prisma.transcribe(b'a', 'a.wav', None, 'k', max_chars=9, transport=post, previous_text='Q')
        self.assertNotIn('previous_text', seen['data'])
        with patch.dict(os.environ, {'GNANI_STT_PROFILE': 'codemix'}):
            prisma.transcribe(b'a', 'a.wav', None, 'k', max_chars=9, transport=post, previous_text='Q')
        self.assertEqual(seen['data']['previous_text'], 'Q')


if __name__ == '__main__':
    unittest.main()
