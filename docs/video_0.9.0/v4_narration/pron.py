"""Pronunciation check: ASR each sentence, align toneless pinyin with the script, report every syllable that differs."""
import json, sys, difflib, re
src = open('asr.py').read().split("if __name__")[0]
sys.argv = [sys.argv[0], sys.argv[1] if len(sys.argv) > 1 else 'medium']; exec(src)
from pypinyin import lazy_pinyin, Style
FILES = sys.argv[2:] if len(sys.argv) > 2 else None
M = json.load(open('sent.json'))
han = lambda s: re.sub(r'[^一-鿿]', '', s)
def P(s, tone): return lazy_pinyin(han(s), style=Style.TONE3 if tone else Style.NORMAL, neutral_tone_with_five=True)
# Taiwan Mandarin merges some finals in casual speech; ASR also does. Treat these as equivalent for the toneless check.
def soft(p): return p.replace('ing', 'in').replace('eng', 'en')
report = {}
for sid, mm in M.items():
    heard = tr(f'sent/{sid}.wav')
    D_ = '零一二三四五六七八九'
    def num(mo):
        n = int(mo.group()); 
        if n < 10: return D_[n]
        if n < 20: return '十' + (D_[n % 10] if n % 10 else '')
        return D_[n // 10] + '十' + (D_[n % 10] if n % 10 else '')
    heard = re.sub(r'\d+', num, heard)
    a, b = P(mm['zh'], 0), P(heard, 0); at, bt = P(mm['zh'], 1), P(heard, 1)
    sm = difflib.SequenceMatcher(None, [soft(x) for x in a], [soft(x) for x in b])
    bad = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != 'equal': bad.append((op, han(mm['zh'])[i1:i2], ' '.join(at[i1:i2]), han(heard)[j1:j2], ' '.join(bt[j1:j2])))
        else:
            for k in range(i2 - i1):
                if at[i1 + k] != bt[j1 + k] and not (at[i1 + k][-1] == '5' or bt[j1 + k][-1] == '5'):
                    bad.append(('tone', han(mm['zh'])[i1 + k], at[i1 + k], han(heard)[j1 + k], bt[j1 + k]))
    report[sid] = {'script': mm['zh'], 'heard': heard, 'diffs': bad}
    print(f"{sid:8s} {'OK ' if not bad else 'CHK'} 劇本：{mm['zh']}\n         聽寫：{heard}")
    for d in bad: print('           ', d)
json.dump(report, open('pron_report.json', 'w'), ensure_ascii=False, indent=1)
