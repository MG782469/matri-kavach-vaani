# Stage 9 — Testing, benchmarking, reproducibility

## What is actually verified

- Stage 8 Case Overview displays **Express demo status, backend reference, and last handoff step** from the persisted SQLite case event. Existing Stage 7 cases with incomplete historical events show `Linked · retry handoff to recover reference` instead of inventing a backend ID.
- The Stage 7 bridge is demo-only, sends an explicitly worker-selected synthetic scenario, and never forwards transcript, contact, village, patient reference, or audio to the Express backend.
- Offline automated tests cover version conflicts, read-back confirmation gates, late edits, idempotent submission, mock Gnani STT/TTS response handling (where existing test coverage applies), isolated backend handoff, error responses, SQLite restoration and concurrency.
- `py -m unittest discover -s tests -v`: see the actual count in your run. The supplied baseline has **101** passing tests, including 22 Stage 9-specific tests (16 workflow + 6 benchmark tests).
- `py benchmarks\run_benchmark.py` writes a machine-readable JSON and Markdown report under `benchmarks/results/`. The provided reference run covers **16 hand-authored synthetic transcripts, 64 labeled fields**.

## Baseline benchmark (local build environment; NOT provider accuracy)

| Measure | Measured baseline |
|---|---:|
| Synthetic transcript fixtures | 16 |
| Fully correct 4-field cases | 16/16 |
| Exact field slots | 64/64 |
| Correct nonempty fields | 36/36 |
| False nonempty extraction on absent/ambiguous fields | 0 |

The fixtures include 3 English, 3 Hindi, 2 Hinglish, 4 negative/ambiguous, and 4 partial examples. **These are development fixtures, not a blinded or independent benchmark**. In particular, this is NOT a 100% real-world accuracy claim.

## Real Prisma STT / Timbre (pending measurement)

Live Prisma was previously shown working via the user's browser and the Timbre-generated event appeared in its audit logs, but a **quantitative STT WER/CER, noise robustness score, or TTS listening-quality score has not been independently established.** No live patient recordings should ever be used in the project.

To evaluate using self-recorded synthetic cases:

1. Make 10–20 non-patient synthetic recordings (Hindi, Hinglish, low/high volume and ordinary ambient noise). Keep the reference transcription you spoke.
2. With your own authorized key, upload each through the local UI and copy the read-only Prisma output. Verify transcripts manually; do not upload or export identifiers belonging to real people.
3. Store the pairs in a **local private** JSON file outside the project directory, with `id`, `reference`, `hypothesis`; e.g. `[ {"id":"clip_01", "reference":"patient reference 1024 hai", "hypothesis":"patient reference 1024 hai"} ]`.
4. Run `py benchmarks\score_transcripts.py C:\path\to\private\pairs.json` to calculate corpus WER and CER using the documented normalization. For Hindi, word segmentation and numerals can affect results; manually inspect substitutions and normalized numeral mismatches.
5. Record extraction correctness *after* Prisma separately from extraction using a perfect reference transcript; these are different error sources.
6. Listen to Timbre output and note whether the fictitious ID, digit-by-digit phone number, village and reason are intelligible. Do not claim a MOS (Mean Opinion Score) unless you perform a sufficiently documented human listening study.

## Fault injection / checklist for Windows

1. Create a new synthetic case, save corrected fields, prepare Hindi read-back, acknowledge and confirm, submit once.
2. Retry the same POST `/submit` with the same idempotency key. Expect the same `DEMO-*` ID and **one** `simulated_referral_created` audit event.
3. Edit before submitting: old version confirmation must be invalidated. After submitting, edits must be rejected.
4. Retry the Stage 7 handoff with the same worker-selected scenario. Expect the same backend reference, with `Existing: true` on retries. Case Overview must show the reference and last handoff step.
5. Reload the browser (and restart Uvicorn) and check Case Overview is populated from local SQLite data. Older handoff records without metadata require one acknowledged retry to populate the reference.
6. Choose an invalid scenario or remove synthetic-only acknowledgement; bridge must refuse before network action.
7. Run in mock mode without credentials: audio endpoints must not claim live STT/TTS.

## Constraints / safety caveats

- This is **not** a medical referral product, diagnostic tool, triage system or authorised live hospital integration.
- The synthetic bridge calls the original Express **demo session** only, opening the `details` step; it does not initiate routing or notify a real hospital.
- No genuine emergency scenario is AI-classified. The worker explicitly selects a fictional scenario.
- This is a single-instance local SQLite demo, not a security-reviewed production service; concurrency coverage is limited to tested code paths.
- Do not publish any Gnani API key, person-identifying document or audio. Run real-provider benchmarks only on synthetic consented speech.
- REST API reliability tests with mocked Gnani responses do not measure provider availability or request latency.
