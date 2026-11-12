"""Public mode guardrails, entirely local, never contact external services."""
import base64
import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.deploy_guard import public_mode, validate_public_config, correct_basic_auth
from app.main import app

class PublicDemoTests(unittest.TestCase):
    def test_off_by_default(self):
        with patch.dict(os.environ, {'DEMO_PUBLIC':'0'}):
            self.assertFalse(public_mode())
            self.assertTrue(correct_basic_auth(None))

    def test_public_requires_password_and_mock(self):
        with patch.dict(os.environ,{'DEMO_PUBLIC':'1','GNANI_MODE':'mock','DEMO_ACCESS_PASSWORD':'a-unique-password-very-long'},clear=False):
            validate_public_config()
        with patch.dict(os.environ,{'DEMO_PUBLIC':'1','GNANI_MODE':'live','DEMO_ACCESS_PASSWORD':'a-unique-password-very-long'},clear=False):
            with self.assertRaises(ValueError):validate_public_config()
        with patch.dict(os.environ,{'DEMO_PUBLIC':'1','GNANI_MODE':'mock','DEMO_ACCESS_PASSWORD':'short'},clear=False):
            with self.assertRaises(ValueError):validate_public_config()

    def test_password_protects_ui_and_api_but_health_is_public(self):
        env={'DEMO_PUBLIC':'1','GNANI_MODE':'mock','DEMO_ACCESS_PASSWORD':'a-unique-password-very-long'}
        with patch.dict(os.environ,env,clear=False):
            client=TestClient(app)
            self.assertEqual(client.get('/api/health').status_code,200)
            r=client.get('/');self.assertEqual(r.status_code,401)
            self.assertIn('WWW-Authenticate',r.headers)
            self.assertEqual(client.get('/api/config').status_code,401)
            bad={'Authorization':'Basic '+base64.b64encode(b'demo:wrong').decode()}
            self.assertEqual(client.get('/api/config',headers=bad).status_code,401)
            good={'Authorization':'Basic '+base64.b64encode(b'demo:a-unique-password-very-long').decode()}
            yes=client.get('/api/config',headers=good)
            self.assertEqual(yes.status_code,200)
            self.assertEqual(yes.headers['cache-control'],'no-store')
            self.assertEqual(yes.headers['x-content-type-options'],'nosniff')

    def test_public_handoff_blocked_without_network(self):
        env={'DEMO_PUBLIC':'1','GNANI_MODE':'mock','DEMO_ACCESS_PASSWORD':'a-unique-password-very-long'}
        with patch.dict(os.environ,env,clear=False):
            client=TestClient(app)
            auth=('demo','a-unique-password-very-long')
            response=client.post('/api/cases/no-case/handoff/demo',json={'expected_version':0,'scenario':'bleeding','acknowledged_synthetic_only':True},auth=auth)
            self.assertEqual(response.status_code,403)

if __name__=='__main__':unittest.main()
