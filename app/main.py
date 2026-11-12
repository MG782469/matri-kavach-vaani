import os, io, json, requests
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from .storage import SQLiteCaseStore, CaseMissing, StaleCase
from .core import Case, REQUIRED, parse_transcript, validate
from .settings import Settings
from .timbre import synthesize, TimbreError, model_and_voice
from .handoff import create_demo_handoff, BridgeError
from .deploy_guard import public_mode, validate_public_config, correct_basic_auth

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
            'readback_ready':case.can_confirm()}

@app.get('/api/health')
def health(): return {'status':'ok', 'service':'matri-kavach-vaani', 'mode':MODE, 'clinical_use':False}

@app.get('/api/config')
def config(): return {'mode': MODE, 'prisma_live': MODE=='live' and bool(os.getenv('GNANI_API_KEY')), 'timbre_live': MODE=='live' and bool(os.getenv('GNANI_API_KEY'))}

@app.post('/api/cases/from-transcript')
def new_case(body: TranscriptInput):
    if not body.transcript.strip(): raise HTTPException(422,'Transcript required')
    if len(body.transcript)>SETTINGS.max_transcript_chars: raise HTTPException(413,'Transcript too long')
    c=Case(transcript=body.transcript);c.fields=parse_transcript(c.transcript);c.log('demo_transcript_entered')
    STORE.create(c)
    return view(c)

@app.post('/api/cases/from-audio')
async def from_audio(file:UploadFile=File(...)):
    if MODE!='live': raise HTTPException(400,'Live speech recognition disabled. Set GNANI_MODE=live and GNANI_API_KEY. For mock use text form.')
    key=os.getenv('GNANI_API_KEY')
    if not key: raise HTTPException(503,'Missing GNANI_API_KEY')
    audio=await file.read(SETTINGS.max_audio_bytes + 1)
    if len(audio)>SETTINGS.max_audio_bytes: raise HTTPException(413,'Audio too large')
    if not audio: raise HTTPException(422,'Audio required')
    try:
        resp=requests.post('https://api.vachana.ai/stt/v3',headers={'X-API-Key-ID':key},
            data={'language_code':'hi-IN','preferred_language':'hi-IN','format':'transcribe','itn_native_numerals':'true'},
            files={'audio_file':(file.filename or 'voice.wav',io.BytesIO(audio),file.content_type or 'audio/wav')},timeout=35)
        resp.raise_for_status(); result=resp.json()
        transcript=result.get('transcript','')
        if not isinstance(transcript,str) or not transcript.strip(): raise ValueError('No transcript returned')
        if len(transcript)>SETTINGS.max_transcript_chars: raise ValueError('Transcript exceeds limit')
    except Exception as exc:
        raise HTTPException(502,f'Prisma request failed; no referral created: {type(exc).__name__}')
    c=Case(transcript=transcript);c.fields=parse_transcript(c.transcript);c.log('prisma_transcribed')
    STORE.create(c)
    return view(c)

@app.get('/api/cases/{case_id}')
def read_case(case_id:str):return view(get_case(case_id))

@app.put('/api/cases/{case_id}/fields')
def update_case(case_id:str, body:FieldsInput):
    def apply(c):
        c.update(body.fields)
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
    # Deliberate digit-by-digit contact readback to avoid number grouping ambiguity.
    return (f"मरीज़ संदर्भ {' '.join(c.fields['patient_ref']) if c.fields['patient_ref'].isdigit() else c.fields['patient_ref']}. "
            f"गांव {c.fields['village']}. संपर्क नंबर {' '.join(c.fields['contact'])}. "
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
    return {'text':text,'audio_available':MODE=='live' and bool(os.getenv('GNANI_API_KEY')),
            'source':'text_only', 'notice':'Text preview; audio requires the Generate Timbre audio action.'}

@app.post('/api/cases/{case_id}/readback/audio')
def readback_audio(case_id:str, body:AudioReadbackInput):
    if MODE!='live': raise HTTPException(400, 'Timbre is unavailable in mock mode')
    key=os.getenv('GNANI_API_KEY')
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
        current.log('timbre_audio_generated_for_review')
    try: STORE.mutate(case_id,apply, expected_version=body.expected_version)
    except CaseMissing: raise HTTPException(404,'Case not found')
    except StaleCase as e: raise HTTPException(409,str(e))
    except ValueError as e: raise HTTPException(409,str(e))
    return Response(audio, media_type='audio/wav',headers={'Cache-Control':'no-store',
           'X-Case-Version':str(body.expected_version),'X-Audio-Source':'gnani-timbre'})

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
