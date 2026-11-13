"""Make noisy and telephone-quality copies of CLEAN synthetic WAV recordings (stdlib only).

For each input  clip.wav  this writes into OUT_DIR:
  clip__clean.wav    16 kHz mono copy
  clip__noisy10.wav  white noise mixed at 10 dB SNR
  clip__noisy5.wav   white noise mixed at 5 dB SNR
  clip__phone.wav    8 kHz, 300-3400 Hz-ish band, mu-law quantised (narrowband call)

Usage:  py benchmarks\\make_variants.py C:\\private\\clean_wavs C:\\private\\variants
Input must be 16-bit PCM WAV (mono or stereo, any rate; the app's browser recorder makes 16 kHz mono).
Use synthetic, consented demo speech only. Do not commit audio to the repository.
"""
import math
import random
import sys
import wave
from array import array
from pathlib import Path


def read_wav(path):
    with wave.open(str(path), 'rb') as w:
        if w.getsampwidth() != 2:
            raise ValueError(f'{path.name}: need 16-bit PCM WAV')
        ch, rate, n = w.getnchannels(), w.getframerate(), w.getnframes()
        data = array('h', w.readframes(n))
    if sys.byteorder == 'big':
        data.byteswap()
    samples = [x / 32768.0 for x in data]
    if ch > 1:
        samples = [sum(samples[i:i + ch]) / ch for i in range(0, len(samples), ch)]
    return samples, rate


def write_wav(path, samples, rate):
    data = array('h', (max(-32768, min(32767, int(round(s * 32767)))) for s in samples))
    if sys.byteorder == 'big':
        data.byteswap()
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(data.tobytes())


def resample(samples, src, dst):
    if src == dst or not samples:
        return list(samples)
    n = max(1, int(len(samples) * dst / src))
    step = src / dst
    out = []
    for i in range(n):
        x = i * step
        j = int(x); f = x - j
        a = samples[j]; b = samples[min(j + 1, len(samples) - 1)]
        out.append(a + (b - a) * f)
    return out


def lowpass(samples, rate, cutoff):
    # One-pole low-pass applied twice (gentle, adequate for a narrowband simulation).
    a = math.exp(-2 * math.pi * cutoff / rate)
    for _ in range(2):
        y = 0.0; out = []
        for s in samples:
            y = (1 - a) * s + a * y; out.append(y)
        samples = out
    return samples


def highpass(samples, rate, cutoff):
    low = lowpass(samples, rate, cutoff)
    return [s - l for s, l in zip(samples, low)]


def add_noise(samples, snr_db, seed):
    rng = random.Random(seed)
    power = sum(s * s for s in samples) / max(1, len(samples))
    sigma = math.sqrt(power / (10 ** (snr_db / 10))) if power > 0 else 0.0
    return [s + rng.gauss(0, sigma) for s in samples]


def mulaw_roundtrip(samples, mu=255):
    out = []
    for s in samples:
        s = max(-1.0, min(1.0, s))
        y = math.copysign(math.log1p(mu * abs(s)) / math.log1p(mu), s)
        y = round(y * 127) / 127  # 8-bit companded code
        out.append(math.copysign(((1 + mu) ** abs(y) - 1) / mu, y))
    return out


def variants(samples, rate, seed=7):
    clean = resample(samples, rate, 16000)
    phone = resample(lowpass(clean, 16000, 3400), 16000, 8000)
    phone = mulaw_roundtrip(highpass(phone, 8000, 300))
    return {'clean': (clean, 16000), 'noisy10': (add_noise(clean, 10, seed), 16000),
            'noisy5': (add_noise(clean, 5, seed + 1), 16000), 'phone': (phone, 8000)}


def main(argv):
    if len(argv) != 3:
        print(__doc__); return 2
    src, dst = Path(argv[1]), Path(argv[2])
    dst.mkdir(parents=True, exist_ok=True)
    clips = sorted(src.glob('*.wav'))
    if not clips:
        print('No .wav files found'); return 1
    for i, clip in enumerate(clips):
        samples, rate = read_wav(clip)
        for name, (data, r) in variants(samples, rate, seed=i * 10).items():
            write_wav(dst / f'{clip.stem}__{name}.wav', data, r)
        print(f'{clip.name}: 4 variants written')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
