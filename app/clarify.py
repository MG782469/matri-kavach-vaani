"""Voice clarification: ask for ONE missing/invalid field and parse ONLY that answer.

Safety rules:
- The question targets a field that currently fails validation; nothing is guessed.
- An answer can only change the field that was asked about.
- Every filled value still goes through worker review, read-back and confirmation.
"""
import re
from .extraction import normalize_digits, _clean_village
from .core import REQUIRED, validate

LABELS = {'patient_ref': 'Patient reference', 'village': 'Village',
          'contact': 'Contact number', 'referral_reason': 'Referral reason'}

QUESTIONS = {
    'patient_ref': 'मरीज़ का रेफरेंस नंबर नहीं मिला। कृपया रेफरेंस नंबर बताइए।',
    'village': 'गाँव का नाम नहीं मिला। कृपया गाँव का नाम बताइए।',
    'contact': 'संपर्क नंबर नहीं मिला या अधूरा है। कृपया दस अंकों का नंबर एक-एक अंक करके बताइए।',
    'referral_reason': 'रेफरल का कारण नहीं मिला। कृपया रेफरल का कारण बताइए।',
}

# Spoken digits in Hindi (Devanagari + romanised) and English. Prisma v2.5 with
# native-numeral ITN usually returns digits, but code-mix mode or slow
# digit-by-digit speech can return words.
_DIGIT_WORDS = {
    # Ambiguous romanised words ('do' = give, 'no', 'sat', 'tin') are left out on purpose.
    '0': ['शून्य', 'ज़ीरो', 'जीरो', 'zero', 'shunya', 'sunya'],
    '1': ['एक', 'वन', 'one', 'ek'],
    '2': ['दो', 'टू', 'two'],
    '3': ['तीन', 'थ्री', 'three', 'teen'],
    '4': ['चार', 'फोर', 'फ़ोर', 'four', 'char', 'chaar'],
    '5': ['पांच', 'पाँच', 'फाइव', 'five', 'paanch', 'panch'],
    '6': ['छह', 'छः', 'छे', 'छै', 'सिक्स', 'six', 'chhah', 'chhe'],
    '7': ['सात', 'सेवन', 'seven', 'saat'],
    '8': ['आठ', 'एट', 'eight', 'aath'],
    '9': ['नौ', 'नाइन', 'nine', 'nau'],
}
_WORD_TO_DIGIT = {w.lower(): d for d, words in _DIGIT_WORDS.items() for w in words}
_REPEAT = {'डबल': 2, 'double': 2, 'ट्रिपल': 3, 'triple': 3}
_TOKEN = re.compile(r'[A-Za-z]+|[ऀ-ॿ]+|\d+')


_NOUN = {'patient_ref': 'रेफरेंस नंबर', 'village': 'गाँव', 'contact': 'संपर्क नंबर', 'referral_reason': 'रेफरल कारण'}


def spoken_value(field, value):
    if field == 'contact' and value.isdigit() and len(value) == 10:
        return ' '.join(value[:5]) + ', ' + ' '.join(value[5:])
    if field in ('contact', 'patient_ref') and value.isdigit():
        return ' '.join(value)
    return value


def conflict_question(field, candidates, kind):
    a, b = (spoken_value(field, v) for v in candidates[:2])
    if kind == 'correction':
        return f'आपने पहले {_NOUN[field]} {a} बताया था, अब {b} कहा। सही कौन सा है, पहला या दूसरा?'
    return f'{_NOUN[field]} के लिए दो अलग जवाब मिले: पहला {a}, दूसरा {b}। सही कौन सा है?'


CONFIRM_QUESTION = 'क्या सभी विवरण सही हैं? पुष्टि के लिए कहिए: हाँ, सब सही है। कुछ गलत हो तो कहिए: नहीं।'
_CONF_NO = {'नहीं', 'नही', 'nahi', 'nahin', 'no', 'गलत', 'ग़लत', 'galat', 'wrong', 'मत', 'mat', 'रुकिए', 'ruko', 'cancel', 'रुको'}
_CONF_AFFIRM = {'हाँ', 'हां', 'जी', 'haan', 'han', 'haa', 'ha', 'yes', 'ji', 'सब', 'sab', 'बिल्कुल', 'bilkul'}
_CONF_CORRECT = {'सही', 'ठीक', 'sahi', 'theek', 'thik', 'correct', 'right'}
_CONF_EXPLICIT = {'confirm', 'confirmed', 'कन्फर्म', 'पुष्टि'}


def parse_confirmation(text):
    """'yes' only for an unambiguous approval ("हाँ, सब सही है", "जी सही है", "confirm").
    'no' if ANY negative word appears (conservative). '' for anything else, including a bare "हाँ"."""
    words = {w.lower() for w in re.findall(r'[A-Za-z]+|[ऀ-ॿ]+', normalize_digits(text or ''))}
    if words & _CONF_NO:
        return 'no'
    if words & _CONF_EXPLICIT or (words & _CONF_CORRECT and words & _CONF_AFFIRM):
        return 'yes'
    return ''


def next_field(fields, conflicts=None):
    if conflicts:
        return next(k for k in REQUIRED if k in conflicts)
    errors = validate(fields)
    return next((k for k in REQUIRED if k in errors), None)


def question_for(fields, conflicts=None, conflict_kinds=None):
    """Conflicts are asked first (a wrong value is worse than a blank one), then missing/invalid fields."""
    conflicts = conflicts or {}
    errors = validate(fields)
    remaining = [k for k in REQUIRED if k in conflicts or k in errors]
    field = next_field(fields, conflicts)
    if field is None:
        return None
    if field in conflicts:
        kind = (conflict_kinds or {}).get(field, 'transcript')
        return {'field': field, 'label': LABELS[field], 'kind': 'conflict', 'candidates': conflicts[field],
                'question': conflict_question(field, conflicts[field], kind),
                'reason': 'Two different values were heard; the worker must choose', 'remaining': remaining}
    return {'field': field, 'label': LABELS[field], 'kind': 'missing', 'candidates': [],
            'question': QUESTIONS[field], 'reason': errors[field], 'remaining': remaining}


# Not 'पहले/pehle' ("earlier") — "pehle Ramgarh bola, ab Rampur" must not pick the first one.
_FIRST = {'पहला', 'पहली', 'पुराना', 'पुराने', 'first', 'pehla', 'pahla', 'old', 'purana'}
_SECOND = {'दूसरा', 'दूसरे', 'दूसरी', 'नया', 'नए', 'second', 'doosra', 'dusra', 'dusre', 'new', 'naya', 'latest'}


def resolve_choice(field, text, candidates):
    """Pick a candidate by ordinal ('पहला'/'second') or by naming it; else accept a fresh valid value."""
    norm = normalize_digits(text or '')
    words = {w.lower() for w in re.findall(r'[A-Za-z]+|[ऀ-ॿ]+', norm)}
    # Prisma's number normalisation (ITN) turns "पहला"/"दूसरा" into "१st"/"2nd" — seen in live testing.
    compact = re.sub(r'\s+', '', norm.lower())
    first = bool(words & _FIRST) or bool(re.search(r'(?<!\d)1(?:st|ला|ली|ले)(?![0-9])', compact))
    second = bool(words & _SECOND) or bool(re.search(r'(?<!\d)2(?:nd|रा|री|रे)(?![0-9])', compact))
    if first != second and len(candidates) >= 2:
        return candidates[0] if first else candidates[1]
    value = parse_answer(field, text)
    if not value:
        return ''
    for c in candidates:
        if value.lower() == c.lower():
            return c
    # A fresh value may settle a conflict only if it is itself complete and valid
    # (a stray "1" must not replace two full phone numbers).
    probe = {k: 'x' for k in REQUIRED}
    probe[field] = value
    return value if field not in validate(probe) else ''


def spoken_digits(text):
    """Turn '9 8 सात छह double five ...' into '9876 55...' digits only.

    Words that are not digits are ignored; repeat markers apply to the next digit.
    """
    tokens = _TOKEN.findall(normalize_digits(text))
    is_digit = lambda t: t.isdigit() or t.lower() in _WORD_TO_DIGIT
    out, repeat = [], 1
    for i, tok in enumerate(tokens):
        low = tok.lower()
        if low in _REPEAT:
            repeat = _REPEAT[low]
            continue
        if tok.isdigit():
            out.append(tok[0] * repeat + tok[1:])
        elif low in _WORD_TO_DIGIT:
            out.append(_WORD_TO_DIGIT[low] * repeat)
        elif low == 'do' and 0 < i < len(tokens) - 1 and is_digit(tokens[i - 1]) and is_digit(tokens[i + 1]):
            # Romanised 'do' is 'two' only when sandwiched between digits ('teen do ek'),
            # never as a trailing verb ('number ... do' = 'give').
            out.append('2' * repeat)
        else:
            continue
        repeat = 1
    return ''.join(out)


_REF_NOISE = re.compile(r'^(?:patient|मरीज़?|पेशेंट|रोगी|का|की|के|reference|ref|रेफरेंस|रिफरेंस|संदर्भ|'
                        r'id|आईडी|number|no|नंबर|नम्बर|is|hai|है|मेरा|mera)$', re.I)
_VILLAGE_LEAD = re.compile(r'^\s*(?:(?:मेरे|मेरा|हमारे|हमारा|उनका|उसका|mera|hamara)\s+)?'
                           r'(?:गाँव|गांव|गाव|village|gaon)\s*(?:का\s+नाम|ka\s+naam|name|is|:|-)?\s*', re.I)
_REASON_LEAD = re.compile(r'^\s*(?:(?:रेफरल|referral)\s+)?(?:का\s+)?(?:कारण|वजह|reason)\s*(?:है|hai|is|:|-)?\s*', re.I)
_TRAIL = re.compile(r'[\s,.;:।!?-]+$')
_UNKNOWN = re.compile(r'पता\s+नहीं|नहीं\s+पता|मालूम\s+नहीं|नहीं\s+मालूम|\bpata\s+nahi?n?\b|\bnahi?n?\s+pata\b|'
                      r'\bmaloom\s+nahi?n?\b|don\'?t\s+know|not\s+sure|\bunknown\b', re.I)
# Acknowledgements, fillers, ordinals and meta-talk. An answer made ONLY of these is
# not a village / reference / reason ("हाँ", "ok", "theek hai", "kya?", "दोबारा बोलिए").
_NON_ANSWER = {
    'हाँ', 'हां', 'हा', 'जी', 'haan', 'han', 'haa', 'ha', 'ji', 'ok', 'okay', 'ओके', 'ठीक', 'theek', 'thik', 'है', 'hai',
    'yes', 'no', 'नहीं', 'नही', 'nahi', 'nahin', 'क्या', 'kya', 'hello', 'हेलो', 'हैलो', 'hi', 'उम्म', 'umm', 'um',
    'hmm', 'हम्म', 'अं', 'नमस्ते', 'namaste', 'सही', 'sahi', 'पहला', 'दूसरा', 'pehla', 'pahla', 'doosra', 'dusra',
    'first', 'second', 'दोनों', 'dono', 'both', 'दोबारा', 'dobara', 'बोलिए', 'boliye', 'bolo', 'repeat', 'again',
    'फिर', 'phir', 'से', 'se', 'sorry', 'सॉरी', 'sir', 'सर', 'madam', 'मैडम', 'accha', 'acha', 'अच्छा', 'wait',
    'रुकिए', 'ruko', 'मिनट', 'minute', 'वाला', 'वाली', 'wala', 'wali', 'जो', 'jo', 'बताया', 'bataya', 'था', 'tha',
}


def _only_filler(text):
    words = re.findall(r'[A-Za-z]+|[ऀ-ॿ]+|\d+', text)
    return not [w for w in words if w.lower() not in _NON_ANSWER]


_NEGATION = re.compile(r'\s*(?:नहीं|नही|\bnahi?n?\b|\bnot\b)\s*[,;:।-]?\s*', re.I)


def parse_answer(field, text):
    """Return a cleaned value for `field`, or '' if the answer cannot be used."""
    if field not in REQUIRED or not isinstance(text, str):
        return ''
    text = normalize_digits(text).strip()
    if _UNKNOWN.search(text) or (field != 'contact' and _only_filler(text)):
        return ''
    # "रामगढ़ नहीं, रामपुर" / "Ramgarh nahi, Rampur" -> keep only what follows the negation.
    # Never for the referral reason: there "नहीं" is clinical meaning ("साँस नहीं आ रही").
    parts = _NEGATION.split(text) if field != 'referral_reason' else [text]
    if len(parts) > 1 and parts[0].strip(' ,.;:।-') and parts[-1].strip(' ,.;:।-'):
        text = parts[-1].strip(' ,.;:।-')
    # Drop leading acknowledgements: "जी, सोनपुर" -> "सोनपुर", "haan, 1024" -> "1024".
    while True:
        m = re.match(r'\s*([A-Za-z]+|[ऀ-ॿ]+)[\s,.;:।!?-]+', text)
        if not m or m.group(1).lower() not in _NON_ANSWER:
            break
        text = text[m.end():]
    if field == 'contact':
        digits = spoken_digits(text)
        return digits if 1 <= len(digits) <= 15 else ''
    if field == 'patient_ref':
        tokens = [t for t in re.findall(r'[A-Za-z0-9ऀ-ॿ_-]+', text) if not _REF_NOISE.match(t)]
        spoken = spoken_digits(' '.join(tokens))
        ascii_tokens = [t for t in tokens if re.fullmatch(r'[A-Za-z0-9_-]+', t) and t.lower() not in _WORD_TO_DIGIT]
        value = '-'.join(ascii_tokens) if ascii_tokens else spoken
        return value if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,29}', value or '') else ''
    if field == 'village':
        value = _VILLAGE_LEAD.sub('', text)
        value = _TRAIL.sub('', value)
        value = _clean_village(value)
        value = re.sub(r'\s+(?:गाँव|गांव|गाव|gaon|village)$', '', value, flags=re.I).strip()
        if not re.fullmatch(r'[A-Za-zऀ-ॿ]+(?:[ -][A-Za-zऀ-ॿ]+){0,3}', value):
            return ''
        return value[:100]
    value = _TRAIL.sub('', _REASON_LEAD.sub('', text))
    return value[:200] if len(value) >= 3 else ''
