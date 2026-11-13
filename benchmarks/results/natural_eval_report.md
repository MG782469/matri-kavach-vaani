# Natural-speech extraction (offline, synthetic)

14 hand-written fictional transcripts (natural Hindi, Prisma-style, Hinglish, a conflict, negatives, marker regressions). Not independent validation; in-sample fixtures.

| Extraction | Exact fields | **Wrong values** | Left for the assistant | **Questions per draft** |
|---|---|---|---|---|
| Marker patterns only | 30/56 | **0** | 26 | **3.43** |
| + natural-speech fallback | 56/56 | **0** | 0 | **1.57** |

"Questions per draft" counts the fields the voice assistant still has to ask about after the first utterance (missing, invalid or conflicting). A wrong value is the failure that matters, because the assistant would not ask about it, so the read-back and worker confirmation are the last line of defence.
