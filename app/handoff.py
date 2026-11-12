"""Synthetic-only bridge to the existing Matri-Kavach Express demo API.

No patient fields are sent, no live session is accessible, and the bridge never
calls /api/act 'send' or 'details'. Nurse chooses scenario explicitly.
"""
import hashlib
import os
from urllib.parse import urlparse
import requests

SCENARIOS = {'bleeding', 'fits', 'obstructed', 'aph', 'sepsis', 'newborn'}
DEFAULT_BASE = 'https://matri-kavach-mvp.onrender.com'

class BridgeError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)

def base_url():
    raw = os.getenv('MATRI_DEMO_BASE_URL', DEFAULT_BASE).rstrip('/')
    parsed = urlparse(raw)
    # Never accept credentials, query strings, fragments or arbitrary remote hosts.
    allowed = parsed.scheme == 'https' and parsed.netloc == 'matri-kavach-mvp.onrender.com'
    local = parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost') and parsed.port in (3000, 3001, 8766)
    if not (allowed or local) or parsed.username or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment:
        raise BridgeError(422, 'Demo backend must be the official demo HTTPS host or approved localhost port')
    return raw

def demo_sid(case_id):
    # Existing Express /api/act accepts precisely 16 lowercase hex digits; never 'live'.
    return hashlib.sha256(('vaani-synthetic-demo:'+case_id).encode()).hexdigest()[:16]

def check_state(base, sid):
    r = requests.get(base+'/api/state', params={'sid':sid}, timeout=15, allow_redirects=False)
    if r.status_code != 200:
        raise BridgeError(502, 'Matri-Kavach demo state unavailable ('+str(r.status_code)+')')
    try: data = r.json()
    except ValueError: raise BridgeError(502,'Invalid response from Matri-Kavach demo')
    if not isinstance(data,dict) or data.get('live') is not False or data.get('id') != sid:
        raise BridgeError(502, 'Demo isolation check failed; nothing submitted')
    return data

def create_demo_handoff(case_id, scenario):
    if scenario not in SCENARIOS:
        raise BridgeError(422,'Select a signed synthetic scenario; no automated medical classification')
    base = base_url()
    sid = demo_sid(case_id)
    try:
        state = check_state(base,sid)
        # Reconciliation before send: prevents a network retry creating a second demo case.
        if state.get('cur'):
            current = state['cur']
            if current.get('type') != scenario:
                raise BridgeError(409,'This demo handoff already has another scenario; do not override')
            return {'mode':'synthetic_demo_only','backend':'Matri-Kavach Express demo',
                    'backend_ref':current.get('id'),'backend_step':state.get('step'),
                    'already_exists':True,'no_patient_data_transferred':True,
                    'external_notifications_sent':False,'session_id':sid}
        r = requests.post(base+'/api/act',json={'sid':sid,'action':'startReferral','args':{'typeId':scenario}},
                          timeout=20,allow_redirects=False)
        if r.status_code != 200:
            raise BridgeError(502, 'Matri-Kavach demo rejected the synthetic handoff ('+str(r.status_code)+')')
        data = r.json()
        if data.get('live') is not False or data.get('id') != sid or not data.get('cur') or data['cur'].get('type') != scenario:
            raise BridgeError(502,'Unexpected demo response; verify backend state')
        return {'mode':'synthetic_demo_only','backend':'Matri-Kavach Express demo',
                'backend_ref':data['cur'].get('id'),'backend_step':data.get('step'),
                'already_exists':False,'no_patient_data_transferred':True,
                'external_notifications_sent':False,'session_id':sid}
    except requests.RequestException:
        raise BridgeError(502,'Demo backend unreachable. Retry will reconcile state before creating anything')
