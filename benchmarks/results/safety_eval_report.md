# False-ready safety evaluation (offline, synthetic)

Workflow guardrail check. It does not measure speech recognition accuracy and is not clinical validation.

| Check | Result |
|---|---|
| Transcripts pushed straight to submit (16 fixtures + 8 adversarial) | 24 |
| Submitted untouched (all fields complete and correct) | 6 |
| Held for worker review / clarification | 18 |
| **False-ready** (submitted with a wrong or missing value) | **0** |
| Bypass attempts (skip read-back, stale version, open conflict, voice-confirm tricks, ...) | 15 |
| **Bypasses that succeeded** | **0** |
| Non-answers sent to the voice assistant | 26 |
| **Non-answers wrongly accepted** | **0** |

Note: "submitted untouched" uses this script as the worker and ticks the acknowledgement automatically; in the real app a human must listen to the read-back and tick it.
