# Architecture

```text
Browser: chat view (app/static/chat.html) or dashboard (app/static/index.html); recorder in app/static/voice.js
  ├─ MediaRecorder → decode → 16 kHz mono WAV (Prisma REST does not accept webm)
  ├─ Voice assistant panel: Timbre question → auto-record answer → next question
  └─ Field states, Evidence Passport, audit timeline
        │ JSON / multipart
FastAPI (app/main.py)
  ├─ /from-audio ──────────────▶ app/prisma.py ──▶ Gnani Prisma  (v2.5 hi-IN | v3.0 codemix + previous_text)
  ├─ extraction (app/extraction.py): marker patterns first, natural-speech fallback only if none matched;
  │     find_conflicts (never picks between values)
  ├─ clarification (app/clarify.py): next question (conflicts first, then missing/invalid),
  │     answer parsing (digit words, ITN ordinals, negation, non-answer rejection), resolve_choice
  ├─ /clarification/audio, /readback/audio ─▶ app/timbre.py ──▶ Gnani Timbre
  ├─ /correct: a different spoken value becomes a conflict, never an overwrite
  ├─ /confirm/question-audio + /confirm/voice: strict spoken approval, only after audio read-back of this version
  ├─ versioned workflow (app/core.py): update → version+1, read-back + confirmation invalidated
  │     read-back digest → explicit acknowledgement → confirm(version) → idempotent submit
  └─ /handoff/demo ─▶ app/handoff.py ─▶ Matri-Kavach Express DEMO (scenario only, no patient fields)
        │
SQLite (app/storage.py): one JSON body per case, BEGIN IMMEDIATE + expected_version checks
```

## The case state machine

| State | How to enter it | What can leave it |
|---|---|---|
| Draft with **conflicts** | Two explicit values in one transcript, or a spoken correction that differs from the current value | Choosing a value by voice or tap, or typing a changed value |
| Draft with **missing or invalid fields** | Extraction abstains, or validation fails (10 digits, starting with 6–9) | A voice or typed clarification answer, or a manual edit |
| **Read back** | `/readback` or `/readback/audio` while the draft is complete and has no conflicts | Any change (the version goes up, so the read-back no longer applies) |
| **Confirmed** | The checkbox acknowledgement on the version that was read back, **or** the spoken phrase "हाँ, सब सही है" after the Timbre read-back *audio* of that exact version | Any change, including a voice correction |
| **Submitted** | Confirmed and unchanged, with an idempotency key | Nothing. A submitted case cannot be changed. |

## Trust boundaries

- The API key is read on the server only. It is cleaned of quotes and spaces, and it is never returned, logged or stored.
- Synthetic data only. The Evidence Passport and audit events contain no patient values.
- Gnani failures never change a case: a Prisma error is 502, silence is 422 "nothing heard", and a Timbre error changes no state.
- Public preview mode means mock mode only, behind a shared password, with the remote handoff disabled.
