"""twin/gate_samples — 根據閘門（`grounding_gate.py`）的真跑覆蓋（2026-10-01，舊 VM，不是展場）。

這支在架構裡承重什麼：計畫 P7 §4——挑 sub_id 讓 `twinground` 抽中不同的關聯組，用 W3 那 6 組合成特質輪流跑
（真 pi＋真模型＋真 launcher 閘門），直到 B1、B2a–d、B3、B4、B5、B6 每一條至少真的發生 1 次，或跑滿 30 跑；
每一跑把**每一次 gate_ran 的四格結果與訊息、重改次數、最後 accepted、秒數**，以及**每一個 ✗ 被擋的那一行原文
與對應的地上出處**原樣收起來，讓人逐條判斷「真的沒根據」還是「閘門誤擋」。

用法（VM 上）：
    PYTHONPATH=<repo> python3 ops/exhibit/twin/gate_samples.py run --spec spec.json --out-dir <dir> \\
        --endpoint http://100.119.113.56:5500/v1 --timeout 300
    python3 ops/exhibit/twin/gate_samples.py report --out-dir <dir>

⚠ 合成特質（不是真人）；每一跑跑完就撤回（抹除暫存）。事件流（lifecycle＋旁註）在抹除前原樣存進 out-dir。
⚠ 分身是真模型：同一個 sub_id 重跑不保證同一個結果。覆蓋表只報「這幾跑裡真的發生過幾次」。
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import pathlib
import re
import shutil
import sys
import tempfile
import time
from typing import Any

HERE = pathlib.Path(__file__).resolve()
REPO = HERE.parents[3]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

BRANCHES = ("B1", "B2a", "B2b", "B2c", "B2d", "B3", "B4", "B5", "B6", "B7", "B8")
WINDOW_BRANCH = {"G1": "B2a", "G2": "B2b", "G3": "B2c", "G4": "B2d"}
_SEG_LOC = re.compile(r"(成品|計畫)(?:『([^』]*)』)?第\s?(\d+)\s?行")


def _lines(p: pathlib.Path) -> list[str]:
    try:
        return p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _line_at(frozen: pathlib.Path, where: str, name: str | None, ln: int) -> dict[str, Any]:
    from ops.exhibit.twin import grounding_gate as gg
    if where == "計畫":
        ls = _lines(frozen / "PLAN.md")
        return {"file": "PLAN.md", "line": ln, "text": ls[ln - 1] if 0 < ln <= len(ls) else None}
    arts = gg.read_artifacts(frozen)
    pick = None
    if name:
        pick = next((a for a in arts if a[0] == name), None)
    elif len(arts) >= 1:
        pick = arts[0]
    if not pick:
        return {"file": name, "line": ln, "text": None}
    ls = pick[1].splitlines()
    return {"file": pick[0], "line": ln, "text": ls[ln - 1] if 0 < ln <= len(ls) else None}


def _ground_hits(ground: dict[str, str], read: set[str], token: str) -> list[dict[str, Any]]:
    out = []
    pat = re.compile(r"(?<!\d)" + re.escape(token) + r"(?!\d)") if token.isdigit() else re.compile(re.escape(token))
    for rel, text in sorted(ground.items()):
        for i, ln in enumerate(text.splitlines(), 1):
            if pat.search(ln):
                out.append({"path": rel, "line": i, "text": ln.strip()[:120], "read": rel in read})
    return out[:8]


def evidence_for(case: str, message: str, frozen: pathlib.Path, ground: dict[str, str],
                 read: set[str]) -> list[dict[str, Any]]:
    """每一個 ✗ 的證據：被擋的那一行原文＋對應的地上出處（讓人判斷是真的沒根據還是誤擋）。"""
    from ops.exhibit.twin import grounding_gate as gg
    out = []
    for seg in [s for s in message.split("；") if s.strip()]:
        m = _SEG_LOC.search(seg)
        row: dict[str, Any] = {"message": seg}
        if m:
            row["blocked_line"] = _line_at(frozen, m.group(1), m.group(2), int(m.group(3)))
        toks = re.findall(r"『([^』]*)』", seg)
        if case == "check_w2_source":
            row["ground_origin"] = {t: _ground_hits(ground, read, t) for t in toks if not t.startswith("地上/")}
        elif case == "check_w3_agree":
            facts = gg.load_facts()
            ent = next((e for e in facts["entities"].values() if e["label"] in toks), None)
            paths = [t for t in toks if t.startswith("地上/")]
            if ent:
                subj = re.compile(ent["subject"])
                row["entity"] = ent["label"]
                row["authority_value"] = ent["authority_value"]
                row["ground_origin"] = {
                    p: [f"{i}: {ln.strip()[:100]}" for i, ln in enumerate(ground.get(p, "").splitlines(), 1)
                        if subj.search(ln)][:3] for p in paths}
        elif case == "check_w1_read":
            paths = [t for t in toks if t.startswith("地上/")]
            row["named_exists_on_ground"] = {p: (p in ground or any(g.startswith(p + "/") for g in ground))
                                             for p in paths}
        elif case == "check_w4_receipt":
            row["ground_lines_with_gate_words"] = [
                f"{rel}:{i}: {ln.strip()[:80]}" for rel, t in sorted(ground.items())
                for i, ln in enumerate(t.splitlines(), 1)
                if re.search(r"閘門|窗：|收據", ln)][:6]
        out.append(row)
    return out


def run_one(spec: dict[str, Any], endpoint: str, model: str, timeout: float,
            out_dir: pathlib.Path, enclose: str = "off", require_tier: str | None = None) -> dict[str, Any]:
    from ops.exhibit.twin import grounding_gate as gg
    from ops.exhibit.twin import sidecar as sidecarlib
    from ops.exhibit.twin import twinagent, twinground, twinlink, twinvault, w3b_samples
    from ops.exhibit.twin.twinstore import KIND_SUBMITTED, TwinStore
    from vacant_network.vrun import lifecycle

    persona = next(p for p in w3b_samples.PERSONAS if p["name"] == spec["persona"])
    sid = spec["sub_id"]
    name = spec["name"]
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="twin_gate_"))
    rec: dict[str, Any] = {"name": name, "persona": persona["name"], "sub_id_hash": hashlib.sha256(
        sid.encode()).hexdigest()[:12], "synthetic": True, "endpoint": endpoint,
        "model_requested": model, "timeout_s": timeout, "spec_note": spec.get("note"),
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        db, events = tmp / "twinstore.sqlite3", tmp / "lifecycle.jsonl"
        st = TwinStore(db)
        payload, secs = st.vault.seal_card(sid, persona["card"], persona["text"], ts=int(time.time() * 1000))
        twinvault.append_sealed(st, KIND_SUBMITTED, sid, payload, secs, source="gate_samples:synthetic", what="card")
        st.close()
        t0 = time.time()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = twinlink.main(["--db", str(db), "generate", "--endpoint", endpoint, "--model", model,
                                "--engine", "agent", "--parallel", "1", "--agent-timeout", str(timeout),
                                "--events", str(events), "--enclose", enclose]
                               + (["--require-tier", require_tier] if require_tier else []))
        rec["generate_rc"], rec["wall_s"] = rc, round(time.time() - t0, 1)
        st = TwinStore(db)
        tw = (st.current(sid) or {}).get("twin") or {}
        rec["twin"] = {k: tw.get(k) for k in (
            "engine", "degrade_kind", "decision", "run_id", "verdict_hash", "accepted", "stop_reason",
            "requests_seen", "agent_rc", "agent_timed_out", "latency_ms", "tier", "twin_id", "degrade_reason")}
        rec["outcome"] = twinlink.run_outcome(tw)
        rec["enclosed"], rec["enclosure_applied"] = tw.get("enclosed"), tw.get("enclosure_applied")
        rec["door_calls"] = tw.get("door_calls")
        ws, rd = twinagent.paths_for(twinagent.default_work_root(db), sid)

        man = json.loads((rd / "ground_manifest.json").read_text(encoding="utf-8")) \
            if (rd / "ground_manifest.json").is_file() else {}
        rec["ground_groups"] = man.get("groups")
        rec["ground_files"] = [f["path"] for f in man.get("files", [])]
        ground = {f["path"]: (rd / "stage2_in" / f["path"]).read_text(encoding="utf-8", errors="replace")
                  for f in man.get("files", []) if (rd / "stage2_in" / f["path"]).is_file()}
        steps = twinagent.read_step_log(rd)
        read = {s["path"] for s in steps if s.get("tool") == "ws_read" and s.get("ok")
                and (s.get("path") or "").startswith("地上/")}
        rec["ground_read"] = sorted(read)
        rec["steps_n"] = len(steps)
        rec["ground_write_blocked"] = [s.get("path") for s in steps
                                       if s.get("tool") == "ws_write" and s.get("ok") is False
                                       and (s.get("path") or "").startswith("地上")]
        rec["step_failures"] = [{"tool": s.get("tool"), "path": s.get("path")} for s in steps if s.get("ok") is False]

        runj = json.loads((rd / "run_RUN-ON.json").read_text(encoding="utf-8")) \
            if (rd / "run_RUN-ON.json").is_file() else {}
        attempts = []
        for a in runj.get("attempts", []):
            n = a.get("attempt")
            vp = pathlib.Path(a["visible_path"]) if a.get("visible_path") else None
            vis = json.loads(vp.read_text(encoding="utf-8")) if vp and vp.is_file() else {}
            frozen = pathlib.Path(a["frozen_path"]) if a.get("frozen_path") else rd
            row = {"attempt": n, "agent_rc": a.get("agent_rc"), "timed_out": a.get("agent_timed_out"),
                   "agent_wall_s": a.get("agent_wall_s"), "requests_seen": a.get("requests_seen"),
                   "accepted": a.get("accepted"), "stop_reason": a.get("stop_reason"),
                   "feedback_in_prompt_bytes": a.get("feedback_in_prompt_bytes"),
                   "feedback_text": (a.get("feedback") or {}).get("text"),
                   "windows": [], "artifacts": [{"name": x[0], "text": x[1]} for x in gg.read_artifacts(frozen)],
                   "plan": (frozen / "PLAN.md").read_text(encoding="utf-8", errors="replace")
                   if (frozen / "PLAN.md").is_file() else None}
            for f in vis.get("files", []):
                for c in f.get("cases", []):
                    cid, label = gg.describe(c.get("case"), bool(c.get("ok")), c.get("message") or "")
                    w = {"id": cid, "case": c.get("case"), "ok": bool(c.get("ok")), "label": label,
                         "message": c.get("message") or ""}
                    if not c.get("ok"):
                        w["evidence"] = evidence_for(c["case"], w["message"], frozen, ground, read)
                    row["windows"].append(w)
            attempts.append(row)
        rec["attempts"] = attempts
        rec["attempts_used"] = len(attempts)
        rec["stop_reason"], rec["accepted"] = runj.get("stop_reason"), runj.get("accepted")
        rec["review_labels"] = twinagent.read_review(rd)
        rec["cut_attempts"] = sorted(gg.cut_attempts(rd))
        rec["run_budget_s"] = twinagent.RUN_BUDGET_S
        rec["letter_present"] = (ws / "信.md").is_file()

        # 事件流（lifecycle＋旁註）原封不動存下來——之後要餵電視
        out_dir.mkdir(parents=True, exist_ok=True)
        if events.is_file():
            shutil.copyfile(events, out_dir / f"{name}.lifecycle.jsonl")
        sc = sidecarlib.sidecar_path(events)
        if sc.is_file():
            shutil.copyfile(sc, out_dir / f"{name}.lifecycle.sidecar.jsonl")
        evs = lifecycle.read(events) if events.is_file() else []
        rec["event_types"] = [e["type"] for e in evs if e["type"] in (
            "attempt_started", "agent_exited", "gate_ran", "feedback_ready", "run_ended")]

        # 分支（這一跑真的發生了哪些）
        hit: dict[str, bool] = {b: False for b in BRANCHES}
        if attempts:
            first = attempts[0]
            hit["B1"] = bool(first["windows"]) and all(w["ok"] for w in first["windows"]) and rec["accepted"] is True
            for a in attempts:
                for w in a["windows"]:
                    if (not w["ok"] and w["id"] in WINDOW_BRANCH
                            and w["message"] != gg.NO_LEDGER_MSG):      # 沒有紀錄可對照是 B7，不算 B2
                        hit[WINDOW_BRANCH[w["id"]]] = True
            hit["B3"] = len(attempts) >= 2
            hit["B4"] = len(attempts) >= 2 and rec["accepted"] is True
            hit["B5"] = rec.get("stop_reason") == "attempts_exhausted"
        hit["B6"] = bool(rec["ground_write_blocked"])
        hit["B7"] = bool(rec["cut_attempts"])
        # B8：pi 起得來但打不到模型 ⇒ requests_seen=0、退化 no_model_call
        hit["B8"] = rec["twin"].get("requests_seen") == 0 or rec["twin"].get("degrade_kind") == "no_model_call"
        rec["branches"] = {b: v for b, v in hit.items() if v}

        w = twinlink.withdraw(st, sid, reason="gate_samples:cleanup")
        rec["withdrawn"] = bool(w.get("ok"))
        rec["erased_left"] = twinagent.run_artifacts_present(twinagent.default_work_root(db), sid)
        st.close()
    except Exception as exc:                                  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"[:600]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rec


def cmd_run(a: argparse.Namespace) -> int:
    if a.dead_endpoint:
        # 測試環境造 B8：模型端點是關閉的埠，但**略過 twinlink 的探測**（production 的探測會直接退化、不起 pi），
        # 讓 pi 起得來、打不到模型。只在這個行程改，production 程式不動。
        from ops.exhibit.twin import twinagent
        twinagent.upstream_reachable = lambda *args, **kw: True
    spec = json.loads(pathlib.Path(a.spec).read_text(encoding="utf-8"))
    out = pathlib.Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for s in spec:
        if a.only and s["name"] not in a.only.split(","):
            continue
        f = out / f"{s['name']}.json"
        if f.exists() and not a.redo:
            continue
        rec = run_one(s, a.endpoint, a.model, a.timeout, out, a.enclose, a.require_tier)
        f.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({"name": s["name"], "wall_s": rec.get("wall_s"), "accepted": rec.get("accepted"),
                          "attempts": rec.get("attempts_used"), "branches": list((rec.get("branches") or {})),
                          "error": rec.get("error")}, ensure_ascii=False), flush=True)
    return 0


def cmd_report(a: argparse.Namespace) -> int:
    out = pathlib.Path(a.out_dir)
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(q for q in out.glob("*.json") if not q.name.startswith(("spec", "SUMMARY")))]
    cov = {b: [r["name"] for r in runs if b in (r.get("branches") or {})] for b in BRANCHES}
    walls = sorted(r["wall_s"] for r in runs if isinstance(r.get("wall_s"), (int, float)))
    summ = {"runs": len(runs), "errors": [r["name"] for r in runs if r.get("error")],
            "coverage": {b: {"n": len(v), "runs": v} for b, v in cov.items()},
            "wall_median_s": walls[len(walls) // 2] if walls else None,
            "wall_max_s": walls[-1] if walls else None,
            "accepted": {str(k): sum(1 for r in runs if r.get("accepted") is k) for k in (True, False, None)}}
    (out / "SUMMARY.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summ, ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="根據閘門真跑覆蓋（舊 VM）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--spec", required=True)
    r.add_argument("--out-dir", required=True)
    r.add_argument("--endpoint", default="http://100.119.113.56:5500/v1")
    r.add_argument("--model", default="gemma-4-12b-it-qat")
    r.add_argument("--timeout", type=float, default=300.0)
    r.add_argument("--only", default=None)
    r.add_argument("--redo", action="store_true")
    r.add_argument("--enclose", default="off", choices=["off", "auto", "on"])
    r.add_argument("--require-tier", default=None)
    r.add_argument("--dead-endpoint", action="store_true", help="B8：略過端點探測，讓 pi 起來打一個關閉的埠")
    r.set_defaults(fn=cmd_run)
    p = sub.add_parser("report")
    p.add_argument("--out-dir", required=True)
    p.set_defaults(fn=cmd_report)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
