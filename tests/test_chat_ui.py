"""Chat view (/chat): served, wired to every workflow endpoint, safe rendering (offline)."""
import os, tempfile, atexit, unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

DIR = tempfile.TemporaryDirectory(); atexit.register(DIR.cleanup)
_prev = os.environ.get('CASE_DB_PATH')
os.environ['CASE_DB_PATH'] = os.path.join(DIR.name, 'chatui.sqlite3')
from app import main
if _prev is None: os.environ.pop('CASE_DB_PATH', None)
else: os.environ['CASE_DB_PATH'] = _prev

STATIC = Path(__file__).resolve().parents[1] / 'app' / 'static'
CHAT = (STATIC / 'chat.html').read_text(encoding='utf-8')
VOICE = (STATIC / 'voice.js').read_text(encoding='utf-8')


class ChatUiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_chat_and_recorder_are_served(self):
        r = self.client.get('/chat')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Vaani Chat', r.text)
        self.assertEqual(self.client.get('/static/voice.js').status_code, 200)
        self.assertIn('/static/voice.js', CHAT)

    def test_every_workflow_endpoint_is_wired(self):
        for path in ('/api/cases/from-transcript', '/api/cases/from-audio', '/clarify', '/correct', '/clarification/audio',
                     '/readback', '/readback/audio', '/confirm/voice', '/confirm/question-audio', "'/confirm'",
                     '/submit', '/handoff/demo', '/api/config'):
            self.assertIn(path, CHAT, path)

    def test_safety_contract_in_ui(self):
        self.assertIn('acknowledged_synthetic_only: true', CHAT)          # handoff acknowledgement
        self.assertIn('idempotency_key', CHAT)
        self.assertIn('expected_version: c.version', CHAT)                # stale-version protection
        self.assertIn('Synthetic demo', CHAT)
        self.assertIn('not for clinical use', CHAT)

    def test_server_text_is_escaped_before_innerHTML(self):
        self.assertRegex(CHAT, r"const esc = \w+ =>")
        for risky in ("esc(text)", "esc(v)", "esc(x.referral_id)", "esc(r.backend_ref)", "esc(opts.heard"):
            self.assertIn(risky, CHAT, risky)

    def test_recorder_makes_16k_wav(self):
        self.assertIn("encodeWav(out.getChannelData(0), 16000)", VOICE)
        self.assertIn("'RIFF'", VOICE)

    def test_dark_mode_and_mobile(self):
        self.assertIn('prefers-color-scheme: dark', CHAT)
        self.assertIn('@media (max-width: 900px)', CHAT)
        self.assertIn('100dvh', CHAT)

    def test_dashboard_links_to_chat(self):
        html = (STATIC / 'index.html').read_text(encoding='utf-8')
        self.assertIn('href="/chat"', html)
        self.assertIn('href="/"', CHAT)

    def test_matri_kavach_opening_flow(self):
        # Hi -> language -> emergency list -> details (all at once / one by one)
        for marker in ("function hello()", "function greet()", "function chooseLang(", "function askEmergency()",
                       "function openList()", "function chooseEmergency(", "function askDetails()", "async function startGuided()"):
            self.assertIn(marker, CHAT, marker)
        self.assertIn("'English'", CHAT)
        self.assertIn("हिंदी (Hindi)", CHAT)

    def test_emergency_list_matches_backend_scenarios(self):
        import re
        from app.handoff import SCENARIOS
        ids = set(re.findall(r"\{id:'(\w+)'", CHAT))
        self.assertEqual(ids - {'other'}, SCENARIOS)                       # every choice can be handed off
        self.assertIn("noReferral:true", CHAT)                            # "call the doctor" never creates a referral
        self.assertIn("scenario: emergency.id", CHAT)                     # handoff uses the worker's own choice

    def test_clinical_advisor_and_no_diagnosis_wording(self):
        self.assertIn('Moluvi Gufran', CHAT)
        self.assertIn('never diagnoses', CHAT)

    def test_guided_draft_has_no_fields_so_every_field_is_asked(self):
        from app.extraction import parse_transcript
        for name in ('Heavy bleeding after delivery (PPH)', 'Fits or eclampsia', 'Obstructed labour',
                     'Bleeding before delivery (APH)', 'Fever after delivery (possible sepsis)', 'Newborn emergency'):
            self.assertEqual(set(parse_transcript('Guided referral · ' + name).values()), {''}, name)

    def test_public_mode_protects_chat(self):
        with patch.dict(os.environ, {'DEMO_PUBLIC': '1', 'DEMO_ACCESS_PASSWORD': 'a-very-long-demo-pass'}):
            self.assertEqual(self.client.get('/chat').status_code, 401)


if __name__ == '__main__':
    unittest.main()
