"""Natural-speech fallback must reduce questions without introducing wrong values."""
import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
import run_natural_eval
from app.extraction import parse_transcript


class NaturalEvalTests(unittest.TestCase):
    def test_zero_wrong_values_and_fewer_questions(self):
        before, after = run_natural_eval.evaluate(False), run_natural_eval.evaluate(True)
        self.assertEqual(after['wrong_values'], 0, [c for c in after['per_case'] if c['wrong']])
        self.assertLess(after['questions_per_draft'], before['questions_per_draft'])
        self.assertGreater(after['exact_fields'], before['exact_fields'])

    def test_marker_matches_take_priority_over_natural(self):
        # "village: Rampur" (marker) wins; the natural "Sonpur ki mareez" is never consulted.
        x = parse_transcript('village: Rampur, Sonpur ki mareez')
        self.assertEqual(x['village'], 'Rampur')

    def test_natural_negatives_stay_blank(self):
        self.assertEqual(parse_transcript('इस गाँव की मरीज़ है, जल्दी आइए')['village'], '')
        self.assertEqual(parse_transcript('9876543210 पर कॉल बैक कीजिए')['contact'], '')
        self.assertEqual(parse_transcript('नंबर 98765 है')['contact'], '')


if __name__ == '__main__':
    unittest.main()
