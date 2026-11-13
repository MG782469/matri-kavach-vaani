"""Natural-speech extraction: marker-only vs marker + natural fallback (offline, synthetic).

Main number: **questions per draft**, i.e. how many fields the voice assistant still has to ask
for after the first utterance. Fewer questions with ZERO wrong values is the goal. A wrong
value is worse than a question, because the worker might not catch it.

Run: py benchmarks\\run_natural_eval.py   -> benchmarks/results/natural_eval_report.md
Fixtures: benchmarks/natural_cases.json (hand-written, fictional, NOT independent validation).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.extraction import parse_transcript, find_conflicts, FIELDS  # noqa: E402
from app.core import validate  # noqa: E402
from run_audio_eval import field_result  # noqa: E402

CASES = Path(__file__).with_name('natural_cases.json')


def evaluate(natural):
    rows = json.loads(CASES.read_text(encoding='utf-8'))
    exact = wrong = abstain = questions = 0
    per_case = []
    for row in rows:
        got = parse_transcript(row['transcript'], natural=natural)
        conflicts = find_conflicts(row['transcript']) if natural else {}
        res = {k: field_result(row['expected'][k], got[k]) for k in FIELDS}
        exact += sum(v == 'exact' for v in res.values())
        wrong += sum(v == 'wrong' for v in res.values())
        abstain += sum(v == 'abstain' for v in res.values())
        q = len(set(validate(got)) | set(conflicts))   # fields the assistant must still ask about
        questions += q
        per_case.append({'id': row['id'], 'questions': q, 'wrong': [k for k, v in res.items() if v == 'wrong']})
    n = len(rows)
    return {'cases': n, 'fields': n * len(FIELDS), 'exact_fields': exact, 'wrong_values': wrong,
            'abstentions': abstain, 'questions_per_draft': round(questions / n, 2), 'per_case': per_case}


def write_report(before, after):
    path = ROOT / 'benchmarks' / 'results' / 'natural_eval_report.md'
    lines = ['# Natural-speech extraction (offline, synthetic)', '',
             f'{after["cases"]} hand-written fictional transcripts (natural Hindi, Prisma-style, Hinglish, a conflict, '
             'negatives, marker regressions). Not independent validation; in-sample fixtures.', '',
             '| Extraction | Exact fields | **Wrong values** | Left for the assistant | **Questions per draft** |',
             '|---|---|---|---|---|',
             f"| Marker patterns only | {before['exact_fields']}/{before['fields']} | **{before['wrong_values']}** | {before['abstentions']} | **{before['questions_per_draft']}** |",
             f"| + natural-speech fallback | {after['exact_fields']}/{after['fields']} | **{after['wrong_values']}** | {after['abstentions']} | **{after['questions_per_draft']}** |",
             '', '"Questions per draft" counts the fields the voice assistant still has to ask about after the first '
             'utterance (missing, invalid or conflicting). A wrong value is the failure that matters, because the '
             'assistant would not ask about it, so the read-back and worker confirmation are the last line of defence.']
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return path


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    before, after = evaluate(False), evaluate(True)
    for name, r in (('marker-only', before), ('with natural', after)):
        print(f"{name:<13} exact {r['exact_fields']}/{r['fields']}  wrong {r['wrong_values']}  "
              f"abstain {r['abstentions']}  questions/draft {r['questions_per_draft']}")
    print('wrong-value cases:', [c for c in after['per_case'] if c['wrong']])
    print('Report:', write_report(before, after).relative_to(ROOT))
    raise SystemExit(1 if after['wrong_values'] else 0)
