"""Stage 9 independent-of-network functional regressions; all cases are synthetic."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import main
from app.storage import SQLiteCaseStore
from app.handoff import demo_sid

TRANSCRIPT='Patient ID: BENCH001, village: Rampur, contact: 9999999999, reason: referral coordination'
class Reply:
    def __init__(self, data): self.status_code=200;self.data=data
    def json(self): return self.data

class Stage9Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.old=main.STORE
        main.STORE=SQLiteCaseStore(self.temp.name+'/cases.sqlite3')
        self.client=TestClient(main.app)
        self.case=self.client.post('/api/cases/from-transcript',json={'transcript':TRANSCRIPT}).json()
        self.url='/api/cases/'+self.case['id']
    def tearDown(self):
        main.STORE=self.old
        self.temp.cleanup()
    def ready(self):
        self.assertEqual(self.client.post(self.url+'/readback').status_code,200)
        self.assertEqual(self.client.post(self.url+'/confirm',json={'expected_version':0,'acknowledged':True}).status_code,200)
        self.assertEqual(self.client.post(self.url+'/submit',json={'expected_version':0,'idempotency_key':'benchmark-key-01'}).status_code,200)
    def handoff(self,scenario='bleeding'):
        return self.client.post(self.url+'/handoff/demo',json={'expected_version':0,'scenario':scenario,'acknowledged_synthetic_only':True})
    def test_initial_backend_overview_is_not_linked(self):
        self.assertEqual(self.client.get(self.url).json()['demo_backend'],{'status':'not_linked','backend_ref':None,'backend_step':None})
    def test_unconfirmed_handoff_fails_before_network(self):
        with patch('app.handoff.requests.get') as req:
            self.assertEqual(self.handoff().status_code,409)
            req.assert_not_called()
    def test_handoff_overview_persists_across_restart_and_retry(self):
        self.ready();sid=demo_sid(self.case['id'])
        state={'id':sid,'live':False,'cur':None,'step':'start'}
        def fake_post(*args,**kwargs):
            state.update({'cur':{'id':'MK-SYN-144','type':'bleeding'},'step':'details'})
            return Reply(dict(state))
        with patch('app.handoff.requests.get',side_effect=lambda *a,**k:Reply(dict(state))),patch('app.handoff.requests.post',side_effect=fake_post) as posted:
            a=self.handoff(); b=self.handoff()
            self.assertEqual(a.status_code,200,a.text)
            self.assertEqual(b.status_code,200,b.text)
            self.assertEqual(posted.call_count,1)
        v=self.client.get(self.url).json()
        self.assertEqual(v['demo_backend'],{'status':'linked','backend_ref':'MK-SYN-144','backend_step':'details'})
        self.assertEqual(sum(e['event']=='matri_demo_handoff_created' for e in v['events']),1)
        restored=SQLiteCaseStore(main.STORE.path).get(self.case['id'])
        self.assertTrue(restored.submitted)
        self.assertEqual(main.demo_link_from_events(restored),v['demo_backend'])
    def test_old_stage7_handoff_event_can_be_upgraded_without_duplicating(self):
        self.ready()
        main.STORE.mutate(self.case['id'], lambda c: c.log('matri_demo_handoff_created'))
        v=self.client.get(self.url).json()
        self.assertEqual(v['demo_backend']['status'],'linked_reference_unrecorded')
        sid=demo_sid(self.case['id'])
        state={'id':sid,'live':False,'cur':{'id':'MK-RECOVER','type':'bleeding'},'step':'details'}
        with patch('app.handoff.requests.get',return_value=Reply(state)),patch('app.handoff.requests.post') as post:
            r=self.handoff();self.assertEqual(r.status_code,200,r.text)
            post.assert_not_called()
        v=self.client.get(self.url).json()
        self.assertEqual(v['demo_backend']['backend_ref'],'MK-RECOVER')
        self.assertEqual(sum(e['event']=='matri_demo_handoff_created' for e in v['events']),1)
    def test_backend_overview_contains_no_contact_or_transcript(self):
        self.ready();sid=demo_sid(self.case['id'])
        state={'id':sid,'live':False,'cur':{'id':'MK-SAFE','type':'bleeding'},'step':'details'}
        with patch('app.handoff.requests.get',return_value=Reply(state)):
            self.handoff()
        v=self.client.get(self.url).json()
        self.assertNotIn('9999999999',str(v['demo_backend']))
        self.assertNotIn('BENCH001',str(v['demo_backend']))
        self.assertNotIn(sid,str(v['demo_backend']))
    def test_legacy_metadata_missing_correctly_not_presented_as_validated(self):
        self.ready()
        main.STORE.mutate(self.case['id'], lambda c: c.log('matri_demo_handoff_created'))
        v=self.client.get(self.url).json()
        self.assertEqual(v['demo_backend']['status'],'linked_reference_unrecorded')
        self.assertIsNone(v['demo_backend']['backend_ref'])
    def test_concurrent_idempotent_submits_only_one_audit_event(self):
        self.client.post(self.url+'/readback')
        self.client.post(self.url+'/confirm',json={'expected_version':0,'acknowledged':True})
        body={'expected_version':0,'idempotency_key':'benchmark-key-01'}
        with ThreadPoolExecutor(max_workers=6) as pool:
            responses=list(pool.map(lambda _: self.client.post(self.url+'/submit',json=body),range(12)))
        self.assertTrue(all(r.status_code==200 for r in responses))
        self.assertEqual(len({r.json()['referral_id'] for r in responses}),1)
        self.assertEqual(sum(e['event']=='simulated_referral_created' for e in self.client.get(self.url).json()['events']),1)
    def test_wrong_request_key_after_submit_is_rejected(self):
        self.ready()
        res=self.client.post(self.url+'/submit',json={'expected_version':0,'idempotency_key':'different-key-99'})
        self.assertEqual(res.status_code,409)
    def test_stale_confirmation_cannot_submit(self):
        fields=self.case['fields'].copy();fields['village']='OtherVillage'
        r=self.client.put(self.url+'/fields',json={'expected_version':0,'fields':fields})
        self.assertEqual(r.status_code,200)
        self.assertEqual(self.client.post(self.url+'/submit',json={'expected_version':1,'idempotency_key':'benchmark-key-01'}).status_code,409)
    def test_mock_mode_audio_cannot_fake_real_tts(self):
        with patch.object(main,'MODE','mock'):
            r=self.client.post(self.url+'/readback/audio',json={'expected_version':0})
        self.assertEqual(r.status_code,400)
    def test_invalid_fields_do_not_allow_confirmation(self):
        fields={**self.case['fields'],'contact':'1234'}
        self.client.put(self.url+'/fields',json={'expected_version':0,'fields':fields})
        self.assertEqual(self.client.post(self.url+'/readback').status_code,422)
        self.assertEqual(self.client.post(self.url+'/confirm',json={'expected_version':1,'acknowledged':True}).status_code,409)
    def test_invalid_scenario_does_not_contact_backend(self):
        self.ready()
        with patch('app.handoff.requests.get') as get:
            self.assertEqual(self.handoff('not-real').status_code,422)
            get.assert_not_called()
    def test_backend_rejects_live_session(self):
        self.ready();sid=demo_sid(self.case['id'])
        with patch('app.handoff.requests.get',return_value=Reply({'id':sid,'live':True})):
            self.assertEqual(self.handoff().status_code,502)
    def test_recovery_state_keeps_exact_version(self):
        self.ready()
        c=SQLiteCaseStore(main.STORE.path).get(self.case['id'])
        self.assertEqual(c.version,0)
        self.assertTrue(c.can_submit())
        self.assertTrue(c.submitted)
    def test_handoff_disabled_before_submit(self):
        self.client.post(self.url+'/readback')
        self.client.post(self.url+'/confirm',json={'expected_version':0,'acknowledged':True})
        self.assertEqual(self.handoff().status_code,409)
    def test_stage9_ui_has_last_known_backend_reference(self):
        from pathlib import Path
        html=(Path(__file__).resolve().parents[1]/'app/static/index.html').read_text()
        for name in ('caseBackendStatus','caseBackendRef','caseBackendStep'):
            self.assertIn('id="'+name+'"',html)
        self.assertIn('x.demo_backend',html)

if __name__=='__main__':unittest.main()
