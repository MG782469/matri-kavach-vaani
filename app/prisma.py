"""Gnani Prisma REST STT adapter. Synthetic audio only; the key never leaves the server.

Docs: https://docs.gnani.ai/api/STT/speech-to-text  (POST https://api.vachana.ai/stt/v3)
REST accepts WAV/MP3/OGG/FLAC/AAC/M4A up to 30 s; browser recordings are
converted to 16 kHz mono WAV client-side before upload.
"""
import io
import os
import requests

STT_URL = 'https://api.vachana.ai/stt/v3'

# 'hindi'   : Prisma v2.5, hi-IN, ITN with native numerals (the verified default).
# 'codemix' : Prisma v3.0, Hindi+English hints, English words kept in Latin script.
PROFILES = {
    'hindi': {'language_code': 'hi-IN', 'preferred_language': 'hi-IN',
              'format': 'transcribe', 'itn_native_numerals': 'true'},
    'codemix': {'model': 'prisma-v3.0', 'language_code': 'hi-IN,en-IN', 'format': 'codemix'},
}


class PrismaError(Exception):
    pass


class NothingHeard(PrismaError):
    """Prisma returned an empty transcript (silence / no speech)."""


def profile_name():
    name = os.getenv('GNANI_STT_PROFILE', 'hindi').strip().lower()
    if name not in PROFILES:
        raise PrismaError('GNANI_STT_PROFILE must be hindi or codemix')
    return name


def transcribe(audio, filename, content_type, api_key, *, max_chars, transport=None, previous_text=None):
    name = profile_name()
    form = dict(PROFILES[name])
    if previous_text and name == 'codemix':
        # v3.0 context field: the question the worker is answering helps Prisma
        # interpret a short reply ("रामपुर", "दूसरा"). Not sent on v2.5.
        form['previous_text'] = previous_text[:500]
    post = transport or requests.post
    resp = post(STT_URL, headers={'X-API-Key-ID': api_key}, data=form,
                files={'audio_file': (filename or 'voice.wav', io.BytesIO(audio), content_type or 'audio/wav')},
                timeout=35)
    resp.raise_for_status()
    transcript = resp.json().get('transcript', '')
    if not isinstance(transcript, str) or not transcript.strip():
        raise NothingHeard('No speech was recognised')
    if len(transcript) > max_chars:
        raise PrismaError('Transcript exceeds limit')
    return transcript.strip()
