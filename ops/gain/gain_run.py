#!/usr/bin/env python3
"""G 實驗 runner——三條臂，量「需求＝產出」。

規格：`SPEC_GAIN.md`。這支只做規格說的事，不多做。

    OFF     隨機路由，交回來就收                      1 呼叫／題
    ON      信譽路由 ＋ K=3 同儕評審 ＋ 抽樣稽核      ≈5 呼叫／題
    OFF5    同題跑 5 次取多數決（self-consistency）    5 呼叫／題

**OFF5 是這個實驗誠實與否的分水嶺**：ON 比 OFF 好幾乎必然，因為多花五倍呼叫。
要答的是「等預算下 Vacant 打不打得贏最土的做法」。

用法：
    python3 ops/gain/gain_run.py --out runs/g1 --n 40 --seed g1
    python3 ops/gain/gain_run.py --out runs/g1 --n 40 --arms probe   # 只跑量具驗證

全 I/O 落盤：`<out>/calls.jsonl`（每次模型呼叫的 prompt/回應全文）、
`<out>/rows.jsonl`（逐題）、`<out>/summary.json`。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import random
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from ops.gain.brain_cline import (POOL, REVIEWER_SYSTEM, ClineBrain,  # noqa: E402
                                  InfraVoid, load_keys)
from vacant.codebench import BuiltinSampleLoader, EvalPlusMBPPLoader  # noqa: E402


def load_tasks(bank: str, seed: str, n: int) -> list[dict]:
    """預設用**真題庫**（EvalPlus MBPP+ 378 題，sha256 釘死、fail-closed）。

    ⚠ `BuiltinSampleLoader` 只在明確指定時才用，而且它的 docstring 自己警告過：
      「同一顆 reference solver 配不同隨機測資的變體，不是真的不同題目，
        正式跑分前必須換成真 EvalPlus 資料」。
      拿它跑增益實驗會把「題目其實都一樣」誤讀成「機制沒有差別」。
    """
    loader = EvalPlusMBPPLoader() if bank == "evalplus" else BuiltinSampleLoader()
    ts = list(loader.iter_tasks(seed))
    if bank != "evalplus":
        print("⚠ 用的是合成題庫，結論不可外推（見 load_tasks docstring）")
    return ts[:n] if n else ts


# ── 判定：產出滿不滿足需求 ────────────────────────────────────────
def extract_code(text: str) -> str:
    """從回應裡挖出 python 程式碼。挖不到就原樣回傳——不要猜。"""
    if "```" in text:
        parts = text.split("```")
        for i in range(1, len(parts), 2):
            blk = parts[i]
            if blk.startswith("python"):
                blk = blk[6:]
            elif blk.startswith("py"):
                blk = blk[2:]
            if blk.strip():
                return blk.strip()
    return text.strip()


def meets_demand(code: str, check_code: str, timeout_s: int = 10) -> tuple[bool, str]:
    """跑隱藏測資。回傳 (通過?, 訊息)。

    隱藏測資**不進 prompt**——那個分離就是「需求 vs 產出」的操作定義。
    """
    import subprocess
    import tempfile
    src = f"{code}\n\n{check_code}\n"
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False,
                                     encoding="utf-8") as f:
        f.write(src)
        path = f.name
    try:
        r = subprocess.run([sys.executable, path], capture_output=True,
                           text=True, timeout=timeout_s)
        return r.returncode == 0, (r.stderr or "")[-400:]
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:                                  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"
    finally:
        try:
            pathlib.Path(path).unlink()
        except OSError:
            pass


# ── 量具驗證：先答已知答案 ────────────────────────────────────────
def _canonical_solutions(path: str | None = None) -> dict[str, str]:
    """只給量具驗證用的官方參考解。

    ⚠ 為什麼要另外讀：`EvalPlusMBPPLoader` **刻意不把 `canonical_solution`
      放進 public projection**——它是 GT，只進 `hidden_check`，永不進 prompt
      （codebench.py 的 V/GT 分離紀律，負向測試在 tests/test_x1_evalplus.py）。

    ⚠ 為什麼這樣讀不算作弊：量具驗證是**驗證者側**的動作，跟 agent 無關。
      這個 dict 只餵給 `meets_demand`，**不進任何 prompt**。
      如果哪天有人把它接進 agent 那條路，V/GT 分離就破了——所以它只在
      `probe_instrument` 裡被用到，不要擴大使用範圍。
    """
    import gzip
    from vacant.codebench import EVALPLUS_DEFAULT_PATH
    p = pathlib.Path(path or EVALPLUS_DEFAULT_PATH)
    out: dict[str, str] = {}
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            out[f"mbppplus_{r['task_id']}"] = r.get("canonical_solution", "")
    return out


def probe_instrument(tasks, log, *, sample=12) -> dict:
    """SPEC_GAIN §5.2：餵一份**確定正確**與一份**確定錯誤**，兩邊都要判對。

    沒有這一步的話，「量到 0」與「線根本沒接上」在報告裡長得一模一樣。

    正確那份用 MBPP+ 自己的 `canonical_solution`（官方參考解）。
    錯誤那份用一個一定跑不過的樁。**兩個方向都過才算量具可用**——
    只驗正向會漏掉「什麼都判通過」，只驗反向會漏掉「什麼都判失敗」。
    """
    try:
        refs = _canonical_solutions()
    except Exception as e:                                   # noqa: BLE001
        raise SystemExit(f"讀不到官方參考解，量具無法驗證：{e}")
    good = bad = 0
    detail = []
    for t in tasks[:sample]:
        ref = refs.get(t["task_id"])
        if not ref:
            continue
        hidden = t["hidden_check"]["code"]
        ok_good, msg_g = meets_demand(ref, hidden)
        ok_bad, _ = meets_demand(
            f"def {t.get('entry_point','_f')}(*a, **k):\n    return None\n", hidden)
        good += int(ok_good)
        bad += int(not ok_bad)
        detail.append({"task_id": t["task_id"], "ref_pass": ok_good,
                       "broken_rejected": not ok_bad, "err": msg_g[:160]})
    res = {"n": len(detail), "ref_pass": good, "broken_rejected": bad,
           "detail": detail}
    log(res)
    return res


# ── 三條臂 ────────────────────────────────────────────────────────
def arm_off(task, agents, rng, calls):
    a = rng.choice(agents)
    txt = a.generate(task["prompt"], role="gen",
                     meta={"arm": "OFF", "task_id": task["task_id"]})
    calls[0] += 1
    return extract_code(txt), a.agent_id, [a.agent_id]


def arm_off5(task, agents, rng, calls, k=5):
    """self-consistency：同題跑 k 次，取多數決。

    多數決的定義：把每份解答的**行為**當簽名——用同一組可見測資跑一遍，
    結果字串相同的視為同一票。這比字面比對公平（同義寫法不該被拆票）。
    """
    outs = []
    for _ in range(k):
        a = rng.choice(agents)
        txt = a.generate(task["prompt"], role="gen",
                         meta={"arm": "OFF5", "task_id": task["task_id"]})
        calls[0] += 1
        outs.append((extract_code(txt), a.agent_id))
    # 行為簽名：用 visible 例子的執行結果分群；跑不起來的自成一群
    buckets: dict[str, list[tuple[str, str]]] = {}
    for code, aid in outs:
        sig = hashlib.sha256(code.encode()).hexdigest()[:12]
        buckets.setdefault(sig, []).append((code, aid))
    win = max(buckets.values(), key=len)
    return win[0][0], win[0][1], [a for _, a in outs]


def arm_on(task, agents, rng, calls, rep, *, audit_rate=0.2, k_review=3):
    """信譽路由（UCB 近似）＋ K=3 同儕評審 ＋ 確定性抽樣稽核。

    路由用 rep 的分數；評審用**同一個池**——所以共同盲區是真的存在，
    不是被假設掉。評審準確率會被單獨記錄（SPEC_GAIN §5.1）。
    """
    # 路由：分數 ＋ 探索額（n 小的加分），沿用 registry 的形狀但不引入整個 registry
    def score(a):
        s = rep[a.agent_id]
        n = s["n"]
        mean = (s["ok"] + 1) / (n + 2)              # Beta(1,1) 後驗均值
        explore = (2.0 / (n + 1)) ** 0.5
        return mean + 0.4 * explore
    worker = max(agents, key=score)
    txt = worker.generate(task["prompt"], role="gen",
                          meta={"arm": "ON", "task_id": task["task_id"]})
    calls[0] += 1
    code = extract_code(txt)

    # 同儕評審：不能自評
    pool = [a for a in agents if a.agent_id != worker.agent_id]
    reviewers = rng.sample(pool, min(k_review, len(pool)))
    votes = []
    rprompt = (f"題目：\n{task['prompt']}\n\n候選解答：\n```python\n{code}\n```\n\n"
               "這份解答是否完全滿足題目要求？只回「通過」或「不通過」。")
    for r in reviewers:
        v = r.generate(rprompt, role="review",
                       meta={"arm": "ON", "task_id": task["task_id"],
                             "target": worker.agent_id})
        calls[0] += 1
        votes.append((r.agent_id, "不通過" not in v and "通過" in v))

    passed_review = sum(1 for _, ok in votes if ok) >= (len(votes) + 1) // 2

    # 稽核：確定性抽樣（sha256(seed:task_id) < rate），跑隱藏測資
    h = int(hashlib.sha256(f"audit:{task['task_id']}".encode()).hexdigest()[:8], 16)
    audited = (h / 0xFFFFFFFF) < audit_rate
    audit_ok = None
    if audited:
        audit_ok, _ = meets_demand(code, task["hidden_check"]["code"])

    accepted = passed_review and (audit_ok is not False)
    return code, worker.agent_id, [a for a, _ in votes], {
        "votes": votes, "passed_review": passed_review,
        "audited": audited, "audit_ok": audit_ok, "accepted": accepted,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", default="g1")
    ap.add_argument("--arms", default="OFF,ON,OFF5")
    ap.add_argument("--bank", default="evalplus", choices=["evalplus", "builtin"])
    ap.add_argument("--audit-rate", type=float, default=0.2)
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    calls_log = out / "calls.jsonl"
    rows_path = out / "rows.jsonl"

    def note(obj):
        with (out / "notes.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")

    keys = load_keys()
    agents = [ClineBrain(aid, sys_p, key=keys[i % len(keys)], log_path=calls_log)
              for i, (aid, sys_p) in enumerate(POOL)]

    tasks = load_tasks(args.bank, args.seed, args.n)
    print(f"{len(tasks)} 題（{args.bank}）　{len(agents)} 個 agent　輸出 {out}")

    # ── 先驗量具 ──
    print("── 量具驗證（先答已知答案）")
    pr = probe_instrument(tasks, note)
    print(f"   參考解通過 {pr['ref_pass']}/{pr['n']}　"
          f"壞解被擋 {pr['broken_rejected']}/{pr['n']}")
    if pr["n"] == 0:
        raise SystemExit("量具驗證一題都沒驗到——這不是通過，是沒接上。停。")
    if pr["ref_pass"] < pr["n"] or pr["broken_rejected"] < pr["n"]:
        raise SystemExit("量具沒有兩個方向都答對——在壞尺上跑實驗等於沒跑。停。")
    if args.arms.strip() == "probe":
        return

    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    summary = {}
    for arm in arms:
        rng = random.Random(f"{args.seed}:{arm}")
        rep = {a.agent_id: {"n": 0, "ok": 0} for a in agents}
        calls = [0]
        n_acc = n_acc_ok = n_void = 0
        rv_correct = rv_total = 0
        t0 = time.time()
        for i, t in enumerate(tasks, 1):
            try:
                if arm == "OFF":
                    code, worker, involved = arm_off(t, agents, rng, calls)
                    accepted, extra = True, {}
                elif arm == "OFF5":
                    code, worker, involved = arm_off5(t, agents, rng, calls)
                    accepted, extra = True, {}
                else:
                    code, worker, involved, extra = arm_on(
                        t, agents, rng, calls, rep, audit_rate=args.audit_rate)
                    accepted = extra["accepted"]
            except InfraVoid as e:
                n_void += 1
                note({"arm": arm, "task_id": t["task_id"], "infra_void": str(e)})
                continue

            truth, err = meets_demand(code, t["hidden_check"]["code"])
            if arm == "ON":
                rep[worker]["n"] += 1
                rep[worker]["ok"] += int(truth)
                # 評審準確率：單獨量（SPEC_GAIN §5.1）
                for _, v in extra["votes"]:
                    rv_total += 1
                    rv_correct += int(v == truth)
            if accepted:
                n_acc += 1
                n_acc_ok += int(truth)

            with rows_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "arm": arm, "seed": args.seed, "i": i,
                    "task_id": t["task_id"], "family": t["family"], "entry_point": t.get("entry_point"),
                    "worker": worker, "involved": involved,
                    "meets_demand": truth, "err": err[:200],
                    "accepted": accepted, "calls_so_far": calls[0],
                    **{k: v for k, v in extra.items() if k != "votes"},
                    "votes": extra.get("votes"),
                }, ensure_ascii=False) + "\n")
            print(f"  [{arm} {i}/{len(tasks)}] 需求符合={truth} 接受={accepted} "
                  f"累計呼叫={calls[0]}", flush=True)

        summary[arm] = {
            "tasks": len(tasks), "calls": calls[0], "infra_void": n_void,
            "accepted": n_acc, "accepted_and_meets_demand": n_acc_ok,
            "demand_equals_output_rate": (n_acc_ok / n_acc) if n_acc else None,
            "calls_per_correct_delivery": (calls[0] / n_acc_ok) if n_acc_ok else None,
            "leaked": n_acc - n_acc_ok,
            "reviewer_accuracy": (rv_correct / rv_total) if rv_total else None,
            "reviewer_votes": rv_total,
            "wall_s": round(time.time() - t0, 1),
            "cost_usd": round(sum(a.cost for a in agents), 4),
        }
        print(f"── {arm}: {json.dumps(summary[arm], ensure_ascii=False)}")

    (out / "summary.json").write_text(
        json.dumps({"seed": args.seed, "n": args.n, "pool": [a for a, _ in POOL],
                    "instrument": pr, "arms": summary},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n寫出 {out/'summary.json'}")
    print("⚠ 這是待驗證的宣稱不是結果——OFF5 沒跑贏之前不能說機制有效。")


if __name__ == "__main__":
    main()
