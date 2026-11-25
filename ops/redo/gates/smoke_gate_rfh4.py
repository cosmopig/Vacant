#!/usr/bin/env python3
"""rfh4 冒煙關卡（四臂 A／H／R／RF，2026-11-25）：冒煙跑完後只依事先寫死的「基礎設施＋操作」條件判斷要不要接主批。
條件與通過率無關（不看 pass／b／c）。沿用 smoke_gate.py 的做法，另外檢查：
- 四臂都在、每臂 0 infra_void、每格模型呼叫量得到且平均 > 0、驗收 status 全是 ok、評分器一種；
- H：至少一格的病歷（attempt_*/logs/vacant-home/trace/projects/*/chain.ndjson）有 payload.mode＝evidence 的 review 事件；
- R：所有嘗試 hint_bytes＝0；RF：有任何第 2 次以上的嘗試時，那些嘗試 hint_bytes 都 > 0，且 hint_text 以 harness 模板開頭；
- runner.log 沒有「harness 例外」。
用法：smoke_gate_rfh4.py <gate.json>
gate.json：{"smoke_plan", "smoke_root", "expect_pairs", "expect_grader", "next": [{"queue": 佇列檔, "line": 佇列行}, ...]}
結束碼：0＝通過並已把每一行加進各自的佇列；1＝不通過（GATE_FAIL 寫進 <smoke_root>/GATE.txt）；2＝用法錯。
"""
import json, os, pathlib, subprocess, sys, time

HINT_HEAD = "An earlier attempt at this task ended with the tests in this directory not passing."
ARMS = ["A", "H", "R", "RF"]


def runner_alive(plan: str) -> bool:
    r = subprocess.run(["pgrep", "-f", f"redo.py run --plan {plan}"], capture_output=True, text=True)
    return bool(r.stdout.strip())


def check(g: dict) -> list[str]:
    root = pathlib.Path(os.path.expanduser(g["smoke_root"]))
    rp = root / "REPORT.json"
    if not rp.exists():
        return ["REPORT.json 不存在"]
    r = json.loads(rp.read_text())
    bad = []
    n = g["expect_pairs"]
    if r.get("pairs_planned") != n or r.get("pairs_complete") != n:
        bad.append(f"pairs planned/complete = {r.get('pairs_planned')}/{r.get('pairs_complete')}，要 {n}/{n}")
    if r.get("harness_changed_mid_run"):
        bad.append("harness 中途變了")
    per = r.get("per_arm") or {}
    if sorted(per) != sorted(ARMS):
        bad.append(f"per_arm 不是四臂：{sorted(per)}")
    for arm, s in per.items():
        if s.get("cells") != n:
            bad.append(f"{arm} cells={s.get('cells')}，要 {n}")
        if s.get("infra_void"):
            bad.append(f"{arm} infra_void={s['infra_void']}")
        if s.get("grader_kinds") != [g["expect_grader"]]:
            bad.append(f"{arm} grader_kinds={s.get('grader_kinds')}")
        if s.get("model_calls_known_cells") != s.get("cells") or not (s.get("mean_model_calls") or 0) > 0:
            bad.append(f"{arm} 模型呼叫量不到或為 0（known {s.get('model_calls_known_cells')}/{s.get('cells')}，mean {s.get('mean_model_calls')}）")
    hook_seen = False
    for cj in sorted(root.glob("cells/*/*/*/cell.json")):
        c = json.loads(cj.read_text())
        arm = c.get("arm")
        for a in c.get("attempts", []):
            if a.get("acc_status") != "ok":
                bad.append(f"{c.get('cell')} 第 {a.get('k')} 次驗收 status={a.get('acc_status')}")
        for aj in sorted(cj.parent.glob("attempt_*/attempt.json")):
            k = int(aj.parent.name.split("_")[1])
            d = json.loads(aj.read_text())
            hb, ht = int(d.get("hint_bytes") or 0), d.get("hint_text")
            if arm == "R" and hb:
                bad.append(f"{c.get('cell')} R 的第 {k} 次送了 hint（{hb} 位元組）")
            if arm == "RF" and k >= 2 and not (hb > 0 and isinstance(ht, str) and ht.startswith(HINT_HEAD)):
                bad.append(f"{c.get('cell')} RF 的第 {k} 次沒有送出 harness 模板的 hint（{hb} 位元組）")
            if arm in ("A", "H", "R") and hb:
                bad.append(f"{c.get('cell')} {arm} 的第 {k} 次有 hint")
            if arm == "H":
                # 掛鉤有載入、而且交件前檢查以 evidence 模式跑過（install.json 有被放進這次的 VACANT_HOME）
                for ch in (aj.parent / "logs" / "vacant-home" / "trace" / "projects").glob("*/chain.ndjson"):
                    for line in ch.read_text(errors="replace").splitlines():
                        try:
                            e = json.loads(line)
                        except ValueError:
                            continue
                        if e.get("type") == "review" and (e.get("payload") or {}).get("mode") == "evidence":
                            hook_seen = True
    if not hook_seen:
        bad.append("H 沒有任何一格的病歷裡有 evidence 模式的 review 事件（掛鉤沒載入，或 install.json 沒放進 VACANT_HOME）")
    log = root / "runner.log"
    if log.exists() and "harness 例外" in log.read_text(errors="replace"):
        bad.append("runner.log 有 harness 例外")
    return bad


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__); return 2
    g = json.loads(pathlib.Path(sys.argv[1]).read_text())
    root = pathlib.Path(os.path.expanduser(g["smoke_root"]))
    seen = False
    while True:
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
    lines = []
    for nx in g["next"]:
        q = pathlib.Path(os.path.expanduser(nx["queue"]))
        with q.open("a") as f:
            f.write(nx["line"].rstrip("\n") + "\n")
        lines.append(f"{q}：{nx['line']}")
    (root / "GATE.txt").write_text(f"{stamp} GATE_PASS → 已加進\n" + "\n".join(lines) + "\n")
    print("GATE_PASS"); return 0


if __name__ == "__main__":
    sys.exit(main())
