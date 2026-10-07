import json, sys, re, subprocess, numpy as np, difflib
src = open('asr.py').read().split("if __name__")[0]; sys.argv = [sys.argv[0], 'medium']; exec(src)
from pypinyin import lazy_pinyin
raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', 'mix4.wav', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'])
x = np.frombuffer(raw, np.float32)
han = lambda s: re.sub(r'[^一-鿿]', '', s)
D_ = '零一二三四五六七八九'
def num(mo):
    n = int(mo.group()); return D_[n] if n < 10 else ('十' + (D_[n % 10] if n % 10 else '') if n < 20 else D_[n // 10] + '十' + (D_[n % 10] if n % 10 else ''))
tot = ok = 0
for c in json.load(open('cues.json')):
    seg = x[int((c['start'] - .1) * 16000):int((c['end'] + .25) * 16000)]
    segs, _ = m.transcribe(seg, language='zh', beam_size=5)
    heard = re.sub(r'\d+', num, ''.join(s.text for s in segs)).replace('%', '')
    exp = c['zh'].replace('百分之', '')
    a, b = lazy_pinyin(han(exp)), lazy_pinyin(han(heard))
    r = difflib.SequenceMatcher(None, a, b).ratio(); tot += 1; ok += r > .9
    print(f"{r:4.2f}  {c['zh']}  ←  {heard}")
print(f'{ok}/{tot} cues ≥ 0.90 syllable match in the final mix')
