# Status (13 Nov 2026)

| Area | Status |
|---|---|
| Voice capture (browser → 16 kHz WAV → Prisma) | Done. Prisma live run verified with a Hindi referral that had Devanagari numerals. |
| Voice clarification agent for missing fields (Timbre asks, Prisma hears, one field filled) | Done. 199 offline tests. Use `scripts/live_smoke_test.py` for the live check. |
| Contradiction-aware resolution ("पहला/दूसरा", ITN "1st/2nd", values, tap) | Done. Live run verified: Timbre asked the question, the spoken answer resolved the conflict, and the read-back was generated. |
| Voice correction never overwrites silently | Done (offline tests + smoke test). |
| Rejecting non-answers and silence | Done (offline tests + safety eval + smoke test). |
| Field verification states and Evidence Passport | Done. |
| Chat view (`/chat`): Matri-Kavach opening (Hi → language → emergency list), all-at-once or guided voice details, voice notes, Timbre replies, chips, hands-free loop, case sheet, dark mode | Done. Checked in a browser with stubbed Gnani (desktop, mobile 375 px, dark mode). 8 offline UI tests. |
| Natural-speech extraction (no markers needed) | Done: 56/56 fields, 0 wrong values, 3.43 → 1.57 questions per draft (offline fixtures). |
| Hands-free spoken confirmation ("हाँ, सब सही है") | Done (12 offline tests + safety eval + smoke test). Not yet verified live. |
| False-ready safety evaluation | Done: 0 false-ready / 0 bypasses / 0 non-answers accepted, and the eval catches deliberately broken guards. |
| Noise benchmark (Timbre speech, clean / noisy / phone) | Script ready (`benchmarks/run_tts_benchmark.py`). Needs a live key to run. |
| Hinglish `codemix` profile (Prisma v3.0) | Implemented per the docs. Not yet verified live. |
| Public mock preview (`render.yaml`) | Config ready. Not deployed. |
| Clinical use / real dispatch | Not implemented and not authorised. Synthetic data only. |
