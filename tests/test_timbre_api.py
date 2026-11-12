import os, tempfile, atexit, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
DIR=tempfile.TemporaryDirectory();atexit.register(DIR.cleanup)
os.environ['CASE_DB_PATH']=DIR.name+'/tts_tests.db'
os.environ['GNANI_MODE']='live'
from app import main

WAV=b'RIFF'+(40).to_bytes(4,'little')+b'WAVE'+b'0'*36

class TimbreApiTests(unittest.TestCase):
    def setUp(self):
        main.STORE.clear()
        self.client=TestClient(main.app)
        x=self.client.post('/api/cases/from-transcript',json={'transcript':'Patient ID: TEST001, village: Rampur, contact: 9999999999, reason: referral coordination'})
        self.assertEqual(x.status_code,200)
        self.case=x.json()
        self.url='/api/cases/'+self.case['id']

    def test_audio_requires_key(self):
        with patch.object(main,'MODE','live'),patch.dict(os.environ,{'GNANI_API_KEY':''}):
            r=self.client.post(self.url+'/readback/audio',json={'expected_version':0})
        self.assertEqual(r.status_code,503)

    def test_audio_generated_and_logged_without_confirm(self):
        seen={}
        def stub(text,key): seen['text']=text;seen['key']=key;return WAV
        with patch.object(main,'MODE','live'),patch.dict(os.environ,{'GNANI_API_KEY':'dummy-secret'}),patch.object(main,'synthesize',stub):
            r=self.client.post(self.url+'/readback/audio',json={'expected_version':0})
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.content,WAV)
        self.assertEqual(r.headers['cache-control'],'no-store')
        self.assertIn('9 9 9',seen['text'])
        status=self.client.get(self.url).json()
        self.assertFalse(status['confirmed']);self.assertFalse(status['submitted'])
        self.assertTrue(any(e['event']=='timbre_audio_generated_for_review' for e in status['events']))
        self.assertNotIn('dummy-secret',repr(status))

    def test_invalid_draft_does_not_call_timbre(self):
        x=self.client.put(self.url+'/fields',json={'fields':{'patient_ref':'TEST','village':'','contact':'123','referral_reason':''},'expected_version':0}).json()
        with patch.object(main,'MODE','live'),patch.dict(os.environ,{'GNANI_API_KEY':'fake'}),patch.object(main,'synthesize') as f:
            r=self.client.post(self.url+'/readback/audio',json={'expected_version':x['version']})
        self.assertEqual(r.status_code,422)
        f.assert_not_called()

    def test_stale_version_and_submitted_blocked(self):
        with patch.object(main,'MODE','live'),patch.dict(os.environ,{'GNANI_API_KEY':'fake'}),patch.object(main,'synthesize') as f:
            self.assertEqual(self.client.post(self.url+'/readback/audio',json={'expected_version':99}).status_code,409)
            self.client.post(self.url+'/readback');self.client.post(self.url+'/confirm',json={'expected_version':0,'acknowledged':True});self.client.post(self.url+'/submit',json={'expected_version':0,'idempotency_key':'test-key-tts-001'})
            self.assertEqual(self.client.post(self.url+'/readback/audio',json={'expected_version':0}).status_code,409)
        f.assert_not_called()

    def test_failure_does_not_create_audio_event_or_confirmation(self):
        from app.timbre import TimbreError
        with patch.object(main,'MODE','live'),patch.dict(os.environ,{'GNANI_API_KEY':'fake'}),patch.object(main,'synthesize',side_effect=TimbreError('Service unavailable')):
            r=self.client.post(self.url+'/readback/audio',json={'expected_version':0})
        self.assertEqual(r.status_code,502)
        x=self.client.get(self.url).json()
        self.assertFalse(x['confirmed'])
        self.assertFalse(any(e['event']=='timbre_audio_generated_for_review' for e in x['events']))

if __name__ == '__main__':unittest.main()
