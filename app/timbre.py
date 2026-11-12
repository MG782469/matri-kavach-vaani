"""Gnani Timbre REST adapter. Only synthetic data; secrets never leave the server.

Endpoint and model/voice are documented at https://docs.gnani.ai/api/TTS/tts-inference.
"""
import os
import requests

TTS_URL = 'https://api.vachana.ai/api/v1/tts/inference'
MAX_TTS_TEXT_CHARS = 900
MAX_AUDIO_RESPONSE_BYTES = 5 * 1024 * 1024

class TimbreError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def model_and_voice():
    model = os.getenv('GNANI_TIMBRE_MODEL', 'timbre-v2.5').strip()
    if model not in ('timbre-v2.5', 'timbre-v3.0'):
        raise TimbreError('Invalid Timbre model configuration', 503)
    default = 'Nalini' if model == 'timbre-v2.5' else 'Shivani'
    voice = os.getenv('GNANI_TIMBRE_VOICE', default).strip()
    # Don't allow arbitrary user-controlled voice value; known valid defaults
    # and a small allowlist of documented voices per model.
    allowed = {'timbre-v2.5': {'Nalini', 'Kaveri', 'Deepak', 'Poorvi'},
               'timbre-v3.0': {'Shivani', 'Avinash', 'Lakshmi'}}
    if voice not in allowed[model]:
        raise TimbreError('Unsupported Timbre voice for selected model', 503)
    return model, voice


def synthesize(text, api_key, *, transport=None):
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TTS_TEXT_CHARS:
        raise TimbreError('Read-back text is empty or exceeds the safe limit', 422)
    if not api_key:
        raise TimbreError('Gnani API key not configured', 503)
    model, voice = model_and_voice()
    payload = {'text': text, 'model': model, 'voice': voice, 'language': 'hi-IN',
               'speed': 0.9, 'audio_config': {'sample_rate': 24000, 'num_channels': 1,
                 'sample_width': 2, 'encoding': 'linear_pcm', 'container': 'wav'}}
    post = transport or requests.post
    try:
        # stream=True lets us bound response size before loading large audio into memory.
        response = post(TTS_URL, json=payload,
                        headers={'X-API-Key-ID': api_key, 'Content-Type': 'application/json'},
                        timeout=(8, 45), stream=True)
        try:
            if response.status_code != 200:
                status = response.status_code
                if status in (401, 403): raise TimbreError('Gnani TTS credentials or scope rejected', 502)
                if status == 402: raise TimbreError('Gnani TTS credits unavailable', 503)
                if status == 429: raise TimbreError('Gnani TTS rate limited; retry shortly', 503)
                raise TimbreError('Gnani TTS service could not synthesize audio', 502)
            chunks = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk: continue
                total += len(chunk)
                if total > MAX_AUDIO_RESPONSE_BYTES:
                    raise TimbreError('Gnani TTS audio exceeds size limit', 502)
                chunks.append(chunk)
            audio = b''.join(chunks)
            # Docs specify raw WAV bytes, not a JSON/base64 success envelope.
            if len(audio) < 44 or audio[:4] != b'RIFF' or audio[8:12] != b'WAVE':
                raise TimbreError('Unexpected Gnani TTS audio format', 502)
            return audio
        finally:
            close = getattr(response, 'close', None)
            if close: close()
    except TimbreError:
        raise
    except requests.exceptions.Timeout:
        raise TimbreError('Gnani TTS timed out; try again', 504)
    except requests.exceptions.RequestException:
        raise TimbreError('Unable to reach Gnani TTS', 502)
