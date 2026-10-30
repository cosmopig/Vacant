#!/usr/bin/env python3
"""opencode_cell_audit — OpenCode 實驗格子唯讀審計量具（成本 ＋ C 臂 Vacant 證據）。
- events.jsonl（OpenCode）：model_calls（outer type step_finish）、tokens input/output/total、
  tool_calls（outer type tool_use）與工具分佈。
- C 臂 vacant_home.tgz：review 判定分佈（hooks events 的 action）＋ trace 鏈
  （seq 連續、prev_hash 串接以 vacant_network.logbook._entry_hash 重算）。
誠實規則（與 p02_carm_audit 同規矩）：格未完成（無 cell.json）→ state=incomplete，
全 NA、不計入退出碼判定；.infra- 隔離目錄 → state=quarantined_infra，同不計入。
唯讀、不寫任何位置。用法：
  python3 ops/vlab/tools/opencode_cell_audit.py --runs-dir <dir> [--json]
  python3 ops/vlab/tools/opencode_cell_audit.py --selftest
退出碼：0 全部 OK；1 有格子 FAIL/UNKNOWN；2 selftest 失敗。
"""
import argparse, json, re, shutil, sys, tarfile, tempfile
from collections import Counter
from pathlib import Path

STEP, TOOL, ZERO64 = ("step_finish", "step-finish"), ("tool_use", "tool"), "0" * 64
_SECOND_RE = re.compile(r"opencode|\bpi\b")  # 第二 agent 證據：opencode / pi 獨立字詞（pip 等不誤中）


def _i(x) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def _cmd_text(e: dict) -> str:
    """tool_use 事件命令文字多路徑收集（OpenCode part 形態不固定：command/input/state）。"""
    bits: list[str] = []

    def walk(x) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(v, str) and k in ("command", "cmd", "input"):
                    bits.append(v)
                elif isinstance(v, dict) and k in ("part", "input", "state"):
                    walk(v)

    walk(e)
    return " ".join(bits)


def parse_events(path) -> dict:
    """OpenCode events.jsonl → 成本統計（model_calls/tokens/tool_calls）＋ M 臂第二 agent 偵測。"""
    st = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0,
          "total_tokens": 0, "tool_calls": 0, "tools": {}, "has_second_agent": False}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            e = json.loads(line.strip()) if line.strip() else {}
        except json.JSONDecodeError:
            continue
        if not isinstance(e, dict):
            continue
        t, part = e.get("type"), e.get("part") if isinstance(e.get("part"), dict) else {}
        if t in STEP:
            tk = part.get("tokens") or e.get("tokens") or {}
            st["model_calls"] += 1
            st["input_tokens"] += _i(tk.get("input"))
            st["output_tokens"] += _i(tk.get("output"))
            st["total_tokens"] += _i(tk.get("total"))
        elif t in TOOL:
            st["tool_calls"] += 1
            tool = part.get("tool")
            if tool:
                st["tools"][tool] = st["tools"].get(tool, 0) + 1
                if tool in ("bash", "shell") and _SECOND_RE.search(_cmd_text(e)):
                    st["has_second_agent"] = True
    return st


def _link_ok(rows: list) -> str:
    """重算 prev_hash 串接：'ok'/'broken'/'unknown'（vacant_network 不可匯入時）。"""
    try:
        from vacant_network.logbook import _entry_hash
    except Exception:
        return "unknown"
    prev = ZERO64
    for i, r in enumerate(rows):
        if r.get("seq") != i + 1 or r.get("prev_hash") != prev:
            return "broken"
        prev = _entry_hash(r.get("stream_id"), r.get("branch_id"), r.get("seq"),
                           r.get("prev_hash"), r.get("ts_ms"), r.get("type"), r.get("payload"))
    return "ok"


def _find(tf, want: str):
    for n in tf.getnames():
        m = n[2:] if n.startswith("./") else n
        if m == want or m.endswith("/" + want):
            return n
    return None


def _ndjson(f) -> list:
    return [json.loads(l) for l in f.read().decode("utf-8", "replace").splitlines() if l.strip()]


def audit_vacant_home(tgz) -> dict:
    """C 臂 vacant_home.tgz → review 判定分佈 ＋ trace 鏈驗證（唯讀）。"""
    out: dict = {}
    with tarfile.open(tgz, "r:gz") as tf:
        hm = _find(tf, ".vacant/intake/hooks/events.jsonl")
        evs = _ndjson(tf.extractfile(hm)) if hm else None
        if evs is None:
            out["review"] = None
        else:
            out["review"] = {"n": len(evs), "actions": dict(Counter(str(e.get("action")) for e in evs)),
                             "denied": sum(1 for e in evs if e.get("action") != "allow")}
        cm = _find(tf, "chain.ndjson")
        if cm:
            rows = _ndjson(tf.extractfile(cm))
            out["trace"] = {"chain": cm[2:] if cm.startswith("./") else cm, "n_entries": len(rows),
                            "seq_ok": all(r.get("seq") == i + 1 for i, r in enumerate(rows)),
                            "prev_link": _link_ok(rows)}
    return out


def audit_cell(cell_path) -> dict:
    """審計一個格子（唯讀）→ JSON 可序列化 dict。未完成格＝state=incomplete＋NA（p02 規矩）。"""
    cell = Path(cell_path)
    cj = cell / "cell.json"
    if ".infra-" in cell.name:
        state = "quarantined_infra"
    elif not cj.is_file():
        state = "incomplete"
    else:
        state = None
    if state is not None:
        return {"cell": cell.name, "state": state, "ok": None, "unknown": [],
                "arm": None, "agent_rc": None, "wall_s": None, "events": None, "vacant": None,
                "score_pass": None}
    meta = json.loads(cj.read_text(encoding="utf-8"))
    rec: dict = {"cell": cell.name, "state": "complete", "ok": True, "unknown": [], "score_pass": None}
    rec.update(arm=meta.get("arm"), agent_rc=meta.get("agent_rc"), wall_s=meta.get("wall_s"))
    sp = cell / "score.json"
    if sp.is_file():
        try:
            sc = json.loads(sp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            sc = None
        if isinstance(sc, dict) and isinstance(sc.get("pass"), bool):
            rec["score_pass"] = sc["pass"]
    ev = cell / "events.jsonl"
    if ev.is_file():
        rec["events"] = parse_events(ev)
    else:
        rec["ok"] = False
        rec["unknown"].append("events.jsonl missing")
    if rec["arm"] == "M":  # e004 封包 §3：M 臂須有真第二 agent 證據，否則 H-review(M) UNKNOWN
        rec["second_agent_verified"] = bool((rec.get("events") or {}).get("has_second_agent"))
        if not rec["second_agent_verified"]:
            rec["unknown"].append("M arm lacks second agent execution evidence (H-review(M) UNKNOWN)")

    tgz = cell / "vacant_home.tgz"
    if tgz.is_file():
        v = audit_vacant_home(tgz)
        rec["vacant"] = v
        if v.get("review") is None:
            rec["unknown"].append("review missing (hooks events unreadable)")
        tr = v.get("trace")
        if tr and (tr.get("prev_link") in ("broken", "unknown") or tr.get("seq_ok") is False):
            rec["ok"] = False
            rec["unknown"].append(f"trace {tr.get('prev_link')}")
    elif rec["arm"] == "C":
        rec["ok"] = False
        rec["unknown"].append("vacant_home.tgz missing (arm C)")
    return rec


def summarize(recs: list) -> dict:
    """分臂成本彙總（complete 且有 arm）＋ 2×A 成本紅線（e004 封包 §3：calls 或 tokens 任一 > 2×A）。"""
    arms: dict = {}
    for r in recs:
        if r.get("state") != "complete" or not r.get("arm"):
            continue
        g = arms.setdefault(r["arm"], {"cells": 0, "pass": 0, "model_calls": 0, "total_tokens": 0})
        ev = r.get("events") or {}
        g["cells"] += 1
        g["pass"] += 1 if r.get("score_pass") is True else 0
        g["model_calls"] += _i(ev.get("model_calls"))
        g["total_tokens"] += _i(ev.get("total_tokens"))
    per_arm: dict = {}
    for arm, g in sorted(arms.items()):
        d = dict(g)
        d["calls_per_success"] = g["model_calls"] / g["pass"] if g["pass"] > 0 else None
        d["tokens_per_success"] = g["total_tokens"] / g["pass"] if g["pass"] > 0 else None
        per_arm[arm] = d
    base = per_arm.get("A")
    if base and base.get("tokens_per_success"):
        for d in per_arm.values():
            d["calls_vs_A"] = d["calls_per_success"] / base["calls_per_success"] if d["calls_per_success"] else None
            d["tokens_vs_A"] = d["tokens_per_success"] / base["tokens_per_success"] if d["tokens_per_success"] else None
            d["over_2x_A_cost"] = (d["calls_vs_A"] is not None and d["calls_vs_A"] > 2) or \
                                 (d["tokens_vs_A"] is not None and d["tokens_vs_A"] > 2)
    return {"per_arm": per_arm}


def _mock_cell(root: Path, name: str, arm: str, tamper: bool = False, score_pass: bool | None = None,
               bash_command: str | None = None) -> Path:
    """合成 mock 格子：OpenCode 格式 events.jsonl ＋（C 臂）vacant_home.tgz；bash_command 可注入第二 agent 命令。"""
    cell = root / name
    cell.mkdir(parents=True)
    (cell / "cell.json").write_text(json.dumps(
        {"exp": "mock", "cell": name, "arm": arm, "agent": "opencode", "agent_rc": 0, "wall_s": 1.5}), encoding="utf-8")
    ev = [{"type": "step_finish", "part": {"type": "step-finish", "tokens": {"total": 300, "input": 100, "output": 10, "cache": {"write": 0, "read": 0}}}},
          {"type": "step_finish", "part": {"type": "step-finish", "tokens": {"total": 500, "input": 200, "output": 20}}},
          {"type": "tool_use", "part": {"type": "tool", "tool": "read"}}]
    bash_ev = {"type": "tool_use", "part": {"type": "tool", "tool": "bash"}}
    if bash_command:
        bash_ev["part"]["command"] = bash_command
    ev.append(bash_ev)
    ev += [{"type": "tool_use", "part": {"type": "tool", "tool": "read"}},
           {"type": "text", "text": "noise"}, "not-json"]
    (cell / "events.jsonl").write_text("\n".join(json.dumps(x) if not isinstance(x, str) else x for x in ev) + "\n", encoding="utf-8")
    if arm == "C":
        home = root / (name + "_home")
        (home / ".vacant/intake/hooks").mkdir(parents=True)
        (home / ".vacant/intake/hooks/events.jsonl").write_text(
            "\n".join(json.dumps({"event": k, "action": a}) for k, a in
                      [("prompt", "allow"), ("pre_tool", "allow"), ("post_tool", "deny"), ("session_end", "allow")]) + "\n",
            encoding="utf-8")
        from vacant_network.identity import Identity
        from vacant_network.logbook import Logbook
        book, me = Logbook(), Identity.generate()
        book.append("prompt", {"text_blob": "aa"}, me, ts_ms=1)
        book.append("step", {"file": "a.py"}, me, ts_ms=2)
        (home / ".vacant/trace/projects/p1").mkdir(parents=True)
        ch = home / ".vacant/trace/projects/p1/chain.ndjson"
        book.save(ch)
        if tamper:  # 破壞對照：改第一筆 payload → 串接必 broken
            rows = _ndjson(ch.open("rb"))
            rows[0]["payload"]["text_blob"] = "TAMPERED"
            ch.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        with tarfile.open(cell / "vacant_home.tgz", "w:gz") as tf:
            tf.add(home, arcname=".")
    if score_pass is not None:
        (cell / "score.json").write_text(json.dumps(
            {"pass": score_pass, "tests_passed": 2 if score_pass else 0, "tests_total": 2}), encoding="utf-8")
    return cell


def selftest() -> bool:
    root = Path(tempfile.mkdtemp(prefix="ocaudit_"))
    try:
        a = audit_cell(_mock_cell(root, "mock-opencode-A-r1", "A", score_pass=True))
        c = audit_cell(_mock_cell(root, "mock-opencode-C-r1", "C", score_pass=True))
        t = audit_cell(_mock_cell(root, "mock-opencode-C-tampered", "C", tamper=True, score_pass=False))
        f = audit_cell(_mock_cell(root, "mock-opencode-C-nopass", "C", score_pass=False))
        (root / "mock-opencode-A-incomplete").mkdir()  # 無 cell.json → incomplete（p02 規矩）
        i = audit_cell(root / "mock-opencode-A-incomplete")
        m = audit_cell(_mock_cell(root, "mock-opencode-M-r1", "M", bash_command="pi run --model x", score_pass=True))
        m2 = audit_cell(_mock_cell(root, "mock-opencode-M-noagent", "M", score_pass=False))
        exp_ev = {"model_calls": 2, "input_tokens": 300, "output_tokens": 30,
                  "total_tokens": 800, "tool_calls": 3, "tools": {"read": 2, "bash": 1}, "has_second_agent": False}
        per_arm = summarize([a, c, t, f, i, m, m2])["per_arm"]
        return (a["events"] == exp_ev and a["arm"] == "A" and a["ok"] and "vacant" not in a
                and c["arm"] == "C" and c["ok"] and not c["unknown"]
                and c["vacant"]["review"] == {"n": 4, "actions": {"allow": 3, "deny": 1}, "denied": 1}
                and c["vacant"]["trace"]["n_entries"] == 2 and c["vacant"]["trace"]["seq_ok"] is True
                and c["vacant"]["trace"]["prev_link"] == "ok"
                and t["vacant"]["trace"]["prev_link"] == "broken" and t["ok"] is False
                and i["state"] == "incomplete" and i["ok"] is None and i["events"] is None
                and i["unknown"] == []
                and a["score_pass"] is True and c["score_pass"] is True
                and t["score_pass"] is False and f["score_pass"] is False and i["score_pass"] is None
                and m["score_pass"] is True and m2["score_pass"] is False
                and "second_agent_verified" not in a and m["second_agent_verified"] is True
                and m["events"]["has_second_agent"] is True and m["ok"] and not m["unknown"]
                and m2["second_agent_verified"] is False and m2["state"] == "complete"
                and "M arm lacks second agent execution evidence (H-review(M) UNKNOWN)" in m2["unknown"]
                and set(per_arm) == {"A", "C", "M"}
                and per_arm["A"] == {"cells": 1, "pass": 1, "model_calls": 2, "total_tokens": 800,
                                     "calls_per_success": 2.0, "tokens_per_success": 800.0,
                                     "calls_vs_A": 1.0, "tokens_vs_A": 1.0, "over_2x_A_cost": False}
                and per_arm["C"]["cells"] == 3 and per_arm["C"]["pass"] == 1
                and per_arm["C"]["model_calls"] == 6 and per_arm["C"]["total_tokens"] == 2400
                and per_arm["C"]["calls_per_success"] == 6.0 and per_arm["C"]["tokens_per_success"] == 2400.0
                and per_arm["C"]["calls_vs_A"] == 3.0 and per_arm["C"]["tokens_vs_A"] == 3.0
                and per_arm["C"]["over_2x_A_cost"] is True
                and per_arm["M"] == {"cells": 2, "pass": 1, "model_calls": 4, "total_tokens": 1600,
                                     "calls_per_success": 4.0, "tokens_per_success": 1600.0,
                                     "calls_vs_A": 2.0, "tokens_vs_A": 2.0, "over_2x_A_cost": False})
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="OpenCode 格子唯讀審計（成本 ＋ C 臂 Vacant 證據）")
    ap.add_argument("--runs-dir", type=Path, help="含格子子目錄的目錄（每個格子有 cell.json）")
    ap.add_argument("--json", action="store_true", help="JSON 摘要輸出（預設即 JSON；保留以穩定介面）")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        ok = selftest()
        print("opencode_cell_audit selftest " + ("PASS" if ok else "FAIL"))
        return 0 if ok else 2
    if not a.runs_dir or not a.runs_dir.is_dir():
        ap.error("--runs-dir 必給且存在（或用 --selftest）")
    cells = sorted(d for d in a.runs_dir.iterdir() if d.is_dir())
    recs = [audit_cell(c) for c in cells]
    bad = [r["cell"] for r in recs if r.get("state") == "complete" and (not r["ok"] or r["unknown"])]
    print(json.dumps({"tool": "opencode_cell_audit", "n_cells": len(recs), "bad": bad,
                      "summary": summarize(recs), "cells": recs},
                     ensure_ascii=False, indent=1))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
