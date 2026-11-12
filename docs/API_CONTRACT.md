# Matri-Kavach Vaani API — Stage 6 demo contract

FastAPI explorer: `http://localhost:8000/docs`. Synthetic data ONLY; no production authentication, no real referral dispatch.

- `POST /api/cases/from-transcript` JSON `{"transcript":"..."}` creates demo case.
- `POST /api/cases/from-audio` multipart `file` transcribes through live Prisma when configured.
- `GET /api/cases/{id}` returns stored draft and fields. `readback_ready` indicates the server prepared the current version for review.
- `PUT /api/cases/{id}/fields` JSON `{"fields": {"patient_ref":"...","village":"...","contact":"...","referral_reason":"..."},"expected_version":0}`. Required version; stale version 409. Saves invalidate previous readback and confirmation.
- `POST /api/cases/{id}/readback` prepares text for the current fields, records review readiness, and returns the Hindi readback. Does not confirm.
- `POST /api/cases/{id}/readback/audio` JSON `{"expected_version":0}` returns Gnani Timbre WAV in live mode; audio generation does not confirm.
- `POST /api/cases/{id}/confirm` JSON `{"expected_version":0,"acknowledged":true}`. Requires a prepared readback at the same version; 409 on conflict/missing review, 422 for missing body or validation. Read-back preparation is **not** proof that the audio was heard.
- `POST /api/cases/{id}/submit` JSON `{"expected_version":0,"idempotency_key":"unique-demo-request-key"}`. Creates only a simulated DEMO referral. Retry with identical idempotency key returns same referral, different key after submission gets 409.

The server uses SQLite transaction locking for local single-instance demo state. This is not a claim of hospital-backend exactly-once delivery. Never put real patient information or secrets in this app.
