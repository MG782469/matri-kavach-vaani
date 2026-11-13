# Innovation and evidence notes (for pitch and interview)

Research was done on 13 Nov 2026. Items marked **[unverified]** came only from search abstracts or snippets. Read the full text before you quote them.

## What is new in this build

1. **A voice clarification agent that fills missing fields.** When a referral is missing a field, or a field fails validation, Gnani **Timbre** asks for it in Hindi ("गाँव का नाम नहीं मिला। कृपया गाँव का नाम बताइए।"). The worker answers out loud and Gnani **Prisma** transcribes the answer. The answer can fill **only the field that was asked about**. The loop repeats until every field passes validation, then produces the Timbre read-back.
2. **Spoken-number understanding.** Workers can say numbers as Hindi (Devanagari or romanised) or English words, including "double"/"डबल" and "triple". Romanised "do" counts as 2 only when it sits between digits, so "number do" (meaning "give the number") is not misread.
3. **Read-back in ICAO style.** The contact number is read back one digit at a time, in groups of 5+5, so the voice pauses in the middle of the number.
4. **Recording in the browser.** Audio is converted to 16 kHz mono WAV on the client, because the Prisma REST API accepts WAV/MP3/OGG/FLAC/AAC/M4A (≤30 s) but not webm.
5. **A code-mix STT profile.** `GNANI_STT_PROFILE=codemix` switches Prisma to v3.0 with `language_code=hi-IN,en-IN` and `format=codemix`.
6. **Mobile-number check.** Numbers must start with 6–9, which matches the Indian mobile numbering pattern.

7. **Contradiction-aware clarification.** If the speaker gives two different explicit values (for example two phone numbers), the parser does not pick one. The assistant asks "पहला … दूसरा … सही कौन सा है?" and the worker answers with an ordinal ("पहला"/"दूसरा"), by naming the value, or by tapping a button. Negation corrections are understood ("रामपुर नहीं, सोनपुर"). Negation is never stripped from the referral reason, because "साँस नहीं आ रही" is clinical meaning. "पता नहीं" is never accepted as a value.
8. **Voice correction is never applied silently.** When a spoken correction differs from the current value, both values are kept as a conflict, the version number goes up, any earlier confirmation is cancelled, and the assistant asks which value is right. The resolution history records the field, both candidates, the chosen value, how it was chosen, and the version.
9. **Verification state for each field.** Each field shows conflict, missing, needs fixing, needs read-back, read back, or confirmed, plus where its value came from (speech, typed transcript, voice answer, manual edit). Every state comes from a recorded workflow fact. There are no made-up confidence percentages.
10. **Referral Evidence Passport.** It shows the case reference and version, how many fields are verified, voice clarifications, conflicts resolved, manual edits, whether the read-back covers the current version, Timbre audio, the worker-approved version, the referral ID and the handoff status. It contains no patient values.
11. **Prisma context.** In the `codemix` profile, the question the assistant asked is sent to Prisma v3.0 as `previous_text`, so short replies ("दूसरा", "रामपुर") are transcribed with that context. This has not been verified live.

12. **Natural-speech extraction.** The extractor understands phrasings like "X की मरीज़ / X की रहने वाली / X से आई हैं", a bare "नंबर …" followed by 10 digits, "ID/रेफरेंस 1024", and reasons like "…के लिए अस्पताल ले जाना / PHC भेजना है". These natural-speech patterns run only when no marker pattern matched. On 14 fictional transcripts: marker-only gave 30/56 fields and 3.43 questions per draft; with the fallback, **56/56 fields, 0 wrong values and 1.57 questions per draft** ([report](../benchmarks/results/natural_eval_report.md)). It also fixed a marker bug where "इस गाँव की मरीज़" produced the village name "की मरीज़".
13. **Hands-free spoken confirmation.** After the Timbre read-back, Timbre asks "क्या सभी विवरण सही हैं?" and records the worker's answer. Only an unambiguous approval ("हाँ, सब सही है") confirms, and only for the version whose read-back audio was generated. A bare "हाँ" is rejected, any negative word never confirms, and the passport records `confirmed_by: voice`. The safety eval adds 5 voice-confirmation bypass attempts, and none of them succeeds.

Safety design did not change. The clarification step never confirms anything. Every answer creates a new version, cancels any earlier read-back or confirmation, and the worker still has to listen to the read-back and confirm explicitly.

## Why this problem

- **ASHAs prefer speaking to typing.** In George Institute field work, ASHAs used voice dictation and WhatsApp voice notes rather than typing.
  https://cdn.georgeinstitute.org/sites/default/files/2025-05/Large-AI-model-community-health-workers.pdf
- **Referral slips are often incomplete.** One study reported about 15% of maternal referral slips were incomplete and about 44% of referrals had no pre-referral communication **[unverified]**.
  https://doaj.org/article/a7bf836ae175419cb59564f050ddc9c3
- **Delays in Indian maternal referrals.** The three-delays model has been applied to maternal referrals in India, and a missing standard referral protocol was identified as a cause of delay.
  https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9883712/
- **The ASHA diary is hard to use.** It is described as hard to read and hard to retrieve information from (Social Science & Medicine, 2025).
  https://ideas.repec.org/a/eee/socmed/v382y2025ics0277953625007014.html

## Why read-back and confirmation

- **Joint Commission.** It required a full read-back of verbal and telephone orders and of critical results.
  https://dermatology.cdlib.org/content/qt75z671jb/table12.htm
- **I-PASS handoff bundle.** Its closed-loop "synthesis" step was associated with 23% fewer medical errors. This result is for the whole bundle, not read-back alone.
  https://psnet.ahrq.gov/web-mm/signout-fallout
- **ICAO Annex 10.** It says numbers are transmitted by pronouncing each digit separately.
  https://transportstyrelsen.se/globalassets/global/regler/remisser/luftfart/annex-10-vol-ii-och-pans-atm-proposal-17_23.pdf

## Gap compared with existing tools (as far as we found)

| Tool | What it does | What it does not do |
|---|---|---|
| ImTeCHO / TeCHO+ | Form-based smartphone app | No voice input or read-back |
| Kilkari / Mobile Academy | One-way IVR messages | Does not capture data |
| Khushi Baby | Offline records, entered through forms | No voice input or read-back |
| Wadhwani HealthVaani | Hindi/Hinglish Q&A assistant | Does not capture structured referrals |
| ASHABot | Q&A chatbot | No referral workflow |

None of these combines voice capture, a question for each missing field, digit-by-digit read-back, and an explicit confirmation before a referral is created.

## False-ready safety evaluation (measured, offline)

Command: `py benchmarks\run_safety_eval.py`. The report is at [benchmarks/results/safety_eval_report.md](../benchmarks/results/safety_eval_report.md).

- **Transcripts:** 24 synthetic transcripts (16 fixtures plus 8 adversarial ones: two contacts, two villages, two IDs, a landline-like number, 9 digits, all zeros, no markers, missing reason) were pushed straight to submit, skipping review. **0 were submitted with a wrong or missing value.** 18 were held for review or clarification.
- **Bypass attempts:** 15 attempts were made (5 of them voice-confirmation tricks), including skipping read-back, skipping the acknowledgement, confirming a stale version, editing after confirm, submitting after a voice correction, an open conflict, and a second idempotency key. **None of them got through.**
- **Non-answers:** 26 non-answers ("हाँ", "ok", "kya?", "पता नहीं", ...) were sent as replies to a missing field or a conflict. **None of them was accepted.** "पहला" and "दूसरा" are allowed only as a choice in a conflict.
- **Check that the eval works:** when the guards were deliberately broken, the same evaluation reported 18 false-ready, 3 bypasses and 10 accepted non-answers. So the zeros above are meaningful.
- **Scope:** this checks the workflow guardrails on synthetic input only. It is not a measure of speech recognition accuracy and not a clinical validation.

## How to produce the noisy-audio numbers (Noise Canceller evidence)

1. Record about 10 fictional referral scripts as clean WAV files, using the app's recorder or any 16-bit WAV. Use a mix of Hindi, Hinglish and digit-heavy scripts. Keep them outside the repo, for example in `C:\private\clean`.
2. Make the acoustic variants:
   `py benchmarks\make_variants.py C:\private\clean C:\private\variants`
   This creates clean, noisy10 (10 dB SNR), noisy5 (5 dB SNR) and phone (8 kHz μ-law) versions of each clip.
3. Write `C:\private\manifest.json` with one row per variant: `id`, `audio`, `condition`, `group`, a reviewed `reference` transcript, and the `expected` fields.
4. Run the evaluation (it needs `GNANI_API_KEY`, and each clip costs credits):
   `py benchmarks\run_audio_eval.py C:\private\manifest.json`
   The script writes `benchmarks/results/audio_eval_report.md`, which contains aggregates only.

The main metrics are **phone exact-match**, **wrong-value rate** (the dangerous case), **abstention rate** (the safe case, since the assistant then asks for the field) and **false-ready rate**. WER and CER are supporting metrics. Report the sample size together with every number.

## Honest limits

- Extraction is rule-based (marker patterns first, then natural-speech patterns). Very free-form speech may still leave fields blank, which is the safe failure because the assistant then asks for them. The natural-speech numbers come from in-sample fixtures.
- No measurement of WER/CER on real or noisy audio has been done yet. `benchmarks/score_transcripts.py` is the tool to use once synthetic recordings exist.
- The `codemix` profile follows the Gnani docs but has not been checked end to end with a live key.
