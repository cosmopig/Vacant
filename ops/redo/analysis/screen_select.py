#!/usr/bin/env python3
"""W3-5：從「只跑原生臂」的篩選批選題，並產生確認批計畫（規則在篩選前寫死、跟計畫一起 commit）。

規則（不可在看過結果後改）：
- 篩選批：每題原生 pi 跑 2 次（兩個完全相同的單次臂 A、A2，reps 1）。
- 某題兩次都有效（沒有 infra_void）才計分；有 void 的題不入選、列在報告的分母裡。
- 入選：2 次裡過 ≤ 1 次。
- 入選超過 N：照 sha256(task + salt) 升冪取前 N。入選少於 MIN（15）：照跑，結論寫明檢定力不足；不加題、不改門檻。
- 確認批：入選題 × 5 次全新 rep，A（原生 pi 單次 1800 秒）對 P（`vacant do pi`，rc4，不載入擴充），同一個後端。

用法：screen_select.py <screen_root> <screen_plan.json> <confirm_template.json> <out_plan.json> --n N --salt S
輸出：分母報告（stdout，也寫到 <out_plan>.selection.json）與確認批計畫。
"""
import argparse, hashlib, json, pathlib, sys

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("screen_root"); ap.add_argument("screen_plan"); ap.add_argument("confirm_template"); ap.add_argument("out_plan")
    ap.add_argument("--n", type=int, required=True); ap.add_argument("--salt", required=True); ap.add_argument("--min", type=int, default=15)
    a = ap.parse_args(argv)
    sp = json.loads(pathlib.Path(a.screen_plan).read_text())
    root = pathlib.Path(a.screen_root)
    per = {t: {"runs": 0, "passes": 0, "void": 0} for t in sp["tasks"]}
    for cj in root.glob("cells/*/*/*/cell.json"):
        c = json.loads(cj.read_text())
        t = c["task"]
        if t not in per: continue
        if c.get("infra_void"):
            per[t]["void"] += 1; continue
        per[t]["runs"] += 1; per[t]["passes"] += int(bool(c.get("pass")))
    incomplete = sorted(t for t, v in per.items() if v["runs"] + v["void"] < 2)
    if incomplete:
        print(f"SCREEN_INCOMPLETE: {len(incomplete)} tasks without 2 cells", file=sys.stderr); return 2
    scored = {t: v for t, v in per.items() if v["void"] == 0 and v["runs"] == 2}
    voided = sorted(t for t, v in per.items() if v["void"] > 0)
    dist = {k: sorted(t for t, v in scored.items() if v["passes"] == k) for k in (0, 1, 2)}
    eligible = dist[0] + dist[1]
    order = sorted(eligible, key=lambda t: hashlib.sha256((t + a.salt).encode()).hexdigest())
    chosen = order[: a.n]
    rep = {"screen_plan": sp["id"], "tasks_screened": len(per), "scored": len(scored), "voided": voided,
           "passes_2of2": len(dist[2]), "passes_1of2": len(dist[1]), "passes_0of2": len(dist[0]),
           "eligible": len(eligible), "cap_n": a.n, "chosen": chosen, "chosen_count": len(chosen),
           "underpowered": len(chosen) < a.min, "salt": a.salt,
           "per_task": {t: per[t] for t in sorted(per)}}
    tpl = json.loads(pathlib.Path(a.confirm_template).read_text())
    if not chosen:
        print(json.dumps({k: v for k, v in rep.items() if k != "per_task"}, ensure_ascii=False, indent=1))
        print("NO_TASKS_SELECTED: confirm batch not generated", file=sys.stderr); return 3
    tpl["tasks"] = chosen
    tpl["prereg"]["selection"] = {k: v for k, v in rep.items() if k != "per_task"}
    if rep["underpowered"]:
        tpl["prereg"].setdefault("known_limits", []).append(
            f"入選只有 {len(chosen)} 題（< {a.min}）：照預註冊照跑，檢定力不足，結論要寫明。")
    pathlib.Path(a.out_plan).write_text(json.dumps(tpl, ensure_ascii=False, indent=1) + "\n")
    pathlib.Path(a.out_plan + ".selection.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: v for k, v in rep.items() if k != "per_task"}, ensure_ascii=False, indent=1))
    return 0

if __name__ == "__main__":
    sys.exit(main())
