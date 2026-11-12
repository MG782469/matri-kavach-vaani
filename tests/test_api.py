import os
import tempfile
import atexit
import unittest
from fastapi.testclient import TestClient
from unittest.mock import patch
# Prevent automated tests from ever clearing a user's persistent demo cases.
_TEST_DB_DIR = tempfile.TemporaryDirectory()
atexit.register(_TEST_DB_DIR.cleanup)
_PREVIOUS_CASE_DB = os.environ.get('CASE_DB_PATH')
os.environ['CASE_DB_PATH'] = os.path.join(_TEST_DB_DIR.name,'api-tests.sqlite3')
from app.main import app, STORE
if _PREVIOUS_CASE_DB is None:
    os.environ.pop('CASE_DB_PATH',None)
else:
    os.environ['CASE_DB_PATH'] = _PREVIOUS_CASE_DB

class ApiTests(unittest.TestCase):
    def setUp(self):
        STORE.clear()
        self.client = TestClient(app)
    def create(self):
        response=self.client.post('/api/cases/from-transcript',json={'transcript':'Patient ID: TEST001, village: Rampur, contact: 9999999999, reason: referral coordination'})
        self.assertEqual(response.status_code,200,response.text)
        return response.json()
    def test_health_and_contract(self):
        r=self.client.get('/api/health')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['status'],'ok')
        self.assertFalse(r.json()['clinical_use'])
        self.assertIn('/api/cases/from-transcript', self.client.get('/openapi.json').json()['paths'])
    def test_mock_audio_rejected(self):
        with patch('app.main.MODE', 'mock'):
            r=self.client.post('/api/cases/from-audio',files={'file':('clip.wav',b'test','audio/wav')})
        self.assertEqual(r.status_code,400)
        self.assertEqual(STORE.count(),0)
    def test_transcript_bounds(self):
        self.assertEqual(self.client.post('/api/cases/from-transcript',json={'transcript':' '} ).status_code,422)
        self.assertEqual(self.client.post('/api/cases/from-transcript',json={'transcript':'x'*2001}).status_code,413)
    def review_confirm(self,url,version=0):
        self.assertEqual(self.client.post(url+'/readback').status_code,200)
        r=self.client.post(url+'/confirm',json={'expected_version':version,'acknowledged':True})
        self.assertEqual(r.status_code,200,r.text)
        return r
    def submit_demo(self,url,version=0,key='test-key-00001'):
        return self.client.post(url+'/submit',json={'expected_version':version,'idempotency_key':key})

    def test_unconfirmed_rejected_and_confirmed_idempotent(self):
        case=self.create();url='/api/cases/'+case['id']
        self.assertEqual(self.submit_demo(url).status_code,409)
        confirm=self.review_confirm(url)
        self.assertEqual(confirm.status_code,200,confirm.text)
        first=self.submit_demo(url);self.assertEqual(first.status_code,200)
        second=self.submit_demo(url);self.assertEqual(second.status_code,200)
        self.assertEqual(first.json()['referral_id'],second.json()['referral_id'])
        self.assertTrue(first.json()['referral_id'].startswith('DEMO-'))
    def test_edit_invalidates_confirmation(self):
        case=self.create();url='/api/cases/'+case['id']
        self.review_confirm(url)
        new=dict(case['fields']);new['village']='Another Village'
        edited=self.client.put(url+'/fields',json={'fields':new,'expected_version':0});self.assertFalse(edited.json()['confirmed'])
        self.assertEqual(self.submit_demo(url).status_code,409)
    def test_readback_no_claim_of_audio(self):
        case=self.create();url='/api/cases/'+case['id']
        with patch('app.main.MODE', 'mock'):
            result=self.client.post(url+'/readback')
        self.assertEqual(result.status_code,200)
        self.assertFalse(result.json()['audio_available'])
        self.assertEqual(result.json()['source'],'text_only')
    def test_prisma_shaped_hindi_text_via_api(self):
        transcript=('नमस्ते पेशेंट्स का रेफरेंस नंबर १०२४ है पेशेंट्स रामपुर गाँव से हैं '
                    'कॉन्टेक्ट नंबर ९८७६५४३२१० है पेशेंट को चेकअप के लिए हॉस्पिटल रेफरल की जरूरत है '
                    'कृपया हॉस्पिटल रेफरल अरेंज करें')
        r=self.client.post('/api/cases/from-transcript',json={'transcript':transcript})
        self.assertEqual(r.status_code,200,r.text)
        fields=r.json()['fields']
        self.assertEqual(fields['patient_ref'],'1024')
        self.assertEqual(fields['village'],'रामपुर')
        self.assertEqual(fields['contact'],'9876543210')
        self.assertIn('हॉस्पिटल रेफरल',fields['referral_reason'])
        self.assertEqual(r.json()['errors'],{})
        self.assertFalse(r.json()['confirmed'])
        self.assertEqual(self.submit_demo('/api/cases/'+r.json()['id']).status_code,409)

    def test_stale_save_returns_conflict(self):
        c=self.create(); url='/api/cases/'+c['id']
        changed={**c['fields'],'village':'Newville'}
        first=self.client.put(url+'/fields',json={'fields':changed,'expected_version':0})
        self.assertEqual(first.status_code,200)
        second=self.client.put(url+'/fields',json={'fields':c['fields'],'expected_version':0})
        self.assertEqual(second.status_code,409)
        self.assertEqual(self.client.get(url).json()['fields']['village'],'Newville')

    def test_invalid_contact_cannot_be_confirmed(self):
        c=self.create();url='/api/cases/'+c['id']
        fields={**c['fields'],'contact':'123'}
        r=self.client.put(url+'/fields',json={'fields':fields,'expected_version':0})
        self.assertIn('contact',r.json()['errors'])
        self.assertEqual(self.client.post(url+'/confirm',json={'expected_version':1,'acknowledged':True}).status_code,409)
        self.assertEqual(self.submit_demo(url).status_code,409)

    def test_missing_case(self):
        self.assertEqual(self.client.get('/api/cases/no-such-id').status_code,404)

if __name__=='__main__': unittest.main()
