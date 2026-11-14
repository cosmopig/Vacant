#!/usr/bin/env python3
"""agree_sim — 「同模型再跑一次、答案一致才交」值不值得做？（探索性、0 次模型呼叫）

結論（2026-11-14，本機正式批次 gemma-4-12b、DABstep 79 題、每題 A×3＋C1×3 跑）：**在這裡不值得**。
單跑對 52.5%／沒交 33.5%／交錯 13.9%；「沒交就重跑」上限 3 跑 58.8%（平均 1.59 跑）；「兩跑一致才交、
否則交第一個」上限 3 跑 59.3%（平均 2.48 跑）。一致的答案 85–88% 對，隨便一個有交的答案本來就 79% 對
——錯的答案是系統性的，重跑會錯成同一個。所以 ops/redo/MISSION.md 沒有把「一致性」排進旋鈕。
⚠ 事後分析、同一批題、A 與 C1 混用當成可交換的跑；只能當方向，不是檢定。

用法（原始資料在 ops/eval/evidence_20260926_local/formal/formal_jobs.tar.xz）：
    mkdir /tmp/jobs && tar -xJf ops/eval/evidence_20260926_local/formal/formal_jobs.tar.xz -C /tmp/jobs \
        --wildcards '*/verifier/test-stdout.txt' '*/verifier/reward.txt'
    python3 ops/redo/analysis/agree_sim.py /tmp/jobs A,C1
"""
import sys, re, glob, os, itertools, collections, json
root = sys.argv[1]; arms = sys.argv[2].split(',')
runs = collections.defaultdict(list)   # task -> [(answer|None, ok)]
for p in glob.glob(os.path.join(root, 'formal_v3', '*', '*', '*', 'verifier', 'test-stdout.txt')):
    parts = p.split(os.sep); arm = parts[-5].split('-')[2]
    if arm not in arms: continue
    task = re.match(r'dabstep-(\d+)__', parts[-3]).group(1)
    txt = open(p, encoding='utf-8', errors='replace').read()
    m = re.search(r'^Got: ?(.*)$', txt, re.M)
    ans = None
    if m:
        a = ' '.join(m.group(1).strip().lower().split())
        try: a = repr(round(float(a.replace(',', '')), 2))
        except ValueError: pass
        ans = a if a != '' else None
    rw = os.path.join(os.path.dirname(p), 'reward.txt')
    ok = os.path.exists(rw) and float(open(rw).read().strip() or 0) >= 1.0
    runs[task].append((ans, ok))
n = len(runs); print('tasks', n, 'runs/task', collections.Counter(len(v) for v in runs.values()))
tot = sum(len(v) for v in runs.values())
print('single run: correct %.1f%%  no-answer %.1f%%  wrong %.1f%%' % tuple(100*sum(f(a,o) for v in runs.values() for a,o in v)/tot for f in (lambda a,o:o, lambda a,o:a is None, lambda a,o:a is not None and not o)))
def policy(seq, cap, mode):
    """回傳 (交出去的是否對, 用了幾跑, 是否以一致交件)"""
    seen = []
    for i,(a,ok) in enumerate(seq[:cap]):
        if mode == 'missing':
            if a is not None: return ok, i+1, False
            continue
        if a is not None:
            for b,okb in seen:
                if b == a: return ok, i+1, True
            seen.append((a,ok))
    k = min(cap, len(seq))
    if mode == 'missing': return False, k, False
    if mode == 'agree_or_first': return (seen[0][1] if seen else False), k, False
    if mode == 'agree_only': return None, k, False       # 不一致就不交（拒交）
res = {}
for mode in ('missing','agree_or_first','agree_only'):
    for cap in (1,2,3,4,5,6):
        acc=used=agreed=agreed_ok=refused=wrong=0; cnt=0
        for t,v in runs.items():
            perms = list(itertools.permutations(v)) if len(v)<=6 else [v]
            w = 1/len(perms)
            for s in perms:
                ok,u,ag = policy(list(s),cap,mode)
                used += w*u
                if ok is None: refused += w
                else:
                    acc += w*bool(ok); wrong += w*(not ok and any(a is not None for a,_ in s[:u]))
                if ag: agreed += w; agreed_ok += w*bool(ok)
        res[(mode,cap)] = (acc/n, used/n, agreed/n, (agreed_ok/agreed if agreed else float('nan')), refused/n)
        print(f'{mode:15s} cap={cap}: correct {100*acc/n:5.1f}%  mean runs {used/n:4.2f}  delivered-by-agreement {100*agreed/n:5.1f}% (precision {100*(agreed_ok/agreed if agreed else 0):5.1f}%)  refused {100*refused/n:5.1f}%')
print('oracle any run correct: %.1f%%' % (100*sum(any(o for _,o in v) for v in runs.values())/n))
