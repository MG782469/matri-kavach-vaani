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


def _match_unique(text, patterns, transform=lambda x: x):
    """Never choose arbitrarily between conflicting explicitly marked values."""
    found = []
    for pat in patterns:
        for m in re.finditer(pat, text, re.I | re.U):
            value = transform(m.group('value').strip(' ,.;।:-'))
            if value and value not in found:
                found.append(value)
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
]

_CONTACT = [
    r'(?:\b(?:contact|mobile|phone)\s*(?:number|no)?\b|(?:कॉन्टेक्ट|कांटेक्ट|संपर्क|मोबाइल|फोन)\s*(?:नंबर|नम्बर|संख्या)?)\s*(?:is|hai|है|:|-)?\s*(?P<value>(?:[0-9][\s-]*){10})\b',
]

# Capture only an explicit referral/reason clause; never invent diagnosis or
# urgency. A sentence may contain further polite requests, which we discard.
_REASON = [
    r'\b(?:reason|referral\s*reason)\s*[:\-]\s*(?P<value>[^,.;।]{4,180})',
    r'(?P<value>(?:पेशेंट|मरीज|मरीज़|रोगी)\s+को\s+[^।.!?\n]{3,140}?(?:रेफरल|रिफरल)\s+की\s+जर[ूु]रत\s+है)(?=\s*(?:।|\.|!|\?|कृपया|प्लीज|$))',
    r'(?P<value>(?:patient|mareez|mariz)\s+ko\s+[^.!?\n]{3,140}?(?:referral|refer)\s+(?:ki\s+)?(?:zarurat|jarurat|chahiye|needed|required)(?:\s+hai)?)(?=\s*(?:\.|!|\?|kripya|please|$))',
]


def _clean_village(value):
    value = re.sub(r'\s+(?:से|का|की|के|में|है|हैं|se|hai|hain)$', '', value.strip(), flags=re.I)
    return value.strip()


def parse_transcript(transcript: str) -> dict:
    if not isinstance(transcript, str):
        raise TypeError('Transcript must be text')
    text = normalize_digits(transcript)
    out = {k: '' for k in FIELDS}
    out['patient_ref'] = _match_unique(text, _ID)
    out['contact'] = _match_unique(text, _CONTACT, lambda s: re.sub(r'[\s-]', '', s))
    out['village'] = _match_unique(text, _VILLAGE, _clean_village)
    out['referral_reason'] = _match_unique(text, _REASON)
    return out
