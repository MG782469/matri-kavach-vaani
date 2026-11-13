# Submission kit — Great Indian AI Internship Challenge

**Deadline:** 15 Nov 2026, 6:00 PM IST, as stated on gnani.ai/internship. The page's own countdown timer shows a different time, so go by the date and submit early.

**Order to follow:**
1. Record the demo.
2. Post it on LinkedIn and/or X.
3. Make sure the posts are **live**.
4. Fill the submission form with the post links: https://forms.cloud.microsoft/r/dfFShbp7W7

**Rules to remember:**
- Synthetic data only: no real phone numbers, names, Aadhaar or recorded calls.
- No bought engagement, bots or engagement swaps.
- The shortlist is based on *verified engagement* on your nominated posts.

---

## 1. Before recording (5 minutes)

- [ ] In the server terminal: `set GNANI_MODE=live` and `set GNANI_API_KEY=<real key>`.
- [ ] Run `py scripts\check_gnani.py`. It must show `Looks like template: False` and HTTP 200.
- [ ] Run `py scripts\live_smoke_test.py`. All checks must PASS. If one fails, do not record yet.
- [ ] Start the server, open `localhost:8000`, press Ctrl+Shift+R. The badge must say **"Prisma live / Timbre enabled"**.
- [ ] Use a quiet room, set the browser zoom to 90%, and close other tabs. Turn on system audio capture in your screen recorder, because judges must **hear** Timbre.
- [ ] Do one practice run, then create a fresh case for the real take.

## 2. 60-second demo (also enters "Demo Day Drop")

**Record in the chat view (`localhost:8000/chat`).** It follows the Matri-Kavach conversation: **Hi → हिंदी → ☰ आपातकाल चुनें** (pick "प्रसव के बाद भारी रक्तस्राव") **→ भेजें → 🎙 एक साथ बोलें** (or "❓ एक-एक करके पूछें" to show Vaani asking each field). It looks like the messaging app health workers already use. Keep the browser around 1100 px wide so the case panel and Evidence Passport sit next to the chat. Hands-free is on by default: after Vaani speaks, the mic opens by itself. Use 🎙 and ➤ to start and send a voice note.
- Conflict step: when Vaani asks with a voice note, answer **"हाँ"** first (show that it is rejected), then **"दूसरा"**.
- Confirmation step: say **"हाँ, सब सही है"**.
- Then tap **📤 रेफ़रल भेजें**. The readiness card appears (CHC Sonpur ✗ no anaesthetist). Tap **📤 SEND**.
- Show **multi-role** (about 10 s): open `localhost:8000/roles` in a second tab, log in as **DH Devgarh**, and tap **✓ Ready**. The chat shows "✓ … स्वीकार किया · 108 Ambulance 1" live. Then switch to the **108 driver** phone (pickup and route only, no medical details) and the **family** phone (hospital and ETA only).
- Fallback: tap **"Sample: दो अलग नंबर"** instead of speaking the first message.

| Time | Screen | Do | Say (voice-over, Hinglish is fine) |
|---|---|---|---|
| 0–8 s | Hero and safety badge | — | "ASHA workers send emergency referrals under pressure. One wrong digit in a phone number costs time a mother doesn't have. This is Matri-Kavach Vaani, built on Gnani Prisma and Timbre." |
| 8–20 s | Capture | Click 🎙 **Record referral** and speak naturally: *"रामपुर की मरीज़ है, नंबर 9 8 7 6 5, 4 3 2 1 0, डिलीवरी के लिए अस्पताल ले जाना है… माफ़ कीजिए, नंबर 9 1 2 3 4, 5 6 7 8 9 है।"* Then stop. | "She just talks, no form. Prisma transcribes the Hindi, numbers included." |
| 20–35 s | Orange conflict panel | Click **🔊 Ask with Timbre & listen**. Let Timbre ask. Answer **"हाँ"** and show the rejection. Then answer **"दूसरा"**. | "Two numbers, so it doesn't guess. Timbre asks which one is right. 'Haan' isn't an answer. 'Doosra' is." |
| 35–45 s | Fields and Evidence Passport | Point to the "conflict resolved" chip and the passport row "Conflicts resolved 1/1". | "Both numbers stay in the history. Every field shows where its value came from." |
| 45–55 s | Read-back + spoken confirmation | Let the Timbre read-back play (digit by digit). With hands-free on, Timbre asks "क्या सभी विवरण सही हैं?". Say **"हाँ, सब सही है"**, then click **Submit**. | "Timbre reads every digit back, and she confirms by voice, hands-free. A bare 'haan' isn't enough, and nothing is submitted until she approves this exact version." |
| 55–60 s | Passport and safety-eval report | Show `benchmarks/results/safety_eval_report.md`. | "Zero false-ready referrals across 24 adversarial cases. Synthetic data only, not clinical." |

**If Timbre or Prisma lags on the day**, use "Sample: conflicting numbers" and **Create draft** instead of recording, then continue from 20 s. The voice part of the story stays the same.

## 3. LinkedIn post (draft — edit it in your own voice)

> One wrong digit in a referral phone number can cost a mother in labour the time she doesn't have.
>
> For the #GreatIndianAIInternshipChallenge I built **Matri-Kavach Vaani**, a Hindi/Hinglish voice assistant for frontline health workers, on @Gnani.ai's **Prisma** (speech-to-text) and **Timbre** (text-to-speech).
>
> 🗣️ The worker speaks the referral, and Prisma transcribes it, Devanagari numbers included.
> ⚠️ If a detail is missing or two values conflict, it **doesn't guess**. Timbre asks in Hindi ("पहला या दूसरा?"), the worker answers by voice, and only that field changes.
> 🔁 Every phone number is read back digit by digit, and the worker confirms by voice ("हाँ, सब सही है"), hands-free. Nothing is submitted until she approves that exact version.
> 🧾 An Evidence Passport shows what was heard, changed and approved.
>
> Safety eval: **0 false-ready referrals** across 24 adversarial transcripts and 15 bypass attempts. Synthetic data only. This is a prototype, not a clinical tool.
>
> Demo 👇 · Code: <GitHub link>
>
> #GreatIndianAIInternshipChallenge #GnaniAI #VoiceAI #IndicAI #HealthTech

(Tag the Gnani AI company page by typing @ and selecting it. Attach the video natively instead of as a link, because native video gets more reach.)

## 4. X post (≤280 characters)

> Built Matri-Kavach Vaani on @GnaniAI Prisma + Timbre: a Hindi voice assistant that catches missing or conflicting details in health referrals, asks "पहला या दूसरा?", and reads every digit back before anything is submitted. Synthetic demo 👇 #GreatIndianAIInternshipChallenge #GnaniAI

(Check Gnani's exact X handle before posting.)

## 5. Submission form answers (copy and adjust)

- **Project title:** Matri-Kavach Vaani: error-aware voice referral assistant
- **Problem:** Frontline health workers create maternal-emergency referrals under time pressure. Typing is slow, and wrong or missing details (a phone digit, a village) delay care. Voice dictation alone just moves the error somewhere else.
- **Who will use it:** ASHA workers, ANMs and PHC staff who create or relay referrals. Many prefer speaking to typing.
- **What it does:**
  - The worker speaks the referral naturally in Hindi or Hinglish (no form, no fixed keywords), and Prisma transcribes it.
  - The app extracts the patient reference, village, contact and reason.
  - It detects missing, invalid and contradictory values, and Timbre asks a targeted Hindi question for each one. The spoken answer fills only that field. Non-answers and silence are rejected.
  - Spoken corrections never overwrite silently.
  - Timbre reads the details back digit by digit and asks "क्या सभी विवरण सही हैं?". The worker confirms that exact version by saying "हाँ, सब सही है" (a bare "haan" is not accepted), or with a checkbox.
  - A simulated referral is created, followed by an isolated demo handoff.
  - An Evidence Passport records what was heard, changed and approved.
- **Gnani models/APIs used:**
  - Prisma STT: v2.5 hi-IN with ITN, plus an optional v3.0 codemix profile that sends `previous_text` context.
  - Timbre TTS: v2.5 (Nalini) for clarification questions and the read-back.
- **Evidence:**
  - 220 automated tests (incl. routing and RBAC leak tests).
  - Natural speech: 56/56 fields, 0 wrong values, questions per draft down from 3.43 to 1.57 (14 fictional transcripts).
  - False-ready safety eval: 0 false-ready, 0 bypasses and 0 non-answers accepted (24 transcripts, 15 bypass attempts, 26 non-answers). With the guards deliberately broken, the eval catches them.
  - Live Gnani run of the full conflict → voice answer → read-back loop.
  - Add the noise benchmark numbers from `benchmarks/results/audio_eval_report.md` if you ran it, labelled "Timbre-generated speech with added noise".
- **Team / contributions:** *(fill in: name, and for each member what they built, e.g. backend, voice agent, UI, evaluation, demo)*

## 6. Award categories this fits

- **Real Deal:** rural health workers. This is the main fit.
- **Mixed Vibes:** Hinglish and the codemix profile. Show it only if you tested it live.
- **Jugaad Genius:** using Timbre and Prisma as a closed-loop verification agent.
- **Noise Canceller:** only if you ran `run_tts_benchmark.py` and can show the numbers.

A team can win at most one award.

## 7. Final checklist

- [ ] `py -m unittest discover -s tests` shows OK.
- [ ] `py benchmarks\run_safety_eval.py` shows 0 / 0 / 0.
- [ ] `py scripts\live_smoke_test.py` shows all PASS.
- [ ] The GitHub repo is public and has no `.env`, no key and no `data/*.sqlite3`. The README is up to date.
- [ ] The video is recorded in live mode and Timbre is audible.
- [ ] The posts are live, tag Gnani AI, and use both hashtags.
- [ ] The form is submitted with the post links, before 6 PM IST on 15 Nov.
