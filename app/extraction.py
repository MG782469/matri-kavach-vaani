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


def parse_transcript(transcript: str) -> dict:
    if not isinstance(transcript, str):
        raise TypeError('Transcript must be text')
    text = _prep(transcript)
    out = {k: '' for k in FIELDS}
    out['patient_ref'] = _match_unique(text, _ID)
    out['contact'] = _match_unique(text, _CONTACT, _contact_digits)
    out['village'] = _match_unique(text, _VILLAGE, _clean_village)
    out['referral_reason'] = _match_unique(text, _REASON)
    return out


_FILLERS = {'से', 'का', 'की', 'के', 'में', 'है', 'हैं', 'se', 'hai', 'hain', 'ka', 'ki', 'ke', 'mein', 'is', 'the', 'name', 'naam', 'नाम'}


def find_conflicts(transcript: str) -> dict:
    """Fields where the speaker gave two or more DIFFERENT explicit values.

    parse_transcript leaves these blank (it never picks one); this exposes the
    candidates so the worker can be asked which one is right.
    """
    text = _prep(transcript)
    specs = {'patient_ref': (_ID, lambda x: x),
             'contact': (_CONTACT, _contact_digits),
             'village': (_VILLAGE, _clean_village),
             'referral_reason': (_REASON, lambda x: x)}
    out = {}
    for field, (patterns, transform) in specs.items():
        found = _match_all(text, patterns, transform)
        if field == 'village':
            # Drop filler words a marker regex can catch ("गाँव से"), and keep the
            # longest form when one regex catches "Rampur" and another "Rampur Kalan".
            found = [v for v in found if v.lower() not in _FILLERS]
            found = [v for v in found if not any(v != o and v in o for o in found)]
        if len(found) > 1:
            out[field] = found[:3]
    return out
