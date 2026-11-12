"""No remote connections: mocked transport checks against original Express API shape."""
import unittest
import tempfile
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import main
from app.storage import SQLiteCaseStore
from app.handoff import create_demo_handoff, demo_sid, BridgeError

TRANSCRIPT='Patient ID: TEST001, village: Rampur, contact: 9999999999, reason: referral coordination'
class FakeReply:
    def __init__(self, code, data): self.status_code,self.data=code,data
    def json(self): return self.data

class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.original=main.STORE
        main.STORE=SQLiteCaseStore(self.tmp.name+'/db.sqlite3')
        self.client=TestClient(main.app)
        self.case=self.client.post('/api/cases/from-transcript',json={'transcript':TRANSCRIPT}).json()
        self.endpoint='/api/cases/'+self.case['id']+'/handoff/demo'
    def tearDown(self):
        main.STORE=self.original
        self.tmp.cleanup()
    def body(self,scenario='bleeding',version=0,ack=True):
        return {'expected_version':version,'scenario':scenario,'acknowledged_synthetic_only':ack}
    def submit_case(self):
        root='/api/cases/'+self.case['id']
        self.assertEqual(self.client.post(root+'/readback').status_code,200)
        self.assertEqual(self.client.post(root+'/confirm',json={'expected_version':0,'acknowledged':True}).status_code,200)
        self.assertEqual(self.client.post(root+'/submit',json={'expected_version':0,'idempotency_key':'demo-stage7-12345'}).status_code,200)
    def test_cannot_handoff_unsubmitted(self):
        self.assertEqual(self.client.post(self.endpoint,json=self.body()).status_code,409)
    def test_requires_explicit_ack(self):
        self.submit_case()
        self.assertEqual(self.client.post(self.endpoint,json=self.body(ack=False)).status_code,422)
    def test_rejects_invalid_scenario_without_network(self):
        self.submit_case()
        with patch('app.handoff.requests.get') as get:
            self.assertEqual(self.client.post(self.endpoint,json=self.body(scenario='checkup')).status_code,422)
            get.assert_not_called()
    def test_stale_version_without_network(self):
        self.submit_case()
        with patch('app.handoff.requests.get') as get:
            self.assertEqual(self.client.post(self.endpoint,json=self.body(version=7)).status_code,409)
            get.assert_not_called()
    def test_no_patient_info_sent_and_idempotent(self):
        self.submit_case()
        sid=demo_sid(self.case['id'])
        calls=[]
        state={'id':sid,'live':False,'cur':None,'step':'start'}
        def get(url,**kwargs):
            calls.append(('get',url,kwargs))
            return FakeReply(200,dict(state))
        def post(url,**kwargs):
            calls.append(('post',url,kwargs))
            self.assertEqual(kwargs['json']['action'],'startReferral')
            self.assertEqual(kwargs['json']['sid'],sid)
            self.assertEqual(kwargs['json']['args'],{'typeId':'bleeding'})
            state.update({'cur':{'id':'MK-DEMO','type':'bleeding'},'step':'details'})
            return FakeReply(200,dict(state))
        with patch('app.handoff.requests.get',side_effect=get),patch('app.handoff.requests.post',side_effect=post):
            a=self.client.post(self.endpoint,json=self.body())
            b=self.client.post(self.endpoint,json=self.body())
        self.assertEqual(a.status_code,200,a.text)
        self.assertEqual(b.status_code,200,b.text)
        self.assertTrue(b.json()['already_exists'])
        self.assertFalse(a.json()['already_exists'])
        self.assertEqual(len([x for x in calls if x[0]=='post']),1)
        self.assertNotIn('9999999999',str(calls))
        self.assertNotIn('TEST001',str(calls))
        self.assertFalse(a.json()['external_notifications_sent'])
        c=self.client.get('/api/cases/'+self.case['id']).json()
        self.assertEqual(sum(e['event']=='matri_demo_handoff_created' for e in c['events']),1)
    def test_live_session_rejected(self):
        self.submit_case()
        sid=demo_sid(self.case['id'])
        with patch('app.handoff.requests.get',return_value=FakeReply(200,{'id':sid,'live':True})):
            r=self.client.post(self.endpoint,json=self.body())
        self.assertEqual(r.status_code,502)
    def test_wrong_sid_rejected(self):
        self.submit_case()
        with patch('app.handoff.requests.get',return_value=FakeReply(200,{'id':'live','live':False})):
            r=self.client.post(self.endpoint,json=self.body())
        self.assertEqual(r.status_code,502)
    def test_bad_backend_host_rejected(self):
        self.submit_case()
        with patch.dict('os.environ',{'MATRI_DEMO_BASE_URL':'https://evil.example'}):
            r=self.client.post(self.endpoint,json=self.body())
        self.assertEqual(r.status_code,422)
    def test_backend_down_returns_safe_error(self):
        import requests
        self.submit_case()
        with patch('app.handoff.requests.get',side_effect=requests.Timeout):
            r=self.client.post(self.endpoint,json=self.body())
        self.assertEqual(r.status_code,502)
    def test_scenario_collision_blocked(self):
        self.submit_case()
        sid=demo_sid(self.case['id'])
        with patch('app.handoff.requests.get',return_value=FakeReply(200,{'id':sid,'live':False,'cur':{'id':'MK-1','type':'fits'},'step':'details'})):
            r=self.client.post(self.endpoint,json=self.body())
        self.assertEqual(r.status_code,409)
    def test_demo_sid_stable_and_not_live(self):
        self.assertEqual(demo_sid('abc'),demo_sid('abc'))
        self.assertRegex(demo_sid('abc'),r'^[a-f0-9]{16}$')
        self.assertNotEqual(demo_sid('abc'),demo_sid('def'))

if __name__=='__main__': unittest.main()
