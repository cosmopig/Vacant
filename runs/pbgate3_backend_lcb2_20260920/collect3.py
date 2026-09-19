#!/usr/bin/env python3
"""把 30 格的落盤收成一份可攜的證據包，並做**事後**隱藏測資計分。

零模型呼叫。兩件事分得很開，報告裡也不准混：

  A. **閘門的判決**（`run_RUN-ON.json` 逐字）——這是被量的東西。
  B. **事後隱藏測資計分**（本檔自己跑的）——這是**衍生物**，用來把
     `vacant/suitegauge.py` 那句單邊保證（「擋得住已知壞解 ≠ 涵蓋真需求」）
     在公開題庫上量成一個數字。它**沒有**在跑的時候影響任何一格，
     也**沒有**任何一個位元組回饋給模型（V/GT 紅線）。

隱藏測資只在本檔執行的那一瞬間出現在一個 `/tmp` 暫存目錄裡，跑完就刪；
工作區、回饋、argv 三個地方都碰不到它。
"""
from __future__ import annotations
import hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path("/var/tmp/vacant_pbgate3")
REPO = ROOT / "repo"
R534 = REPO / "ops" / "gain" / "r534"
OUT = ROOT / "evidence"
TASKS = ["lcb_3522","lcb_3583","lcb_3584","lcb_3637","lcb_3654",
         "lcb_3681","lcb_3686","lcb_3700","lcb_3764","lcb_3794"]
AGENTS = ["pi","claude","opencode"]
ARM = "V"          # 本輪臂固定；變的維度是 agent
HIDDEN_TIMEOUT_S = 120

DRIVER = r'''
import importlib.util, os, sys, traceback, json
sys.path.insert(0, os.getcwd())
path = sys.argv[1]
spec = importlib.util.spec_from_file_location("hid", path)
mod = importlib.util.module_from_spec(spec)
out = {"cases": [], "import_error": None}
try:
    spec.loader.exec_module(mod)
except Exception as e:
    out["import_error"] = "%s: %s" % (type(e).__name__, e)
    print(json.dumps(out)); raise SystemExit
checks = [(n, v) for n, v in vars(mod).items() if n.startswith("check_") and callable(v)]
for cname, fn in checks:
    try:
        fn()
    except Exception as e:
        out["cases"].append({"case": cname, "ok": False,
                             "kind": type(e).__name__, "message": str(e)[:400]})
    else:
        out["cases"].append({"case": cname, "ok": True, "kind": "pass", "message": ""})
print(json.dumps(out))
'''

def sha(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()



#: 拒交格的**形狀**。收官要能分得開的四種，判準全部只看落盤欄位。
#:
#:   true_refuse     agent 交了東西、驗收沒過（assert／exception）⇒「交了但不對」
#:   no_delivery     rs>0（真的打了模型）但工作區裡沒有 solution.py ⇒ 驗收的失敗理由是
#:                   import／nofile 而不是答錯 ⇒「它根本沒交」
#:   timeout_killed  agent 被 `--timeout` 砍掉（`agent_timed_out=true`、`agent_rc<0`）
#:                   ⚠ r530vrun 踩過這個坑：被砍掉的格 `stop_reason` 跟正常失敗一樣是
#:                     `visible_fail`，**只看 stop_reason 分不出來**
#:   fake_refuse     `requests_seen == 0` 且 `wire_by_protocol` 空 ⇒ **中介根本沒發生**
#:                   除了 requests_seen，每個欄位都跟合法拒交格一樣
#:
#: ⚠ 一格可以同時是 timeout_killed 與 no_delivery；回傳的是一個**有序理由串**，
#:   不壓成單一標籤（壓成單一標籤就是把資訊丟掉）。
def classify(rec, visible_json):
    tags = []
    rs = rec.get("requests_seen") or 0
    wire = rec.get("wire_by_protocol") or {}
    if rs == 0 and not wire:
        tags.append("fake_refuse")
    if rec.get("agent_timed_out"):
        tags.append("timeout_killed")
    kinds = []
    if visible_json:
        for f in visible_json.get("files", []):
            for c in f.get("cases", []):
                if not c.get("ok"):
                    kinds.append(c.get("kind"))
    if kinds:
        if all(k in ("import", "nofile") for k in kinds):
            tags.append("no_delivery")
        elif any(k in ("assert", "exception") for k in kinds):
            tags.append("true_refuse")
        if "timeout" in kinds:
            tags.append("test_timeout")
    return {"tags": tags, "failing_case_kinds": sorted(set(kinds)),
            "solution_py_present": rec.get("solution_sha256") is not None}


def wire_usage(wdir: pathlib.Path):
    """把每一通回應的 `usage` 加起來。**來源是逐位元落盤的 `*.resp.bin`**，
    不是向後端另外問的。

    ⚠ 本輪比上一輪多一條路要走：**兩個 agent 講不同的 wire**。

      · pi 0.85.1        → OpenAI Chat Completions SSE（`data: {...}`，
                           `usage` 只出現在 `[DONE]` 前那一塊）
      · Claude Code 2.1.278 → Anthropic Messages SSE
                           （`message_start.message.usage.input_tokens` ＋
                            `message_delta.usage.output_tokens`）

    上一輪的解析器只認得 OpenAI 那條。**照抄過來會把 Claude Code 的 10 格全部
    算成 0 token**——「量到 0」跟「沒量到」是兩件事（鐵律 3）。所以這裡：
      1. 兩條 wire 都解析，且**分開記** `by_wire`；
      2. `no_usage` / `unparsed_chunks` 一律留著當自我檢查——它們不為 0
         就代表這個數字是下界，不是總數。

    **thinking 的全批證據**也在這裡算。判準（memory「兩張卡共 8 串」那條）：
      · OpenAI 路：巢狀 `usage.completion_tokens_details.reasoning_tokens`
        ＋ SSE 裡 `delta.reasoning_content` 的字元數；
      · ⚠ **頂層 `usage.reasoning_tokens` 不可以當判準**——兩台都回 None。
      · Anthropic 路：數 `content_block_start` 裡 type=`thinking` 的區塊
        （冒煙實測一格 2 個 ⇒ 這條 wire 上思考是**看得見**的）。
        ⚠ **它與 OpenAI 路的 `reasoning_tokens` 不是同一個量**：一個數區塊、
        一個數 token，**不可以相加、不可以互相換算**。Anthropic 路的
        `reasoning_tokens` 欄位在本輪一律是 0，那是**這條 wire 沒有這個欄位**，
        不是「思考是 0」。
    """
    if not wdir.exists():
        return {"status": "no_wire_dir"}
    tot = {"calls": 0, "with_usage": 0, "no_usage": 0, "unparsed_chunks": 0,
           "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
           "reasoning_tokens": 0, "reasoning_tokens_present": False,
           "reasoning_content_chars": 0, "anthropic_thinking_blocks": 0,
           "transport": set(), "by_wire": {}}

    def bump(wire, key, n=1):
        tot["by_wire"].setdefault(wire, {"calls": 0, "with_usage": 0,
                                         "prompt_tokens": 0, "completion_tokens": 0,
                                         "reasoning_tokens": 0,
                                         "reasoning_content_chars": 0})
        tot["by_wire"][wire][key] = tot["by_wire"][wire].get(key, 0) + n

    for f in sorted(wdir.glob("*.resp.bin")):
        tot["calls"] += 1
        raw = f.read_bytes().decode("utf-8", "replace")
        chunks = []
        if raw.lstrip().startswith("data:") or "\nevent:" in raw or raw.lstrip().startswith("event:"):
            tot["transport"].add("sse")
            for line in raw.splitlines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload or payload == "[DONE]":
                    continue
                try:
                    chunks.append(json.loads(payload))
                except Exception:
                    tot["unparsed_chunks"] += 1
        else:
            tot["transport"].add("json")
            try:
                chunks.append(json.loads(raw))
            except Exception:
                tot["unparsed_chunks"] += 1

        # 這一通是哪一條 wire？用 payload 自己說的 type 判，不用檔名猜。
        types = {c.get("type") for c in chunks if isinstance(c, dict)}
        is_anthropic = bool(types & {"message_start", "message_delta", "message_stop",
                                     "content_block_start", "content_block_delta"})
        wire = "anthropic_messages" if is_anthropic else "openai_chat"
        bump(wire, "calls")

        p_tok = c_tok = t_tok = 0
        r_tok = 0
        saw_usage = False
        for c in chunks:
            if not isinstance(c, dict):
                continue
            if is_anthropic:
                if c.get("type") == "message_start":
                    u = ((c.get("message") or {}).get("usage") or {})
                    if u:
                        saw_usage = True
                        if isinstance(u.get("input_tokens"), int):
                            p_tok = u["input_tokens"]
                        if isinstance(u.get("output_tokens"), int):
                            c_tok = max(c_tok, u["output_tokens"])
                elif c.get("type") == "message_delta":
                    u = c.get("usage") or {}
                    if u:
                        saw_usage = True
                        if isinstance(u.get("output_tokens"), int):
                            c_tok = max(c_tok, u["output_tokens"])
                        if isinstance(u.get("input_tokens"), int):
                            p_tok = max(p_tok, u["input_tokens"])
                elif c.get("type") == "content_block_start":
                    if ((c.get("content_block") or {}).get("type")) == "thinking":
                        tot["anthropic_thinking_blocks"] += 1
                elif c.get("type") == "content_block_delta":
                    if ((c.get("delta") or {}).get("type")) == "thinking_delta":
                        tot["anthropic_thinking_blocks"] += 0  # 只數 block_start
                elif c.get("type") is None and isinstance(c.get("usage"), dict):
                    u = c["usage"]; saw_usage = True
                    p_tok = max(p_tok, u.get("input_tokens") or 0)
                    c_tok = max(c_tok, u.get("output_tokens") or 0)
            else:
                for ch in (c.get("choices") or []):
                    d = ch.get("delta") or ch.get("message") or {}
                    rc = d.get("reasoning_content")
                    if isinstance(rc, str):
                        tot["reasoning_content_chars"] += len(rc)
                        bump(wire, "reasoning_content_chars", len(rc))
                u = c.get("usage")
                if isinstance(u, dict):
                    saw_usage = True
                    if isinstance(u.get("prompt_tokens"), int):
                        p_tok = u["prompt_tokens"]
                    if isinstance(u.get("completion_tokens"), int):
                        c_tok = u["completion_tokens"]
                    if isinstance(u.get("total_tokens"), int):
                        t_tok = u["total_tokens"]
                    det = u.get("completion_tokens_details") or {}
                    if isinstance(det, dict) and "reasoning_tokens" in det:
                        tot["reasoning_tokens_present"] = True
                        if isinstance(det.get("reasoning_tokens"), int):
                            r_tok = det["reasoning_tokens"]
        if not saw_usage:
            tot["no_usage"] += 1
        else:
            tot["with_usage"] += 1
            bump(wire, "with_usage")
        tot["prompt_tokens"] += p_tok
        tot["completion_tokens"] += c_tok
        tot["total_tokens"] += (t_tok or (p_tok + c_tok))
        tot["reasoning_tokens"] += r_tok
        bump(wire, "prompt_tokens", p_tok)
        bump(wire, "completion_tokens", c_tok)
        bump(wire, "reasoning_tokens", r_tok)
    tot["transport"] = sorted(tot["transport"])
    return tot


def score_hidden(tid: str, solution: pathlib.Path):
    """把 frozen 的 solution.py 丟進暫存目錄，對 hidden/<tid>/test_hidden.py 跑一次。"""
    hid = R534 / "hidden" / tid / "test_hidden.py"
    if not hid.exists():
        return {"status": "no_hidden_file"}
    if solution is None or not solution.exists():
        return {"status": "no_solution", "passed": 0, "total": None}
    tmp = tempfile.mkdtemp(prefix="pbgate_hidden_")
    try:
        shutil.copy2(solution, os.path.join(tmp, "solution.py"))
        drv = os.path.join(tmp, "_driver.py")
        open(drv, "w", encoding="utf-8").write(DRIVER)
        hid_copy = os.path.join(tmp, "test_hidden.py")
        shutil.copy2(hid, hid_copy)
        try:
            r = subprocess.run([sys.executable, drv, hid_copy], cwd=tmp,
                               capture_output=True, text=True, timeout=HIDDEN_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "timeout_s": HIDDEN_TIMEOUT_S}
        line = (r.stdout or "").strip().splitlines()
        if not line:
            return {"status": "driver_error", "stderr_tail": (r.stderr or "")[-400:]}
        try:
            d = json.loads(line[-1])
        except Exception:
            return {"status": "driver_error", "stdout_tail": (r.stdout or "")[-400:],
                    "stderr_tail": (r.stderr or "")[-400:]}
        if d.get("import_error"):
            return {"status": "import_error", "message": d["import_error"],
                    "passed": 0, "total": None}
        cases = d["cases"]
        return {"status": "ok",
                "passed": sum(1 for c in cases if c["ok"]), "total": len(cases),
                "all_pass": all(c["ok"] for c in cases),
                "first_failure": next((c for c in cases if not c["ok"]), None)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)   # 隱藏測資不留在磁碟上


def hidden_scorer_negative_control():
    """**負控制：證明這支計分器抓得到壞解。**

    沒有這一條，「每一個交付格的隱藏測資都全過」是一句不可信的話——一個永遠說 pass
    的計分器會印出一模一樣的結果。判準沿用 R534 `gauge_bank.py` 的退化樁：
    整支 `solution.py` 只有 `def <entry_point>(*a, **k): return None`，
    **每一題的隱藏檔都必須判它不過**。有一題沒擋住 ⇒ 這一節的數字全部不可引用。
    """
    out = {}
    man = json.loads((R534 / "bank_manifest.json").read_text(encoding="utf-8"))
    for tid in TASKS:
        ep = man["tasks"][tid]["entry_point"]
        tmp = tempfile.mkdtemp(prefix="pbgate_negctl_")
        try:
            stub = pathlib.Path(tmp) / "solution.py"
            stub.write_text("def %s(*a, **k):\n    return None\n" % ep, encoding="utf-8")
            r = score_hidden(tid, stub)
            out[tid] = {"status": r.get("status"), "passed": r.get("passed"),
                        "total": r.get("total"), "all_pass": r.get("all_pass")}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    blocked = [t for t, v in out.items() if v.get("all_pass") is not True]
    return {"stub": "def <entry_point>(*a, **k): return None",
            "per_task": out,
            "blocked_n": len(blocked), "tasks_n": len(TASKS),
            "verdict": "OK" if len(blocked) == len(TASKS) else "FAIL",
            "honesty": "單邊：擋得住這一個退化樁 ≠ 這份隱藏套件涵蓋了真需求。"}


def main():
    man = json.loads((R534 / "bank_manifest.json").read_text(encoding="utf-8"))
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "cells").mkdir(parents=True)
    cells = []
    for agent in AGENTS:
        for tid in TASKS:
            name = f"{tid}_{agent}"
            rd = ROOT / f"rd_{name}"
            cd = OUT / "cells" / name
            cd.mkdir(parents=True)
            rec = {"cell": name, "task_id": tid, "agent": agent, "arm": ARM,
                   "bank": "lcb_v2", "layer": man["tasks"][tid]["layer"],
                   "difficulty": man["tasks"][tid]["difficulty"],
                   "entry_point": man["tasks"][tid]["entry_point"],
                   "n_visible_cases": man["tasks"][tid]["n_visible_cases"],
                   "n_hidden_cases_full": man["tasks"][tid]["n_hidden_cases_full"]}
            f = rd / "run_RUN-ON.json"
            if not f.exists():
                rec["status"] = "MISSING_run_json"
                cells.append(rec); continue
            d = json.loads(f.read_text(encoding="utf-8"))
            for k in ("vacant","accepted","refused","stop_reason","requests_seen",
                      "wire_by_protocol","wire_errors","agent_rc","agent_timed_out",
                      "infra_void","agent_wall_s","run_wall_s","visible_passed",
                      "visible_total","ws_start_sha256","ws_end_sha256","wire_digest",
                      "verdict_sha256","verdict_hash","upstreams","upstreams_defaulted",
                      "attempts_used","max_attempts","retry","feedback_into","sandbox"):
                if k in d:
                    rec[k] = d[k]
            ec = rd / "_launcher_exit_code.txt"
            rec["exit_code"] = int(ec.read_text().strip()) if ec.exists() else None
            cw = rd / "_cell_wall_s.txt"
            if cw.exists():
                rec["cell_wall_s"] = float(cw.read_text().strip().split("=")[-1])
            # 可見驗收逐條（含每個測試檔的 wall_ms——第二輪要用它定 --test-timeout）
            vj = rd / "visible_RUN-ON.json"
            if vj.exists():
                v = json.loads(vj.read_text(encoding="utf-8"))
                rec["visible_all_pass"] = v.get("all_pass")
                rec["visible_wall_ms"] = [fr.get("wall_ms") for fr in v.get("files", [])]
                shutil.copy2(vj, cd / "visible_RUN-ON.json")
            # frozen 的交付物（驗收實際跑的那一份）
            sol = rd / "_frozen_RUN-ON" / "solution.py"
            if sol.exists():
                rec["solution_bytes"] = sol.stat().st_size
                rec["solution_sha256"] = sha(sol)
                rec["solution_text"] = sol.read_text(encoding="utf-8", errors="replace")
                shutil.copy2(sol, cd / "solution.py")
            else:
                rec["solution_bytes"] = None; rec["solution_sha256"] = None
            rec["hidden_posthoc"] = score_hidden(tid, sol if sol.exists() else None)
            vj_obj = json.loads(vj.read_text(encoding="utf-8")) if vj.exists() else None
            rec["refusal_shape"] = (classify(rec, vj_obj)
                                    if rec.get("accepted") is not True else None)
            for n in ("run_RUN-ON.json","receipts_RUN-ON.ndjson","receipts_RUN-ON.pub.json",
                      "rows.jsonl","agent_stdout.log","_launcher_exit_code.txt"):
                if (rd / n).exists():
                    shutil.copy2(rd / n, cd / n)
            wi = rd / "wire_RUN-ON" / "index.jsonl"
            if wi.exists():
                (cd / "wire").mkdir(exist_ok=True)
                shutil.copy2(wi, cd / "wire" / "index.jsonl")
            rec["wire_usage"] = wire_usage(rd / "wire_RUN-ON")
            av = ROOT / "argv" / f"{name}.argv.txt"
            if av.exists():
                shutil.copy2(av, cd / "argv.txt")
            cells.append(rec)
    negctl = hidden_scorer_negative_control()
    (OUT / "hidden_scorer_negative_control.json").write_text(
        json.dumps(negctl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("hidden scorer negative control:", negctl["verdict"],
          f'({negctl["blocked_n"]}/{negctl["tasks_n"]} 題擋住退化樁)')
    (OUT / "matrix.json").write_text(
        json.dumps({"cells": cells, "hidden_scorer_negative_control": negctl},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    # 摘要表
    lines = ["cell | agent | exit | accepted | stop | rs | rc | vis | hidden(事後) | agent_s | tok_out | reas"]
    for c in cells:
        h = c.get("hidden_posthoc", {})
        hs = (f"{h.get('passed')}/{h.get('total')}" if h.get("status") == "ok"
              else h.get("status", "?"))
        lines.append(" | ".join(str(x) for x in [
            c["cell"], c["agent"], c.get("exit_code"), c.get("accepted"),
            c.get("stop_reason"), c.get("requests_seen"), c.get("agent_rc"),
            f'{c.get("visible_passed")}/{c.get("visible_total")}', hs,
            round(c.get("agent_wall_s") or 0, 1),
            (c.get("wire_usage") or {}).get("completion_tokens"),
            (c.get("wire_usage") or {}).get("reasoning_tokens"),
            ",".join((c.get("refusal_shape") or {}).get("tags") or []) or "-"]))
    (OUT / "SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {OUT}")

if __name__ == "__main__":
    main()
