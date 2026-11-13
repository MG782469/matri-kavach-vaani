"""The false-ready safety evaluation must stay at zero (offline, synthetic, mock mode)."""
import os, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))


class SafetyEvalTests(unittest.TestCase):
    def test_zero_false_ready_bypasses_and_non_answers(self):
        saved = {k: os.environ.get(k) for k in ('CASE_DB_PATH', 'GNANI_MODE')}
        try:
            import run_safety_eval
            r = run_safety_eval.run()
        finally:
            for k, v in saved.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v
        self.assertEqual(r['false_ready'], 0, r['false_ready_ids'])
        self.assertEqual(r['bypasses_succeeded'], [])
        self.assertEqual(r['non_answers_wrongly_accepted'], [])
        self.assertGreater(r['submitted_untouched'], 0)   # the legitimate path still works
        self.assertGreater(r['held_for_worker_review'], 0)


if __name__ == '__main__':
    unittest.main()
