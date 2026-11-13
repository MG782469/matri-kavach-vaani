# Matri-Kavach Vaani

**An error-aware Hindi/Hinglish voice assistant that turns a frontline health worker's spoken referral into a verified record.** It works by finding missing or contradictory details, asking for each one aloud, reading every critical digit back, and refusing to submit anything the worker has not explicitly confirmed. The confirmation can be spoken too, so the whole flow is hands-free.

Built on **Gnani Prisma** (speech-to-text) and **Gnani Timbre** (text-to-speech) for the Great Indian AI Internship Challenge.

> ⚠️ This is a research and hackathon prototype that uses **synthetic data only**. It does not diagnose, triage or dispatch, and it must never be used with real patients.

```
 Speak ─▶ Prisma transcript ─▶ Extract fields ─▶ Detect missing / conflicting ─▶ Timbre asks ─▶ Worker answers
   ▲                                                                                            │
   └──────────────────────────── repeat until every field is complete and settled ◀─────────────┘
                                         │
             Timbre reads back digit by digit ─▶ "क्या सब सही है?" ─▶ Worker says "हाँ, सब सही है" (or ticks) for THIS version ─▶ Simulated referral ─▶ Isolated demo handoff
```

## The problem

ASHA and frontline health workers write maternal-emergency referrals under time pressure, often on paper or in form-heavy apps.

- Field researchers found that ASHAs **rarely type on their phones** and instead use voice dictation and WhatsApp voice notes ([George Institute, 2025](https://cdn.georgeinstitute.org/sites/default/files/2025-05/Large-AI-model-community-health-workers.pdf)).
- Studies of Indian maternal referrals describe incomplete referral slips and delays in reaching and receiving care ([Public Health 2022](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9883712/)).

A wrong digit in a phone number, or the wrong village, costs time that a mother in labour does not have.

**Users:** ASHA workers, ANMs and PHC staff who create or relay referrals.

## What makes it different

| Capability | What happens |
|---|---|
| **Understands natural speech** | Markers like "patient ID" are not needed. From "रामपुर की मरीज़ है, नंबर 98765 43210, डिलीवरी के लिए अस्पताल ले जाना है", all four fields are filled. Natural-speech patterns run only when no marker matched, so marker-based behaviour is unchanged. Questions per draft dropped from 3.43 to 1.57, with 0 wrong values. |
| **Voice clarification agent** | If a field is missing or invalid, Timbre asks in Hindi ("गाँव का नाम नहीं मिला। कृपया गाँव का नाम बताइए।"). The worker answers aloud, Prisma transcribes the answer, and **only that one field** is filled. |
| **Contradiction-aware** | If the worker gave two different phone numbers, the app picks neither. Timbre asks "पहला … दूसरा … सही कौन सा है?" and the worker can answer "पहला/दूसरा", say the value, or tap it. |
| **Corrections never overwrite silently** | When a spoken correction such as "रामपुर नहीं, सोनपुर" differs from the current value, both values are kept as a conflict, any earlier confirmation is cancelled, and the agent asks which one is right. The history records both values. |
| **Built for real Prisma output** | It handles Devanagari numerals (९८७६…), ordinals normalised by ITN ("१st" → पहला), spoken digit words ("नौ आठ सात…", "double five"), English markers written in Devanagari ("विलेज", "रीज़न") and negation ("X नहीं, Y"). |
| **Rejects non-answers** | "हाँ", "ok", "kya?", "पता नहीं" and silence are never accepted as a value. Negation in a clinical reason ("साँस नहीं आ रही") is kept as said. |
| **Hands-free spoken confirmation** | After the read-back, Timbre asks "क्या सभी विवरण सही हैं?". **"हाँ, सब सही है"** confirms this exact version. A bare "हाँ" is not enough, and any "नहीं/गलत" never confirms. Spoken confirmation is allowed only after the Timbre read-back **audio** of the same version. The passport records whether the confirmation was by voice or by checkbox. |
| **ICAO-style read-back** | Timbre reads the phone number one digit at a time, grouped 5+5 ("9 8 7 6 5, 4 3 2 1 0"). |
| **Verification state for each field** | Each field shows Conflict, Missing, Needs read-back, Read back or ✓ Confirmed, plus where its value came from (speech, voice answer, manual edit). These states come from recorded events, not from invented confidence scores. |
| **Evidence Passport** | A record of what was heard, changed and approved: fields verified, conflicts resolved, whether the read-back covers the current version, and which version the worker approved. It contains no patient values. |

## Gnani models used

| Model | Where | How |
|---|---|---|
| **Prisma v2.5** (default, `hi-IN`, `format=transcribe`, native-numeral ITN) | Referral capture, clarification answers, voice corrections | REST `POST /stt/v3`. The browser records 16 kHz mono WAV, because the REST API does not accept webm. |
| **Prisma v3.0** (`GNANI_STT_PROFILE=codemix`) | Optional Hinglish profile | `language_code=hi-IN,en-IN`, `format=codemix`. The assistant's question is passed as `previous_text` so short replies ("दूसरा") are transcribed in context. |
| **Timbre v2.5** (Nalini) or **v3.0** (Shivani) | Clarification questions and the final read-back | REST `POST /api/v1/tts/inference`, 24 kHz WAV, Hindi. |

## Evidence

| What | Result | How to reproduce |
|---|---|---|
| Automated tests (offline, Gnani stubbed) | **186 / 186 pass** | `py -m unittest discover -s tests` |
| **False-ready safety eval:** 24 transcripts pushed straight to submit, 15 bypass attempts (5 of them voice-confirmation tricks), 26 non-answers | **0 false-ready · 0 bypasses · 0 non-answers accepted.** When the guards are deliberately broken, the same eval catches them. | `py benchmarks\run_safety_eval.py` → [report](benchmarks/results/safety_eval_report.md) |
| **Natural-speech extraction** (14 fictional transcripts) | Marker-only: 30/56 fields, 3.43 questions per draft. **With natural fallback: 56/56 fields, 0 wrong values, 1.57 questions per draft** | `py benchmarks\run_natural_eval.py` → [report](benchmarks/results/natural_eval_report.md) |
| Field-extraction fixtures (hand-written synthetic transcripts) | 16/16 cases, 64/64 fields | `py benchmarks\run_benchmark.py` → [report](benchmarks/results/stage9_report.md) |
| Live Gnani run (developer key, synthetic case) | Prisma transcribed a Hindi referral with Devanagari numerals and all 4 fields were extracted. Timbre asked a conflict question, the spoken answer resolved it, and the Timbre read-back was generated. | Manual run on 12–13 Nov 2026. Use `py scripts\live_smoke_test.py` (15 checks, including spoken confirmation) to repeat it. |
| Noise robustness (clean / 10 dB / 5 dB / 8 kHz phone) | Run with your key. The report separates wrong values (dangerous) from abstentions (safe, because the agent asks) and false-ready drafts. | `py benchmarks\run_tts_benchmark.py C:\private\tts_bench` |

The safety and fixture results check the workflow guardrails on synthetic input. They do not measure speech-recognition accuracy, and none of this is clinical validation.

## Run it

```cmd
py -m pip install -r requirements.txt
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://localhost:8000.

**Mock mode** (the default) works without a key. Try "Sample: conflicting numbers" or "Sample: missing details" and answer by typing.

**Live mode** needs your own Gnani key. Set it in the same terminal that starts the server:

```cmd
set GNANI_MODE=live
set GNANI_API_KEY=your_real_key
py scripts\check_gnani.py
py scripts\live_smoke_test.py
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

- `check_gnani.py` checks the key and its access without printing the key.
- `live_smoke_test.py` runs the whole voice-agent flow, about 14 calls.
- In PowerShell, set the variables with `$env:GNANI_MODE="live"` and `$env:GNANI_API_KEY="..."` instead.
- Optional: `GNANI_STT_PROFILE=codemix` (Prisma v3.0), and `GNANI_TIMBRE_MODEL=timbre-v3.0` with `GNANI_TIMBRE_VOICE=Shivani`.

## Safety boundaries

- Synthetic data only, with fictional numbers and names. Keys stay on the server and are never returned or logged.
- An answer can only change the field that was asked about. Clarification never confirms anything.
- Every change creates a new version and cancels earlier read-backs and confirmations. Submission requires a read-back and an explicit acknowledgement for the exact current version, and it is idempotent.
- The handoff to the original Matri-Kavach Express demo sends **no patient fields**, creates no hospital routing and sends no messages.
- The public preview (`render.yaml`) runs in mock mode behind a shared demo password. It is not a secure multi-user service.

## Limits

- Extraction is rule-based: marker patterns first, then natural-speech patterns. Very free-form speech can still leave fields blank. That is the safe failure, because the assistant then asks for them. The natural-speech numbers come from hand-written fixtures, not independent data.
- The noise benchmark uses Timbre-generated speech with noise added artificially. It is a robustness check, not a field recording study.
- The `codemix` profile follows the Gnani docs but has not been checked end to end with a live key.

## Repository map

```
app/main.py           FastAPI endpoints, versioned case workflow, field states, evidence passport
app/clarify.py        Clarification questions, answer parsing, conflict resolution, non-answer rejection
app/extraction.py     Conservative field extraction and conflict detection (Prisma-style Hindi/Hinglish)
app/prisma.py         Gnani Prisma REST adapter (hindi / codemix profiles, previous_text context)
app/timbre.py         Gnani Timbre REST adapter (bounded, validated WAV)
app/core.py           Case model: versions, read-back/confirmation digests, conflicts, resolution history
app/static/index.html Single-page UI: recorder (16 kHz WAV), voice assistant, field states, passport
benchmarks/           Safety eval, fixture benchmark, TTS noise benchmark, audio variant generator
scripts/              check_gnani.py (key diagnosis), live_smoke_test.py (live end-to-end check)
docs/                 Architecture, API, evidence, demo and submission kit
tests/                186 offline tests
```

More detail: [Architecture](docs/ARCHITECTURE.md) · [API](docs/API_CONTRACT.md) · [Innovation & evidence](docs/INNOVATION_AND_EVIDENCE.md) · [Demo & submission kit](docs/SUBMISSION_KIT.md) · [Deployment](docs/STAGE10_DEPLOYMENT.md)

## License

MIT, see [LICENSE](LICENSE).
