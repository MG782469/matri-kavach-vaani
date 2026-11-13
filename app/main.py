import os, io, json, requests
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from .storage import SQLiteCaseStore, CaseMissing, StaleCase
from .core import Case, REQUIRED, parse_transcript, validate
from .settings import Settings
from .timbre import synthesize, TimbreError, model_and_voice
from .handoff import create_demo_handoff, BridgeError
from .deploy_guard import public_mode, validate_public_config, correct_basic_auth
from .prisma import transcribe, PrismaError, NothingHeard, profile_name
from .clarify import question_for, parse_answer, resolve_choice, parse_confirmation, LABELS, QUESTIONS, CONFIRM_QUESTION
from .extraction import find_conflicts

def gnani_key():
    """API key from the environment, cleaned of the quotes/spaces a shell `set` easily adds.

    CMD keeps quotes literally (set GNANI_API_KEY="abc" -> '"abc"'), which Gnani rejects as 401.
    """
    return (os.getenv('GNANI_API_KEY') or '').strip().strip('"\'').strip()

SETTINGS = Settings.from_environment()
validate_public_config()

app = FastAPI(title='Matri-Kavach Vaani — prototype', version='0.1.0')
STORE = SQLiteCaseStore()  # Persistent synthetic-data demo; still not clinical storage.
MODE = SETTINGS.mode

@app.middleware('http')
async def demo_security(request: Request, call_next):
    # Health reports no case data and supports deployment health checks.
    from fastapi.responses import JSONResponse
    if public_mode() and request.url.path != '/api/health':
        if not correct_basic_auth(request.headers.get('authorization')):
            return JSONResponse({'detail':'Demo password required'}, status_code=401,
                headers={'WWW-Authenticate':'Basic realm="Matri-Kavach synthetic demonstration"',
                         'Cache-Control':'no-store'})
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response

class TranscriptInput(BaseModel):
    transcript: str
class AudioReadbackInput(BaseModel):
    expected_version: int

class ConfirmInput(BaseModel):
    expected_version: int
    acknowledged: bool

class SubmitInput(BaseModel):
    expected_version: int
    idempotency_key: str

class FieldsInput(BaseModel):
    fields: dict[str,str]
    expected_version: int

class DemoHandoffInput(BaseModel):
    expected_version: int
    scenario: str
    acknowledged_synthetic_only: bool

def get_case(case_id):
    try: return STORE.get(case_id)
    except CaseMissing: raise HTTPException(404,'Case not found; create a new draft')

def modify_case(case_id, fn, expected_version=None):
    try: return STORE.mutate(case_id, fn, expected_version)[0]
    except CaseMissing: raise HTTPException(404,'Case not found; create a new draft')
    except StaleCase as exc: raise HTTPException(409,str(exc))

def demo_link_from_events(case):
    # The Stage 7 event may be present without metadata on older saved cases.
    # Never include backend session IDs or patient data in this summary.
    for event in reversed(case.events):
        if event.get('event') == 'matri_demo_handoff_created':
            ref = event.get('backend_ref')
            return {'status':'linked' if ref else 'linked_reference_unrecorded',
                    'backend_ref':ref,'backend_step':event.get('backend_step')}
    return {'status':'not_linked','backend_ref':None,'backend_step':None}

def view(case):
    return {'demo_backend':demo_link_from_events(case),'id':case.id,'transcript':case.transcript,'fields':case.fields,'version':case.version,
            'confirmed':case.can_submit(),'submitted':case.submitted,'referral_id':case.referral_id,
            'errors':validate(case.fields),'events':case.events,'mode':MODE,
            'correction_count':sum(e['event']=='fields_corrected_confirmation_invalidated' for e in case.events),
            'readback_ready':case.can_confirm(),
            'clarification':None if case.submitted else open_question(case),
            'clarification_count':sum(str(e.get('event','')).startswith('voice_clarification_filled') for e in case.events),
            'conflicts':case.conflicts,'resolutions':case.resolutions,
            'field_states':field_states(case),'evidence':evidence(case)}

def open_question(case):
    kinds={k:('correction' if case.fields.get(k) else 'transcript') for k in case.conflicts}
    return question_for(case.fields, case.conflicts, kinds)

def field_states(case):
    """Traceable per-field verification state, derived only from observable workflow facts."""
    errors=validate(case.fields); out={}
    for k in REQUIRED:
        if k in case.conflicts: state='conflict'
        elif not case.fields.get(k): state='missing'
        elif k in errors: state='invalid'
        elif case.submitted or case.can_submit(): state='confirmed'
        elif case.can_confirm(): state='read_back'
        else: state='needs_readback'
        source=case.sources.get(k) or ('not provided' if not case.fields.get(k) else 'transcript')
        if k in case.conflicts: source=f'{len(case.conflicts[k])} different values heard'
        out[k]={'state':state,'source':source,
                'resolved_conflict':any(r['field']==k for r in case.resolutions)}
    return out

def evidence(case):
    """Referral Evidence Passport: what was heard, changed and approved — no patient values."""
    ev=[e.get('event','') for e in case.events]
    return {'case_ref':case.id[:8].upper(),'version':case.version,
            'fields_complete':sum(1 for k in REQUIRED if case.fields.get(k) and k not in validate(case.fields) and k not in case.conflicts),
            'fields_total':len(REQUIRED),
            'voice_clarifications':sum(x.startswith('voice_clarification_filled') for x in ev),
            'conflicts_detected':len(case.resolutions)+len(case.conflicts),'conflicts_resolved':len(case.resolutions),
            'manual_edits':sum(1 for k in REQUIRED if case.sources.get(k)=='manual edit'),
            'readback_current_version':case.can_confirm() or case.can_submit(),
            'timbre_audio_generated':'timbre_audio_generated_for_review' in ev,
            'worker_confirmed_version':case.confirmed_version if case.can_submit() else None,
            'confirmed_by':case.confirmed_by if case.can_submit() else None,
            'audio_readback_current_version':case.audio_readback_version==case.version,
            'submitted':case.submitted,'referral_id':case.referral_id,
            'handoff':demo_link_from_events(case)['status'],'synthetic_only':True}

def set_sources(case, source):
    case.sources={k:source for k in REQUIRED if case.fields.get(k)}

@app.get('/api/health')
def health(): return {'status':'ok', 'service':'matri-kavach-vaani', 'mode':MODE, 'clinical_use':False}

@app.get('/api/config')
def config():
    live = MODE=='live' and bool(gnani_key())
    try: profile = profile_name()
    except PrismaError: profile = 'invalid'
    return {'mode': MODE, 'prisma_live': live, 'timbre_live': live, 'stt_profile': profile}

async def read_audio(file):
    audio=await file.read(SETTINGS.max_audio_bytes + 1)
    if len(audio)>SETTINGS.max_audio_bytes: raise HTTPException(413,'Audio too large')
    if not audio: raise HTTPException(422,'Audio required')
    return audio

def live_key():
    if MODE!='live': raise HTTPException(400,'Live speech recognition disabled. Set GNANI_MODE=live and GNANI_API_KEY. For mock use text form.')
    key=gnani_key()
    if not key: raise HTTPException(503,'Missing GNANI_API_KEY')
    return key

def prisma_text(audio, file, key, previous_text=None):
    try:
        return transcribe(audio, file.filename, file.content_type, key, max_chars=SETTINGS.max_transcript_chars,
                          transport=requests.post, previous_text=previous_text)
    except NothingHeard:
        raise HTTPException(422,'कुछ सुनाई नहीं दिया — nothing was heard. Please speak again closer to the microphone; nothing changed.')
    except Exception as exc:
        raise HTTPException(502,f'Prisma request failed; nothing changed: {type(exc).__name__}')

@app.post('/api/cases/from-transcript')
def new_case(body: TranscriptInput):
    if not body.transcript.strip(): raise HTTPException(422,'Transcript required')
    if len(body.transcript)>SETTINGS.max_transcript_chars: raise HTTPException(413,'Transcript too long')
    c=Case(transcript=body.transcript);c.fields=parse_transcript(c.transcript);c.log('demo_transcript_entered')
    c.conflicts=find_conflicts(c.transcript);set_sources(c,'typed transcript')
    if c.conflicts: c.log('conflicting_values_detected')
    STORE.create(c)
    return view(c)

@app.post('/api/cases/from-audio')
async def from_audio(file:UploadFile=File(...)):
    key=live_key()
    audio=await read_audio(file)
    transcript=await run_in_threadpool(prisma_text, audio, file, key)
    c=Case(transcript=transcript);c.fields=parse_transcript(c.transcript);c.log('prisma_transcribed')
    c.conflicts=find_conflicts(c.transcript);set_sources(c,'speech (Prisma)')
    if c.conflicts: c.log('conflicting_values_detected')
    STORE.create(c)
    return view(c)

@app.get('/api/cases/{case_id}')
def read_case(case_id:str):return view(get_case(case_id))

@app.put('/api/cases/{case_id}/fields')
def update_case(case_id:str, body:FieldsInput):
    def apply(c):
        before=dict(c.fields)
        c.update(body.fields)
        for k in REQUIRED:
            if c.fields[k]!=before.get(k): c.sources[k]='manual edit'
            # Typing a value is an explicit worker decision on a conflicted field.
            # Only a CHANGED value counts; saving another field must not silently settle a conflict.
            if k in c.conflicts and c.fields[k] and c.fields[k]!=before.get(k):
                c.resolve_conflict(k,c.fields[k],'manual edit')
    try: return view(modify_case(case_id, apply, body.expected_version))
    except ValueError as e: raise HTTPException(409,str(e))

@app.post('/api/cases/{case_id}/confirm')
def confirm(case_id:str, body:ConfirmInput):
    def apply(c): c.confirm(expected_version=body.expected_version, acknowledged=body.acknowledged)
    try: return view(modify_case(case_id,apply,body.expected_version))
    except ValueError as e: raise HTTPException(409,str(e))

def readback_text(c):
    errors = validate(c.fields)
    if errors: raise ValueError('Invalid fields: '+json.dumps(errors, ensure_ascii=False))
    # Digit-by-digit read-back (ICAO-style), grouped 5+5 so the voice pauses mid-number.
    contact = c.fields['contact']
    spoken_contact = ' '.join(contact[:5]) + ', ' + ' '.join(contact[5:])
    return (f"मरीज़ संदर्भ {' '.join(c.fields['patient_ref']) if c.fields['patient_ref'].isdigit() else c.fields['patient_ref']}. "
            f"गांव {c.fields['village']}. संपर्क नंबर {spoken_contact}. "
            f"रेफरल कारण {c.fields['referral_reason']}. "
            "कृपया सभी विवरण ध्यान से जांचें। यह केवल परीक्षण है।")

@app.post('/api/cases/{case_id}/readback')
def readback(case_id:str):
    def apply(c):
        text = readback_text(c)
        c.mark_readback()
        c.log('readback_text_prepared')
        return text
    try: _, text=STORE.mutate(case_id,apply)
    except CaseMissing: raise HTTPException(404,'Case not found; create a new draft')
    except ValueError as e: raise HTTPException(422,str(e))
    return {'text':text,'audio_available':MODE=='live' and bool(gnani_key()),
            'source':'text_only', 'notice':'Text preview; audio requires the Generate Timbre audio action.'}

@app.post('/api/cases/{case_id}/readback/audio')
def readback_audio(case_id:str, body:AudioReadbackInput):
    if MODE!='live': raise HTTPException(400, 'Timbre is unavailable in mock mode')
    key=gnani_key()
    if not key: raise HTTPException(503,'Missing GNANI_API_KEY')
    c=get_case(case_id)
    if c.submitted: raise HTTPException(409,'Submitted case cannot regenerate read-back')
    if c.version != body.expected_version: raise HTTPException(409,'Case changed; refresh and try again')
    try: text=readback_text(c)
    except ValueError as e: raise HTTPException(422,str(e))
    try: audio=synthesize(text,key)
    except TimbreError as e: raise HTTPException(e.status, str(e))
    def apply(current):
        if current.submitted: raise ValueError('Submitted case cannot regenerate read-back')
        if current.fields != c.fields: raise ValueError('Fields changed during audio synthesis')
        current.mark_readback()
        current.audio_readback_version = current.version
        current.log('timbre_audio_generated_for_review')
    try: STORE.mutate(case_id,apply, expected_version=body.expected_version)
    except CaseMissing: raise HTTPException(404,'Case not found')
    except StaleCase as e: raise HTTPException(409,str(e))
    except ValueError as e: raise HTTPException(409,str(e))
    return Response(audio, media_type='audio/wav',headers={'Cache-Control':'no-store',
           'X-Case-Version':str(body.expected_version),'X-Audio-Source':'gnani-timbre'})

class ClarifyQuestionInput(BaseModel):
    expected_version: int
    field: str

def require_open_question(c, field, expected_version):
    if c.submitted: raise HTTPException(409,'Submitted case cannot be changed')
    if c.version != expected_version: raise HTTPException(409,'Case changed; refresh and try again')
    q = open_question(c)
    if q is None or field not in q['remaining']:
        raise HTTPException(409,'This field does not need clarification')
    return q

def question_text(c, field):
    kinds={k:('correction' if c.fields.get(k) else 'transcript') for k in c.conflicts}
    if field in c.conflicts:
        return question_for({**c.fields}, {field:c.conflicts[field]}, kinds)['question']
    return QUESTIONS[field]

@app.post('/api/cases/{case_id}/clarification/audio')
def clarification_audio(case_id:str, body:ClarifyQuestionInput):
    """Timbre speaks the Hindi question for one missing, invalid or conflicting field (live mode only)."""
    if MODE!='live': raise HTTPException(400,'Timbre is unavailable in mock mode')
    key=gnani_key()
    if not key: raise HTTPException(503,'Missing GNANI_API_KEY')
    c=get_case(case_id)
    require_open_question(c, body.field, body.expected_version)
    try: audio=synthesize(question_text(c, body.field),key)
    except TimbreError as e: raise HTTPException(e.status, str(e))
    return Response(audio, media_type='audio/wav',headers={'Cache-Control':'no-store','X-Audio-Source':'gnani-timbre'})

async def heard_answer(c, field, answer_text, file):
    """Prisma transcript of a spoken answer, or a typed fallback. Returns (text, source)."""
    if file is not None:
        key=live_key()
        audio=await read_audio(file)
        return await run_in_threadpool(prisma_text, audio, file, key, question_text(c, field) if field in REQUIRED else None), 'prisma'
    if answer_text and answer_text.strip():
        if len(answer_text)>SETTINGS.max_transcript_chars: raise HTTPException(413,'Answer too long')
        return answer_text.strip(), 'typed'
    raise HTTPException(422,'Provide a spoken or typed answer')

@app.post('/api/cases/{case_id}/clarify')
async def clarify(case_id:str, field:str=Form(...), expected_version:int=Form(...),
                  answer_text:str|None=Form(None), file:UploadFile|None=File(None)):
    """Fill or settle ONE field from a spoken (Prisma) or typed answer. Other fields never change."""
    c=get_case(case_id)
    require_open_question(c, field, expected_version)
    heard, source = await heard_answer(c, field, answer_text, file)
    conflicted = field in c.conflicts
    value = resolve_choice(field, heard, c.conflicts[field]) if conflicted else parse_answer(field, heard)
    if not value:
        hint = ' Say "पहला" or "दूसरा", or say the correct value.' if conflicted else ''
        raise HTTPException(422,f'Could not find a usable {LABELS[field].lower()} in the answer: "{heard[:120]}". Please answer again.{hint}')
    def apply(current):
        if current.submitted: raise ValueError('Submitted case cannot be changed')
        fields=dict(current.fields); fields[field]=value
        current.update(fields)
        current.sources[field]='voice answer (Prisma)' if source=='prisma' else 'typed answer'
        if field in current.conflicts:
            current.resolve_conflict(field, value, 'voice' if source=='prisma' else 'typed')
        else:
            current.log(f'voice_clarification_filled_{field}' if source=='prisma' else f'voice_clarification_filled_{field}_typed')
    try: updated=modify_case(case_id, apply, expected_version)
    except ValueError as e: raise HTTPException(409,str(e))
    out=view(updated); out['clarified']={'field':field,'heard':heard,'value':updated.fields[field],'source':source,'resolved_conflict':conflicted}
    return out

@app.post('/api/cases/{case_id}/correct')
async def voice_correct(case_id:str, field:str=Form(...), expected_version:int=Form(...),
                        answer_text:str|None=Form(None), file:UploadFile|None=File(None)):
    """Spoken correction of a field that already has a value.

    A different value is NOT applied silently: both values are kept as a conflict and
    the assistant asks the worker which one is right.
    """
    if field not in REQUIRED: raise HTTPException(422,'Unknown field')
    c=get_case(case_id)
    if c.submitted: raise HTTPException(409,'Submitted case cannot be changed')
    if c.version != expected_version: raise HTTPException(409,'Case changed; refresh and try again')
    if field in c.conflicts: raise HTTPException(409,'Answer the open conflict question first')
    if not c.fields.get(field): raise HTTPException(409,'Field is empty; answer the clarification question instead')
    heard, source = await heard_answer(c, None, answer_text, file)
    value=parse_answer(field, heard)
    if not value:
        raise HTTPException(422,f'Could not find a usable {LABELS[field].lower()} in: "{heard[:120]}"')
    # A correction must itself be complete and valid ("98765" must not become a candidate).
    probe={k:(c.fields.get(k) or 'x') for k in REQUIRED}; probe[field]=value
    if field in validate(probe):
        raise HTTPException(422,f'Heard "{heard[:120]}" but {LABELS[field].lower()} "{value}" is incomplete or invalid: {validate(probe)[field]}')
    same = value.lower()==c.fields[field].lower()
    def apply(current):
        if same: current.log('voice_correction_matched_'+field)
        else: current.add_correction_conflict(field, value)
    try: updated=modify_case(case_id, apply, expected_version)
    except ValueError as e: raise HTTPException(409,str(e))
    out=view(updated); out['correction']={'field':field,'heard':heard,'value':value,'matches_existing':same,'source':source}
    return out

class VersionInput(BaseModel):
    expected_version: int

def require_voice_confirmable(c, expected_version):
    """Spoken approval is allowed only after the worker has had the Timbre read-back of THIS version."""
    if c.submitted: raise HTTPException(409,'Submitted case cannot be changed')
    if c.version != expected_version: raise HTTPException(409,'Case changed; refresh and try again')
    if c.conflicts: raise HTTPException(409,'Resolve conflicting values first')
    if validate(c.fields): raise HTTPException(409,'Complete and fix all fields first')
    if not c.can_confirm(): raise HTTPException(409,'Prepare the read-back for the current version first')
    if c.audio_readback_version != c.version:
        raise HTTPException(409,'Play the Timbre read-back of this exact version before confirming by voice')

@app.post('/api/cases/{case_id}/confirm/question-audio')
def confirm_question_audio(case_id:str, body:VersionInput):
    """Timbre asks: 'क्या सभी विवरण सही हैं? …' (live mode only)."""
    if MODE!='live': raise HTTPException(400,'Timbre is unavailable in mock mode')
    key=gnani_key()
    if not key: raise HTTPException(503,'Missing GNANI_API_KEY')
    c=get_case(case_id)
    require_voice_confirmable(c, body.expected_version)
    try: audio=synthesize(CONFIRM_QUESTION,key)
    except TimbreError as e: raise HTTPException(e.status, str(e))
    return Response(audio, media_type='audio/wav',headers={'Cache-Control':'no-store','X-Audio-Source':'gnani-timbre'})

@app.post('/api/cases/{case_id}/confirm/voice')
async def confirm_by_voice(case_id:str, expected_version:int=Form(...),
                           answer_text:str|None=Form(None), file:UploadFile|None=File(None)):
    """Hands-free approval. 'हाँ, सब सही है' confirms THIS version; any 'नहीं/गलत' never confirms;
    a bare 'हाँ' or anything unclear is rejected and nothing changes."""
    c=get_case(case_id)
    require_voice_confirmable(c, expected_version)
    if file is not None:
        key=live_key()
        audio=await read_audio(file)
        heard=await run_in_threadpool(prisma_text, audio, file, key, CONFIRM_QUESTION)
        source='prisma'
    elif answer_text and answer_text.strip():
        if len(answer_text)>200: raise HTTPException(413,'Answer too long')
        heard=answer_text.strip(); source='typed'
    else:
        raise HTTPException(422,'Provide a spoken or typed answer')
    decision=parse_confirmation(heard)
    if decision=='':
        raise HTTPException(422,f'Heard "{heard[:80]}". To confirm say "हाँ, सब सही है"; if something is wrong say "नहीं". Nothing changed.')
    def apply(current):
        if decision=='yes':
            current.confirm(expected_version=expected_version, acknowledged=True, method='voice')
        else:
            current.log('worker_rejected_readback_by_voice')
    try: updated=modify_case(case_id, apply, expected_version)
    except ValueError as e: raise HTTPException(409,str(e))
    out=view(updated); out['voice_confirmation']={'decision':decision,'heard':heard,'source':source}
    return out

@app.post('/api/cases/{case_id}/submit')
def submit(case_id:str, body:SubmitInput):
    if not (8 <= len(body.idempotency_key) <= 128):
        raise HTTPException(422,'idempotency_key must be 8-128 characters')
    def apply(c):
        if c.version != body.expected_version: raise PermissionError('Case changed; reload before submitting')
        if c.submitted:
            if c.submission_key != body.idempotency_key:
                raise PermissionError('Already submitted with another request key')
            return  # same request retry; no duplicate action or audit log
        if not c.can_submit(): raise PermissionError('Fields must be complete and confirmed at current version')
        if os.getenv('REFERRAL_BACKEND_URL'):
            raise NotImplementedError('Real referral backend integration not configured; use demo route only')
        c.referral_id='DEMO-'+c.id[:8].upper()
        c.submission_key=body.idempotency_key
        c.submitted=True;c.log('simulated_referral_created')
    try: return view(modify_case(case_id,apply,body.expected_version))
    except PermissionError as e: raise HTTPException(409,str(e))
    except NotImplementedError as e: raise HTTPException(501,str(e))

@app.post('/api/cases/{case_id}/handoff/demo')
def handoff_demo(case_id: str, body: DemoHandoffInput):
    """Creates only an initial synthetic scenario in an isolated Express demo session.

    No extracted patient fields, no hospital routing, no messages or calls.
    Refusal for non-submitted, outdated, or non-acknowledged cases.
    """
    if public_mode():
        raise HTTPException(403,'Remote demo handoff is disabled in public preview mode')
    c = get_case(case_id)
    if c.version != body.expected_version or not c.submitted or not c.can_submit():
        raise HTTPException(409,'Current synthetic draft must be submitted and confirmed first')
    if not body.acknowledged_synthetic_only:
        raise HTTPException(422,'Explicit synthetic-only handoff acknowledgement required')
    try:
        result = create_demo_handoff(c.id, body.scenario)
    except BridgeError as exc:
        raise HTTPException(exc.code,exc.message)
    # Store a reference-only snapshot for Case Overview and restart restoration.
    # A retry upgrades legacy events missing metadata, without adding a duplicate event.
    # No patient fields, backend session token, messages or contact are stored here.
    def record(existing):
        events = [e for e in existing.events if e.get('event') == 'matri_demo_handoff_created']
        if events:
            event = events[0]
        else:
            existing.log('matri_demo_handoff_created')
            event = existing.events[-1]
        event['backend_ref'] = result['backend_ref']
        event['backend_step'] = result['backend_step']
    modify_case(case_id,record,body.expected_version)
    return result

app.mount('/static',StaticFiles(directory=os.path.join(os.path.dirname(__file__),'static')),name='static')
@app.get('/')
def index():return FileResponse(os.path.join(os.path.dirname(__file__),'static','index.html'))
