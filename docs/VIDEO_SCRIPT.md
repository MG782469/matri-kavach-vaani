# 🎬 Matri-Kavach Vaani: demo video script (about 2:45)

**Format:** screen recording, with your voice-over and a small face-cam in the corner (optional). The voice-over is in Hinglish. Add **English captions**, because judges may not understand Hindi audio.

**Rules:** live mode only (Gnani must actually run). Fictional data only. **Timbre's voice must be audible** in the recording.

---

## 🧰 Before recording (10 minutes)

1. In the server terminal, run these lines one by one:
   - `set GNANI_MODE=live`
   - `set GNANI_API_KEY=<key>`
   - `py scripts\check_gnani.py` (all should show 200)
   - `py scripts\live_smoke_test.py` (all should PASS)
   - `py -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
2. In Chrome, open **two windows side by side**:
   - **Left:** `localhost:8000/chat`
   - **Right:** `localhost:8000/roles`. Log in **before recording** on the DH Devgarh, SDH Kheri, 108 driver and Family phones (Send code, then Verify), so the video has no wait.
3. Set the browser zoom to **90–100%** and close other tabs and notifications. Use Focus Assist (Windows: `Win + N`, then Do not disturb).
4. In the chat's side panel, keep **Auto-play ✓** and **Hands-free ✓** on.
5. Recorder: OBS or Windows `Win + Alt + R` (Xbox Game Bar), with **system audio ON** so Timbre is recorded. Use a quiet room and a headset mic if you have one.
6. Do **one full practice run**, then press ➕ in the chat to start fresh, and record the real take.

**Lines the worker speaks in the demo (fictional data):**
- **Referral:** *"रामपुर की मरीज़ है, रेफ़रेंस 2048, नंबर 9 8 7 6 5, 4 3 2 1 0, डिलीवरी के लिए अस्पताल ले जाना है… माफ़ कीजिए, नंबर 9 1 2 3 4, 5 6 7 8 9 है।"*
- **First reply to the conflict question:** *"हाँ"* (Vaani rejects this)
- **Second reply:** *"दूसरा"*
- **Confirmation:** *"हाँ, सब सही है"*

---

## 🎞️ The script

### Scene 1: Hook (0:00–0:12)
| Screen | Voice-over |
|---|---|
| Black screen, then slow text: **"9 8 7 6 5 4 3 2 1 0"**. One digit turns red: **"9 8 7 6 5 4 3 2 1 8"** | *"Ek ASHA didi raat ke 2 baje emergency referral bhej rahi hai. Haath kaanp rahe hain, phone pe type karna mushkil hai. Aur agar ek digit galat ho gaya… to ambulance aur hospital ka phone kisi aur ko lag jaata hai."* |
| Text: **"One wrong digit = lost time a mother doesn't have."** | *"Maternal emergency mein ye time maa ke paas nahi hota."* |

### Scene 2: The problem (0:12–0:27)
| Screen | Voice-over |
|---|---|
| The README's "The problem" section, or 2 slides: *"ASHAs rarely type, they send voice notes" (George Institute, 2025)* and *"Incomplete referral slips, delays in care"* | *"Research kehti hai ki ASHA workers phone pe type nahi karti, voice notes bhejti hain. Lekin sirf voice-to-text kaafi nahi hai, kyunki galti keyboard se nikal ke transcript mein aa jaati hai. Chahiye ek **closed loop**: poocho, padh ke sunao, confirm karwao."* |

### Scene 3: Introducing Vaani (0:27–0:37)
| Screen | Voice-over |
|---|---|
| The chat view opens (`/chat`), showing the header "Matri-Kavach Vaani · online · Gnani Prisma + Timbre" | *"Ye hai **Matri-Kavach Vaani**: ek Hindi voice assistant jo **galat digit ko aage nahi jaane deta**. Gnani **Prisma** sunta hai, Gnani **Timbre** bolta hai."* |

### Scene 4: Matri-Kavach style start (0:37–0:52)
| Screen | Voice-over |
|---|---|
| Tap **Hi**, then **हिंदी**, then **☰ आपातकाल चुनें**. The sheet opens: pick **"प्रसव के बाद भारी रक्तस्राव (PPH)"**, then **भेजें** | *"Shuruaat Matri-Kavach jaisi: Hi, bhasha, aur emergency ka type. Ye list clinical advisor ke saath bani hai, aur emergency **worker chunti hai**. AI koi diagnosis nahi karta."* |

### Scene 5: Speaking the referral + conflict (0:52–1:22) ⭐
| Screen | Voice-over |
|---|---|
| Tap **🎙 एक साथ बोलें**. The red recording bar appears. Speak the full referral line, including the two different phone numbers, then tap ➤ | *(Your recording plays. Stay silent.)* |
| Your voice note appears with **"Prisma heard: …"** below it, then the draft card, with **⚠ Conflict** on the contact field | *"Prisma ne Hindi mein sab sun liya. Lekin dhyaan do: maine **do alag number** bole. Normal app aakhri wala utha leta. Vaani **guess nahi karti**."* |
| Timbre's voice note plays: **"…पहला 9 8 7 6 5… दूसरा 9 1 2 3 4… सही कौन सा है?"** and the mic opens by itself (hands-free) | *(Let Timbre's voice play. Stay silent.)* |
| Say **"हाँ"**. The red error appears | *"Agar main sirf 'haan' bolu, to wo bhi accept nahi hota."* |
| Say **"दूसरा"**. ✓ Contact = 9123456789, and the chip shows "conflict resolved" | *"'Doosra' bola, aur **sirf wahi ek field** badla. Dono purane number history mein safe hain."* |

### Scene 6: Read-back + voice confirmation (1:22–1:45) ⭐
| Screen | Voice-over |
|---|---|
| The Timbre read-back plays: **"…संपर्क नंबर 9 1 2 3 4, 5 6 7 8 9…"** | *"Ab Timbre har digit **alag-alag** padh ke sunata hai, aviation-style read-back."* |
| Timbre asks **"क्या सभी विवरण सही हैं?"**. You say **"हाँ, सब सही है"**. The card shows **"Confirmed by voice 🎙"** | *"Aur worker bol ke confirm karti hai: 'haan, sab sahi hai'. Ye confirmation **sirf isi version** ke liye hai. Kuch bhi badla, to dobara confirm karna padega."* |
| Zoom on the side-panel **Evidence Passport**: "Conflicts resolved 1/1 · Approved v1 · by voice" | *"Evidence Passport mein sab record hota hai: kya suna, kya badla, kisne approve kiya."* |

### Scene 7: Hospital routing + role phones (1:45–2:20) ⭐
| Screen | Voice-over |
|---|---|
| Tap **📤 रेफ़रल भेजें**. The readiness card appears: **CHC Sonpur ✗ anaesthetist nahi · DH Devgarh → first · SDH Kheri → backup** | *"Ab Matri-Kavach ka asli kaam: aaj raat **kaunsa hospital sach mein ready hai**. CHC Sonpur sabse paas hai, par wahan anaesthetist nahi hai, to skip."* |
| Tap **📤 SEND**. Switch to the **right window: DH Devgarh phone**. The request shows with the **2:00 timer** | *"DH Devgarh ke phone pe request aayi, 2 minute ka timer ke saath."* |
| DH taps **✗ Not ready tonight**. The chat (left) shows **"⚠ … अब SDH Kheri से पूछा गया"** | *"Agar hospital mana kare, ya 2 minute mein jawab na de, to Vaani **apne aap backup** se poochti hai."* |
| Switch to the **SDH Kheri** phone and tap **✓ Ready**. The chat shows **"✓ SDH Kheri ने स्वीकार किया · 108 Ambulance 1"** | *"SDH Kheri ne accept kiya. Ambulance assign ho gayi."* |
| Quickly switch to the **108 driver**, then **Family**, then **District** phones | *"Aur yahan hai RBAC: **driver** ko sirf pickup aur route, koi medical detail nahi. **Family** ko sirf hospital aur ETA. **District** ko sirf alerts, naam nahi. **Phone number kisi ko nahi milta**, aur ye browser mein nahi, **server pe** enforce hota hai."* |

### Scene 8: Proof (2:20–2:35)
| Screen | Voice-over |
|---|---|
| `benchmarks/results/safety_eval_report.md` open: **False-ready 0 · Bypasses 0 · RBAC leaks 0** | *"Humne isse todne ki koshish ki. 24 adversarial referrals, 15 bypass attempts, 26 bekaar jawab: **zero** galat referral aage gaya, aur **zero** data leak hua. 220 automated tests."* |
| (Optional) The terminal showing `Ran 220 tests … OK` | *"Aur ye sab synthetic data pe hai. Ye clinical tool nahi, ek safe prototype hai."* |

### Scene 9: Close (2:35–2:50)
| Screen | Voice-over |
|---|---|
| The README top (badges and screenshots), then the end card: **Matri-Kavach Vaani · Gnani Prisma + Timbre · Manas Girdhar · Meenakshi Satpathy · Clinical advisor: Moluvi Gufran** · GitHub link · #GreatIndianAIInternshipChallenge #GnaniAI | *"Matri-Kavach Vaani. ASHA bolti hai, Vaani sunti hai, poochti hai, padh ke sunati hai, aur tabhi aage bhejti hai jab sab sahi ho. Next step: yahi voice agent WhatsApp pe, jahan ASHAs pehle se hain. Thank you, Gnani AI!"* |

---

## ✂️ 60-second cut (for the "Demo Day Drop" award)
Keep only scene 1 (first 5 s), scene 5, scene 6, scene 7 (the DH ✗ and SDH ✓ part) and the end card. The voice-over lines stay the same, just shorter.

| Time | What to show |
|---|---|
| 0–5 s | Hook: "One wrong digit…" |
| 5–25 s | Spoken referral → conflict → "हाँ" rejected → "दूसरा" |
| 25–40 s | Read-back → "हाँ, सब सही है" → Confirmed by voice |
| 40–55 s | SEND → DH ✗ → automatic backup SDH ✓ → driver and family phones |
| 55–60 s | "0 false-ready · 0 leaks" + end card |

---

## 🎙️ Recording and editing tips
- **Captions:** add English subtitles for every Hindi line (CapCut can auto-caption, then fix the text by hand).
- **Zoom:** use a 1.3–1.5× zoom on the important moments: "Prisma heard", the conflict chip, "Confirmed by voice", the driver card. The judge's attention should go exactly there.
- **Speed:** you can play Timbre voice notes at **1.0×**, but speed up waiting and typing parts to 1.5–2×. Never fake the API response; only speed up the waiting.
- **Music:** soft background music at 10–15% volume, and duck it (lower it) while Timbre is speaking.
- **If something fails during recording:** don't stop, take it again. If Prisma hears a number wrong, that is a **good demo moment**: Vaani asks, and the worker corrects it. But keep it clean for the final cut.
- **Before posting:** blur the API key, terminal history and personal notifications. Everything else in the video is fictional.

## 📣 Post caption (LinkedIn; adjust for X)
> One wrong digit in a referral phone number can cost a mother in labour the time she doesn't have.
>
> We built **Matri-Kavach Vaani**, a Hindi voice assistant for ASHA workers, on **@Gnani.ai Prisma + Timbre**:
> 🗣 She speaks the referral naturally. ⚠ Two different numbers? Vaani doesn't guess; it asks "पहला या दूसरा?"
> 🔢 Every digit is read back, and she confirms by voice: "हाँ, सब सही है".
> 🏥 Vaani asks the nearest hospital that is *ready tonight*, and switches to the backup if there is no reply in 2 minutes.
> 🔐 The 108 driver, family and district each see only their part (server-side RBAC).
> ✅ 0 false-ready referrals · 0 data leaks in our adversarial safety eval · synthetic data only.
>
> Team: Manas Girdhar, Meenakshi Satpathy · Clinical advisor: Moluvi Gufran
> 🎥 Demo below · Code: github.com/MG782469/matri-kavach-vaani
> #GreatIndianAIInternshipChallenge #GnaniAI #VoiceAI #HealthTech
