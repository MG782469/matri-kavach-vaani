/* Shared browser recorder: MediaRecorder -> decode -> 16 kHz mono 16-bit WAV.
   Gnani Prisma REST accepts WAV/MP3/OGG/FLAC/AAC/M4A (not webm), max 30 s. */
(function (global) {
  'use strict';
  function encodeWav(pcm, rate) {
    const ab = new ArrayBuffer(44 + pcm.length * 2), v = new DataView(ab);
    const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    w(0, 'RIFF'); v.setUint32(4, 36 + pcm.length * 2, true); w(8, 'WAVE'); w(12, 'fmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    w(36, 'data'); v.setUint32(40, pcm.length * 2, true);
    for (let i = 0; i < pcm.length; i++) { const s = Math.max(-1, Math.min(1, pcm[i])); v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true); }
    return new Blob([ab], { type: 'audio/wav' });
  }

  async function toWav16k(blob) {
    const AC = global.AudioContext || global.webkitAudioContext, ac = new AC();
    let decoded;
    try { decoded = await ac.decodeAudioData(await blob.arrayBuffer()); } finally { ac.close(); }
    const off = new OfflineAudioContext(1, Math.max(1, Math.ceil(decoded.duration * 16000)), 16000);
    const src = off.createBufferSource(); src.buffer = decoded; src.connect(off.destination); src.start();
    const out = await off.startRendering();
    return { wav: encodeWav(out.getChannelData(0), 16000), seconds: decoded.duration };
  }

  /* start({maxSeconds, onTick(sec), onLevel(0..1)}) -> controller {stop(), cancel()}
     controller.result is a Promise<{wav, seconds}> (rejects on cancel / error). */
  async function start(opts) {
    opts = opts || {};
    if (!navigator.mediaDevices || !global.MediaRecorder) throw new Error('This browser cannot record audio');
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    } catch (e) { throw new Error('Microphone permission denied or unavailable'); }
    const mr = new MediaRecorder(stream), chunks = [];
    let cancelled = false, seconds = 0, raf = 0, actx = null;
    const max = opts.maxSeconds || 25;
    // Live input level for the waveform animation.
    try {
      const AC = global.AudioContext || global.webkitAudioContext; actx = new AC();
      const an = actx.createAnalyser(); an.fftSize = 256; actx.createMediaStreamSource(stream).connect(an);
      const buf = new Uint8Array(an.frequencyBinCount);
      const loop = () => { an.getByteTimeDomainData(buf); let p = 0; for (const b of buf) p = Math.max(p, Math.abs(b - 128)); opts.onLevel && opts.onLevel(Math.min(1, p / 64)); raf = requestAnimationFrame(loop); };
      loop();
    } catch (e) { /* level meter is optional */ }
    const tick = setInterval(() => { seconds++; opts.onTick && opts.onTick(seconds); if (seconds >= max) stop(); }, 1000);
    const cleanup = () => { clearInterval(tick); cancelAnimationFrame(raf); stream.getTracks().forEach(t => t.stop()); if (actx) actx.close().catch(() => {}); };
    const result = new Promise((resolve, reject) => {
      mr.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      mr.onstop = async () => {
        cleanup();
        if (cancelled) return reject(new Error('cancelled'));
        try {
          const r = await toWav16k(new Blob(chunks, { type: mr.mimeType || 'audio/webm' }));
          if (r.wav.size < 16000 * 2 * 0.3) throw new Error('Recording too short; try again');
          resolve(r);
        } catch (e) { reject(e); }
      };
    });
    function stop() { if (mr.state !== 'inactive') mr.stop(); }
    function cancel() { cancelled = true; stop(); }
    mr.start();
    return { stop, cancel, result };
  }

  global.VaaniVoice = { encodeWav, toWav16k, start };
})(window);
