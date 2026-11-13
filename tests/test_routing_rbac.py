"""Routing (readiness, reroute, timer) and server-side RBAC (who sees what), offline."""
import os, tempfile, atexit, time, unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

DIR = tempfile.TemporaryDirectory(); atexit.register(DIR.cleanup)
_prev = os.environ.get('CASE_DB_PATH')
os.environ['CASE_DB_PATH'] = os.path.join(DIR.name, 'routing.sqlite3')
from app import main, routing, rbac
if _prev is None: os.environ.pop('CASE_DB_PATH', None)
else: os.environ['CASE_DB_PATH'] = _prev

TRANSCRIPT = 'Patient ID: RB-77, village: Rampur, contact: 9876543210, reason: heavy bleeding after delivery'
ALL_ROLES = list(rbac.ROLES)


class ReadinessTests(unittest.TestCase):
    def test_bleeding_skips_chc_and_proposes_dh(self):
        rows = {r['id']: r for r in routing.readiness('bleeding')}
        self.assertFalse(rows['chc']['ready']); self.assertIn('anaesthetist', rows['chc']['missing'])
        self.assertEqual(routing.plan('bleeding'), {'proposed': 'dh', 'backup': 'sdh'})

    def test_eclampsia_goes_to_sdh_because_dh_has_no_hdu(self):
        self.assertIn('hdu', {r['id']: r for r in routing.readiness('fits')}['dh']['missing'])
        self.assertEqual(routing.plan('fits'), {'proposed': 'sdh', 'backup': 'mc'})

    def test_medical_college_is_a_fallback(self):
        self.assertEqual(routing.plan('bleeding', exclude=('dh', 'sdh'))['proposed'], 'mc')
        self.assertEqual(routing.plan('bleeding', exclude=('dh', 'sdh', 'mc')), {'proposed': None, 'backup': None})


class RoutingRbacApiTests(unittest.TestCase):
    def setUp(self):
        main.STORE.clear()
        self.client = TestClient(main.app)
        self.tokens = {}

    def token(self, role):
        if role not in self.tokens:
            code = self.client.post('/api/role/login', json={'role': role}).json()['demo_code']
            r = self.client.post('/api/role/verify', json={'role': role, 'code': code})
            self.assertEqual(r.status_code, 200, r.text)
            self.tokens[role] = r.json()['token']
        return {'X-Role-Token': self.tokens[role]}

    def inbox(self, role):
        r = self.client.get('/api/role/inbox', headers=self.token(role))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()['cases']

    def act(self, role, ref, action):
        return self.client.post(f'/api/role/cases/{ref}/act', json={'action': action}, headers=self.token(role))

    def submitted_case(self, emergency='bleeding'):
        x = self.client.post('/api/cases/from-transcript', json={'transcript': TRANSCRIPT, 'emergency': emergency}).json()
        u = '/api/cases/' + x['id']
        self.client.post(u + '/readback')
        self.client.post(u + '/confirm', json={'expected_version': 0, 'acknowledged': True})
        s = self.client.post(u + '/submit', json={'expected_version': 0, 'idempotency_key': 'route-' + x['id'][:8]})
        self.assertEqual(s.status_code, 200, s.text)
        return x['id'], u, x['id'][:8].upper()

    def send(self, u):
        r = self.client.post(u + '/routing/send', json={'expected_version': 0})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    # ---- routing
    def test_emergency_is_worker_selected_and_validated(self):
        x = self.client.post('/api/cases/from-transcript', json={'transcript': TRANSCRIPT, 'emergency': 'bleeding'}).json()
        self.assertEqual(x['emergency'], 'bleeding')
        self.assertTrue(any(e['event'] == 'emergency_selected_by_worker_bleeding' for e in x['events']))
        self.assertEqual(self.client.post('/api/cases/from-transcript', json={'transcript': TRANSCRIPT, 'emergency': 'diagnose-me'}).status_code, 422)

    def test_cannot_route_before_submit_or_without_emergency(self):
        x = self.client.post('/api/cases/from-transcript', json={'transcript': TRANSCRIPT, 'emergency': 'bleeding'}).json()
        self.assertEqual(self.client.post(f"/api/cases/{x['id']}/routing/send", json={'expected_version': 0}).status_code, 409)
        y = self.client.post('/api/cases/from-transcript', json={'transcript': TRANSCRIPT}).json()
        u = '/api/cases/' + y['id']
        self.client.post(u + '/readback'); self.client.post(u + '/confirm', json={'expected_version': 0, 'acknowledged': True})
        self.client.post(u + '/submit', json={'expected_version': 0, 'idempotency_key': 'no-emer-01'})
        self.assertEqual(self.client.post(u + '/routing/send', json={'expected_version': 0}).status_code, 409)

    def test_send_asks_nearest_ready_hospital_and_is_idempotent(self):
        _, u, _ = self.submitted_case()
        x = self.send(u)
        self.assertEqual(x['routing']['status'], 'asked')
        self.assertEqual(x['routing']['target_name'], 'DH Devgarh')
        self.assertEqual(x['routing']['backup_name'], 'SDH Kheri')
        self.assertEqual(self.send(u)['routing']['target'], 'dh')
        self.assertEqual(sum(e['event'].startswith('routing_asked') for e in self.client.get(u).json()['events']), 1)

    def test_hospital_confirms_then_team_is_told(self):
        _, u, ref = self.submitted_case()
        self.send(u)
        dh = self.inbox('dh')
        self.assertEqual(len(dh), 1); self.assertEqual(dh[0]['actions'], ['confirm', 'not_ready'])
        self.assertEqual(dh[0]['eta_min'], routing.eta_min(21))            # ETA visible while being asked
        self.assertEqual(self.inbox('driver'), [])                         # nobody else sees it yet
        self.assertEqual(self.act('dh', ref, 'confirm').status_code, 200)
        r = self.client.get(u).json()['routing']
        self.assertEqual(r['status'], 'confirmed'); self.assertEqual(r['ambulance'], '108 Ambulance 1')
        self.assertIn('bloodbank', r['notified'])                          # bleeding needs the blood bank
        for role in ('driver', 'emt', 'doctor', 'family', 'bloodbank', 'district'):
            self.assertEqual(len(self.inbox(role)), 1, role)
        self.assertEqual(self.inbox('sdh'), [])                            # never asked
        self.assertEqual(self.act('dh', ref, 'arrived').status_code, 200)
        self.assertEqual(self.client.get(u).json()['routing']['status'], 'arrived')

    def test_not_ready_reroutes_to_backup(self):
        _, u, ref = self.submitted_case()
        self.send(u)
        self.act('dh', ref, 'not_ready')
        r = self.client.get(u).json()['routing']
        self.assertEqual(r['target'], 'sdh'); self.assertEqual(r['history'][0]['outcome'], 'not_ready')
        self.assertTrue(any('re-routed' in a for a in r['alerts']))
        self.assertEqual(self.inbox('sdh')[0]['actions'], ['confirm', 'not_ready'])
        self.assertEqual(self.inbox('dh')[0]['status'], 'moved_to_another_hospital')
        self.assertEqual(self.act('dh', ref, 'confirm').status_code, 409)   # DH can no longer confirm

    def test_no_reply_in_two_minutes_reroutes(self):
        _, u, ref = self.submitted_case()
        self.send(u)
        later = routing.now_ts() + routing.REPLY_WINDOW_SEC + 1
        with patch.object(routing, 'now_ts', return_value=later):
            r = self.client.get(u).json()['routing']
        self.assertEqual(r['target'], 'sdh'); self.assertEqual(r['history'][0]['outcome'], 'no_reply')

    def test_district_skip_two_minutes_demo_control(self):
        _, u, ref = self.submitted_case()
        self.send(u)
        self.assertEqual(self.act('district', ref, 'skip_wait').status_code, 200)
        self.assertEqual(self.client.get(u).json()['routing']['target'], 'sdh')

    def test_no_hospital_left_alerts_district(self):
        _, u, ref = self.submitted_case()
        self.send(u)
        for fac in ('dh', 'sdh', 'mc'):
            self.act(fac, ref, 'not_ready')
        r = self.client.get(u).json()['routing']
        self.assertEqual(r['status'], 'no_hospital')
        self.assertTrue(any('district control room' in a for a in self.inbox('district')[0]['alerts']))

    # ---- RBAC
    def test_login_needs_the_one_time_code(self):
        self.client.post('/api/role/login', json={'role': 'dh'})
        self.assertEqual(self.client.post('/api/role/verify', json={'role': 'dh', 'code': '000000x'}).status_code, 401)
        self.assertEqual(self.client.post('/api/role/login', json={'role': 'admin'}).status_code, 404)
        self.assertEqual(self.client.get('/api/role/inbox').status_code, 401)
        self.assertEqual(self.client.get('/api/role/inbox', headers={'X-Role-Token': 'forged'}).status_code, 401)

    def test_tampered_token_rejected(self):
        import base64
        good = self.token('driver')['X-Role-Token']
        role, exp, sig = base64.urlsafe_b64decode(good).decode().split('|')
        forged = base64.urlsafe_b64encode(f'district|{exp}|{sig}'.encode()).decode()
        self.assertEqual(self.client.get('/api/role/inbox', headers={'X-Role-Token': forged}).status_code, 401)

    def test_roles_cannot_do_other_roles_actions(self):
        _, u, ref = self.submitted_case()
        self.send(u)
        self.assertEqual(self.act('driver', ref, 'confirm').status_code, 403)
        self.assertEqual(self.act('family', ref, 'skip_wait').status_code, 403)
        self.assertEqual(self.act('sdh', ref, 'confirm').status_code, 409)   # not the asked hospital

    def test_no_role_ever_sees_contact_or_transcript(self):
        _, u, ref = self.submitted_case()
        self.send(u); self.act('dh', ref, 'confirm')
        for role in ALL_ROLES:
            blob = repr(self.client.get('/api/role/inbox', headers=self.token(role)).json())
            self.assertNotIn('9876543210', blob, role)
            self.assertNotIn('Patient ID: RB-77', blob, role)

    def test_minimum_necessary_views(self):
        _, u, ref = self.submitted_case()
        self.send(u); self.act('dh', ref, 'confirm')
        driver, family, district, bloodbank = (self.inbox(r)[0] for r in ('driver', 'family', 'district', 'bloodbank'))
        for v, name in ((driver, 'driver'), (family, 'family'), (district, 'district'), (bloodbank, 'bloodbank')):
            for medical in ('reason', 'patient_ref'):
                self.assertNotIn(medical, v, f'{name} must not see {medical}')
        self.assertEqual(driver['pickup'], 'Rampur')
        self.assertEqual(set(family) - {'case_id', 'status', 'hospital', 'eta_min'}, set())
        self.assertNotIn('village', district)
        hospital = self.inbox('dh')[0]
        self.assertEqual(hospital['patient_ref'], 'RB-77'); self.assertEqual(hospital['reason'], 'heavy bleeding after delivery')
        doctor = self.inbox('doctor')[0]
        self.assertEqual(doctor['patient_ref'], 'RB-77')

    def test_doctor_summary_expires(self):
        _, u, ref = self.submitted_case()
        self.send(u); self.act('dh', ref, 'confirm')
        with patch.object(rbac.time, 'time', return_value=time.time() + rbac.DOCTOR_SUMMARY_TTL + 60):
            # token still valid (8 h); the summary itself is gone
            v = rbac.view_for(main.STORE.get(main.STORE.all_ids()[0]), 'doctor')
        self.assertTrue(v['expired']); self.assertNotIn('patient_ref', v)

    def test_blood_bank_only_for_bleeding_emergencies(self):
        _, u, ref = self.submitted_case('fits')
        self.send(u); self.act('sdh', ref, 'confirm')
        self.assertEqual(self.inbox('bloodbank'), [])
        self.assertEqual(len(self.inbox('driver')), 1)

    def test_readiness_endpoint_and_roles_listing(self):
        r = self.client.get('/api/routing/readiness/bleeding').json()
        self.assertEqual(r['proposed'], 'dh'); self.assertIn('Moluvi Gufran', r['review'])
        self.assertEqual(self.client.get('/api/routing/readiness/xyz').status_code, 404)
        roles = self.client.get('/api/roles').json()
        self.assertIn('driver', [x['role'] for x in roles['roles']])
        self.assertIn('No medical details', roles['who_sees_what']['driver'])

    def test_role_phones_work_behind_public_preview_password(self):
        # Public preview uses HTTP Basic in "Authorization"; the role token must not collide with it.
        import base64
        pw = 'a-very-long-demo-password'
        basic = {'Authorization': 'Basic ' + base64.b64encode(f'demo:{pw}'.encode()).decode()}
        with patch.dict(os.environ, {'DEMO_PUBLIC': '1', 'DEMO_ACCESS_PASSWORD': pw}):
            self.assertEqual(self.client.get('/roles').status_code, 401)                      # password gate
            self.assertEqual(self.client.get('/roles', headers=basic).status_code, 200)
            code = self.client.post('/api/role/login', json={'role': 'district'}, headers=basic).json()['demo_code']
            tok = self.client.post('/api/role/verify', json={'role': 'district', 'code': code}, headers=basic).json()['token']
            r = self.client.get('/api/role/inbox', headers={**basic, 'X-Role-Token': tok})
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(self.client.get('/api/role/inbox', headers=basic).status_code, 401)  # still needs the role login
            self.assertTrue(self.client.get('/api/config', headers=basic).json()['public_preview'])

    def test_old_cases_without_routing_still_load(self):
        import json
        raw = json.dumps({'id': 'legacy2', 'transcript': 't', 'fields': {}, 'version': 0, 'confirmation_digest': None,
                          'confirmed_version': None, 'submitted': False, 'referral_id': None, 'events': [],
                          'reviewed_digest': None, 'reviewed_version': None, 'submission_key': None})
        c = main.STORE._decode(raw)
        self.assertEqual((c.emergency, c.routing), (None, {}))


if __name__ == '__main__':
    unittest.main()
