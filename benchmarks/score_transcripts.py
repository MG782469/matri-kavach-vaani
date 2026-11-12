"""Optional: score manually reviewed synthetic audio reference transcripts vs Prisma output.

Create a LOCAL JSON outside this repository: [{"id":"audio1","reference":"...","hypothesis":"..."}]
Only synthetic, consented demo audio. Never save patient transcriptions in GitHub or shared reports.
Usage: py benchmarks\\score_transcripts.py C:\\private\\audio_eval.json
The script prints only aggregate WER/CER and does not create a transcript file.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

def normalized(s):
    if not isinstance(s,str):raise ValueError('Each reference and hypothesis must be a string')
    s=unicodedata.normalize('NFKC',s).casefold()
    return re.sub(r'\s+',' ',s.strip())

def edit_distance(a,b):
    # Levenshtein distance with O(min(n,m)) additional space.
    if len(a)<len(b):a,b=b,a
    prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        row=[i]
        for j,y in enumerate(b,1):
            row.append(min(prev[j]+1,row[j-1]+1,prev[j-1]+(x!=y)))
        prev=row
    return prev[-1]

def score(rows):
    if not isinstance(rows,list) or not rows: raise ValueError('Nonempty list of reference/hypothesis pairs required')
    edits_word=total_word=edits_char=total_char=0
    for r in rows:
        ref=normalized(r['reference']);hyp=normalized(r['hypothesis'])
        if not ref: raise ValueError('Reference text cannot be blank')
        wr=ref.split();wh=hyp.split()
        edits_word+=edit_distance(wr,wh);total_word+=len(wr)
        edits_char+=edit_distance(ref,hyp);total_char+=len(ref)
    return {'clips':len(rows),'wer':edits_word/total_word,'cer':edits_char/total_char,
            'word_edits':edits_word,'reference_words':total_word,'char_edits':edits_char,'reference_chars':total_char,
            'normalization':'Unicode NFKC, casefold, whitespace collapse; punctuation retained'}

if __name__=='__main__':
    if len(sys.argv)!=2:
        print('Usage: py benchmarks\\score_transcripts.py PATH_TO_LOCAL_SYNTHETIC_PAIRS.json')
        raise SystemExit(2)
    path=Path(sys.argv[1]).resolve()
    if not path.is_file(): raise SystemExit('File not found')
    result=score(json.loads(path.read_text(encoding='utf-8')))
    print(json.dumps(result,indent=2))
