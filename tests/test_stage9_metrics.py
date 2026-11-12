"""Benchmark metric implementations and data contracts; synthetic-only."""
import unittest
from pathlib import Path
from benchmarks.run_benchmark import evaluate
from benchmarks.score_transcripts import score,edit_distance

class BenchmarkMetricsTests(unittest.TestCase):
    def test_fixture_ids_unique_and_groups_present(self):
        import json
        rows=json.loads((Path(__file__).resolve().parents[1]/'benchmarks/synthetic_cases.json').read_text(encoding='utf8'))
        self.assertEqual(len({r['id'] for r in rows}),len(rows))
        self.assertTrue({'hindi','hinglish','english','negative','partial'}.issubset({r['group'] for r in rows}))
    def test_benchmark_never_claims_live_stt_accuracy(self):
        m=evaluate()
        self.assertFalse(m['audio_stt_evaluated'])
        self.assertIsNone(m['gnani_prisma_wer'])
        self.assertIsNone(m['gnani_timbre_mos'])
    def test_exact_fixture_field_accounting(self):
        m=evaluate()
        self.assertEqual(m['fixtures'],16)
        self.assertEqual(m['field_slots'],64)
        self.assertEqual(m['field_exact_match_count']+sum(not x for row in m['cases'] for x in row['field_matches'].values()),64)
    def test_wer_cer_exact(self):
        m=score([{'reference':'namaste aap kaisi hain','hypothesis':'namaste aap hain'}])
        self.assertEqual(m['word_edits'],1)
        self.assertEqual(m['reference_words'],4)
        self.assertAlmostEqual(m['wer'],.25)
    def test_empty_reference_rejected(self):
        with self.assertRaises(ValueError):score([{'reference':'','hypothesis':'abc'}])
    def test_levenshtein_basic(self):
        self.assertEqual(edit_distance('kitten','sitting'),3)
        self.assertEqual(edit_distance([],[]),0)

if __name__=='__main__':unittest.main()
