"""Deterministic, conservative extraction from Prisma Hindi/Hinglish transcripts.

No clinical inferences. Explicit field markers only; missing/ambiguous fields
remain blank for human correction. The original transcript is never modified.
"""
import re
import unicodedata

FIELDS = ('patient_ref', 'village', 'contact', 'referral_reason')


def normalize_digits(text: str) -> str:
    """Convert Unicode decimal digits (including Devanagari) to ASCII."""
    out = []
    for ch in unicodedata.normalize('NFKC', text):
        try:
            out.append(str(unicodedata.decimal(ch)))
        except ValueError:
            out.append(ch)
    return ''.join(out)


def _match_all(text, patterns, transform=lambda x: x):
    found = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.I | re.U):
            value = transform(m.group('value').strip(' ,.;।:-'))
            if value and value not in found:
                found.append(value)
    return found


def _match_unique(text, patterns, transform=lambda x: x):
    """Never choose arbitrarily between conflicting explicitly marked values."""
    found = _match_all(text, patterns, transform)
    return found[0] if len(found) == 1 else ''


# Only accept an identifier next to a known reference marker; prevent catching
# the word 'number' or the contact number as the patient reference.
_ID = [
    r'\bpatient\s*(?:id|reference(?:\s*(?:number|no))?|ref(?:\s*(?:number|no))?)\s*(?:is|hai|है|:|-)?\s*(?P<value>[A-Za-z0-9][A-Za-z0-9_-]{0,29})',
    r'(?:पेशेंट(?:्स)?|मरीज|मरीज़|रोगी)\s*(?:का|की|के)?\s*(?:रेफरेंस|रिफरेंस|संदर्भ|आईडी)\s*(?:नंबर|नम्बर|संख्या)?\s*(?:है|:|-)?\s*(?P<value>[A-Za-z0-9][A-Za-z0-9_-]{0,29})',
]

# Match either "village Rampur" or "Rampur gaon se hai". In both forms the
# village name must be explicitly tied to a village/gaon marker.
_VILLAGE = [
    r'\b(?:village|gaon|गांव|गाँव|गाव)\s*(?::|-)?\s*(?P<value>[A-Za-z\u0900-\u097F]+(?:[ -][A-Za-z\u0900-\u097F]+){0,3}?)(?=\s*(?:,|\.|।|;|\bcontact\b|\bphone\b|\breason\b|\bpatient\b|$))',
    r'(?P<value>[A-Za-z\u0900-\u097F]+)\s+(?:gaon|गांव|गाँव|गाव)(?=\s|[,.;।]|$)',
    r'\b(?:village|gaon)\s*(?:is|:|-)\s*(?P<value>[A-Za-z][A-Za-z -]{1,35}?)(?=\s*(?:,|\.|$))',
    # Prisma (hi-IN) writes the spoken English marker "village" in Devanagari: "विलेज रामपुर".
    r'(?:विलेज़?|विलैज)\s*(?::|-)?\s*(?P<value>[ऀ-ॿA-Za-z]+(?:\s[ऀ-ॿA-Za-z]+){0,2}?)'
    r'(?=\s*(?:[,.;।]|कॉन्टेक्ट|कॉन्टैक्ट|कांटेक्ट|संपर्क|मोबाइल|फ़?फोन|फ़ोन|रीज़न|रीजन|रेफरल|पेशेंट|मरीज|से\b|है|$))',
]

_CONTACT = [
    r'(?:\b(?:contact|mobile|phone)\s*(?:number|no)?\b|(?:कॉन्टेक्ट|कॉन्टैक्ट|कोंटेक्ट|कांटेक्ट|संपर्क|मोबाइल|फोन|फ़ोन)\s*(?:नंबर|नम्बर|संख्या)?)\s*(?:is|hai|है|:|-)?\s*(?P<value>(?:[0-9](?:[\s-]|,\s)*){10})\b',
]

# Capture only an explicit referral/reason clause; never invent diagnosis or
# urgency. A sentence may contain further polite requests, which we discard.
_REASON = [
    # Spoken form has no colon: "referral reason hospital checkup" / "reason hai transport".
    r'\b(?:reason|referral\s*reason)\s*(?:[:\-]|\bis\b|\bhai\b)?\s*(?P<value>[^,.;।]{4,180})',
    r'(?P<value>(?:पेशेंट|मरीज|मरीज़|रोगी)\s+को\s+[^।.!?\n]{3,140}?(?:रेफरल|रिफरल)\s+की\s+जर[ूु]रत\s+है)(?=\s*(?:।|\.|!|\?|कृपया|प्लीज|$))',
    r'(?P<value>(?:patient|mareez|mariz)\s+ko\s+[^.!?\n]{3,140}?(?:referral|refer)\s+(?:ki\s+)?(?:zarurat|jarurat|chahiye|needed|required)(?:\s+hai)?)(?=\s*(?:\.|!|\?|kripya|please|$))',
    # Prisma (hi-IN) writes the spoken English marker "reason" in Devanagari: "रेफरल रीज़न हॉस्पिटल चेकअप".
    r'(?:रेफरल\s+)?(?:रीज़न|रीजन|रिज़न|रीसन)\s*(?:है|:|-)?\s*(?P<value>[^,.;।]{4,180}?)(?=\s*(?:[,.;।!?]|कृपया|प्लीज|$))',
]


def _clean_village(value):
    value = re.sub(r'\s+(?:से|का|की|के|में|है|हैं|se|hai|hain)$', '', value.strip(), flags=re.I)
    value = value.strip()
    # "रामपुर गाँव से है।" makes the marker regex also catch "से"; a bare filler word is
    # never a village and must not create a false conflict that blanks the real name.
    return '' if value.lower() in _FILLERS else value


_DIGIT_WORD = {}
for _d, _ws in {'0': 'शून्य ज़ीरो जीरो zero shunya', '1': 'एक one', '2': 'दो two', '3': 'तीन three teen',
                '4': 'चार four', '5': 'पांच पाँच five paanch', '6': 'छह छः छे six chhah chhe',
                '7': 'सात seven saat', '8': 'आठ eight aath', '9': 'नौ nine nau'}.items():
    for _w in _ws.split():
        _DIGIT_WORD[_w] = _d
_WORD_RUN = re.compile(r'(?:(?<=\s)|^)((?:(?:%s)(?:[\s,]+|$)){4,})' % '|'.join(sorted(map(re.escape, _DIGIT_WORD), key=len, reverse=True)), re.I)


def _digit_word_runs(text):
    """"नौ आठ सात छह पाँच, चार ..." -> "9 8 7 6 5, 4 ...". Only runs of 4+ digit words,
    so ordinary words like "एक मरीज़" are never touched."""
    def repl(m):
        tokens = re.findall(r'[^\s,]+|,', m.group(1))
        out = ' '.join(_DIGIT_WORD.get(t.lower(), t) if t != ',' else ',' for t in tokens).replace(' ,', ',')
        return out + (' ' if m.group(1)[-1:].isspace() else '')
    return _WORD_RUN.sub(repl, text)


def _prep(transcript):
    return _digit_word_runs(normalize_digits(transcript))


def _contact_digits(s):
    return re.sub(r'[\s,-]', '', s)


# ---------------------------------------------------------------------------
# Natural-speech FALLBACK patterns. Used for a field only when no marker pattern
# matched at all, so marker-based behaviour (and its benchmark) is unchanged.
#   "रामपुर की मरीज़ है, नंबर 98765 43210, डिलीवरी के लिए अस्पताल ले जाना है"
# ---------------------------------------------------------------------------
_L = r'A-Za-z\u0900-\u097F'
_ID_NATURAL = [
    r'(?:\b(?:id|reference|ref)\b|आईडी|रेफरेंस|रिफरेंस)\s*(?:number|no|नंबर|नम्बर)?\s*(?:is|hai|है|:|-)?\s*'
    r'(?P<value>[A-Za-z]{0,10}-?[0-9][A-Za-z0-9_-]{0,29})',
]
_VILLAGE_NATURAL = [
    r'(?P<value>[' + _L + r']+)\s+(?:की|के|का|ki|ke|ka)\s+(?:मरीज़?|महिला|गर्भवती|पेशेंट|mareez|mariz|patient|'
    r'रहने\s+वाली|रहने\s+वाले|रहने\s+वाला|rehne\s+wal[aie])',
    r'(?P<value>[' + _L + r']+)\s+(?:से|se)\s+(?:आई|आए|आया|aayi|aai|aaye)\s+(?:है|हैं|hai|hain)',
]
_CONTACT_NATURAL = [
    r'(?:\b(?:number|no|num)\b|नंबर|नम्बर)\s*(?:is|hai|है|:|-|पर|par)?\s*(?P<value>(?:[0-9](?:[\s-]|,\s)*){10})\b',
]
_REASON_NATURAL = [
    r'(?P<value>[^,.;।!?]{2,80}?\s(?:के\s+लिए|ke\s+liye|for)\s+[^,.;।!?]{0,40}?'
    r'(?:ले\s+जाना|भेजना|रेफर\s+करना|दिखाना|le\s+jana|bhejna|refer\s+karna|dikhana)(?:\s+(?:है|hai|होगा|hoga))?)'
    r'(?=\s*(?:[,.;।!?]|कृपया|please|$))',
    r'(?P<value>(?:अस्पताल|हॉस्पिटल|hospital|PHC|CHC)\s+(?:ले\s+जाना|भेजना|le\s+jana|bhejna|refer\s+karna)(?:\s+(?:है|hai))?)',
]
_NOT_A_PLACE = {'इस', 'उस', 'हमारे', 'मेरे', 'एक', 'यह', 'वह', 'इन', 'उन', 'गाँव', 'गांव', 'this', 'that', 'ek', 'hamare',
                'mere', 'is', 'us', 'gaon', 'village', 'अस्पताल', 'hospital', 'मरीज़', 'मरीज', 'महिला', 'पेशेंट',
                'गर्भवती', 'mareez', 'mariz', 'patient', 'naam', 'नाम'}


def _id_value(v):
    return v


def _place_value(v):
    # "इस गाँव की मरीज़" made the marker regex catch "की मरीज़": drop leading particles, then
    # reject anything that is not a place name.
    v = re.sub(r'^(?:(?:की|का|के|से|में|ki|ka|ke|se|mein)\s+)+', '', v.strip(), flags=re.I)
    v = _clean_village(v)
    if not v or v.lower() in _NOT_A_PLACE or any(w.lower() in _NOT_A_PLACE for w in v.split()):
        return ''
    return v


def _reason_value(v):
    return v.strip()


_SPECS = {
    'patient_ref': (_ID, _ID_NATURAL, _id_value),
    'contact': (_CONTACT, _CONTACT_NATURAL, _contact_digits),
    'village': (_VILLAGE, _VILLAGE_NATURAL, _place_value),
    'referral_reason': (_REASON, _REASON_NATURAL, _reason_value),
}


def _dedupe(found):
    """Keep the longest form when one pattern catches "Rampur" and another "Rampur Kalan"."""
    return [v for v in found if not any(v != o and v.lower() in o.lower() for o in found)]


def _candidates(text, field, natural=True):
    primary, fallback, transform = _SPECS[field]
    found = _match_all(text, primary, transform)
    if field == 'village':
        found = _dedupe([v for v in found if v.lower() not in _FILLERS])
    if not found and natural:
        found = _dedupe(_match_all(text, fallback, transform))
    return found


def parse_transcript(transcript: str, natural: bool = True) -> dict:
    """Conservative extraction. A field is filled only when exactly ONE value was found;
    two different values leave it blank (see find_conflicts) — the worker is asked instead."""
    if not isinstance(transcript, str):
        raise TypeError('Transcript must be text')
    text = _prep(transcript)
    out = {}
    for k in FIELDS:
        found = _candidates(text, k, natural)
        out[k] = found[0] if len(found) == 1 else ''
    return out


_FILLERS = {'से', 'का', 'की', 'के', 'में', 'है', 'हैं', 'se', 'hai', 'hain', 'ka', 'ki', 'ke', 'mein', 'is', 'the', 'name', 'naam', 'नाम'}


def find_conflicts(transcript: str) -> dict:
    """Fields where the speaker gave two or more DIFFERENT explicit values.

    parse_transcript leaves these blank (it never picks one); this exposes the
    candidates so the worker can be asked which one is right.
    """
    text = _prep(transcript)
    out = {}
    for field in FIELDS:
        found = _candidates(text, field)
        if len(found) > 1:
            out[field] = found[:3]
    return out
