# Matri-Kavach Vaani — Voice-to-Verified Referral (Synthetic Prototype)

**Speak → Extract → Correct → Hindi read-back → Explicit confirmation → Simulated referral → Isolated Express demo handoff.**

This is a research and hackathon prototype. **Never use it for real patients, diagnosis, triage, ambulance dispatch or hospital communication.** Real patient data is prohibited. No clinical or operational effectiveness has been established.

## Provenance and scope

- Local mode supports real Gnani Prisma Hindi STT and Timbre TTS **only** with the developer's own API key. The user previously observed successful transcription and audio-generation audit events; this does not constitute a measured clinical accuracy or TTS quality study.
- Existing Matri-Kavach Express integration creates an initial **synthetic session at `details`** with clinician/worker-selected scenario. It does not transfer patient details or trigger routing/messages/calls.
- Stage 9 offline fixture suite: 16/16 hand-authored synthetic transcript cases, 64/64 expected field matches; not an independent external validation.
- Stage 10 automated regression suite: 105 local tests (including existing Stage 9 tests). Tests cover mocks/contract behaviour, not real production availability.

## Install Stage 10 without another permanent folder

1. Stop local Uvicorn (Ctrl+C).
2. Extract the Stage 10 ZIP **somewhere outside** your existing `gnani` project.
3. Double-click `update.bat`, confirm with Y. It backs up overwritten files and runs the tests with a temporary mock setting. SQLite case data, your `.env`, and OS credentials are not overwritten.
4. In Windows Command Prompt:

```cmd
cd /d "C:\Users\BIT\OneDrive\Desktop\gnani"
py -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

5. Open http://127.0.0.1:8000 and hard-refresh (Ctrl+Shift+R).

If using a **new** CMD session for local live Gnani testing, set `GNANI_MODE=live` and `GNANI_API_KEY` locally, without sharing the key. Never store keys in a public GitHub repo.

## Local test commands

```cmd
cd /d "C:\Users\BIT\OneDrive\Desktop\gnani"
py -m unittest discover -s tests -v
py benchmarks\run_benchmark.py
```

The two original `test_api` mock-specific tests now **explicitly patch mock mode** and should pass even if `GNANI_MODE=live` was left enabled in CMD. No live STT/TTS network requests are part of this suite.

## Public demo: intentionally LIMITED

The included `render.yaml` is a **deployment starting point**, not proof of deployment. It uses `DEMO_PUBLIC=1` with `GNANI_MODE=mock` and requires a unique 16+ character `DEMO_ACCESS_PASSWORD`, entered in the host's secret environment controls. Visitors use browser HTTP Basic auth with username `demo` and that password, over **HTTPS only**.

For public previews, real Prisma/Timbre calls and Express backend handoff are disabled. Demo text entry, editing, read-back text, confirmation and simulated submission can still be shown with fictional data. The public demo is **not** a secure multi-user case-management service; a shared password is an MVP demo gate, not identity-based authorisation. Public free hosting may use ephemeral storage; SQLite case history may disappear on restart/redeploy. **Do not promise public persistence or upload any real identity/medical records.**

See [docs/STAGE10_DEPLOYMENT.md](docs/STAGE10_DEPLOYMENT.md) for exact deployment, credential and security checks, plus [docs/STAGE10_DEMO_SCRIPT.md](docs/STAGE10_DEMO_SCRIPT.md) for a 3-minute walkthrough.

## Architecture

- FastAPI + local SQLite for synthetic case state, versioned confirmation, audit trail.
- Gnani Prisma STT and Timbre TTS for local authorised developer testing.
- Conservative extraction; a worker must review fields. No diagnosis/classification.
- Optional, isolated Matri-Kavach Express demo bridge; scenario chosen by worker. No patient fields forwarded.
- Responsive HTML/JS dashboard and offline synthetic evaluation scripts.

## Evidence and limitations

`benchmarks/results/stage9_report.md` contains reproducible local fixture results. For true WER/CER, record consent-free **synthetic** speech, create an independently reviewed ground-truth transcript, and use `benchmarks/score_transcripts.py` per `docs/STAGE9_TESTING_AND_EVIDENCE.md`. Do not claim that parser fixture scores are speech recognition accuracy, hospital outcomes or field impact.

## GitHub submission checklist

- Public repo contains only source, synthetic fixtures, clear README, licence selected by the team, and no keys or real patient data.
- Include screenshot/video showing synthetic-only banners and a complete demo workflow.
- Add results from a genuine independent audio evaluation **if and only if conducted**.
- Verify actual hosting behaviour, availability and identity/data protection before sharing links.
- Keep the project described as a synthetic voice-to-referral proof of concept, not a deployed maternal-care service.
