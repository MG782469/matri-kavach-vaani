# Stage 1 Architecture (verified prototype boundary)

```text
Browser (static HTML/JS)
    | JSON API / optional multipart audio
FastAPI  [app/main.py]
    |                     |
Case / validation         Gnani Prisma adapter (live mode only; NOT tested with credentials)
[app/core.py]             |
    |                     External Gnani API
In-memory case store
    |
Human review -> confirmation digest/version -> demo-only referral ID
```

## Safety and trust boundaries
- Only **synthetic** information in this demo. No authentication, encryption-at-rest or persistence; NOT a clinical deployment.
- `mock` explicitly requires typed text and never pretends to transcribe audio.
- `live` attempts Prisma; no API token is returned from `/api/config`.
- Field data can be modified only until submission; modifications invalidate earlier confirmation.
- Referral submission creates a `DEMO-*` ID, never contacts a hospital, even when `REFERRAL_BACKEND_URL` is set (501).
- Do not delay emergency care waiting on this prototype. Use existing local clinical procedures.

## Staged enhancements
- Stage 2: separate and exercise Prisma client using live test credentials and real audio.
- Stage 3: structured extraction accuracy and spoken digit normalization.
- Stage 4: durable corrections and review UX.
- Stage 5: Timbre readback with actual audio.
- Stage 6: persisted, authenticated confirmation and idempotency.
- Stage 7: explicitly authorized Matri-Kavach integration.
- Stage 8+: frontend polish, benchmarks, deployment.
