#!/usr/bin/env python3
"""build_manifest — 由 calls.jsonl 與磁碟上的凍結檔重建 MANIFEST.json（可重複執行；只讀考卷檔）。"""
import ast
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import haiku_call as H  # noqa: E402

KINDS = ["xm", "xmv", "pb", "ex"]


def main() -> int:
    calls = {}
    if H.CALLS.exists():
        for line in H.CALLS.read_text().splitlines():
            r = json.loads(line)
            m = r["meta"]
            if m.get("purpose") == "exam" and r["ok"]:
                calls[(m["kind"], m["task"])] = r
    prompts = {p.name: H.sha(p.read_bytes()) for p in sorted((H.OUT / "prompts").glob("*"))}
    man = {"schema": "haiku_exams/1", "dir": "ops/redo/exams_haiku_20261127",
           "decision": "decisions/DECISION_20261127_HAIKU_EXAMS.md",
           "writer_cli": "claude -p --model haiku --output-format json --tools '' (default sampling; the CLI has no temperature setting)",
           "bank": str(H.BANK), "prompt_templates_sha256": prompts, "tools_sha256": {
               p.name: H.sha(p.read_bytes()) for p in sorted(pathlib.Path(__file__).resolve().parent.glob("*.py"))},
           "models_seen": sorted({r["model"] for r in calls.values() if r["model"]}), "tasks": {}}
    total = 0.0
    for t in H.tasks():
        inp = H.task_inputs(t)
        d = H.OUT / t
        ent = {"writer_inputs": [
            {"role": "requirements", "bank_path": f"{t}/workspace/goal.md", "sha256": H.sha(inp["goal"].encode())},
            {"role": "stub", "repo_path": f"exercises/practice/{inp['slug']}/{inp['module']}.py (exercism/python 479f11b4)",
             "sha256": H.sha(inp["stub"].encode())}], "module": inp["module"], "exams": {}}
        for k in KINDS:
            f = d / f"{k}_test.py"
            if not f.exists() and not (d / f"{k}_FAILED.txt").exists() and not (d / f"{k}_NONE.txt").exists():
                continue
            e: dict = {}
            if f.exists():
                b = f.read_bytes()
                e["file"] = f"{t}/{k}_test.py"
                e["sha256"] = H.sha(b)
                try:
                    ast.parse(b.decode("utf-8"))
                    e["status"] = "ok"
                except (SyntaxError, UnicodeDecodeError) as ex:
                    e["status"] = "malformed"
                    e["parse_error"] = str(ex)
            elif (d / f"{k}_NONE.txt").exists():
                e["status"] = "none"
                e["note"] = (d / f"{k}_NONE.txt").read_text().strip()
            else:
                e["status"] = "failed_infra"
            if k == "xmv" and (d / "xmv_raw.py").exists():
                e["raw_file"] = f"{t}/xmv_raw.py"
                e["raw_sha256"] = H.sha((d / "xmv_raw.py").read_bytes())
            if k == "ex":
                e["generator"] = "deterministic extractor (no model): tools/ex_extract.py"
            else:
                r = calls.get((k, t))
                if r:
                    e["prompt_template"] = f"prompts/{k}_prompt.txt"
                    e["prompt_template_sha256"] = prompts[f"{k}_prompt.txt"]
                    e["prompt_sha256"] = r["prompt_sha256"]
                    e["model"] = r["model"]
                    e["generated_at"] = r["ts"]
                    e["elapsed_s"] = r["elapsed_s"]
                    e["cost_usd"] = r["cost_usd"]
                    e["attempts"] = r["attempt"]
                    total += r["cost_usd"] or 0
            ent["exams"][k] = e
        man["tasks"][t] = ent
    man["exam_cost_usd_total"] = round(total, 6)
    man["all_haiku_calls_cost_usd_total_incl_failures"] = round(H.spent(), 6)
    (H.OUT / "MANIFEST.json").write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    print("tasks", len(man["tasks"]), "cost", man["exam_cost_usd_total"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
