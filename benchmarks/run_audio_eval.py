"""Critical-field audio evaluation on SYNTHETIC recordings (clean vs noisy vs phone).

WER alone is not enough for referrals: one wrong digit in a phone number matters more
than ten small word errors. This script reports, per acoustic condition:
  - WER / CER against a reviewed reference transcript
  - phone-number exact match, village exact match, all-fields exact match
  - wrong-value rate   (a field filled with a WRONG value: the dangerous case)
  - abstention rate    (field left blank / flagged for the assistant to ask: the safe case)
  - false-ready rate   (draft looked complete but at least one field was wrong)

Manifest (keep it OUTSIDE the repo; synthetic data only), a JSON list of:
  {"id": "c01", "audio": "C:/private/variants/c01__noisy10.wav", "condition": "noisy10",
   "group": "hinglish", "reference": "<reviewed transcript>",
   "expected": {"patient_ref": "...", "village": "...", "contact": "...", "referral_reason": "..."}}

Live:     set GNANI_API_KEY, then  py benchmarks\\run_audio_eval.py C:\\private\\manifest.json
Offline:  add "hypothesis": "<saved Prisma transcript>" to each row and pass --offline
Output:   aggregate JSON on stdout + benchmarks/results/audio_eval_report.md (no transcripts).
"""
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app.extraction import parse_transcript, find_conflicts, normalize_digits, FIELDS  # noqa: E402
from score_transcripts import score  # noqa: E402

REPORT = ROOT / 'benchmarks' / 'results' / 'audio_eval_report.md'


def norm(v):
    return ' '.join(normalize_digits(str(v or '')).split()).casefold()


def field_result(want, have):
    """`want` may be a string, a list of acceptable spellings (Rampur / रामपुर), or "*" (any non-empty)."""
    have = norm(have)
    if want == '*':
        return 'exact' if have else 'abstain'
    options = [norm(w) for w in (want if isinstance(want, list) else [want])]
    if have in options:
        return 'exact'
    return 'abstain' if not have else 'wrong'


def transcribe_row(row, key):
    from app.prisma import transcribe
    audio = Path(row['audio']).read_bytes()
    return transcribe(audio, Path(row['audio']).name, 'audio/wav', key, max_chars=4000)


def evaluate(rows, transcriber):
    by_cond = defaultdict(list)
    for row in rows:
        hyp = transcriber(row)
        got = parse_transcript(hyp)
        conflicts = find_conflicts(hyp)
        exp = row['expected']
        fields = {k: field_result(exp.get(k, ''), got.get(k)) for k in FIELDS}
        by_cond[row.get('condition', 'unknown')].append({
            'id': row['id'], 'group': row.get('group', ''), 'reference': row['reference'], 'hypothesis': hyp,
            'fields': fields, 'conflicts': len(conflicts)})
    out = {}
    for cond, items in sorted(by_cond.items()):
        n = len(items)
        cells = [f for it in items for f in it['fields'].values()]
        # Digits normalised so "९८७६" vs "9876" is not counted as a recognition error.
        wer = score([{'reference': normalize_digits(it['reference']), 'hypothesis': normalize_digits(it['hypothesis'])}
                     for it in items])
        out[cond] = {
            'clips': n,
            'wer': round(wer['wer'], 4), 'cer': round(wer['cer'], 4),
            'contact_exact': round(sum(it['fields']['contact'] == 'exact' for it in items) / n, 4),
            'village_exact': round(sum(it['fields']['village'] == 'exact' for it in items) / n, 4),
            'all_fields_exact': round(sum(all(v == 'exact' for v in it['fields'].values()) for it in items) / n, 4),
            'wrong_value_rate': round(cells.count('wrong') / len(cells), 4),
            'abstention_rate': round(cells.count('abstain') / len(cells), 4),
            'false_ready_rate': round(sum(('abstain' not in it['fields'].values()) and ('wrong' in it['fields'].values())
                                          for it in items) / n, 4),
            'conflicts_flagged': sum(it['conflicts'] for it in items),
        }
    return out


def write_report(result, note=None, path=None):
    lines = ['# Audio evaluation (synthetic recordings)', '',
             'Aggregate only; no transcripts or field values are stored. Not a clinical validation.', '']
    if note:
        lines += [note, '']
    lines += [
             '| Condition | Clips | WER | CER | Phone exact | Village exact | All fields exact | Wrong-value rate | Abstention rate | False-ready |',
             '|---|---|---|---|---|---|---|---|---|---|']
    for cond, m in result.items():
        lines.append(f"| {cond} | {m['clips']} | {m['wer']:.1%} | {m['cer']:.1%} | {m['contact_exact']:.0%} | "
                     f"{m['village_exact']:.0%} | {m['all_fields_exact']:.0%} | {m['wrong_value_rate']:.1%} | "
                     f"{m['abstention_rate']:.1%} | {m['false_ready_rate']:.0%} |")
    lines += ['', 'Abstentions are the safe failure: the voice assistant asks for those fields. '
              'Wrong values are the dangerous failure: only read-back + worker confirmation catches them.']
    out = Path(path) if path else REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return out


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    offline = '--offline' in argv
    if len(args) != 1:
        print(__doc__); return 2
    rows = json.loads(Path(args[0]).read_text(encoding='utf-8'))
    if offline:
        transcriber = lambda r: r['hypothesis']
    else:
        key = os.getenv('GNANI_API_KEY')
        if not key:
            print('Set GNANI_API_KEY for live evaluation, or use --offline with saved hypotheses'); return 2
        transcriber = lambda r: transcribe_row(r, key)
    result = evaluate(rows, transcriber)
    write_report(result)
    print(json.dumps(result, indent=2))
    print(f'Report: {REPORT.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
