# -*- coding: utf-8 -*-
"""stray labd 根因審計工具測試（ticket R20261111_2158-1；2026-11-11 r1474 mainline 正規實作）。

覆蓋（全 0 模型呼叫，純解析）：
- 正控制：合成 session 行（93a55755＋nohup 命令）→ 全 checks 通過 → verdict OK
- 負控制：錯誤 msg id → message 找不到（fail-closed，verdict 非 OK）
- 負控制：命令缺 nohup 片段 → 該 check 失敗 → verdict 非 OK
- 負控制：壞 JSON 行 → parse_errors 非空 → fail-closed
- 決策檔關聯：缺檔 → UNKNOWN（不是 0、不是 PASS，紅線 fail-closed）
- --selftest 子程序：退出碼 0、VERDICT 行、每組控制 PASS、無 FAIL
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.audits.stray_labd_root_cause_audit import (  # noqa: E402
    correlate_decision, evaluate, find_message, parse_session, run_audit)

SCRIPT = ROOT / "ops" / "audits" / "stray_labd_root_cause_audit.py"
NOHUP = "VLAB_PAR=1 nohup /usr/bin/python3 /srv/vlab/bin/labd.py >> /srv/vlab/labd.log 2>&1 &"


def _line(msg_id: str, command: str) -> str:
    return json.dumps({
        "type": "message", "id": msg_id, "parentId": "p",
        "timestamp": "2026-11-03T11:15:40.431Z",
        "message": {"role": "assistant", "model": "qwen/qwen3.8-27b",
                    "provider": "lms1003qwen",
                    "content": [{"type": "text", "text": "ok"},
                                {"type": "toolCall",
                                 "id": "B2yTy6xlNAhAT5KnexYVIEJav8SjENSY",
                                 "name": "bash",
                                 "arguments": {"command": command}}]}})


def test_script_exists() -> None:
    assert SCRIPT.is_file(), f"缺少 {SCRIPT}（R20261111_2158-1 未落地）"


def test_positive_control_all_checks_ok(tmp_path: Path) -> None:
    s = tmp_path / "s.jsonl"
    s.write_text(_line("93a55755", f"kill 1638 && sleep 2; {NOHUP}") + "\n", encoding="utf-8")
    recs, errs = parse_session(s)
    assert errs == [] and len(recs) == 1
    ev = find_message(recs, "93a55755")
    assert ev is not None
    checks = evaluate(ev)
    assert all(c["ok"] for c in checks), checks
    assert len(checks) >= 6  # id/ts/model/provider/toolcall/kill/nohup 各一條


def test_negative_control_wrong_id_fail_closed(tmp_path: Path) -> None:
    s = tmp_path / "s.jsonl"
    s.write_text(_line("99999999", f"kill 1638; {NOHUP}") + "\n", encoding="utf-8")
    recs, _ = parse_session(s)
    assert find_message(recs, "93a55755") is None
    rep = run_audit(s, tmp_path / "nope.md")
    assert rep["verdict"] != "STRAY_LABD_ROOT_CAUSE_OK"


def test_negative_control_missing_nohup(tmp_path: Path) -> None:
    s = tmp_path / "s.jsonl"
    s.write_text(_line("93a55755", "kill 1638") + "\n", encoding="utf-8")
    recs, _ = parse_session(s)
    checks = evaluate(find_message(recs, "93a55755"))
    bad = [c for c in checks if not c["ok"]]
    assert bad and bad[0]["name"].startswith("command_"), checks


def test_negative_control_bad_json_fail_closed(tmp_path: Path) -> None:
    s = tmp_path / "s.jsonl"
    s.write_text('{"type":"message","id":"93a55755",\n', encoding="utf-8")
    recs, errs = parse_session(s)
    assert errs and recs == []  # 壞行＝parse error，不得偽造成「找到」


def test_unrelated_bad_json_line_does_not_block_valid_target(tmp_path: Path) -> None:
    """r1484（argon fe731a230 審查採納）：unrelated 壞行不否決 verdict，parse_errors 仍須記錄。"""
    s = tmp_path / "s.jsonl"
    s.write_text(
        _line("93a55755", f"kill 1638 && sleep 2; {NOHUP}") + "\n"
        + '{"type":"compaction","bad":,\n',
        encoding="utf-8",
    )
    d = tmp_path / "d.md"
    d.write_text("stray labd 734502，父 pi 733374。\n", encoding="utf-8")
    rep = run_audit(s, d)
    assert rep["parse_errors"]  # 透明性：壞行仍記錄
    assert rep["verdict"] == "STRAY_LABD_ROOT_CAUSE_OK"


def test_correlation_unknown_when_missing(tmp_path: Path) -> None:
    out = correlate_decision(tmp_path / "nope.md")
    assert out["stray_pid"] == "UNKNOWN" and out["parent_pid"] == "UNKNOWN"
    d = tmp_path / "d.md"
    d.write_text("stray labd 734502，父 pi 733374。\n", encoding="utf-8")
    out2 = correlate_decision(d)
    assert out2["stray_pid"] == 734502 and out2["parent_pid"] == 733374


def test_selftest_subprocess_all_controls_pass() -> None:
    out = subprocess.run([sys.executable, str(SCRIPT), "--selftest"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "VERDICT: STRAY_LABD_ROOT_CAUSE_SELFTEST_OK" in out.stdout
    for name in ("pos_all_checks", "neg_wrong_id", "neg_missing_nohup",
                 "neg_bad_json", "neg_missing_decision"):
        line = next(l for l in out.stdout.splitlines() if l.startswith(f"control {name}"))
        assert line.endswith("PASS"), line
    assert "FAIL" not in out.stdout


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
