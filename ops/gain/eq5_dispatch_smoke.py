#!/usr/bin/env python3
"""EQ5 的**接線**測試：跑真的 `gain_run.main()`，但把模型端點換成假的（零 API）。

為什麼單元測試不夠（記憶鐵律：「工具與判決分支驗過 ≠ 那一行的 run 語意驗過」）：
`arm_eq5` 自己對了，不代表 dispatch 有接上——`vote_meets_demand` 是在 dispatch
算的，那條 `if arm == "EQ5":` 若沒進去，rows 會**安靜**少掉整個反事實欄位，
而 run 照樣跑完、rc=0、summary 一片綠。等預算的答案會變成「沒有資料」。

三個偵測量（每一個都指名「該看到什麼」，不是 rc≠0）：
  D1 EQ5 的 row 數 == 題數                       （安靜量不到型）
  D2 每一列都帶 vote_meets_demand／vote_deliv／gate_deliv
  D3 每一列 calls_used == 5（等預算在真的迴圈裡也成立）
另外驗 summary 的 eq5_* 三個比率存在且分母正確。

M4 突變體：把 dispatch 裡寫 `vote_meets_demand` 那一行拿掉 ⇒ D2 必須變成 BROKEN。
"""
from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SRC = ROOT / "ops" / "gain" / "gain_run.py"
MUT = ROOT / "ops" / "gain" / "_eq5_dispatch_mutant.py"
WORK = pathlib.Path("/dev/shm/eq5_smoke")
# ⚠ 不用 `--bank builtin`：round689 實測它把記憶體吃到 7.0 GB／整台開始 swap
#   （RSS 87%、D 狀態、無子行程），必須 kill -9。合成題庫在這台上不能跑。
#   改用真題庫的前 N 題——反正這支只驗接線，不產生任何實驗結論。
BANK = "evalplus"
N_TASKS = 3

STUB = "def _unused(*a, **k):\n    return None\n"


class _FakeBrain:
    """依 agent_id 決定給參考解還是給樁——不打任何端點。"""

    refs: dict[str, str] = {}

    def __init__(self, agent_id, system_prompt, *, key=None, log_path=None,
                 model=None, timeout_s=None, retries=None, backoff_s=None):
        self.agent_id, self.model, self.log_path = agent_id, model, log_path
        self.cost = self.market_cost = 0.0

    def generate(self, prompt, role=None, meta=None):
        tid = (meta or {}).get("task_id", "")
        good = self.agent_id.startswith("careful") or self.agent_id == "plain-1"
        code = self.refs.get(tid, STUB) if good else STUB
        out = f"```python\n{code}\n```"
        # 真的 ClineBrain 會把每次呼叫寫進 calls.jsonl，而 `latency_summary` 讀它。
        # 假替身不寫 ⇒ finalize 會 FileNotFoundError＝**替身缺能力**，
        # 不是產品缺陷（r674 的三分類）。所以替身也要落盤同樣的最小紀錄。
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "agent_id": self.agent_id, "model": self.model, "role": role,
                    "meta": meta or {}, "ok": True, "latency_ms": 1,
                    "prompt": prompt, "response": out}, ensure_ascii=False) + "\n")
        return out


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _run(mod, out: pathlib.Path, decision: pathlib.Path) -> int:
    mod.ClineBrain = _FakeBrain
    argv = sys.argv[:]
    sys.argv = ["gain_run.py", "--out", str(out), "--n", str(N_TASKS),
                "--decision", str(decision), "--seed", "eq5-smoke",
                "--arms", "EQ5", "--bank", BANK, "--models", "fake-model",
                "--probe-sample", "0"]
    try:
        mod.main()
        return 0
    except SystemExit as e:
        return int(e.code or 0)
    finally:
        sys.argv = argv


def _verify(out: pathlib.Path) -> dict:
    rows = [json.loads(x) for x in (out / "rows.jsonl").read_text().splitlines() if x]
    eq5 = [r for r in rows if r["arm"] == "EQ5"]
    fields = ("vote_meets_demand", "vote_deliv", "gate_deliv", "vote_code_sha256",
              "same_choice", "vote_n_agree")
    summ = json.loads((out / "summary.json").read_text())["arms"].get("EQ5", {})
    return {
        "D1_rows": len(eq5),
        "D2_all_fields": all(all(f in r for f in fields) for r in eq5) and bool(eq5),
        "D3_calls_all_5": all(r["calls_used"] == 5 for r in eq5) and bool(eq5),
        "summary_keys": all(
            k in summ for k in ("eq5_gate_delivery_rate", "eq5_vote_delivery_rate",
                                "eq5_same_choice_rate")),
        "calls_per_task": summ.get("calls_per_task"),
        "gate_rate": summ.get("eq5_gate_delivery_rate"),
        "vote_rate": summ.get("eq5_vote_delivery_rate"),
        "same_choice_rate": summ.get("eq5_same_choice_rate"),
        "no_full_code_in_rows": all("vote_code" not in r for r in eq5),
    }


def main() -> int:
    os.environ["CLINE_KEYS"] = "/nonexistent"
    os.environ.setdefault("VACANT_GAIN_API", "http://127.0.0.1:9/v1/chat/completions")
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    dec = WORK / "DECISION_SMOKE.md"

    clean_out = WORK / "eq5_smoke_clean"
    dec.write_text(f"合成夾具，非實驗：授權 {clean_out.name} 與 eq5_smoke_mut\n")

    mod = _load(SRC, "_eq5_dispatch_clean")
    _FakeBrain.refs = mod._canonical_solutions(BANK)
    rc = _run(mod, clean_out, dec)
    got = _verify(clean_out)
    print(f"乾淨版 rc={rc} 偵測量={json.dumps(got, ensure_ascii=False)}")
    want = {"D1_rows": N_TASKS, "D2_all_fields": True, "D3_calls_all_5": True,
            "summary_keys": True, "calls_per_task": 5.0, "no_full_code_in_rows": True}
    bad = {k: (v, got.get(k)) for k, v in want.items() if got.get(k) != v}
    if rc != 0 or bad:
        print(f"BROKEN：乾淨版就不符合預期 {bad}（rc={rc}）")
        return 1

    # M4：dispatch 少寫 vote_meets_demand ⇒ D2 必須抓到（不是靠 rc）
    src = SRC.read_text(encoding="utf-8")
    anchor = '                extra["vote_meets_demand"] = vote_truth\n'
    if src.count(anchor) != 1:
        print(f"BROKEN  M4：錨點出現 {src.count(anchor)} 次（要 1 次）")
        return 1
    MUT.write_text(src.replace(anchor, "", 1), encoding="utf-8")
    mut_out = WORK / "eq5_smoke_mut"
    try:
        mmod = _load(MUT, "_eq5_dispatch_mut")
        _FakeBrain.refs = mmod._canonical_solutions(BANK)
        mrc = _run(mmod, mut_out, dec)
        mgot = _verify(mut_out)
    finally:
        MUT.unlink(missing_ok=True)
    print(f"M4 突變體 rc={mrc} 偵測量={json.dumps(mgot, ensure_ascii=False)}")
    if mgot["D2_all_fields"] is not False:
        print("MISSED  M4：少掉 vote_meets_demand 卻沒被 D2 抓到——接線測試沒有牙齒。")
        return 1
    print(f"DETECTED M4：D2_all_fields {want['D2_all_fields']} → {mgot['D2_all_fields']}"
          f"（而 rc 仍是 {mrc}——所以判準不能只寫 rc≠0）")
    print("EQ5_DISPATCH_SMOKE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
