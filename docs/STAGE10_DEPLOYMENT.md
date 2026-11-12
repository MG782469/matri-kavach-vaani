# Stage 10 — Deployment and safety verification

## Deployment decision

Two deliberately separate operating modes:

**Local developer demo (preferred for live Gnani evidence).** Run on `127.0.0.1`, `GNANI_MODE=live`, with a server-side `GNANI_API_KEY`. Synthetic recordings ONLY. Isolated Matri-Kavach demo handoff can be shown. The private key must not be sent to the browser, GitHub or shared video.

**Public preview (mock, password protected).** Set `DEMO_PUBLIC=1`, `GNANI_MODE=mock`, and a secret `DEMO_ACCESS_PASSWORD` of at least 16 characters. This public-mode configuration fails fast if live Gnani is enabled. Browser login is HTTP Basic (username `demo`), which requires HTTPS. Real TTS, STT and the remote Express handoff are disabled. This intentionally differs from the local live walkthrough.

## Suggested Render blueprint (manual setup)

The included `render.yaml` sets `DEMO_PUBLIC=1`, `GNANI_MODE=mock`, `CASE_DB_PATH=/tmp/matri-vaani-demo.sqlite3`. Create a new Render web service from the repo, review the blueprint, and set `DEMO_ACCESS_PASSWORD` as a **secret environment variable**. Do not commit its value. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Health path: `/api/health` (returns no personal data).

Render filesystem persistence depends on plan/disk configuration. The sample free deployment uses **ephemeral SQLite**, so all demo cases may be lost on restart. Run one process/one worker for the local SQLite store. Do not use this as a multi-instance clinical system.

Do not publish a local `GNANI_API_KEY`, `LIVE_KEY`, `DATABASE_URL`, Meta/Twilio secret or full patient documents. Never point `REFERRAL_BACKEND_URL` at a live operational backend.

## Security checklist before publishing

1. Run all 105 offline tests; run `python benchmarks/run_benchmark.py`.
2. Confirm public service refuses to start if GNANI_MODE is live or DEMO_ACCESS_PASSWORD is missing/short.
3. On HTTPS public URL, anonymous `GET /` and `/api/config` return HTTP 401; valid Basic credentials reach the mock UI. `/api/health` may remain accessible for monitoring.
4. Confirm no raw synthetic transcript, ID, contact or referral appears in server logs, URLs, copied screenshots or browser console beyond intentionally displayed data.
5. Confirm public `/api/cases/<id>/handoff/demo` returns 403. It should never call the original backend.
6. Confirm public audio upload is disabled, no Gnani API credits are consumed, and no external SMS/voice/WhatsApp dispatch occurs.
7. Check browser/mobile UI, error messages, no-data case, stale edit, duplicate-submission response, and post-refresh behavior.
8. Clearly warn users that the public preview is synthetic, ephemeral, and not clinically usable.
9. Keep the Basic password shared only with reviewers; rotate after the event. This is not per-user authentication.

## Honest deployment claims

- Build/deploy configuration supplied: YES.
- Code-level public-mode safeguards and offline tests: YES.
- Public URL deployed, reachable and tested: NOT VERIFIED BY THIS PACKAGE.
- Real Gnani STT WER/CER or clinical outcome improvement: NOT MEASURED.
- Local live Gnani transcription and Timbre playback: user-observed workflow events, but not externally audited.
- Real hospital system integration: NO; demo-only initial case creation.
