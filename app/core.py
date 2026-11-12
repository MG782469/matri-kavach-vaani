from dataclasses import dataclass, field
from uuid import uuid4
from datetime import datetime, timezone
import hashlib, json, re
from .extraction import parse_transcript, normalize_digits

REQUIRED = ('patient_ref', 'village', 'contact', 'referral_reason')

def digest(fields):
    return hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def validate(fields):
    errors = {k:'Required; must be checked by an authorised worker' for k in REQUIRED if not str(fields.get(k,'')).strip()}
    contact = re.sub(r'[\s-]', '', normalize_digits(str(fields.get('contact',''))))
    if 'contact' not in errors and not re.fullmatch(r'\d{10}',contact): errors['contact']='Enter and verify exactly ten digits (demo-only number)'
    for k, limit in {'patient_ref':64,'village':100,'referral_reason':200}.items():
        if len(str(fields.get(k,''))) > limit: errors[k]=f'Must be at most {limit} characters'
    if 'contact' not in errors and contact == '0000000000': errors['contact']='Use a valid fictional demo number'
    return errors

@dataclass
class Case:
    id: str = field(default_factory=lambda: str(uuid4()))
    transcript: str = ''
    fields: dict = field(default_factory=lambda: {k:'' for k in REQUIRED})
    version: int = 0
    confirmation_digest: str | None = None
    confirmed_version: int | None = None
    submitted: bool = False
    referral_id: str | None = None
    events: list = field(default_factory=list)
    reviewed_digest: str | None = None
    reviewed_version: int | None = None
    submission_key: str | None = None

    def log(self,event):
        self.events.append({'event':event,'at':datetime.now(timezone.utc).isoformat()})

    def update(self, new_fields):
        if self.submitted: raise ValueError('Submitted case is immutable')
        self.fields = {k:(re.sub(r'[\s-]', '', normalize_digits(str(new_fields.get(k,'')).strip())) if k == 'contact' else str(new_fields.get(k,'')).strip()) for k in REQUIRED}
        self.version += 1
        self.confirmation_digest = None
        self.confirmed_version = None
        self.reviewed_digest = None
        self.reviewed_version = None
        self.log('fields_corrected_confirmation_invalidated')

    def mark_readback(self):
        if self.submitted: raise ValueError("Submitted case is immutable")
        errors = validate(self.fields)
        if errors: raise ValueError("Invalid fields: "+json.dumps(errors))
        self.reviewed_digest = digest(self.fields)
        self.reviewed_version = self.version
        self.log("readback_prepared_for_current_version")

    def can_confirm(self):
        return (self.reviewed_version == self.version and
                self.reviewed_digest == digest(self.fields))

    def confirm(self, expected_version=None, acknowledged=False):
        if self.submitted: raise ValueError("Submitted case is immutable")
        if expected_version is not None and expected_version != self.version:
            raise ValueError("Case changed; review the latest version")
        if not acknowledged and expected_version is not None:
            raise ValueError("Explicit verification acknowledgment required")
        if expected_version is not None and not self.can_confirm():
            raise ValueError("Prepare read-back again for current fields")
        errors = validate(self.fields)
        if errors: raise ValueError('Invalid fields: '+json.dumps(errors))
        if self.can_submit(): return
        self.confirmed_version = self.version
        self.confirmation_digest = digest(self.fields)
        self.log('worker_confirmed')

    def can_submit(self):
        return not validate(self.fields) and self.confirmed_version == self.version and self.confirmation_digest == digest(self.fields)
