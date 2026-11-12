import unittest
from unittest.mock import patch
import requests
from app.timbre import synthesize, TimbreError, TTS_URL

WAV = b'RIFF' + (40).to_bytes(4,'little') + b'WAVE' + (b'0' * 36)

class DummyResponse:
    def __init__(self, data=WAV, status=200): self.data=data; self.status_code=status; self.closed=False
    def iter_content(self, chunk_size=65536): yield self.data
    def close(self): self.closed=True

class TimbreTests(unittest.TestCase):
    def test_real_contract_payload_and_secret_header(self):
        observed={}
        def fake_post(url,**kw):
            observed.update(url=url,**kw)
            return DummyResponse()
        self.assertEqual(synthesize('यह परीक्षण है','secret',transport=fake_post),WAV)
        self.assertEqual(observed['url'],TTS_URL)
        self.assertEqual(observed['headers']['X-API-Key-ID'],'secret')
        self.assertEqual(observed['json']['model'],'timbre-v2.5')
        self.assertEqual(observed['json']['voice'],'Nalini')
        self.assertEqual(observed['json']['audio_config']['container'],'wav')
        self.assertEqual(observed['json']['language'],'hi-IN')
        self.assertTrue(observed['stream'])

    def test_api_error_statuses_are_safe(self):
        for http_status in (400,401,402,403,429,500,503):
            with self.subTest(code=http_status):
                with self.assertRaises(TimbreError) as ctx:
                    synthesize('परीक्षण','secret',transport=lambda *a,**k: DummyResponse(status=http_status))
                self.assertNotIn('secret',str(ctx.exception))

    def test_bad_content_rejected(self):
        for data in (b'',b'{"audio":"oops"}',b'1234567890'*6):
            with self.subTest(data=data):
                with self.assertRaises(TimbreError): synthesize('परीक्षण','secret',transport=lambda *a,**k: DummyResponse(data=data))

    def test_large_response_rejected(self):
        with self.assertRaises(TimbreError):
            synthesize('परीक्षण','secret',transport=lambda *a,**k: DummyResponse(data=WAV+b'0'*(5*1024*1024)))

    def test_timeout_and_transport_error(self):
        for error in (requests.exceptions.Timeout(),requests.exceptions.ConnectionError()):
            with self.assertRaises(TimbreError):
                synthesize('परीक्षण','secret',transport=lambda *a,**k: (_ for _ in ()).throw(error))

    def test_empty_text_and_missing_key(self):
        for text,key in (('', 'secret'), ('hi', '')):
            with self.assertRaises(TimbreError): synthesize(text,key)

    def test_model_pair_configuration(self):
        with patch.dict('os.environ', {'GNANI_TIMBRE_MODEL':'timbre-v3.0','GNANI_TIMBRE_VOICE':'Shivani'}):
            seen={}
            def fake_post(url, **kw): seen.update(kw);return DummyResponse()
            synthesize('परीक्षण','secret',transport=fake_post)
            self.assertEqual(seen['json']['model'],'timbre-v3.0')
        with patch.dict('os.environ', {'GNANI_TIMBRE_MODEL':'timbre-v3.0','GNANI_TIMBRE_VOICE':'Nalini'}):
            with self.assertRaises(TimbreError): synthesize('परीक्षण','secret',transport=lambda *a,**k: DummyResponse())

if __name__ == '__main__':unittest.main()
