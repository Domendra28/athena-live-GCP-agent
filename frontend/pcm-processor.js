// AudioWorklet: Fast zero-delay decimation down to 16kHz mono PCM with RMS calculation
class PCMProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this._frac = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;
    const ch = input[0];

    // Linear decimation to 16kHz
    const out = [];
    let idx = this._frac;
    while (idx < ch.length) {
      out.push(ch[Math.floor(idx)]);
      idx += this.ratio;
    }
    this._frac = idx - ch.length;

    const int16 = new Int16Array(out.length);
    let sum = 0;
    for (let i = 0; i < out.length; i++) {
      const s = Math.max(-1, Math.min(1, out[i]));
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      sum += s * s;
    }

    const rms = out.length ? Math.sqrt(sum / out.length) : 0;
    this.port.postMessage({ pcm: int16.buffer, rms }, [int16.buffer]);
    return true;
  }
}

registerProcessor('pcm-processor', PCMProcessor);
