"""Simple, explainable referral routing (synthetic district, mirrors the Matri-Kavach MVP data).

A facility is READY for an emergency only if every checklist item that emergency needs is
checked in tonight. The nearest ready hospital is asked first, the next ready one is the backup.
If the asked hospital says "not ready" or does not reply within REPLY_WINDOW_SEC, the case is
re-routed to the backup automatically. Doctors define readiness; humans choose the emergency.
All places, distances and stock are fictional.
"""
from datetime import datetime, timezone

REPLY_WINDOW_SEC = 120
SPEED_KMH = 40
DETOUR = 1.3

# Checklist items (same ids/labels as Matri-Kavach).
ITEMS = {
    'blood': 'Blood of her group, or cross-match within 1 hour',
    'obstetrician': 'Obstetrician on duty, or on call within 15 min',
    'anaesthetist': 'Anaesthetist on duty',
    'theatre': 'Operating theatre free, suction working',
    'uterotonics': 'Oxytocin, misoprostol, tranexamic acid in stock',
    'iv': 'IV fluids and cannulas in stock',
    'bed': 'Post-op or HDU bed free',
    'mgso4': 'Magnesium sulphate + calcium gluconate in stock',
    'antihtn': 'Labetalol or nifedipine in stock',
    'antibiotics': 'IV antibiotics in stock',
    'airway': 'Oxygen, suction, bag-mask, BP and SpO2 monitor working',
    'lab': 'Emergency lab open: blood counts, kidney, liver',
    'usg': 'Ultrasound available',
    'hdu': 'HDU or ICU bed free',
    'newborn': 'Newborn resuscitation corner ready',
    'paed': 'Paediatrician on duty or on call',
    'sncu': 'SNCU (newborn unit) bed free',
}

# Emergency checklists from the Matri-Kavach MVP (reviewed by its clinical partner, M Gufran;
# obstetrician validation is still needed before any pilot).
EMERGENCIES = {
    'bleeding':   {'label': 'Heavy bleeding after delivery (PPH)', 'blood_bank': True,
                   'items': ['blood', 'obstetrician', 'anaesthetist', 'theatre', 'uterotonics', 'iv', 'bed']},
    'fits':       {'label': 'Fits or eclampsia', 'blood_bank': False,
                   'items': ['mgso4', 'antihtn', 'obstetrician', 'anaesthetist', 'airway', 'lab', 'theatre', 'hdu', 'newborn']},
    'obstructed': {'label': 'Obstructed labour', 'blood_bank': True,
                   'items': ['obstetrician', 'anaesthetist', 'theatre', 'blood', 'iv', 'antibiotics', 'newborn', 'bed']},
    'aph':        {'label': 'Bleeding before delivery (APH)', 'blood_bank': True,
                   'items': ['obstetrician', 'anaesthetist', 'blood', 'theatre', 'iv', 'airway', 'usg', 'newborn']},
    'sepsis':     {'label': 'Fever after delivery (possible sepsis)', 'blood_bank': False,
                   'items': ['antibiotics', 'iv', 'airway', 'lab', 'obstetrician', 'anaesthetist', 'theatre', 'hdu']},
    'newborn':    {'label': 'Newborn emergency', 'blood_bank': False,
                   'items': ['paed', 'sncu', 'airway', 'newborn']},
}
CHECKLIST_REVIEW = 'Checklists from Matri-Kavach, reviewed by clinical advisor Moluvi Gufran; obstetrician validation needed before a pilot.'

_ALL = {k: True for k in ITEMS}
FACILITIES = [
    {'id': 'chc', 'name': 'CHC Sonpur', 'km': 9, 'fallback': False, 'desk': 'CHC Sonpur duty phone',
     'checkin': {**_ALL, 'anaesthetist': False, 'lab': False, 'hdu': False, 'newborn': False, 'usg': False, 'paed': False, 'sncu': False}},
    {'id': 'dh', 'name': 'DH Devgarh', 'km': 21, 'fallback': False, 'desk': 'DH Devgarh labour room',
     'checkin': {**_ALL, 'hdu': False}},
    {'id': 'sdh', 'name': 'SDH Kheri', 'km': 25, 'fallback': False, 'desk': 'SDH Kheri labour room',
     'checkin': dict(_ALL)},
    {'id': 'mc', 'name': 'GMC Rajnagar', 'km': 52, 'fallback': True, 'desk': 'GMC Rajnagar emergency desk',
     'checkin': dict(_ALL)},
]
FACILITY = {f['id']: f for f in FACILITIES}


def now_ts():
    return datetime.now(timezone.utc).timestamp()


def eta_min(km):
    return round(km * DETOUR / SPEED_KMH * 60)


def readiness(emergency):
    """Every facility with ready / missing items for this emergency, nearest first."""
    need = EMERGENCIES[emergency]['items']
    rows = []
    for f in FACILITIES:
        missing = [i for i in need if not f['checkin'].get(i)]
        rows.append({'id': f['id'], 'name': f['name'], 'km': f['km'], 'eta_min': eta_min(f['km']),
                     'fallback': f['fallback'], 'ready': not missing, 'missing': missing})
    return rows


def plan(emergency, exclude=()):
    """Nearest ready hospital first; the medical college is a fallback after the others."""
    ready = [r for r in readiness(emergency) if r['ready'] and r['id'] not in exclude]
    ready.sort(key=lambda r: (r['fallback'], r['km']))
    return {'proposed': ready[0]['id'] if ready else None, 'backup': ready[1]['id'] if len(ready) > 1 else None}


def start(case, ts=None):
    """Ask the proposed hospital. Requires a submitted referral with a worker-selected emergency."""
    if not case.submitted:
        raise ValueError('Submit the confirmed referral first')
    if case.emergency not in EMERGENCIES:
        raise ValueError('Choose the emergency type first')
    if case.routing.get('status') in ('asked', 'confirmed', 'arrived'):
        return False   # idempotent: already routing
    p = plan(case.emergency)
    if not p['proposed']:
        case.routing = {'status': 'no_hospital', 'target': None, 'backup': None, 'history': [], 'alerts': ['No ready hospital tonight: call the district control room']}
        case.log('routing_no_ready_hospital')
        return True
    case.routing = {'status': 'asked', 'target': p['proposed'], 'backup': p['backup'], 'asked_at': ts or now_ts(),
                    'history': [], 'alerts': [], 'ambulance': None, 'notified': []}
    case.log('routing_asked_' + p['proposed'])
    return True


def _reroute(case, reason, ts):
    r = case.routing
    tried = [h['facility'] for h in r['history']] + [r['target']]
    r['history'].append({'facility': r['target'], 'outcome': reason, 'at': ts})
    r['alerts'].append(f"{FACILITY[r['target']]['name']}: {'not ready' if reason == 'not_ready' else 'no reply in 2 min'}, re-routed")
    p = plan(case.emergency, exclude=tried)
    if not p['proposed']:
        r.update(status='no_hospital', target=None, backup=None)
        r['alerts'].append('No ready hospital left: call the district control room')
        case.log('routing_no_ready_hospital')
        return
    r.update(status='asked', target=p['proposed'], backup=p['backup'], asked_at=ts)
    case.log(f"routing_rerouted_{reason}_to_{p['proposed']}")


def check_timeout(case, ts=None):
    """Lazy timer: if the asked hospital has not replied within the window, move to the backup."""
    ts = ts or now_ts()
    r = case.routing
    if r.get('status') == 'asked' and ts - r.get('asked_at', ts) >= REPLY_WINDOW_SEC:
        _reroute(case, 'no_reply', ts)
        return True
    return False


def hospital_reply(case, facility, ready, ts=None):
    ts = ts or now_ts()
    r = case.routing
    if r.get('status') != 'asked' or r.get('target') != facility:
        raise ValueError('This hospital is not being asked about this case')
    if not ready:
        case.log('hospital_not_ready_' + facility)
        _reroute(case, 'not_ready', ts)
        return
    e = EMERGENCIES[case.emergency]
    r.update(status='confirmed', confirmed_at=ts, ambulance='108 Ambulance 1',
             eta_min=eta_min(FACILITY[facility]['km']))
    r['notified'] = ['driver', 'emt', 'doctor', 'family'] + (['bloodbank'] if e['blood_bank'] else [])
    case.log('hospital_confirmed_' + facility)
    case.log('notified_' + '_'.join(r['notified']))


def arrived(case, facility, ts=None):
    r = case.routing
    if r.get('status') != 'confirmed' or r.get('target') != facility:
        raise ValueError('Only the confirmed hospital can record arrival')
    r.update(status='arrived', arrived_at=ts or now_ts())
    case.log('arrived_' + facility)


def skip_wait(case, ts=None):
    """Demo control (like the MVP's 'Skip 2 minutes'): pretend the reply window has passed."""
    ts = ts or now_ts()
    if case.routing.get('status') != 'asked':
        raise ValueError('No hospital is waiting to reply')
    case.routing['asked_at'] = ts - REPLY_WINDOW_SEC
    case.log('demo_skip_2_minutes')
    check_timeout(case, ts)
