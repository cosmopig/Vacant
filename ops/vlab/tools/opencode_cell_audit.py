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
import argparse, json, shutil, sys, tarfile, tempfile
from collections import Counter
from pathlib import Path

STEP, TOOL, ZERO64 = ("step_finish", "step-finish"), ("tool_use", "tool"), "0" * 64


def _i(x) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def parse_events(path) -> dict:
    """OpenCode events.jsonl → 成本統計（model_calls/tokens/tool_calls）。"""
    st = {"model_calls": 0, "input_tokens": 0, "output_tokens": 0,
          "total_tokens": 0, "tool_calls": 0, "tools": {}}
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
            if part.get("tool"):
                st["tools"][part["tool"]] = st["tools"].get(part["tool"], 0) + 1
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
                "arm": None, "agent_rc": None, "wall_s": None, "events": None, "vacant": None}
    meta = json.loads(cj.read_text(encoding="utf-8"))
    rec: dict = {"cell": cell.name, "state": "complete", "ok": True, "unknown": []}
    rec.update(arm=meta.get("arm"), agent_rc=meta.get("agent_rc"), wall_s=meta.get("wall_s"))
    ev = cell / "events.jsonl"
    if ev.is_file():
        rec["events"] = parse_events(ev)
    else:
        rec["ok"] = False
        rec["unknown"].append("events.jsonl missing")

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


def _mock_cell(root: Path, name: str, arm: str, tamper: bool = False) -> Path:
    """合成 mock 格子：OpenCode 格式 events.jsonl ＋（C 臂）vacant_home.tgz。"""
    cell = root / name
    cell.mkdir(parents=True)
    (cell / "cell.json").write_text(json.dumps(
        {"exp": "mock", "cell": name, "arm": arm, "agent": "opencode", "agent_rc": 0, "wall_s": 1.5}), encoding="utf-8")
    ev = [{"type": "step_finish", "part": {"type": "step-finish", "tokens": {"total": 300, "input": 100, "output": 10, "cache": {"write": 0, "read": 0}}}},
          {"type": "step_finish", "part": {"type": "step-finish", "tokens": {"total": 500, "input": 200, "output": 20}}},
          {"type": "tool_use", "part": {"type": "tool", "tool": "read"}},
          {"type": "tool_use", "part": {"type": "tool", "tool": "bash"}},
          {"type": "tool_use", "part": {"type": "tool", "tool": "read"}},
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
    return cell


def selftest() -> bool:
    root = Path(tempfile.mkdtemp(prefix="ocaudit_"))
    try:
        a = audit_cell(_mock_cell(root, "mock-opencode-A-r1", "A"))
        c = audit_cell(_mock_cell(root, "mock-opencode-C-r1", "C"))
        t = audit_cell(_mock_cell(root, "mock-opencode-C-tampered", "C", tamper=True))
        (root / "mock-opencode-A-incomplete").mkdir()  # 無 cell.json → incomplete（p02 規矩）
        i = audit_cell(root / "mock-opencode-A-incomplete")
        exp_ev = {"model_calls": 2, "input_tokens": 300, "output_tokens": 30,
                  "total_tokens": 800, "tool_calls": 3, "tools": {"read": 2, "bash": 1}}
        return (a["events"] == exp_ev and a["arm"] == "A" and a["ok"] and "vacant" not in a
                and c["arm"] == "C" and c["ok"] and not c["unknown"]
                and c["vacant"]["review"] == {"n": 4, "actions": {"allow": 3, "deny": 1}, "denied": 1}
                and c["vacant"]["trace"]["n_entries"] == 2 and c["vacant"]["trace"]["seq_ok"] is True
                and c["vacant"]["trace"]["prev_link"] == "ok"
                and t["vacant"]["trace"]["prev_link"] == "broken" and t["ok"] is False
                and i["state"] == "incomplete" and i["ok"] is None and i["events"] is None
                and i["unknown"] == [])
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
    print(json.dumps({"tool": "opencode_cell_audit", "n_cells": len(recs), "bad": bad, "cells": recs},
                     ensure_ascii=False, indent=1))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
