#!/usr/bin/env python3
"""stray labd 根因審計證據鏈（ticket R20261111_2158-1；2026-11-11 r1474 mainline 正規實作）。

根因（2026-11-11 人類常設 2.b＋審查 #4）：pi session 01a1a112 的 message 93a55755
以 bash 工具先 `kill 1638` 舊實例、再 `nohup` 手動拉起新 labd——不經 labd loop 管理的
實例，啟動環境（VLAB_PAR=1 等）洩入 E010 父環境（與 DECISION_20261103_E016_ENVLEAK_FIX.md
記錄的 stray 734502／父 pi 733374 關聯）。

機械解析 pi session JSONL（0 模型呼叫）：找 id==93a55755 行 → 抽 timestamp/model/
provider/toolCall/command，逐項對照 ticket 預期值（任一不符＝check 失敗 → verdict 非 OK，
fail-closed）；由 DECISION 檔關聯 stray/parent PID（缺值＝UNKNOWN，絕不是 0 或 PASS）。
--selftest：5 組正/負控制（0 模型呼叫）。退出：0=OK；1=verdict 非 OK 或 selftest broken。
r1484（審查 argon fe731a230，已驗證）：verdict 語義修正——unrelated 壞行（真 session 第 190 行
截斷 JSON）不再一票否決；verdict 只取決於「目標 message 找到 ＋ checks 非空 ＋ 全數 ok」，
parse_errors 仍完整記錄於證據（透明性不降）。`bool(checks)` 同時塞住 `all([])` 空集偽真洞。
"""
import argparse
import datetime as _dt
import hashlib
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SESSION = (Path.home() / ".pi/agent/sessions/--home-user1-dev-Vacant--/"
           "2026-11-03T11-01-38-046Z_01a1a112-5e7d-7660-840f-92c1150ee3f1.jsonl")
DECISION = REPO / "decisions/DECISION_20261103_E016_ENVLEAK_FIX.md"
OUT = REPO / "ops/audits/stray_labd_root_cause_evidence.json"
EXPECTED = {"msg_id": "93a55755", "timestamp": "2026-11-03T11:15:40.431Z",
            "model": "qwen/qwen3.8-27b", "provider": "lms1003qwen",
            "toolcall_id": "B2yTy6xlNAhAT5KnexYVIEJav8SjENSY"}
KILL_FRAG = "kill 1638"
NOHUP_FRAG = "VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &"
OK_V, BAD_V = "STRAY_LABD_ROOT_CAUSE_OK", "STRAY_LABD_ROOT_CAUSE_NOT_ESTABLISHED"


def parse_session(path: Path) -> tuple[list[dict], list[str]]:
    """解析 JSONL → (records, parse_errors)；壞行記錯、不偽造成記錄（fail-closed）。"""
    recs, errs = [], []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError as e:
                errs.append(f"line {i}: {e}")
    return recs, errs


def find_message(records: list[dict], msg_id: str) -> dict | None:
    """抽出 msg_id 行的 launch 證據（找不到＝None，fail-closed）。"""
    for r in records:
        if r.get("id") == msg_id:
            m = r.get("message") or {}
            tc = next((c for c in m.get("content", []) if c.get("type") == "toolCall"), None)
            return {"msg_id": r.get("id"), "timestamp": r.get("timestamp"),
                    "model": m.get("model"), "provider": m.get("provider"),
                    "toolcall_id": tc.get("id") if tc else None,
                    "command": (tc or {}).get("arguments", {}).get("command")}
    return None


def evaluate(ev: dict) -> list[dict]:
    """逐項對照預期值 → checks（name/ok/expected/actual）。"""
    rows = [{"name": n, "expected": v, "actual": ev.get(n)} for n, v in EXPECTED.items()]
    cmd = ev.get("command") or ""
    rows += [{"name": "command_kill", "expected": KILL_FRAG, "actual": KILL_FRAG in cmd},
             {"name": "command_nohup", "expected": NOHUP_FRAG, "actual": NOHUP_FRAG in cmd}]
    for r in rows:
        r["ok"] = bool(r["actual"]) if r["name"].startswith("command_") else r["actual"] == r["expected"]
    return rows


def correlate_decision(path: Path) -> dict:
    """DECISION 檔關聯 stray/parent PID；缺值＝UNKNOWN（紅線：不是 0、不是 PASS）。"""
    rel = str(path.relative_to(REPO)) if path.is_relative_to(REPO) else str(path)
    out = {"file": rel, "stray_pid": "UNKNOWN", "parent_pid": "UNKNOWN"}
    if path.is_file():
        text = path.read_text(encoding="utf-8", errors="replace")
        out["stray_pid"] = 734502 if "734502" in text else "UNKNOWN"
        out["parent_pid"] = 733374 if "733374" in text else "UNKNOWN"
    return out


def run_audit(session: Path, decision: Path) -> dict:
    recs, errs = parse_session(session)
    ev = find_message(recs, EXPECTED["msg_id"])
    checks = evaluate(ev) if ev else []
    # r1484：unrelated 壞行不否決（仍記錄於 parse_errors）；目標缺失／checks 空／任一 check 不符仍 fail-closed
    ok = ev is not None and bool(checks) and all(c["ok"] for c in checks)
    return {"schema": "vacant.audit/stray_labd_root_cause/1", "ticket": "R20261111_2158-1",
            "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "session_file": str(session),
            "session_sha256": hashlib.sha256(session.read_bytes()).hexdigest() if session.is_file() else None,
            "parse_errors": errs, "message": ev, "checks": checks,
            "decision_correlation": correlate_decision(decision),
            "root_cause": ("pi session 01a1a112 message 93a55755 以 bash 工具 kill 1638 後以 nohup 手動拉起 labd"
                           "（非 labd loop 管理實例），啟動環境洩入 E010 父環境（stray 734502／父 pi 733374）"
                           if ok else "未建立（fail-closed：message 缺失／parse 失敗／check 不符）"),
            "verdict": OK_V if ok else BAD_V}


def _line(msg_id: str, command: str) -> str:
    return json.dumps({"type": "message", "id": msg_id, "parentId": "p",
                       "timestamp": EXPECTED["timestamp"],
                       "message": {"role": "assistant", "model": EXPECTED["model"],
                                   "provider": EXPECTED["provider"], "content":
                                   [{"type": "text", "text": "ok"},
                                    {"type": "toolCall", "id": EXPECTED["toolcall_id"],
                                     "name": "bash", "arguments": {"command": command}}]}})


def selftest(tmp: Path) -> int:
    s, ok = tmp / "s.jsonl", True

    def ck(name: str, cond: bool) -> None:
        nonlocal ok
        print(f"control {name}: " + ("PASS" if cond else "FAIL"))
        ok = ok and bool(cond)

    s.write_text(_line("93a55755", f"kill 1638 && sleep 2; {NOHUP_FRAG}") + "\n", encoding="utf-8")
    recs, errs = parse_session(s)
    ck("pos_all_checks", errs == []
       and all(c["ok"] for c in evaluate(find_message(recs, "93a55755"))))
    ck("neg_wrong_id", find_message(recs, "99999999") is None)
    s.write_text(_line("93a55755", "kill 1638") + "\n", encoding="utf-8")
    bad = [c for c in evaluate(find_message(parse_session(s)[0], "93a55755")) if not c["ok"]]
    ck("neg_missing_nohup", any(c["name"].startswith("command_") for c in bad))
    s.write_text('{"type":"message","id":"93a55755",\n', encoding="utf-8")
    recs2, errs2 = parse_session(s)
    ck("neg_bad_json", bool(errs2) and recs2 == [])
    ck("neg_missing_decision", correlate_decision(tmp / "nope.md")["stray_pid"] == "UNKNOWN")
    print("VERDICT: STRAY_LABD_ROOT_CAUSE_SELFTEST_OK" if ok
          else "VERDICT: STRAY_LABD_ROOT_CAUSE_SELFTEST_BROKEN")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="stray labd 根因審計（0 模型呼叫）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--selftest", action="store_true", help="5 組正/負控制（0 模型呼叫）")
    g.add_argument("--run", action="store_true", help="解析真實 session＋DECISION，寫證據 JSON")
    a = ap.parse_args(argv)
    if a.selftest:
        with tempfile.TemporaryDirectory() as d:
            return selftest(Path(d))
    rep = run_audit(SESSION, DECISION)
    OUT.write_text(json.dumps(rep, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for c in rep["checks"]:
        print(f"{'PASS' if c['ok'] else 'FAIL'} {c['name']}: {c['expected']} == {c['actual']}")
    print(f"correlation: {rep['decision_correlation']}")
    print(f"VERDICT: {rep['verdict']}")
    return 0 if rep["verdict"] == OK_V else 1


if __name__ == "__main__":
    raise SystemExit(main())
