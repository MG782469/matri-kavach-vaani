"""Static contract checks for the Stage 8 presentation layer (offline, no live credentials)."""
from pathlib import Path
import re
import unittest

HTML = (Path(__file__).resolve().parents[1] / 'app' / 'static' / 'index.html').read_text(encoding='utf-8')

class Stage8UiTests(unittest.TestCase):
    def test_main_four_steps_present(self):
        for step in ('capture', 'verify', 'dispatch', 'handoff'):
            self.assertIn('data-step="'+step+'"', HTML)

    def test_all_live_action_handlers_retained(self):
        for name in ('create', 'upload', 'save', 'readback', 'generateAudio', 'confirm', 'submit', 'handoff'):
            self.assertIn('onclick="'+name+'()"', HTML)

    def test_stage7_safety_controls_preserved(self):
        for name in ('ack', 'handoffAck', 'scenario', 'submit', 'handoffButton'):
            self.assertRegex(HTML, r'id="'+name+r'"')
        self.assertIn('expected_version:c.version', HTML)
        self.assertIn('acknowledged_synthetic_only:true', HTML)

    def test_source_transcript_remains_read_only(self):
        self.assertRegex(HTML, r'id="recognizedText" readonly')

    def test_status_uses_text_not_html_for_events(self):
        self.assertIn("$('proof').textContent=JSON.stringify", HTML)
        self.assertIn('escapeHtml(String(e.event', HTML)

    def test_mobile_and_accessible_controls(self):
        self.assertIn('@media(max-width:600px)',HTML)
        self.assertIn('prefers-reduced-motion',HTML)
        self.assertIn('aria-live="polite"', HTML)

    def test_safety_warning_is_visible(self):
        self.assertIn('not for clinical use',HTML)
        self.assertIn('no hospital routing or real messages',HTML)

    def test_backend_contract_and_case_restore_unchanged(self):
        for path in ('/api/cases/from-transcript', '/api/cases/from-audio', '/readback/audio', '/handoff/demo'):
            self.assertIn(path,HTML)
        self.assertIn("sessionStorage.getItem('vaani_case_id')",HTML)

if __name__ == '__main__':unittest.main()
