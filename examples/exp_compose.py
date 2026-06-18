"""量測：vacant 的『組合』讓同一顆腦比單次更好嗎？（重點實驗）

三條件、等算力（規格 §5）、可檢查任務、客觀 verifier（yes/no、不洩答案）：
  plain  ×1   : 裸單次（無 vacant）
  naive  ×K   : K 次取多數決（自一致；用 K 次算力但無驗證結構）
  vacant ×K   : verify-fix 互查迴圈（錯了帶回饋重試，驗證過即收）

每次 generate 都經 vacant 的 waker（路由＋簽章＋logbook）。腦可選 openai(直連 gemma)
或 hermes(Hermes Agent 當腦)。用法：exp_compose.py [N=20] [K=3] [openai|hermes] [model]
"""
from __future__ import annotations
import sys, tempfile, time, json, urllib.request
from pathlib import Path
from vacant.host import Host
from vacant.composer import Composer
from vacant.verifier import is_correct
from vacant.tasks import task_stream, NICHES

CANDS = ["192.168.76.1", "172.25.16.1", "172.17.119.12"]; PORT = 1234
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
K = int(sys.argv[2]) if len(sys.argv) > 2 else 3
WHICH = sys.argv[3] if len(sys.argv) > 3 else "openai"
MODEL = sys.argv[4] if len(sys.argv) > 4 else "google/gemma-4-e4b"
TEMP = 0.7

def pick_url():
    for ip in CANDS:
        u = f"http://{ip}:{PORT}/v1"
        try:
            urllib.request.urlopen(u + "/models", timeout=4).read(); return u
        except Exception:
            continue
    return None

url = pick_url()
if not url:
    print("[BLOCKED] LM Studio 端點連不到", flush=True); sys.exit(2)

if WHICH == "hermes":
    from vacant.hermes_substrate import HermesSubstrate
    sub = HermesSubstrate(model=MODEL, toolsets="", timeout=180, learn=False)
    brain = f"Hermes Agent -> {MODEL}"
elif WHICH == "responses":
    from vacant.openai_substrate import ResponsesSubstrate
    sub = ResponsesSubstrate(url, model=MODEL, timeout=75, learn=False)
    brain = f"{MODEL} via /api/v1/chat (reasoning model)"
else:
    from vacant.openai_substrate import OpenAISubstrate
    sub = OpenAISubstrate(url, model=MODEL, timeout=60, temperature=TEMP, learn=False)
    brain = f"{MODEL} @ {url} (temp={TEMP})"

root = Path(tempfile.mkdtemp(prefix="vacant-compose-"))
h = Host(root, substrate=sub)
h.mint("req", niches=[])
h.mint("expert", niches=list(NICHES))
eid = h.vacant_id("expert")

def make_gen(task):
    def gen(fb):
        t = dict(task); t["feedback"] = fb
        try:
            return h.waker.wake(eid, t["prompt"], t).result.output  # 經 vacant：路由+簽章+logbook
        except Exception as e:
            return f"[err:{type(e).__name__}]"  # 逾時/錯誤 → 該次視為失敗，不中斷整輪
    return gen

print(f"[compose] 腦={brain}  N={N} K={K}  每次 generate 經 vacant 閘道(簽章/路由/logbook)", flush=True)
stats = {"plain": [0, 0], "naive": [0, 0], "vacant": [0, 0]}  # [hits, calls]
strategies = [("plain", lambda c: c.plain()), ("naive", lambda c: c.naive(K)), ("vacant", lambda c: c.vacant(K))]
t0 = time.time()
for i, task in enumerate(task_stream(N)):
    chk = lambda a, _t=task: is_correct(_t, a)
    row = {}
    for name, fn in strategies:
        r = fn(Composer(make_gen(task), chk))
        stats[name][0] += int(r.correct); stats[name][1] += r.calls
        row[name] = ("OK" if r.correct else "x") + f"({r.calls})"
    print(f"  t{i:02d} [{task['niche']:11}] plain={row['plain']:6} naive={row['naive']:6} vacant={row['vacant']:6}", flush=True)

print("\n================= 結果 (%.0fs) =================" % (time.time() - t0))
for name in ("plain", "naive", "vacant"):
    hits, calls = stats[name]
    print("%-7s 正確率 %3.0f%%   平均腦呼叫 %.1f 次/題" % (name, hits / N * 100, calls / N))
pa = stats["plain"][0] / N; na = stats["naive"][0] / N; va = stats["vacant"][0] / N
print("\n重點：")
print("  vacant − plain  = %+.0f%%   ← vacant 組合 vs 裸單次（含『多花算力』）" % ((va - pa) * 100))
print("  vacant − naive  = %+.0f%%   ← 等算力(同 K)下，驗證結構 vs 純自一致 = vacant 的淨貢獻" % ((va - na) * 100))
print("  腦=%s" % brain)
