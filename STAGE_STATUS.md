# Status (13 Nov 2026)

| Area | Status |
|---|---|
| Voice capture (browser → 16 kHz WAV → Prisma) | Done. Prisma live run verified with a Hindi referral that had Devanagari numerals. |
| Voice clarification agent for missing fields (Timbre asks, Prisma hears, one field filled) | Done. 171 offline tests. Use `scripts/live_smoke_test.py` for the live check. |
| Contradiction-aware resolution ("पहला/दूसरा", ITN "1st/2nd", values, tap) | Done. Live run verified: Timbre asked the question, the spoken answer resolved the conflict, and the read-back was generated. |
| Voice correction never overwrites silently | Done (offline tests + smoke test). |
| Rejecting non-answers and silence | Done (offline tests + safety eval + smoke test). |
| Field verification states and Evidence Passport | Done. |
| False-ready safety evaluation | Done: 0 false-ready / 0 bypasses / 0 non-answers accepted, and the eval catches deliberately broken guards. |
| Noise benchmark (Timbre speech, clean / noisy / phone) | Script ready (`benchmarks/run_tts_benchmark.py`). Needs a live key to run. |
| Hinglish `codemix` profile (Prisma v3.0) | Implemented per the docs. Not yet verified live. |
| Public mock preview (`render.yaml`) | Config ready. Not deployed. |
| Clinical use / real dispatch | Not implemented and not authorised. Synthetic data only. |
