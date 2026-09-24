#!/usr/bin/env python3
"""e2e_trace — **四個真 agent × 四個埋錯情境**：追緝有沒有追到對的那一步、對的起因。

這支在架構裡承重什麼（`decisions/DECISION_20260924_ACCOUNTABLE_TRACE.md` §五；LOOP M6）：

同一個非程式任務（「寫出第三季總數的報告」），四種錯的來源——

| 情境 | 劇本（假模型照演） | 期望 |
|---|---|---|
| B agent 憑空寫錯 | 讀帳本 → 寫「Total: 999」 | `agent`／`provable`，指到寫報告那一步；重跑前後翻轉 |
| A 輸入本來就錯 | 讀財務給的摘要（寫著 75）→ 照抄 | `input`／`lineage_exact`，指到 `inputs/summary.txt`；agent 不背 |
| C 中間的腳本錯 | 寫 `calc.py`（加錯欄）→ 跑它輸出報告 | `agent`／`lineage_internal`，指到**寫腳本**那一步，不是寫報告那一步 |
| D 沒被記錄的改動（負控制） | agent 寫對的報告；**之後**有人在外面改成 999 | `UNOBSERVED`／`gap`；沒有任何行動者被記 |
| F 網頁本身就錯 | 用 `curl` 抓財務入口網站的頁面（寫著 58）→ 照抄 | `input`／`lineage_exact`，來源是那個網址；agent 不背 |

情境 F 的「網站」是 `portal.vacant-lab.test`：實驗環境把 agent 的 `http_proxy` 指到假模型（像公司的代理），
所以 agent 下的指令就是一般的 `curl http://portal.vacant-lab.test/…`。**本機的網址（localhost、這台機器的位址）
不算外部來源**（agent 可能自己開了伺服器）；Vacant 看不到代理／DNS 把名字指到哪裡，這是誠實邊界。
| G 背景子 agent（只有 Claude Code）| 同 E，但子 agent 在背景跑；主 agent 從 `<task-notification>` 照抄數字 | 同 E：指到子 agent；那則通知不可以被當成使用者說的話 |
| E 子 agent 算錯、主 agent 照抄 | 主 agent 用自己的委派工具交給子 agent（`ROLE:sub`）→ 子 agent 讀帳本、把 96 寫進 `figure.txt` → 主 agent 讀它、寫進報告 | `agent`／`lineage_internal`，指到**子 agent** 寫 `figure.txt` 的那一步（行動者帶子 agent 的 id） |

每個 agent 一個隔離的「使用者」（`ops/intake/e2e_four_agents.Lab`：自己的 HOME、provider 指到
假模型、`vacant install` 寫進它自己的設定），**原生地**跑（命令列上沒有 `vacant`）。
量：歸因對不對、回饋（有位置的版本）有沒有出現在下一次模型請求裡、改好之後過不過、
病歷驗不驗得過、掛鉤花了多久（p50／p95）、行動者帳本記了什麼。

輸出：`<out>/results.json`、`<out>/SUMMARY.md`。

## 誠實邊界

1. **L-fake**：模型照劇本回答。證明的是**機制**在四個真 agent 的真掛鉤、真工具迴圈上接得起來、
   歸因規則在乾淨埋錯下給出期望的答案——**不是**真模型下產出會更接近需求（那是預註冊實驗的事）。
2. 劇本決定錯在哪裡；錯的值都選成在別處找不到的數字（999、75、306），巧合相同的值會讓
   值比對誤認來源（`blame.py` 誠實邊界 2）。
3. 子 agent（情境 E）：假模型照 `ROLE:sub` 演子 agent。Claude Code 用前景的 `Agent`（背景模式另有
   `capture/` 的實測）；OpenCode 用 `task`；Codex 用預設開著的 `multi_agent_v1`（`spawn_agent`→`wait_agent`；
   這個版本對自訂 provider 不藏在 `tool_search` 後面，v2 沒跑）；pi 沒有內建子 agent，用它**隨附的範例擴充**
   `subagent`（另開一個 pi 行程，靠 Vacant 的 pi 擴充傳下去的 `VACANT_PI_PARENT` 認出是子 agent）。
   平行委派（一次叫兩個子 agent）沒在這裡跑：pi 那條標記在平行時可能指到兄弟呼叫（工作階段仍然對）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import statistics
import subprocess
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ops" / "intake"))
import e2e_four_agents as E  # noqa: E402

PY = sys.executable
LEDGER = "id,item,amount\n101,alpha,12\n102,beta,23\n103,gamma,34\n"          # 總數 69
SUMMARY_TXT = "Finance quarter summary (preliminary): Total: 75\n"          # 錯的輸入
BAD_CALC = ("import csv\n"
            "rows = list(csv.DictReader(open('inputs/ledger.csv')))\n"
            "print('# Q' + 'three')\nprint()\n"
            "print('Total:', sum(int(r['id']) for r in rows))\n")          # 加錯欄 ⇒ 306
GOOD_CALC = BAD_CALC.replace("int(r['id'])", "int(r['amount'])")
PROMPT = "Write report.md with the quarter total described in the task contract."

SCENARIOS: dict[str, dict] = {
    "B_agent_fault": {
        "steps": [{"run": "cat inputs/ledger.csv"},
                  {"write": ["report.md", "# Quarter\n\nTotal: 999\n"]}],
        "final": "Done.",
        "fix": {"steps": [{"write": ["report.md", "# Quarter\n\nTotal: 69\n"]}],
                "final": "Fixed."}},
    "A_input_fault": {
        "steps": [{"run": "cat inputs/summary.txt"},
                  {"write": ["report.md", "# Quarter\n\nTotal: 75\n"]}],
        "final": "Done.",
        "fix": {"steps": [{"run": "cat inputs/ledger.csv"},
                          {"write": ["report.md", "# Quarter\n\nTotal: 69\n"]}],
                "final": "The finance summary disagrees with the ledger; used the ledger."}},
    "C_script_fault": {
        "steps": [{"write": ["calc.py", BAD_CALC]},
                  {"run": "python3 calc.py > report.md"}],
        "final": "Done.",
        "fix": {"steps": [{"write": ["calc.py", GOOD_CALC]},
                          {"run": "python3 calc.py > report.md"}],
                "final": "Fixed."}},
    "D_unrecorded_change": {
        "steps": [{"write": ["report.md", "# Quarter\n\nTotal: 69\n"]}],
        "final": "Done."},
    "F_web_source_fault": {
        "steps": [{"run": "curl -s http://portal.vacant-lab.test/web/q3.txt"},
                  {"write": ["report.md", "# Quarter\n\nTotal: 58\n"]}],
        "final": "Done.",
        "web": {"q3.txt": "Finance portal (preliminary): Q3 total 58\n"},
        "fix": {"steps": [{"run": "cat inputs/ledger.csv"},
                          {"write": ["report.md", "# Quarter\n\nTotal: 69\n"]}],
                "final": "The portal disagrees with the ledger; used the ledger."}},
    "G_background_subagent_fault": {
        # Claude Code 預設把子 agent 放到背景：主 agent 先收到「已啟動」，結果之後以一則
        # `<task-notification>` 使用者訊息回來；主 agent 直接照抄通知裡的數字（沒有讀檔）
        "steps": [{"agent": {"prompt": "ROLE:sub Add up the amount column of inputs/ledger.csv "
                                       "and write the total (digits only) to figure.txt.",
                             "description": "Compute the quarter total", "background": True}},
                  {"await": "notification"},
                  {"write": ["report.md", "# Quarter\n\nTotal: 96\n"]}],
        "final": "Done.",
        "roles": {"sub": {"steps": [{"run": "cat inputs/ledger.csv"},
                                    {"write": ["figure.txt", "96\n"]}],
                          "final": "The quarter total is 96 (written to figure.txt)."}},
        "fix": {"steps": [{"run": "cat inputs/ledger.csv"},
                          {"write": ["report.md", "# Quarter\n\nTotal: 69\n"]}],
                "final": "Recomputed from the ledger."}},
    "E_subagent_fault": {
        "steps": [{"agent": {"prompt": "ROLE:sub Add up the amount column of inputs/ledger.csv "
                                       "and write the total (digits only) to figure.txt.",
                             "description": "Compute the quarter total", "pi_agent": "worker"}},
                  {"run": "cat figure.txt"},
                  {"write": ["report.md", "# Quarter\n\nTotal: 96\n"]}],
        "final": "Done.",
        "roles": {"sub": {"steps": [{"run": "cat inputs/ledger.csv"},
                                    {"write": ["figure.txt", "96\n"]}],
                          "final": "Wrote 96 to figure.txt."}},
        "fix": {"steps": [{"run": "cat inputs/ledger.csv"},
                          {"write": ["report.md", "# Quarter\n\nTotal: 69\n"]}],
                "final": "Recomputed from the ledger."}},
}
EXPECT = {
    "B_agent_fault": {"state": "located", "fault_class": "agent", "confidence": "provable",
                      "step_writes": "report.md"},
    "A_input_fault": {"state": "located", "fault_class": "input",
                      "confidence": "lineage_exact", "source_path": "inputs/summary.txt"},
    "C_script_fault": {"state": "located", "fault_class": "agent",
                       "confidence": "lineage_internal", "step_writes": "calc.py"},
    "D_unrecorded_change": {"state": "UNOBSERVED", "fault_class": "unattributable",
                            "confidence": "gap"},
    "F_web_source_fault": {"state": "located", "fault_class": "input",
                           "confidence": "lineage_exact", "source_kind": "url"},
    "G_background_subagent_fault": {"state": "located", "fault_class": "agent",
                                    "confidence": "lineage_internal", "step_writes": "figure.txt",
                                    "subagent": True},
    "E_subagent_fault": {"state": "located", "fault_class": "agent",
                         "confidence": "lineage_internal", "step_writes": "figure.txt",
                         "subagent": True},
}
#: 只在某些平台有意義的情境
ONLY = {"G_background_subagent_fault": {"claude"}}
#: pi 沒有內建子 agent：情境 E 用它隨附的範例擴充（另開一個 pi 行程），代理人定義放在隔離的 agent 目錄
PI_SUBAGENT_EXT = "@earendil-works/pi-coding-agent/examples/extensions/subagent/index.ts"
PI_WORKER = ("---\nname: worker\ndescription: does one delegated task\n"
             "tools: read, bash, write\n---\nYou do the delegated task and report what you wrote.\n")


def contract(dest: pathlib.Path, task_id: str) -> dict:
    return {"schema": "vacant-contract/1", "task_id": task_id, "version": 1,
            "objective": "Report the quarter's total from the ledger.", "owner": "",
            "deliverable": {"include": ["report.md"],
                            "exclude": [".git/**", ".vacant/**"]},
            "inputs": {"ledger": {"path": "inputs/ledger.csv"},
                       "summary": {"path": "inputs/summary.txt"}},
            "claims": [{"id": "total", "verifier": "csv_total", "authority": "fact",
                        "required": True, "description": "the total equals the ledger",
                        "params": {"csv": "input:ledger", "column": "amount",
                                   "report": "report.md"}}],
            "unknown_policy": "hold", "conflict_policy": "escalate",
            "release": {"destination": f"dir:{dest}", "requires_approval": False},
            "hooks": {"stop_check": True, "max_feedback_rounds": 2, "submit_on_end": True}}


class Lab(E.Lab):
    def reset_project(self, task_id: str = "q-total") -> None:
        self.task_id = task_id
        if self.proj.exists():
            shutil.rmtree(self.proj)
        (self.proj / ".vacant").mkdir(parents=True)
        (self.proj / "inputs").mkdir()
        (self.proj / "inputs" / "ledger.csv").write_text(LEDGER)
        (self.proj / "inputs" / "summary.txt").write_text(SUMMARY_TXT)
        cp = self.proj / ".vacant" / "contract.json"
        cp.write_text(json.dumps(contract(self.dest, task_id), indent=2))
        subprocess.run(["git", "init", "-q", str(self.proj)], check=True)
        r = self.vacant("contract", "lock")
        assert r.returncode == 0, r.stderr

    def native_argv(self, prompt: str) -> list[str]:
        argv = super().native_argv(prompt)
        if self.agent == "codex" and getattr(self, "web", False):
            # 情境 F：`curl` 要連得到假網頁（workspace-write 預設不給網路）
            argv[2:2] = ["-c", "sandbox_workspace_write.network_access=true"]
        if self.agent == "pi" and getattr(self, "subagents", False):
            ext = self.bindir.parent / PI_SUBAGENT_EXT
            argv[1:1] = ["-e", str(ext)]
            agents = self.home / ".pi" / "agent" / "agents"
            agents.mkdir(parents=True, exist_ok=True)
            (agents / "worker.md").write_text(PI_WORKER)
        return argv

    def trace_dir(self) -> pathlib.Path | None:
        base = self.vhome / "trace" / "projects"
        if not base.is_dir():
            return None
        for d in base.iterdir():
            try:
                st = json.loads((d / "state.json").read_text())
            except (OSError, ValueError):
                continue
            if pathlib.Path(st.get("workspace", "")).resolve() == self.proj.resolve():
                return d
        return None

    def trace_events(self) -> list[dict]:
        r = self.vacant("trace", "show", "--json")
        try:
            return json.loads(r.stdout)
        except ValueError:
            return []


def judge(scn: str, finding: dict | None) -> dict:
    exp = EXPECT[scn]
    if finding is None:
        return {"correct": False, "why": "no finding"}
    bad = [k for k in ("state", "fault_class", "confidence") if finding.get(k) != exp[k]]
    if "step_writes" in exp:
        # 指到的那一步要是寫 `step_writes` 的那一步（從 trace show 對回去）
        if exp["step_writes"] not in (finding.get("_step_writes") or []):
            bad.append(f"step (wrote {finding.get('_step_writes')}, expected "
                       f"{exp['step_writes']})")
    if "source_path" in exp and (finding.get("source") or {}).get("path") != exp["source_path"]:
        bad.append(f"source {finding.get('source')}")
    if "source_kind" in exp and (finding.get("source") or {}).get("kind") != exp["source_kind"]:
        bad.append(f"source {finding.get('source')}")
    if exp.get("subagent") and not ((finding.get("step") or {}).get("actor") or {}).get("agent"):
        bad.append(f"actor is not a sub-agent ({(finding.get('step') or {}).get('actor')})")
    return {"correct": not bad, "mismatch": bad}


def run_one(lab: Lab, scn: str, timeout: float) -> dict:
    # 每個情境一個自己的專案目錄 ⇒ 自己的一條病歷（同一個路徑重設會被記成一個缺口，也會
    # 讓前一個情境的結論混進來——2026-09-24 第一跑就是這樣讀錯的）
    lab.proj = lab.root / f"proj-{scn.split('_')[0].lower()}"
    lab.reset_project(f"q-total-{scn.split('_')[0].lower()}")
    lab.mock_log.unlink(missing_ok=True)
    lab.subagents = scn.startswith(("E_", "G_"))
    lab.web = scn.startswith("F_")
    lab.start_mock(SCENARIOS[scn])
    t0 = time.time()
    env = lab.env()
    if lab.web:
        # 情境 F：假網站走代理（假模型兼代理）；模型請求本身直連本機，不經代理
        env.update(http_proxy=f"http://127.0.0.1:{lab.port}",
                   no_proxy="127.0.0.1,localhost", NO_PROXY="127.0.0.1,localhost")
    try:
        cp = subprocess.run(lab.native_argv(PROMPT), cwd=lab.proj, env=env,
                            capture_output=True, text=True, timeout=timeout,
                            stdin=subprocess.DEVNULL)
        rc, err_tail = cp.returncode, cp.stderr[-400:]
    except subprocess.TimeoutExpired:
        rc, err_tail = None, "timeout"
    wall = round(time.time() - t0, 1)
    lab.stop_mock()
    time.sleep(3)                                   # 背景的 submit／finalize
    if scn == "D_unrecorded_change":
        # 負控制：agent 走了之後，有人在外面把報告改掉（沒有任何一步做這件事）
        (lab.proj / "report.md").write_text("# Quarter\n\nTotal: 999\n")
        lab.vacant("trace", "report", "--check")
    else:
        for _ in range(30):                          # 等 finalize 寫完（OpenCode run 沒有 Stop）
            if any(e["type"] == "finding" for e in lab.trace_events()):
                break
            time.sleep(1)
    evs = lab.trace_events()
    steps = {e.get("n"): e for e in evs if e["type"] == "step"}
    findings = [e for e in evs if e["type"] == "finding" and e.get("status") == "open"
                and e.get("claim") == "total"]
    f = dict(findings[0]) if findings else None
    if f and f.get("step"):
        s = steps.get(f["step"].get("n")) or {}
        f["_step_writes"] = [w["path"] for w in s.get("writes") or []]
        f["_step_tool"] = s.get("tool")
    mock = [json.loads(x) for x in lab.mock_log.read_text().splitlines()] \
        if lab.mock_log.is_file() else []
    fb = [m.get("feedback") for m in mock if m.get("feedback")]
    td = lab.trace_dir()
    perf = []
    if td and (td / "perf.jsonl").is_file():
        perf = [json.loads(x)["ms"] for x in (td / "perf.jsonl").read_text().splitlines()]
    ver = lab.vacant("trace", "verify")
    decisions = [e for e in lab.ledger() if e["type"] == "decision"]
    return {
        "scenario": scn, "agent_rc": rc, "wall_s": wall, "agent_stderr_tail": err_tail,
        "steps_recorded": len(steps),
        "step_tools": [s.get("tool") for _n, s in sorted(steps.items())],
        "gaps": sum(1 for e in evs if e["type"] == "unrecorded_change"),
        "finding": {k: f.get(k) for k in ("state", "fault_class", "confidence", "layer",
                                          "location", "value", "source", "note", "_step_writes",
                                          "_step_tool")} | {
            "step_n": (f.get("step") or {}).get("n"),
            "actor": (f.get("step") or {}).get("actor")} if f else None,
        "judgement": judge(scn, f),
        "feedback_reached_model": bool(fb),
        "feedback_text": fb[0][:600] if fb else None,
        "feedback_has_location": bool(fb) and "report.md:" in fb[0],
        "feedback_has_actor_id": bool(fb) and any(
            str((((f or {}).get("step") or {}).get("actor") or {}).get(k) or "~~") in fb[0]
            for k in ("agent", "agent_type")),
        "resolved_after_feedback": any(e["type"] == "finding" and e.get("status") == "resolved"
                                       for e in evs),
        "final_decision": decisions[-1].get("outcome") if decisions else None,
        "chain_verifies": ver.returncode == 0, "chain_verify_out": ver.stdout.strip()[:120],
        "hook_ms_p50": round(statistics.median(perf), 1) if perf else None,
        "hook_ms_p95": round(sorted(perf)[max(0, int(len(perf) * 0.95) - 1)], 1) if perf else None,
        "hook_calls": len(perf),
        "model_requests": len(mock),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--agents", default="claude,codex,pi,opencode")
    ap.add_argument("--scenarios", default=",".join(SCENARIOS))
    ap.add_argument("--timeout", type=float, default=240)
    args = ap.parse_args()
    out = pathlib.Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    results = {"schema": "vacant-e2e-trace/1", "evidence_level": "L-fake (scripted model)",
               "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "agents": {}}
    for agent in args.agents.split(","):
        root = out / agent
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True)
        lab = Lab(agent, root, pathlib.Path(args.bin).resolve())
        lab.user_config()
        vers = subprocess.run(lab.native_argv("x")[:1] + ["--version"], env=lab.env(),
                              capture_output=True, text=True, timeout=60)
        inst = subprocess.run([PY, "-m", "vacant_network", "install", "--agents", agent],
                              env=lab.env(), capture_output=True, text=True, timeout=120)
        res = {"version": (vers.stdout or vers.stderr).strip().splitlines()[:1],
               "install_exit": inst.returncode, "runs": {}}
        try:
            for scn in args.scenarios.split(","):
                if agent not in ONLY.get(scn, {agent}):
                    continue                    # 這個平台沒有這種東西（例：背景子 agent）
                try:
                    res["runs"][scn] = run_one(lab, scn, args.timeout)
                except Exception as e:  # noqa: BLE001 — 一格壞了照記，不拖垮整張表
                    lab.stop_mock()
                    res["runs"][scn] = {"scenario": scn, "harness_error": repr(e)[:400],
                                        "judgement": {"correct": False, "why": "harness error"},
                                        "finding": None}
                j = res["runs"][scn]["judgement"]
                print(f"[e2e-trace] {agent} {scn}: {'OK' if j['correct'] else 'MISS'} "
                      f"{j.get('mismatch') or ''}", flush=True)
        finally:
            lab.stop_mock()
        act = subprocess.run([PY, "-m", "vacant_network", "trace", "actors", "--json"],
                             env=lab.env(), capture_output=True, text=True, timeout=60,
                             cwd=lab.root)
        try:
            res["actors"] = json.loads(act.stdout)
        except ValueError:
            res["actors"] = {"raw": act.stdout[-300:], "stderr": act.stderr[-300:]}
        results["agents"][agent] = res
    results["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    (out / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False))
    (out / "SUMMARY.md").write_text(summary(results))
    print(summary(results))
    return 0


def summary(r: dict) -> str:
    lines = ["# e2e_trace — four real agents × planted-fault scenarios (L-fake)", "",
             f"started {r.get('started')} · finished {r.get('finished')}", "",
             "| agent | scenario | attribution | got (state / class / grade) | step | "
             "feedback reached model | located in feedback | actor id in feedback | "
             "resolved | final | chain | hook p95 ms |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    n = ok = 0
    for a, res in r["agents"].items():
        for scn, x in res["runs"].items():
            f = x.get("finding") or {}
            n += 1
            if x.get("harness_error"):
                lines.append(f"| {a} | {scn} | ❌ harness error: {x['harness_error'][:80]} |"
                             + " |" * 10)
                continue
            ok += int(x["judgement"]["correct"])
            lines.append(
                f"| {a} | {scn} | {'✅' if x['judgement']['correct'] else '❌ ' + '; '.join(x['judgement'].get('mismatch') or [x['judgement'].get('why', '')])} "
                f"| {f.get('state')} / {f.get('fault_class')} / {f.get('confidence')} "
                f"| {f.get('step_n')} {f.get('_step_tool') or ''} "
                f"| {x['feedback_reached_model']} | {x['feedback_has_location']} "
                f"| {x['feedback_has_actor_id']} | {x['resolved_after_feedback']} "
                f"| {x['final_decision']} | {x['chain_verifies']} | {x['hook_ms_p95']} |")
    lines += ["", f"**attribution correct: {ok}/{n}**", ""]
    for a, res in r["agents"].items():
        st = res.get("actors") or {}
        lines.append(f"- {a} actors: " + json.dumps(
            {"cells": [(c.get('label'), c.get('runs'), c.get('accepted'),
                        c.get('provable_faults')) for c in st.get('cells', [])],
             "sources": {k: v.get('count') for k, v in (st.get('sources') or {}).items()},
             "gaps": st.get("coverage_gaps")}, ensure_ascii=False))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
