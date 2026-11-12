"""Offline reproducible benchmark. Synthetic prewritten transcripts, NOT live Gnani audio.

Run: py benchmarks\\run_benchmark.py
Stores only aggregate metrics and fixture IDs in the report (no real patients).
"""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.extraction import parse_transcript, FIELDS
from app.core import validate

FIXTURES=Path(__file__).with_name('synthetic_cases.json')
REPORT_DIR=ROOT/'benchmarks'/'results'

def evaluate():
    rows=json.loads(FIXTURES.read_text(encoding='utf-8'))
    if not rows: raise RuntimeError('No benchmark fixtures')
    observed=[];counts=defaultdict(int);groups=defaultdict(lambda: {'total':0,'exact':0})
    for row in rows:
        start=time.perf_counter_ns()
        actual=parse_transcript(row['transcript'])
        elapsed=(time.perf_counter_ns()-start)/1e6
        expected=row['expected']
        assert set(expected)==set(FIELDS),row['id']
        assert set(actual)==set(FIELDS),row['id']
        match=all(actual[k]==expected[k] for k in FIELDS)
        groups[row['group']]['total']+=1
        groups[row['group']]['exact']+=int(match)
        for key in FIELDS:
            want=expected[key];got=actual[key]
            counts['field_total']+=1
            if got==want: counts['field_exact']+=1
            if want:
                counts['expected_populated']+=1
                if got==want: counts['correct_populated']+=1
                elif not got: counts['abstentions_on_expected']+=1
                else: counts['wrong_nonempty_on_expected']+=1
            elif got:
                counts['false_populated']+=1
            else:counts['correct_empty']+=1
        observed.append({'id':row['id'],'group':row['group'],'exact':match,'field_matches':{k:actual[k]==expected[k] for k in FIELDS},'latency_ms':round(elapsed,3)})
    ms=sorted(row['latency_ms'] for row in observed)
    metrics={
        'evaluation_type':'offline synthetic transcript-to-fields only',
        'audio_stt_evaluated':False,
        'gnani_prisma_wer':None,
        'gnani_prisma_cer':None,
        'gnani_timbre_mos':None,
        'live_hospital_outcomes':None,
        'fixtures':len(rows),'field_slots':counts['field_total'],
        'case_exact_match_count':sum(x['exact'] for x in observed),
        'case_exact_match_pct':round(100*sum(x['exact'] for x in observed)/len(rows),2),
        'field_exact_match_count':counts['field_exact'],
        'field_exact_match_pct':round(100*counts['field_exact']/counts['field_total'],2),
        'expected_nonempty_fields':counts['expected_populated'],
        'correct_nonempty_fields':counts['correct_populated'],
        'abstentions_on_expected_fields':counts['abstentions_on_expected'],
        'wrong_nonempty_on_expected_fields':counts['wrong_nonempty_on_expected'],
        'false_populated_fields':counts['false_populated'],
        'median_local_parser_ms':ms[len(ms)//2],
        'p95_local_parser_ms':ms[max(0,(len(ms)*95+99)//100-1)],
        'by_group':dict(groups),
        'cases':observed,
    }
    return metrics

def write(metrics):
    REPORT_DIR.mkdir(parents=True,exist_ok=True)
    (REPORT_DIR/'stage9_metrics.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    md=f'''# Stage 9: synthetic extraction benchmark

Scope: **offline deterministic parser**, not live Gnani STT/TTS, not medical or field accuracy.

| Metric | Observed |
|---|---:|
| Synthetic transcripts | {metrics['fixtures']} |
| Exact complete cases | {metrics['case_exact_match_count']}/{metrics['fixtures']} ({metrics['case_exact_match_pct']}%) |
| Exact field matches | {metrics['field_exact_match_count']}/{metrics['field_slots']} ({metrics['field_exact_match_pct']}%) |
| Non-empty expected fields correctly extracted | {metrics['correct_nonempty_fields']}/{metrics['expected_nonempty_fields']} |
| Fields unexpectedly populated when expected empty | {metrics['false_populated_fields']} |
| Abstentions where value expected | {metrics['abstentions_on_expected_fields']} |
| Wrong non-empty where value expected | {metrics['wrong_nonempty_on_expected_fields']} |
| Median local extraction time (machine-specific) | {metrics['median_local_parser_ms']:.3f} ms |
| p95 local extraction time (machine-specific) | {metrics['p95_local_parser_ms']:.3f} ms |

## Group breakdown

| Group | Exact cases |
|---|---:|
'''
    for group,data in metrics['by_group'].items():md+=f"| {group} | {data['exact']}/{data['total']} |\n"
    md+='''
## Important limitations

- Fixtures are hand-authored synthetic utterances used for development; results are **in-sample**, not a blinded generalisation estimate.
- No real patient data and no real hospital messaging are involved.
- Prisma WER/CER, actual Hindi audio quality, noise robustness and clinical interpretation are **not measured**. A real recorded reference set would be needed.
- Parser latency is per-string on the computer running this script, not end-to-end roundtrip latency.
- Separate automated API tests cover stale versions, submission idempotency, and synthetic backend handoff behaviour.
- A zero failure count in these fixtures does **not** establish production safety.
'''
    (REPORT_DIR/'stage9_report.md').write_text(md,encoding='utf-8')

if __name__=='__main__':
    v=evaluate();write(v)
    print(f"Synthetic exact cases: {v['case_exact_match_count']}/{v['fixtures']}; field matches: {v['field_exact_match_count']}/{v['field_slots']}; unexpected population: {v['false_populated_fields']}")
    print('Report: benchmarks/results/stage9_report.md')
