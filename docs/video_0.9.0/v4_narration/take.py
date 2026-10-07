"""One continuous narration take (single voice, single rate) → split into sentences at word-boundary gaps."""
import json, certifi, os, asyncio, subprocess, sys, numpy as np
certifi.where = lambda: "/root/.ccr/ca-bundle.crt"
import edge_tts
from scipy.io import wavfile
RATE = sys.argv[1] if len(sys.argv) > 1 else "+6%"
SC = json.load(open("script.json"))
text = "\n".join(s for _, s in SC)
async def main():
    com = edge_tts.Communicate(text, "zh-TW-HsiaoChenNeural", rate=RATE, boundary="WordBoundary", proxy=os.environ.get("HTTPS_PROXY"))
    words = []
    with open("take.mp3", "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio": f.write(ch["data"])
            elif ch["type"] == "WordBoundary": words.append([ch["offset"] / 1e7, ch["duration"] / 1e7, ch["text"]])
    return words
words = asyncio.run(main())
raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', 'take.mp3', '-ac', '1', '-ar', '48000', '-f', 's16le', '-'])
x = np.frombuffer(raw, np.int16).astype(np.float64) / 32768
# assign words to sentences by consuming characters
def norm(s): return ''.join(ch for ch in s if ch.isalnum())
wi = 0; out = []
for sid, s in SC:
    need = norm(s); got = ''; ws = []
    while wi < len(words) and len(got) < len(need):
        ws.append(words[wi]); got += norm(words[wi][2]); wi += 1
    assert got == need, (sid, got, need)
    out.append((sid, s, ws))
os.makedirs('sent', exist_ok=True); meta = {}
for k, (sid, s, ws) in enumerate(out):
    st = ws[0][0]; en = ws[-1][0] + ws[-1][1]
    prev_end = out[k - 1][2][-1][0] + out[k - 1][2][-1][1] if k else 0
    nxt = out[k + 1][2][0][0] if k + 1 < len(out) else len(x) / 48000
    a = max(prev_end, st - .12) if k else max(0, st - .12); b = min(nxt, en + .25)
    seg = x[int(a * 48000):int(b * 48000)]
    # trim to the voiced part (−45 dB), keep 15 ms pad
    thr = 10 ** (-45 / 20); idx = np.where(np.abs(seg) > thr)[0]
    i0 = max(0, idx[0] - 720); i1 = min(len(seg), idx[-1] + 720); seg = seg[i0:i1]
    t0 = a + i0 / 48000
    # tighten long pauses inside the sentence (cut silence only; voice and rate untouched)
    MAXG = .18 if sid == 'qs' else .22
    env_ = np.convolve(np.abs(seg), np.ones(480) / 480, 'same') > thr * 1.5
    cuts = []; i = 0
    while i < len(env_):
        if not env_[i]:
            j = i
            while j < len(env_) and not env_[j]: j += 1
            if (j - i) / 48000 > MAXG and i > 0 and j < len(env_): cuts.append((i + int(MAXG * 48000 / 2), j - int(MAXG * 48000 / 2)))
            i = j
        else: i += 1
    keep = []; last = 0; removed = []
    for c0, c1 in cuts: keep.append(seg[last:c0]); removed.append((c0, c1 - c0)); last = c1
    keep.append(seg[last:]); seg = np.concatenate(keep)
    def remap(tt_):
        s_ = (tt_ - t0) * 48000; sh = sum(n for p, n in removed if p < s_); return t0 + (s_ - sh) / 48000
    ws = [[remap(w[0]), w[1], w[2]] for w in ws]; en = ws[-1][0] + ws[-1][1]; st = ws[0][0]
    fade = np.minimum(1, np.arange(len(seg)) / 240) * np.minimum(1, (len(seg) - np.arange(len(seg))) / 480)
    wavfile.write(f'sent/{sid}.wav', 48000, (seg * fade * 32767).astype(np.int16))
    meta[sid] = {'zh': s, 'dur': round(len(seg) / 48000, 3), 'words': [[round(w[0] - t0, 3), round(w[1], 3), w[2]] for w in ws]}
    print(f'{sid:8s} {len(seg)/48000:5.2f}s  {len(norm(s))/(en-st):4.2f} 字/秒  {s}')
json.dump(meta, open('sent.json', 'w'), ensure_ascii=False, indent=1)
print('total speech', round(sum(m['dur'] for m in meta.values()), 2))
