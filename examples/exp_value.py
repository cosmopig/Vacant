import sys, tempfile, os
from pathlib import Path
from vacant.host import Host
from vacant.openai_substrate import OpenAISubstrate, HINTS
from vacant.substrate import SubstrateResult
from vacant.tasks import make_task, NICHES

# 端點不寫死（G10）：VACANT_ENDPOINT 指定，預設本機 LM Studio
URL = os.environ.get("VACANT_ENDPOINT", "http://localhost:1234").rstrip("/") + "/v1"
MODEL = "google/gemma-4-e4b"; N = 24

class QualitySub(OpenAISubstrate):
    def run(self, home, prompt, task):
        if task is None:
            return super().run(home, prompt, task)
        niche, inp = task["niche"], task["input"]
        qf = home / "quality.txt"
        q = qf.read_text().strip() if qf.exists() else "bad"
        if q == "good":
            sysmsg = "You solve small string puzzles precisely."
            user = HINTS.get(niche, "") + " Output ONLY the answer, no other words.\nInput: " + inp + "\nAnswer:"
        else:
            sysmsg = "Answer very briefly."
            user = "task=" + niche + " input=" + inp + " answer="
        raw = self._chat(sysmsg, user)
        ans = raw.splitlines()[-1].strip() if raw else raw
        return SubstrateResult(ans, self.substrate_id, None)

def setup(root):
    h = Host(Path(root), substrate=QualitySub(URL, model=MODEL, timeout=60))
    h.mint("req", niches=[])
    for nm, q in (("expert_good", "good"), ("expert_bad", "bad")):
        h.mint(nm, niches=list(NICHES))
        hd = Path(root) / nm / "home"; hd.mkdir(parents=True, exist_ok=True)
        (hd / "quality.txt").write_text(q)
    return h, h.vacant_id("expert_good")

def run_condition(mode, root):
    h, good_id = setup(root)
    correct, to_good = [], []
    for i in range(N):
        t = make_task(i)
        try:
            oc = h.gateway("req").call(t["niche"], t, mode=mode)
            ok = oc.correct; cg = (oc.callee_id == good_id)
            print("    [%s] r%02d %-10s -> %s ans=%-14r %s" % (mode, i, t["niche"], "good" if cg else "bad ", oc.answer, "OK" if ok else "x"), flush=True)
        except Exception as e:
            ok = False; cg = False
            print("    [%s] r%02d %-10s EXC %s: %s" % (mode, i, t["niche"], type(e).__name__, str(e)[:90]), flush=True)
        correct.append(int(ok)); to_good.append(int(cg))
    return correct, to_good

def acc(x): return sum(x) / len(x)
base = tempfile.mkdtemp(prefix="vacant-value-")
print("[exp] model=%s N=%d  good(方法提示) vs bad(最少指令)" % (MODEL, N), flush=True)
print("跑 B: 有 vacant（信譽路由）…", flush=True)
cb, gb = run_condition("reputation", os.path.join(base, "vacant"))
print("跑 A: 無 vacant（隨機路由）…", flush=True)
ca, ga = run_condition("random", os.path.join(base, "novacant"))
h = N // 2
print("\n================= 結果 =================")
print("無 vacant（隨機路由）  正確率 %.0f%%  (送good %.0f%%)" % (acc(ca)*100, acc(ga)*100))
print("有 vacant（信譽路由）  正確率 %.0f%%  (送good %.0f%%)" % (acc(cb)*100, acc(gb)*100))
print("  有vacant 後半段 正確率 %.0f%% (送good %.0f%%)" % (acc(cb[h:])*100, acc(gb[h:])*100))
print("效能差距(有-無)= %+.0f%%   後半段= %+.0f%%" % ((acc(cb)-acc(ca))*100, (acc(cb[h:])-acc(ca))*100))
