# Stage 9: synthetic extraction benchmark

Scope: **offline deterministic parser**, not live Gnani STT/TTS, not medical or field accuracy.

| Metric | Observed |
|---|---:|
| Synthetic transcripts | 16 |
| Exact complete cases | 16/16 (100.0%) |
| Exact field matches | 64/64 (100.0%) |
| Non-empty expected fields correctly extracted | 36/36 |
| Fields unexpectedly populated when expected empty | 0 |
| Abstentions where value expected | 0 |
| Wrong non-empty where value expected | 0 |
| Median local extraction time (machine-specific) | 0.048 ms |
| p95 local extraction time (machine-specific) | 2.738 ms |

## Group breakdown

| Group | Exact cases |
|---|---:|
| english | 3/3 |
| hindi | 3/3 |
| hinglish | 2/2 |
| negative | 4/4 |
| partial | 4/4 |

## Important limitations

- Fixtures are hand-authored synthetic utterances used for development; results are **in-sample**, not a blinded generalisation estimate.
- No real patient data and no real hospital messaging are involved.
- Prisma WER/CER, actual Hindi audio quality, noise robustness and clinical interpretation are **not measured**. A real recorded reference set would be needed.
- Parser latency is per-string on the computer running this script, not end-to-end roundtrip latency.
- Separate automated API tests cover stale versions, submission idempotency, and synthetic backend handoff behaviour.
- A zero failure count in these fixtures does **not** establish production safety.
