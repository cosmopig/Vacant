"""重播結果的敏感度：最後一次測試以可靠的結束碼失敗、只因「說明了失敗」而沒退回的那幾格，
換成舊的 MENTIONS_FAILURE、或完全不看說明時會不會退回，對不對（隱藏測試）。只讀 cells.jsonl 與 runs/。"""
import json, pathlib, re, sys
sys.path.insert(0, "/home/user/Vacant/.claude/worktrees/wf_47b337c8-2fc-1")
from vacant_network.trace import evidence as EV
THOUGHT = re.compile(r"<\|channel>.*?<channel\|>", re.S)
RUNS = pathlib.Path("/home/user/Vacant/.claude/worktrees/wf_47b337c8-2fc-1/runs")
out = {}
for variant in ("product", "counterfactual_run_tests"):
    rows = [json.loads(l) for l in open(f"{variant}/cells.jsonl")]
    failed_last = []
    for r in rows:
        tr = r["test_run_note"]
        if not tr or not r["has_outcome"]:
            continue
        last = None
        for l in open(RUNS / r["run"] / "calls.jsonl"):
            c = json.loads(l); m = c.get("meta") or {}
            if m.get("arm") == "A-SOLO" and m.get("task_id") == r["task"] and "messages" in c:
                last = c
        final = THOUGHT.sub("", last.get("response") or "").strip()
        failed_last.append({"cell": f"{r['run']}/{r['task']}", "hidden": f"{r['hidden_passed']}/{r['hidden_total']}",
                            "fully_correct": r["fully_correct"], "why": tr["why"], "cmd": tr["cmd"][:80], "exit": tr.get("exit"),
                            "disclosure_words": sorted({m.group(0) for m in EV.DISCLOSES_FAILURE.finditer(final)})[:6],
                            "old_mentions_failure": bool(EV.MENTIONS_FAILURE.search(final))})
    def prec(fires):
        return {"fires": len(fires), "on_fully_correct": sum(f["fully_correct"] for f in fires),
                "precision": (sum(not f["fully_correct"] for f in fires) / len(fires)) if fires else None}
    mentioned = [f for f in failed_last if f["why"] == "mentioned"]
    out[variant] = {"last_failed_reliably": failed_last,
                    "if_disclosure_were_old_MENTIONS_FAILURE": prec([f for f in mentioned if not f["old_mentions_failure"]]),
                    "if_no_disclosure_guard": prec(mentioned),
                    "if_no_disclosure_and_no_changed_after_guard": prec(failed_last)}
pathlib.Path("analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
print(json.dumps(out, ensure_ascii=False, indent=1))
