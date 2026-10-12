#!/usr/bin/env python3
"""build_e2e_inputs — 本機端到端的輸入：真題目的子集 staged 樹＋替身模型的劇本＋預期結果表（全部寫進 scratchpad，不進 repo）。

    python3 build_e2e_inputs.py --staged <真 staged 樹> --refs <task_banks_20260927 根> \
        --probe-v12 ops/gain/data/lcb_probe_solutions.json --probe-v3 ops/gain/data/lcb_v3_probe_solutions.json \
        --out <scratchpad>/e2e --prefix t1

這支在架構裡承重什麼：端到端要用「真的題目、真的計分器」才算數，但每題的對答案（LCB 的探針解、dabench／databench 的標準答案、
polyglot 的官方參考解）是**題目內容**——不進 repo。所以劇本與預期表在這裡**執行時**才從那些來源產生，只落在 scratchpad；
repo 裡只有這支產生器。子集的選法讓 `--phase auto` 的天花板規則在真的流程裡被走過一次：
  - dabench：真 screen_sample 的 10 題，替身讓 A 答對 9 題 ⇒ 9/10 ≥ 9 ⇒ 整個題庫被丟掉（記進 ceiling_decision.json）；
  - databench、polyglot_py：各 1 題進篩選（A 沒有到 9/10）⇒ 保留 ⇒ 主跑＝3 題 LCB＋這 2 題＝5 個單位。
每個替身行為先用**真計分器**驗過（對的解 pass:true、錯的／沒寫 pass:false），不符就整個停下來，不產生輸入。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import verify_task_banks as V  # noqa: E402

LCB = [("lcb_v2", "lcb_3594", "R"), ("lcb_v1", "lcb_3653", "W"), ("lcb_v3", "lcb_2808", "N")]
SCREEN_BANK_KEEP = {"databench": "db_066_04", "polyglot_py": "pg_affine_cipher"}
WRONG_DAB_ID = "dab_732"                       # 篩選時 dabench 唯一答錯的那題（9/10）


def lcb_texts(bank: str, tid: str, p12: dict, p3: dict) -> tuple[str, str]:
    right = (p3 if bank == "lcb_v3" else p12)[tid].lstrip("\n")
    if not right.endswith("\n"):
        right += "\n"
    m = re.search(r"^def (\w+)\(", right, re.M)
    assert m, f"no top-level def in the probe solution of {bank}/{tid}"
    return right, f"def {m.group(1)}(*a, **k):\n    return None\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--staged", type=Path, required=True)
    ap.add_argument("--refs", type=Path, required=True)
    ap.add_argument("--probe-v12", type=Path, required=True)
    ap.add_argument("--probe-v3", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--prefix", default="t1")
    ap.add_argument("--hang-s", type=float, default=240.0)
    a = ap.parse_args()
    P, PS = a.prefix, a.prefix + "s"
    out = a.out
    full_manifest = json.loads((a.staged / "MANIFEST.json").read_text())
    p12, p3 = json.loads(a.probe_v12.read_text()), json.loads(a.probe_v3.read_text())
    dab_ids = list(full_manifest["screen_sample"]["dabench"])
    assert WRONG_DAB_ID in dab_ids and len(dab_ids) == 10

    chosen: list[tuple[str, str, str]] = [(b, t, "lcb") for b, t, _ in LCB] + [("dabench", t, "screen") for t in dab_ids] \
        + [(b, t, "screen") for b, t in SCREEN_BANK_KEEP.items()]
    st = out / "staged_e2e"
    shutil.rmtree(st, ignore_errors=True)
    tasks_cfg: dict = {}
    index = []
    problems: list[str] = []
    for bank, tid, role in chosen:
        src = a.staged / bank / tid
        shutil.copytree(src, st / bank / tid, symlinks=True)
        index.append({"bank": bank, "id": tid, "dir": f"/srv/eval/staged/{bank}/{tid}", "role": role})
        if bank.startswith("lcb"):
            right, wrong = lcb_texts(bank, tid, p12, p3)
            fname = "solution.py"
        else:
            fname, cs = V.cases_for(bank, st / bank / tid, a.refs)
            right, wrong = cs["reference"][0], cs["wrong"][0]
        tasks_cfg[f"{bank}/{tid}"] = {"file": fname, "right": right, "wrong": wrong}
        # 先用真計分器量：對的要過、錯的與沒寫的不能過（否則這個劇本沒有鑑別力）
        for label, text, want in (("right", right, True), ("wrong", wrong, False), ("missing", None, False)):
            got = V.run_one(st / bank / tid, fname, text)
            if got.get("pass") is not want:
                problems.append(f"{bank}/{tid} {label}: scorer said pass={got.get('pass')} want {want} ({got.get('note')})")
    if problems:
        print("SCORER GAUGE FAILED:\n  " + "\n  ".join(problems))
        return 2
    man = {k: full_manifest[k] for k in ("schema", "seed", "instruction_sentence", "vm_root")}
    man.update({"screen_n": 10, "derived_from_manifest_sha256": __import__("hashlib").sha256(
        (a.staged / "MANIFEST.json").read_bytes()).hexdigest(), "note": "local E2E subset (3 LCB + 10 dabench + 1 databench + 1 polyglot_py)",
        "screen_sample": {"dabench": dab_ids, **{b: [t] for b, t in SCREEN_BANK_KEEP.items()}}})
    (st / "tasks_index.json").write_text(json.dumps(index, indent=1) + "\n")
    (st / "MANIFEST.json").write_text(json.dumps(man, indent=1) + "\n")

    # ── 替身劇本：regex(標籤) → 行為。標籤＝<前綴>-<組>-<題庫>-<題>-s1[v2].n<段>
    def tag(prefix: str, arm: str, bank: str, tid: str, n: int, att: int = 1) -> str:
        return "^" + re.escape(f"{prefix}-{arm}-{bank}-{tid}-s1" + ("" if att == 1 else f"v{att}") + f".n{n}") + "$"

    rules = [{"tag": tag(PS, "A", "dabench", WRONG_DAB_ID, 1), "mode": "wrong", "note": "screen: the one wrong dabench task (9/10)"},
             {"tag": tag(PS, "A", "polyglot_py", SCREEN_BANK_KEEP["polyglot_py"], 1), "mode": "claim", "note": "screen: polyglot claims done, writes nothing"}]
    (r_b, r_t), (w_b, w_t), (n_b, n_t) = [(b, t) for b, t, _ in LCB]
    d_b, d_t = "databench", SCREEN_BANK_KEEP["databench"]
    g_b, g_t = "polyglot_py", SCREEN_BANK_KEEP["polyglot_py"]
    rules += [
        # U1 (right everywhere); A's first session gets a burst of 500s longer than the proxy's retry budget => infra_void => rerun v2
        {"tag": tag(P, "A", r_b, r_t, 1), "mode": "right", "fail_first": 5, "status": 500, "note": "U1 A attempt1: 5x500 burst => void"},
        # U2 (wrong first; K's fix session writes the right one). One 500 on C's first request: absorbed by the proxy retry => NOT void
        {"tag": tag(P, "A", w_b, w_t, 1), "mode": "wrong", "note": "U2 A wrong"},
        {"tag": tag(P, "C", w_b, w_t, 1), "mode": "wrong", "fail_first": 1, "status": 500, "note": "U2 C wrong; single 500 absorbed by proxy"},
        # U3 (claim): A claims; R retries claim then right; K fixes with wrong twice (never accepted); C is sent back and then writes
        {"tag": tag(P, "A", n_b, n_t, 1), "mode": "claim", "note": "U3 A claim"},
        {"tag": tag(P, "C", n_b, n_t, 1), "mode": "claim", "note": "U3 C claim => Vacant send-back"},
        {"tag": tag(P, "R", n_b, n_t, 2), "mode": "claim", "note": "U3 R retry 1 claims again"},
        {"tag": tag(P, "K", n_b, n_t, 2), "mode": "wrong", "note": "U3 K fix 1 wrong"},
        {"tag": tag(P, "K", n_b, n_t, 3), "mode": "wrong", "note": "U3 K fix 2 wrong => never accepted"},
        # U4 (databench): A and C both hang past AGENT_TIMEOUT; R's retry (copy of A's workspace) is right
        {"tag": tag(P, "A", d_b, d_t, 1), "mode": "hang", "note": "U4 A hangs"},
        {"tag": tag(P, "C", d_b, d_t, 1), "mode": "hang", "note": "U4 C hangs"},
        # U5 (polyglot): A and both R retries claim; C right
        {"tag": tag(P, "A", g_b, g_t, 1), "mode": "claim", "note": "U5 A claim"},
        {"tag": tag(P, "R", g_b, g_t, 2), "mode": "claim", "note": "U5 R retry 1 claim"},
        {"tag": tag(P, "R", g_b, g_t, 3), "mode": "claim", "note": "U5 R retry 2 claim"},
    ]
    script = {"latency_s": 0.3, "hang_s": a.hang_s, "default_mode": "right", "rules": rules, "tasks": tasks_cfg,
              "prefix": P, "note": "generated by build_e2e_inputs.py; contains reference answers; never commit"}
    (out / "stub_script.json").write_text(json.dumps(script, ensure_ascii=False, indent=1) + "\n")

    # ── 預期表（verify_e2e.py 讀）。key＝<組>/<題庫>/<題>/<attempt>
    U = {"U1": (r_b, r_t), "U2": (w_b, w_t), "U3": (n_b, n_t), "U4": (d_b, d_t), "U5": (g_b, g_t)}
    expect = {"prefix": P, "screen_prefix": PS, "units": {k: f"{b}/{t}" for k, (b, t) in U.items()},
              "screen": {"dabench": {"n": 10, "passes": 9, "dropped": True}, d_b: {"n": 1, "passes": 1, "dropped": False},
                         g_b: {"n": 1, "passes": 0, "dropped": False}},
              "main_banks_dropped": ["dabench"]}
    (out / "expect_scenario.json").write_text(json.dumps(expect, indent=1) + "\n")
    print(json.dumps({"staged_e2e": str(st), "tasks": len(index), "rules": len(rules)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
