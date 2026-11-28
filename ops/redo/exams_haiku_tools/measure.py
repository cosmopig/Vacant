#!/usr/bin/env python3
"""measure — 凍結考卷的品質量測（決定檔「品質量測」一節）。不改任何考卷。

階段：
  qualify：每個錯解對**原始完整**測試檔跑；失敗≥1 且通過≥1 才入選（其餘丟棄並記錄原因）。
  exams：每種考卷對參考解（逐測試＋逐斷言）與每個入選錯解跑。
輸出：ops/redo/results/ctl_exams_haiku_20261127/{qualify.json,measure.json}
"""
import argparse
import concurrent.futures as cf
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import haiku_call as H  # noqa: E402
import runner as R  # noqa: E402

RES = H.OUT.parents[0] / "results" / "ctl_exams_haiku_20261127"
KINDS = ["xm", "xmv", "pb", "ex"]
DEVIN = {"ex_dnd_character": "/tmp/claude-0/sp/dv/cells/ex_dnd_character/r1/A/attempt_1/workspace/dnd_character.py",
         "ex_pascals_triangle": "/tmp/claude-0/sp/dv/cells/ex_pascals_triangle/r1/A/attempt_1/workspace/pascals_triangle.py",
         "ex_yacht": "/tmp/claude-0/sp/dv/cells/ex_yacht/r1/A/attempt_1/workspace/yacht.py"}


def paths(task: str) -> dict:
    inp = H.task_inputs(task)
    d = H.SRC / inp["slug"]
    return {"module": inp["module"], "orig_test": (d / f"{inp['module']}_test.py"), "ref": d / ".meta" / "example.py"}


def candidates(task: str) -> list[tuple[str, str, str]]:
    """(source, id, code)：Haiku 錯解 k1..k4（落盤的）＋Devin 失敗交付（落盤複本）。"""
    out = []
    wd = RES / "wrong" / task
    for k in ("1", "2", "3", "4"):
        f = wd / f"k{k}.py"
        if f.exists():
            out.append(("haiku_wrong", f"k{k}", f.read_text(encoding="utf-8")))
    f = wd / "devin_failed.py"
    if f.exists():
        out.append(("devin_failed", "devin", f.read_text(encoding="utf-8")))
    return out


def qualify_one(task: str) -> dict:
    p = paths(task)
    orig = p["orig_test"].read_text(encoding="utf-8")
    ref = R.run_tests(orig, p["ref"].read_text(encoding="utf-8"), p["module"])
    res = {"task": task, "orig_ref": {"n": len(ref["tests"]), "pass": sum(v == "pass" for v in ref["tests"].values()),
                                      "collect_error": ref["collect_error"]}, "cands": []}
    for src, cid, code in candidates(task):
        r = R.run_tests(orig, code, p["module"])
        n = len(r["tests"])
        npass = sum(v == "pass" for v in r["tests"].values())
        nfail = sum(v == "fail" for v in r["tests"].values())
        ok = (not r["collect_error"]) and not r["timeout"] and nfail >= 1 and npass >= 1
        why = "ok" if ok else ("collect_error" if r["collect_error"] else "timeout" if r["timeout"] else
                               "passes_all_original_tests" if nfail == 0 else "passes_none_of_original_tests")
        res["cands"].append({"source": src, "id": cid, "orig_n": n, "orig_pass": npass, "orig_fail": nfail,
                             "qualified": ok, "why": why})
    return res


def exam_runs(task: str, quals: dict) -> dict:
    p = paths(task)
    refsrc = p["ref"].read_text(encoding="utf-8")
    out = {"task": task, "exams": {}}
    cands = {(c["source"], c["id"]): code for c_src, cid, code in candidates(task) for c in [{"source": c_src, "id": cid}]}
    for k in KINDS:
        f = H.OUT / task / f"{k}_test.py"
        if not f.exists():
            out["exams"][k] = {"status": "none" if (H.OUT / task / f"{k}_NONE.txt").exists() else "missing"}
            continue
        src = f.read_text(encoding="utf-8")
        units = R.count_units(src)
        e: dict = {"status": "ok" if units is not None else "malformed", "units": units}
        if units is None:
            out["exams"][k] = e
            continue
        r = R.run_tests(src, refsrc, p["module"])
        e["ref"] = {"collect_error": r["collect_error"], "timeout": r["timeout"], "tests": r["tests"], "tail": r["tail"][-300:]}
        ri = R.run_instrumented(src, refsrc, p["module"])
        e["ref_assertions"] = {str(a): s for a, s in ri["assertions"].items()}
        e["ref_assertion_msgs"] = {str(a): m for a, m in ri["messages"].items()}
        e["wrong"] = []
        for c in quals["cands"]:
            if not c["qualified"]:
                continue
            w = R.run_tests(src, cands[(c["source"], c["id"])], p["module"])
            nf = sum(v == "fail" for v in w["tests"].values())
            rejected = w["collect_error"] or w["timeout"] or nf >= 1
            e["wrong"].append({"source": c["source"], "id": c["id"], "rejected": rejected, "n_fail": nf,
                               "n_tests": len(w["tests"]), "collect_error": w["collect_error"], "timeout": w["timeout"]})
        out["exams"][k] = e
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["qualify", "exams", "versions"])
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    RES.mkdir(parents=True, exist_ok=True)
    if a.stage == "versions":
        print(json.dumps(R.versions(), indent=1))
        return 0
    ts = H.tasks()
    if a.stage == "qualify":
        with cf.ThreadPoolExecutor(a.workers) as ex:
            res = list(ex.map(qualify_one, ts))
        (RES / "qualify.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
        nq = sum(c["qualified"] for r in res for c in r["cands"])
        nc = sum(len(r["cands"]) for r in res)
        print("candidates", nc, "qualified", nq)
        return 0
    quals = {r["task"]: r for r in json.loads((RES / "qualify.json").read_text())}
    with cf.ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(lambda t: exam_runs(t, quals[t]), ts))
    (RES / "measure.json").write_text(json.dumps({"versions": R.versions(), "tasks": res}, indent=1), encoding="utf-8")
    print("done", len(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
