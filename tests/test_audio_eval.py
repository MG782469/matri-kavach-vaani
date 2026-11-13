"""Offline checks for the audio-variant generator and critical-field evaluator (no network, no real audio)."""
import math, sys, tempfile, unittest, wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
import make_variants
import run_audio_eval

EXP = {'patient_ref': 'A1', 'village': 'Rampur', 'contact': '9876543210', 'referral_reason': 'transport coordination'}
REF = 'Patient ID: A1, village: Rampur, contact: 9876543210, reason: transport coordination'


class VariantTests(unittest.TestCase):
    def test_four_variants_with_expected_rates(self):
        tone = [0.4 * math.sin(2 * math.pi * 440 * i / 48000) for i in range(48000)]
        out = make_variants.variants(tone, 48000)
        self.assertEqual(set(out), {'clean', 'noisy10', 'noisy5', 'phone'})
        self.assertEqual(out['clean'][1], 16000); self.assertEqual(len(out['clean'][0]), 16000)
        self.assertEqual(out['phone'][1], 8000); self.assertEqual(len(out['phone'][0]), 8000)
        # 5 dB SNR adds more noise energy than 10 dB SNR.
        def err(x): return sum((a - b) ** 2 for a, b in zip(x, out['clean'][0]))
        self.assertGreater(err(out['noisy5'][0]), err(out['noisy10'][0]))

    def test_wav_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'a.wav'
            make_variants.write_wav(p, [0.0, 0.5, -0.5] * 100, 16000)
            samples, rate = make_variants.read_wav(p)
            self.assertEqual(rate, 16000); self.assertEqual(len(samples), 300)
            with wave.open(str(p)) as w: self.assertEqual(w.getnchannels(), 1)
            rc = make_variants.main(['x', d, str(Path(d) / 'out')])
            self.assertEqual(rc, 0)
            self.assertEqual(len(list((Path(d) / 'out').glob('*.wav'))), 4)


class EvalTests(unittest.TestCase):
    def test_metrics_separate_wrong_from_abstain(self):
        rows = [
            {'id': '1', 'condition': 'clean', 'reference': REF, 'hypothesis': REF, 'expected': EXP},
            # wrong digit in the phone number -> dangerous "wrong" + false-ready
            {'id': '2', 'condition': 'noisy', 'reference': REF, 'expected': EXP,
             'hypothesis': 'Patient ID: A1, village: Rampur, contact: 9876543218, reason: transport coordination'},
            # village lost -> safe abstention, not false-ready
            {'id': '3', 'condition': 'noisy', 'reference': REF, 'expected': EXP,
             'hypothesis': 'Patient ID: A1, contact: 9876543210, reason: transport coordination'},
        ]
        r = run_audio_eval.evaluate(rows, lambda row: row['hypothesis'])
        self.assertEqual(r['clean']['all_fields_exact'], 1.0)
        self.assertEqual(r['clean']['wer'], 0.0)
        n = r['noisy']
        self.assertEqual(n['clips'], 2)
        self.assertEqual(n['contact_exact'], 0.5)
        self.assertEqual(n['village_exact'], 0.5)
        self.assertEqual(n['wrong_value_rate'], 0.125)
        self.assertEqual(n['abstention_rate'], 0.125)
        self.assertEqual(n['false_ready_rate'], 0.5)
        self.assertGreater(n['wer'], 0)


class TtsBenchmarkPipelineTests(unittest.TestCase):
    def test_end_to_end_offline_with_fake_gnani(self):
        import run_tts_benchmark as tb
        calls = {'tts': 0, 'stt': 0}

        def fake_tts(text, voice, lang):
            calls['tts'] += 1
            with tempfile.TemporaryDirectory() as d:
                p = Path(d) / 't.wav'
                make_variants.write_wav(p, [0.3 * math.sin(i / 5) for i in range(8000)], 16000)
                return p.read_bytes()

        def perfect_stt(row):
            calls['stt'] += 1
            return row['reference']

        with tempfile.TemporaryDirectory() as d:
            out = Path(d)
            rows = tb.build_audio(out, tb.SCRIPTS, fake_tts)
            self.assertEqual(len(rows), len(tb.SCRIPTS) * 4)
            self.assertTrue((out / 'manifest.json').exists())
            tr = tb.cached_transcriber(out, perfect_stt)
            r = run_audio_eval.evaluate(rows, tr)
            for cond in tb.CONDITIONS:
                self.assertEqual(r[cond]['all_fields_exact'], 1.0, cond)
                self.assertEqual(r[cond]['false_ready_rate'], 0.0)
                self.assertEqual(r[cond]['conflicts_flagged'], 1)      # the two-numbers script
            # Second run is free: audio and transcripts come from the cache.
            tb.build_audio(out, tb.SCRIPTS, fake_tts)
            run_audio_eval.evaluate(rows, tb.cached_transcriber(out, perfect_stt))
            self.assertEqual(calls['tts'], len(tb.SCRIPTS))
            self.assertEqual(calls['stt'], len(rows))

    def test_refuses_output_inside_repo(self):
        import run_tts_benchmark as tb
        self.assertEqual(tb.main(['x', str(Path(tb.ROOT) / 'tmp_audio'), '--dry-run']), 2)

    def test_expected_alternatives_and_presence(self):
        self.assertEqual(run_audio_eval.field_result(['Rampur', 'रामपुर'], 'रामपुर'), 'exact')
        self.assertEqual(run_audio_eval.field_result('*', 'anything'), 'exact')
        self.assertEqual(run_audio_eval.field_result('*', ''), 'abstain')
        self.assertEqual(run_audio_eval.field_result('9876543210', '९८७६५४३२१०'), 'exact')


if __name__ == '__main__':
    unittest.main()
