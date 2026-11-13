# Matri-Kavach Vaani API

Interactive explorer: `http://localhost:8000/docs`. Synthetic data only. There is no production authentication and no real referral dispatch.

## Capture
- `POST /api/cases/from-transcript`: JSON body `{"transcript": "..."}`. Creates a case and fills `fields`, `conflicts` and `clarification`.
- `POST /api/cases/from-audio`: multipart `file` (WAV/MP3/OGG/FLAC/AAC/M4A, ≤30 s). Live mode only. Prisma transcribes the audio, then the case is created as above. Returns 422 if nothing was heard and 502 on a Prisma error. Neither creates a case.

## Read a case
- `GET /api/cases/{id}` returns:
  - `fields`, `errors`, `version`, `readback_ready`, `confirmed`, `submitted`
  - `clarification`: `{field, label, kind: "missing" | "conflict", candidates, question, reason, remaining}`, or `null`
  - `conflicts`: `{field: [values]}`
  - `resolutions`: `[{field, candidates, chosen, how, version, at}]`
  - `field_states`: `{field: {state, source, resolved_conflict}}`, where `state` is one of conflict, missing, invalid, needs_readback, read_back, confirmed
  - `evidence`: the Evidence Passport (no patient values)
  - `events`

## Voice assistant
- `POST /api/cases/{id}/clarification/audio`: JSON body `{"expected_version": n, "field": "village"}`. Returns Timbre WAV of the Hindi question for an open field. Live mode only. Returns 409 if the field needs no clarification or the version is stale.
- `POST /api/cases/{id}/clarify`: multipart fields `field` and `expected_version`, plus either `file` (spoken, sent to Prisma with the question as context on codemix) or `answer_text` (typed).
  - For a missing or invalid field, it fills **only** that field.
  - For a conflict, it accepts "पहला/दूसरा/1st/2nd", a candidate value, or a complete and valid new value.
  - Returns 422 for non-answers ("हाँ", "ok", "पता नहीं") and for unusable or partial values.
  - The response adds `clarified: {field, heard, value, source, resolved_conflict}`.
- `POST /api/cases/{id}/correct`: multipart fields `field` and `expected_version`, plus `file` or `answer_text`. A spoken correction of a filled field.
  - If the value is the same, it only logs an event.
  - If the value is different, it creates a conflict (both values kept, version+1, confirmation cancelled) and does **not** overwrite.
  - Returns 422 for incomplete values. The response adds `correction: {field, heard, value, matches_existing}`.

## Spoken confirmation (hands-free)
- `POST /api/cases/{id}/confirm/question-audio`: JSON body `{"expected_version": n}`. Returns Timbre WAV of "क्या सभी विवरण सही हैं? …". Live mode only.
- `POST /api/cases/{id}/confirm/voice`: multipart field `expected_version`, plus `file` (sent to Prisma with the question as context) or `answer_text`.
  - Allowed only when the read-back of this version has been prepared **and** its Timbre audio was generated (`audio_readback_version == version`). It also needs no conflicts and valid fields. Otherwise it returns 409.
  - "हाँ, सब सही है", "जी सही है" or "confirm" confirms with `confirmed_by: voice`.
  - Any "नहीं/गलत/no" returns 200 with decision `no`. It is logged and nothing is confirmed.
  - A bare "हाँ" or anything unclear returns 422 and nothing changes.

## Review, confirm, submit
- `PUT /api/cases/{id}/fields`: JSON body `{"fields": {...}, "expected_version": n}`. A manual edit.
  - Changed fields get the source `manual edit`.
  - A **changed** value on a conflicted field settles that conflict.
  - Returns 409 if the version is stale.
- `POST /api/cases/{id}/readback`: prepares the Hindi read-back text for the current version. Returns 422 if any field is invalid or any conflict is open.
- `POST /api/cases/{id}/readback/audio`: JSON body `{"expected_version": n}`. Returns Timbre WAV and marks the read-back for this version. It does not confirm.
- `POST /api/cases/{id}/confirm`: JSON body `{"expected_version": n, "acknowledged": true}`. Requires a read-back of the same version and no conflicts.
- `POST /api/cases/{id}/submit`: JSON body `{"expected_version": n, "idempotency_key": "..."}`. Creates a simulated `DEMO-*` referral. Retrying with the same key returns the same referral. A different key after submission returns 409.
- `POST /api/cases/{id}/handoff/demo`: isolated Matri-Kavach Express demo session (scenario only, no patient fields). Disabled in public mode.

## Service
- `GET /api/health` and `GET /api/config` (`mode`, `prisma_live`, `timbre_live`, `stt_profile`). The key is never exposed.
