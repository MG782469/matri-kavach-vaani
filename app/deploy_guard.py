"""Explicit, synthetic-only, password-protected public demonstration mode.

Not clinical auth: one shared demo password; never suitable for real patient information.
"""
import base64
import hmac
import os


def public_mode():
    return os.getenv('DEMO_PUBLIC', '0').strip() == '1'


def validate_public_config():
    if not public_mode():
        return
    if os.getenv('GNANI_MODE', 'mock').strip().lower() != 'mock':
        raise ValueError('Public demo must run in GNANI_MODE=mock; live Gnani credits are private-only')
    password = os.getenv('DEMO_ACCESS_PASSWORD', '')
    if len(password) < 16 or password.lower() in {'changemechangeme', 'passwordpassword'}:
        raise ValueError('Public demo requires a unique DEMO_ACCESS_PASSWORD of 16+ characters')
    if os.getenv('REFERRAL_BACKEND_URL'):
        raise ValueError('Public demo must not configure REFERRAL_BACKEND_URL')


def correct_basic_auth(value):
    if not public_mode():
        return True
    if not isinstance(value, str) or not value.startswith('Basic '):
        return False
    try:
        payload = base64.b64decode(value[6:], validate=True).decode('utf-8')
        username, password = payload.split(':', 1)
    except (ValueError, UnicodeError):
        return False
    return hmac.compare_digest(username, 'demo') and hmac.compare_digest(password, os.getenv('DEMO_ACCESS_PASSWORD',''))
