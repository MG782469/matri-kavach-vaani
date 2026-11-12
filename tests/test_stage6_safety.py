"""Stage 6 API safety regression tests. All data is synthetic."""
import unittest
import tempfile
from app.storage import SQLiteCaseStore
from fastapi.testclient import TestClient
from app import main

TRANSCRIPT = 'Patient ID: TEST001, village: Rampur, contact: 9999999999, reason: referral coordination'

class Stage6SafetyTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self._original_store = main.STORE
        main.STORE = SQLiteCaseStore(self._temp.name+'/stage6-tests.sqlite3')
        self.addCleanup(self._restore_store)
        self.client = TestClient(main.app)
        r = self.client.post('/api/cases/from-transcript', json={'transcript':TRANSCRIPT})
        self.assertEqual(r.status_code, 200, r.text)
        self.case = r.json()
        self.url = '/api/cases/'+self.case['id']

    def _restore_store(self):
        main.STORE = self._original_store
        self._temp.cleanup()

    def review(self):
        return self.client.post(self.url+'/readback')

    def confirm(self, version=0, acknowledged=True):
        return self.client.post(self.url+'/confirm', json={'expected_version':version, 'acknowledged':acknowledged})

    def submit(self, version=0, key='key-stage6-one'):
        return self.client.post(self.url+'/submit',json={'expected_version':version, 'idempotency_key':key})

    def test_missing_confirm_body_rejected(self):
        self.assertEqual(self.client.post(self.url+'/confirm').status_code,422)

    def test_missing_submit_body_rejected(self):
        self.assertEqual(self.client.post(self.url+'/submit').status_code,422)

    def test_readback_required_before_confirm(self):
        self.assertEqual(self.confirm().status_code,409)
        self.assertFalse(self.client.get(self.url).json()['confirmed'])

    def test_explicit_acknowledgment_required(self):
        self.assertEqual(self.review().status_code,200)
        self.assertEqual(self.confirm(acknowledged=False).status_code,409)
        self.assertFalse(self.client.get(self.url).json()['confirmed'])

    def test_successful_version_bound_confirmation(self):
        self.review()
        self.assertEqual(self.confirm().status_code,200)
        self.assertTrue(self.client.get(self.url).json()['confirmed'])

    def test_duplicate_confirmation_creates_only_one_event(self):
        self.review()
        self.assertEqual(self.confirm().status_code,200)
        self.assertEqual(self.confirm().status_code,200)
        case=self.client.get(self.url).json()
        self.assertEqual(sum(e['event']=='worker_confirmed' for e in case['events']),1)

    def test_review_invalidated_by_edit(self):
        self.review()
        fields=dict(self.case['fields']);fields['village']='Changed'
        self.client.put(self.url+'/fields',json={'fields':fields,'expected_version':0})
        self.assertEqual(self.confirm(version=1).status_code,409)
        case=self.client.get(self.url).json()
        self.assertFalse(case['readback_ready'])
        self.assertFalse(case['confirmed'])
        self.review()
        self.assertEqual(self.confirm(version=1).status_code,200)

    def test_old_confirm_version_conflict(self):
        self.review()
        fields=dict(self.case['fields']);fields['village']='Changed'
        self.client.put(self.url+'/fields',json={'fields':fields,'expected_version':0})
        self.assertEqual(self.confirm(version=0).status_code,409)

    def test_stale_field_update_missing_version_rejected(self):
        self.assertEqual(self.client.put(self.url+'/fields',json={'fields':self.case['fields']}).status_code,422)

    def test_idempotent_submission_same_key_only_one_event(self):
        self.review();self.confirm()
        a=self.submit();b=self.submit()
        self.assertEqual(a.status_code,200,a.text)
        self.assertEqual(b.status_code,200,b.text)
        self.assertEqual(a.json()['referral_id'],b.json()['referral_id'])
        self.assertEqual(sum(e['event']=='simulated_referral_created' for e in b.json()['events']),1)

    def test_second_submission_with_different_key_rejected(self):
        self.review();self.confirm();self.submit()
        self.assertEqual(self.submit(key='key-stage6-two').status_code,409)

    def test_short_submission_key_rejected(self):
        self.review();self.confirm()
        self.assertEqual(self.submit(key='x').status_code,422)

    def test_submission_without_confirmation_blocked(self):
        self.review()
        self.assertEqual(self.submit().status_code,409)

    def test_submission_with_wrong_version_blocked(self):
        self.review();self.confirm()
        self.assertEqual(self.submit(version=4).status_code,409)
        self.assertFalse(self.client.get(self.url).json()['submitted'])

    def test_saved_case_retrieval_and_retry(self):
        self.review();self.confirm();first=self.submit()
        from app.storage import SQLiteCaseStore
        restored=SQLiteCaseStore(main.STORE.path).get(self.case['id'])
        self.assertTrue(restored.submitted)
        self.assertEqual(restored.submission_key,'key-stage6-one')
        self.assertEqual(self.submit().json()['referral_id'],first.json()['referral_id'])

    def test_after_submit_cannot_edit_or_confirm_again(self):
        self.review();self.confirm();self.submit()
        self.assertEqual(self.client.put(self.url+'/fields',json={'fields':self.case['fields'],'expected_version':0}).status_code,409)
        self.assertEqual(self.confirm().status_code,409)

if __name__=='__main__': unittest.main()
