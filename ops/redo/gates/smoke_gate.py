#!/usr/bin/env python3
"""冒煙關卡：冒煙批跑完後，只依事先寫死的「基礎設施」條件判斷要不要自動接下一批。
條件與通過率無關（不看 pass／b／c），寫在發射前、跟計畫一起 commit。

用法：smoke_gate.py <gate.json>
gate.json：{"smoke_plan": 相對路徑, "smoke_root": 目錄, "queue": 佇列檔, "next_line": 要附加的佇列行,
            "expect_pairs": N, "expect_grader": "visible_tests_pristine"}
結束碼：0＝通過並已把 next_line 加進佇列；1＝不通過（寫 GATE_FAIL 到 <smoke_root>/GATE.txt）；2＝用法錯。
"""
import json, os, pathlib, subprocess, sys, time

def runner_alive(plan: str) -> bool:
    r = subprocess.run(["pgrep", "-f", f"redo.py run --plan {plan}"], capture_output=True, text=True)
    return bool(r.stdout.strip())

def check(g: dict) -> list[str]:
    root = pathlib.Path(os.path.expanduser(g["smoke_root"]))
    bad = []
    rp = root / "REPORT.json"
    if not rp.exists():
        return ["REPORT.json 不存在"]
    r = json.loads(rp.read_text())
    n = g["expect_pairs"]
    if r.get("pairs_planned") != n or r.get("pairs_complete") != n:
        bad.append(f"pairs planned/complete = {r.get('pairs_planned')}/{r.get('pairs_complete')}，要 {n}/{n}")
    if r.get("pairs_infra_void"):
        bad.append(f"infra_void 對：{r['pairs_infra_void']}")
    if r.get("harness_changed_mid_run"):
        bad.append("harness 中途變了")
    for arm, s in (r.get("per_arm") or {}).items():
        if s.get("infra_void"):
            bad.append(f"{arm} infra_void={s['infra_void']}")
        if s.get("grader_kinds") != [g["expect_grader"]]:
            bad.append(f"{arm} grader_kinds={s.get('grader_kinds')}")
        if s.get("model_calls_known_cells") != s.get("cells") or not (s.get("mean_model_calls") or 0) > 0:
            bad.append(f"{arm} 模型呼叫量不到或為 0（known {s.get('model_calls_known_cells')}/{s.get('cells')}，mean {s.get('mean_model_calls')}）")
    if len(r.get("per_arm") or {}) != 2:
        bad.append(f"per_arm 不是兩臂：{list((r.get('per_arm') or {}).keys())}")
    for cj in sorted(root.glob("cells/*/*/*/cell.json")):
        c = json.loads(cj.read_text())
        for a in c.get("attempts", []):
            if a.get("acc_status") != "ok":
                bad.append(f"{c.get('cell')} 第 {a.get('k')} 次驗收 status={a.get('acc_status')}")
    return bad

def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__); return 2
    g = json.loads(pathlib.Path(sys.argv[1]).read_text())
    root = pathlib.Path(os.path.expanduser(g["smoke_root"]))
    seen = False
    while True:  # 等冒煙發射、再等它結束（或已經有 REPORT 且沒有 runner）
        alive = runner_alive(g["smoke_plan"])
        seen = seen or alive
        if not alive and (seen or (root / "REPORT.json").exists()):
            time.sleep(30)
            if not runner_alive(g["smoke_plan"]):
                break
        time.sleep(60)
    bad = check(g)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if bad:
        (root / "GATE.txt").write_text(f"{stamp} GATE_FAIL\n" + "\n".join(bad) + "\n")
        print("GATE_FAIL"); print("\n".join(bad)); return 1
    q = pathlib.Path(os.path.expanduser(g["queue"]))
    with q.open("a") as f:
        f.write(g["next_line"].rstrip("\n") + "\n")
    (root / "GATE.txt").write_text(f"{stamp} GATE_PASS → 已加進 {q}：{g['next_line']}\n")
    print("GATE_PASS"); return 0

if __name__ == "__main__":
    sys.exit(main())
