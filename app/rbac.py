"""Role-based access (RBAC) for the referral team, enforced on the SERVER.

Same roles and "who sees what" as the Matri-Kavach MVP. Each role logs in with a synthetic phone
number and a one-time code (shown on screen in this demo). Every role view is built from an
allow-list of fields; nothing is filtered in the browser. Only the worker who created the case
(the nurse / ASHA view, /chat) sees the patient's contact number and transcript.
"""
import base64
import hashlib
import hmac
import os
import secrets
import time

from .routing import EMERGENCIES, FACILITY, CHECKLIST_REVIEW, eta_min

ROLES = {
    'nurse':     {'label': 'PHC nurse / ASHA', 'phone': '90000 00001'},
    'dh':        {'label': 'DH Devgarh labour room', 'phone': '90000 00002', 'facility': 'dh'},
    'sdh':       {'label': 'SDH Kheri labour room', 'phone': '90000 00003', 'facility': 'sdh'},
    'chc':       {'label': 'CHC Sonpur duty phone', 'phone': '90000 00004', 'facility': 'chc'},
    'mc':        {'label': 'GMC Rajnagar emergency desk', 'phone': '90000 00005', 'facility': 'mc'},
    'doctor':    {'label': 'Receiving doctor', 'phone': '90000 00006'},
    'bloodbank': {'label': 'Blood bank', 'phone': '90000 00007'},
    'driver':    {'label': '108 driver, Ambulance 1', 'phone': '90000 00008'},
    'emt':       {'label': '108 EMT, Ambulance 1', 'phone': '90000 00009'},
    'family':    {'label': 'Family', 'phone': '90000 00010'},
    'district':  {'label': 'District officer', 'phone': '90000 00011'},
}
WHO_SEES_WHAT = {
    'nurse': 'Everything she entered, including contact number and transcript',
    'hospital': 'Emergency, needs, reference, village, reason, ETA (no phone number)',
    'doctor': 'Private summary for 2 hours after confirmation',
    'bloodbank': 'Emergency type and hospital only (bleeding emergencies)',
    'driver': 'Case ID, pickup village, hospital and route only. No medical details',
    'emt': 'Emergency, reason and route, for care on the way',
    'family': 'Hospital, ETA and status only. No medical details',
    'district': 'Case ID, emergency type, status and alerts. No patient details',
}
CODE_TTL = 300
TOKEN_TTL = 8 * 3600
DOCTOR_SUMMARY_TTL = 2 * 3600
_SECRET = (os.getenv('ROLE_TOKEN_SECRET') or secrets.token_hex(32)).encode()
_codes = {}   # role -> (code, expires)


class AuthError(Exception):
    pass


def request_code(role):
    if role not in ROLES:
        raise AuthError('Unknown role')
    code = f'{secrets.randbelow(10**6):06d}'
    _codes[role] = (code, time.time() + CODE_TTL)
    return code


def verify_code(role, code):
    saved = _codes.get(role)
    if not saved or time.time() > saved[1] or not hmac.compare_digest(saved[0], str(code or '')):
        raise AuthError('Wrong or expired code')
    _codes.pop(role, None)
    return issue_token(role)


def issue_token(role, ttl=TOKEN_TTL):
    exp = int(time.time() + ttl)
    msg = f'{role}|{exp}'.encode()
    sig = hmac.new(_SECRET, msg, hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(msg + b'|' + sig.encode()).decode()


def role_from_token(token):
    try:
        role, exp, sig = base64.urlsafe_b64decode((token or '').encode()).decode().split('|')
    except Exception:
        raise AuthError('Login required')
    good = hmac.new(_SECRET, f'{role}|{exp}'.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(good, sig) or int(exp) < time.time() or role not in ROLES:
        raise AuthError('Login required')
    return role


def _base(case):
    r = case.routing or {}
    target = FACILITY.get(r.get('target') or '', {}).get('name')
    return {'case_id': case.id[:8].upper(), 'status': r.get('status') or 'not_routed', 'hospital': target}


def _emergency(case):
    e = EMERGENCIES.get(case.emergency or '')
    return e['label'] if e else None


def involved(case, role):
    """Which cases a role may see at all."""
    r = case.routing or {}
    if not case.submitted or not r:
        return False
    if role == 'district':
        return True
    fac = ROLES.get(role, {}).get('facility')
    if fac:
        return r.get('target') == fac or any(h['facility'] == fac for h in r.get('history', []))
    if r.get('status') not in ('confirmed', 'arrived'):
        return False
    if role == 'bloodbank':
        return EMERGENCIES.get(case.emergency, {}).get('blood_bank', False)
    return role in ('driver', 'emt', 'doctor', 'family')


def view_for(case, role, ts=None):
    """Allow-listed view of one case for one role. Never includes the contact number or transcript."""
    ts = ts or time.time()
    if not involved(case, role):
        return None
    r = case.routing or {}
    f = case.fields
    out = _base(case)
    eta = r.get('eta_min')
    fac = ROLES[role].get('facility')
    if fac:
        mine = r.get('target') == fac
        e = EMERGENCIES[case.emergency]
        out.update(emergency=_emergency(case), needs=[i for i in e['items']], patient_ref=f.get('patient_ref'),
                   village=f.get('village'), reason=f.get('referral_reason'),
                   eta_min=(eta or eta_min(FACILITY[fac]['km'])) if mine else None,
                   asked=mine and r.get('status') == 'asked', reply_deadline=(r.get('asked_at', ts) + 120) if mine else None,
                   you_are_target=mine, review=CHECKLIST_REVIEW,
                   approved_by=(case.confirmed_by or 'checkbox') + f' (v{case.confirmed_version})',
                   actions=(['confirm', 'not_ready'] if mine and r.get('status') == 'asked' else
                            ['arrived'] if mine and r.get('status') == 'confirmed' else []))
        if not mine:
            out.update(status='moved_to_another_hospital', hospital=None)
    elif role == 'doctor':
        expires = r.get('confirmed_at', ts) + DOCTOR_SUMMARY_TTL
        out.update(summary_expires_at=expires, expired=ts > expires)
        if ts <= expires:
            out.update(emergency=_emergency(case), patient_ref=f.get('patient_ref'), reason=f.get('referral_reason'), eta_min=eta)
    elif role == 'bloodbank':
        out.update(emergency=_emergency(case))
    elif role == 'driver':
        out.update(pickup=f.get('village'), map=f"Route: {f.get('village')} → {out['hospital']} (synthetic)", eta_min=eta)
    elif role == 'emt':
        out.update(emergency=_emergency(case), reason=f.get('referral_reason'), pickup=f.get('village'), eta_min=eta)
    elif role == 'family':
        out.update(eta_min=eta)
    elif role == 'district':
        out.update(emergency=_emergency(case), alerts=list(r.get('alerts', [])),
                   asked_count=len(r.get('history', [])) + (1 if r.get('target') else 0),
                   actions=['skip_wait'] if r.get('status') == 'asked' else [])
    return out
