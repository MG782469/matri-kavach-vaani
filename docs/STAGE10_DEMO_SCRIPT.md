# Matri-Kavach Vaani — 3-minute synthetic walkthrough

**Record the full feature demo LOCALLY in the developer's authorised live mode.** Use a fictional reference number, fictional contact, village and non-clinical referral-reason wording. No real medical records.

| Time | Open/show | What to explain |
|---|---|---|
| 0:00–0:20 | Main dashboard + safety banner | “Matri-Kavach Vaani is a synthetic, voice-to-verified-referral proof of concept. It doesn't diagnose, triage, or send hospital notifications.” |
| 0:20–0:45 | Capture → upload a pre-recorded synthetic Hindi/Hinglish clip | “Gnani Prisma provides the transcript. We retain the raw transcription so staff can compare it with the recording.” |
| 0:45–1:15 | Correct fields | “Extraction is conservative; staff check patient reference, village, test contact and the referral reason. Editing invalidates previous approval.” |
| 1:15–1:45 | Prepare Hindi read-back → Generate Timbre audio | “Gnani Timbre reads the structured details out; staff verify numbers digit by digit.” Actually play a short excerpt; do not claim quality scores without listening evaluation. |
| 1:45–2:10 | Check acknowledgment → Confirm exact version | “We require explicit review of the current version; stale confirmation cannot dispatch.” |
| 2:10–2:30 | Submit demo referral | “Idempotent submission creates a synthetic DEMO ID. Retrying cannot create a second request.” |
| 2:30–2:50 | Isolated demo handoff; choose a synthetic scenario | “Staff choose the demonstration scenario. The original Matri-Kavach Express engine receives no patient fields, and only opens a case at its initial details stage.” |
| 2:50–3:00 | Case Overview + audit timeline | “The backend reference, test evidence and audit history make every action inspectable. This is not clinical deployment.” |

## Extra screenshots

- Test output `Ran 105 tests` / `OK` (if reproduced locally).
- `benchmarks/results/stage9_report.md` synthetic parser results and explicit in-sample label.
- Case Overview: `Demo linked`, `MK-...`, and `details` after local demo handoff.
- Evidence of edit-after-confirmation invalidation / stale request rejection (synthetic only).

## Critical distinction

The public password-protected preview intentionally runs in MOCK mode and will NOT demonstrate live Prisma/Timbre or Express handoff. Use the local screen recording for those features. Avoid claiming that public preview equals the local live workflow.
