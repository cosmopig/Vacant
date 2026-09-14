"""R530：三臂 prompt 逐字相同、KS-1、DENY、預算、驗收 runner、整條迴圈。"""
from __future__ import annotations

import inspect
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain.r530 import acceptance, gauge, openwork_arms as oa  # noqa: E402
from ops.gain.r530 import sandbox as sb, tasks as taskmod, wshash  # noqa: E402
from ops.localagent import DENY as LOCALAGENT_DENY  # noqa: E402
from vacant.memory import KS1_FORBIDDEN, KS1Violation, assert_ks1_clean  # noqa: E402


# ── 三臂 prompt 逐字相同（Fable 裁決的核心約束）──────────────────────────
def test_three_arms_render_byte_identical_first_messages(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "goal.md").write_text("g", encoding="utf-8")
    task = {"task_id": "t", "goal": "Goal. Something.",
            "contract": "Contract\n- solution.f(x)"}
    persona = oa.PERSONAS[0][1]
    rendered = {
        arm: json.dumps(oa.initial_messages(task, ws, arm=arm,
                                            persona_text=persona),
                        ensure_ascii=False)
        for arm in oa.ARMS
    }
    assert len(set(rendered.values())) == 1, rendered


def test_initial_messages_source_has_no_arm_branch():
    """`arm` 是收了但不准用的參數——原始碼裡不准有針對 arm 的分支。

    import 時的 `assert_arm_prompts_identical()` 抓的是行為；這一條抓的是
    形狀，兩條互補：有人寫 `if arm == "A-GATE": pass` 行為不變但意圖已經歪了。
    """
    src = inspect.getsource(oa.initial_messages)
    body = src.split('"""')[-1]
    assert "if arm ==" not in body and 'arm in (' not in body, src


def test_import_time_prompt_identity_assertion_is_real(monkeypatch, tmp_path):
    """把一個 arm 分支塞進去，`assert_arm_prompts_identical` 必須炸。"""
    real = oa.initial_messages

    def fake(task, workspace, *, arm, persona_text):
        system, msgs = real(task, workspace, arm=arm, persona_text=persona_text)
        if arm == "A-GATE":
            system = system + "\nyou are being watched"
        return system, msgs

    monkeypatch.setattr(oa, "initial_messages", fake)
    with pytest.raises(AssertionError):
        oa.assert_arm_prompts_identical()


# ── KS-1 ──────────────────────────────────────────────────────────────────
def test_every_frozen_text_is_ks1_clean():
    for txt in oa._FROZEN_TEXTS:
        assert_ks1_clean(txt)


def test_ks1_assertion_would_actually_fire():
    """反向牙齒：放寬偵測面而沒有負控＝把稽核關掉（round460e 的教訓）。"""
    for phrase in KS1_FORBIDDEN:
        with pytest.raises(KS1Violation):
            assert_ks1_clean(f"Rules:\n{phrase}\nDo the task.")


def test_feedback_never_mentions_hidden_checks():
    """隱藏驗收的存在、條數、內容一律不進回饋（§二-5）。"""
    low = (oa.FEEDBACK_TEMPLATE + oa.RULES + oa.TASK_MESSAGE).lower()
    for word in ("hidden", "rubric", "secret"):
        assert word not in low, f"回饋模板提到了 {word!r}"


# ── DENY ──────────────────────────────────────────────────────────────────
def test_localagent_deny_rules_are_carried_over_verbatim():
    """前 13 條逐字沿用 `ops/localagent.py`——不准被「順手改寬」。"""
    ours = [(p, w) for p, w, tag in oa.DENY if tag == "localagent"]
    assert ours == list(LOCALAGENT_DENY)


def test_deny_blocks_network_escape_and_hidden():
    assert oa.deny_reason("curl http://example.com")[1] == oa.DENY_NETWORK
    assert oa.deny_reason("pip install requests")[1] == oa.DENY_NETWORK
    assert oa.deny_reason("cat ../../etc/passwd")[1] == oa.DENY_ESCAPE
    assert oa.deny_reason("cd /")[1] == oa.DENY_ESCAPE
    assert oa.deny_reason("echo x > /etc/hosts")[1] == oa.DENY_ESCAPE
    assert oa.deny_reason("cat hidden/test_hidden.py")[1] == oa.DENY_HIDDEN
    assert oa.deny_reason("ls rubric")[1] == oa.DENY_HIDDEN
    assert oa.deny_reason("sudo apt install x")[1] == "localagent"


def test_deny_does_not_fire_on_ordinary_work():
    for cmd in ("ls -la", "cat solution.py", "python3 -c 'print(1)'",
                "bash run_tests.sh", "python3 -m solution in.csv",
                "grep -n def solution.py"):
        assert oa.deny_reason(cmd) is None, cmd


def test_deny_reads_the_shell_not_the_heredoc_body():
    """寫一個含 shebang／`hidden` 註解／`../` 字串的檔案不該被擋。

    寬的版本會系統性地打到「寫比較多程式碼」的那條臂——量到的東西會有
    一半是「模型多常踩到我們的正則」。
    """
    cmd = ("cat > solution.py <<'EOF'\n"
           "#!/usr/bin/env python3\n"
           "# nothing hidden here\n"
           "P = '../relative'\n"
           "EOF")
    assert oa.deny_reason(cmd) is None
    # …但 heredoc **外面**的同一個字樣照樣擋。
    assert oa.deny_reason(cmd + "\ncat hidden/x.py") is not None


def test_strip_heredoc_keeps_the_shell_lines():
    out = oa.strip_heredoc_bodies("cat > a <<'E'\nbody\nE\nls -la")
    assert "body" not in out and "ls -la" in out and "cat > a" in out


# ── 預算與停止理由 ────────────────────────────────────────────────────────
def test_budget_is_a_module_constant_not_a_cli_knob():
    assert oa.OPENWORK_BUDGET["max_model_calls"] == 72
    assert oa.OPENWORK_BUDGET["max_calls_per_attempt"] == 24
    assert oa.OPENWORK_BUDGET["max_conf_attempts"] == 3
    assert oa.OPENWORK_BUDGET["max_gate_rounds"] == 5
    from ops.gain.r530 import run_r530
    src = inspect.getsource(run_r530.main)
    for knob in ("--max-model-calls", "--max-gate-rounds", "--max-tokens",
                 "--max-conf-attempts", "--max-completion-tokens"):
        assert knob not in src, f"{knob} 不准做成 CLI 旋鈕（§二-3）"


def test_stop_reasons_are_a_closed_set():
    assert "visible_pass" in oa.STOP_REASONS
    # 10 ＝ 原本 9 ＋ `budget_context`（Fable 2026-09-14）。
    assert len(oa.STOP_REASONS) == 10
    assert "budget_context" in oa.STOP_REASONS
    # 拒交只有三種，而且 `budget_calls`／`budget_wall` **不在裡面**
    # ——「沒跑完」不是「不交」。
    assert set(oa.REFUSAL_REASONS) == {
        "gate_exhausted", "attempts_exhausted", "budget_context"}
    assert set(oa.REFUSAL_REASONS) <= oa.STOP_REASONS


# ── 驗收 runner ───────────────────────────────────────────────────────────
def _stage(tmp_path, task, candidate_src: str) -> pathlib.Path:
    ws = tmp_path / "ws"
    oa.prepare_workspace(task["template_dir"], ws, git_init=False)
    (ws / "solution.py").write_text(candidate_src, encoding="utf-8")
    return ws


def test_runner_passes_a_known_good_solution(tmp_path):
    task = taskmod.load_task("ow_01_csvjson")
    good = (task["gauge_dir"] / "good.py").read_text(encoding="utf-8")
    ws = _stage(tmp_path, task, good)
    s = sb.NoneSandbox()
    vis = acceptance.run_suite(s, ws, task["visible_dir"], suite="visible",
                               task_id=task["task_id"],
                               verify_root=tmp_path / "_verify")
    hid = acceptance.run_suite(s, ws, task["hidden_dir"], suite="hidden",
                               task_id=task["task_id"],
                               verify_root=tmp_path / "_verify")
    assert vis["all_pass"] and hid["all_pass"]
    assert hid["total"] == 14


def test_runner_catches_a_known_bad_solution_and_says_which_case(tmp_path):
    task = taskmod.load_task("ow_01_csvjson")
    bad = (task["gauge_dir"] / "bad_a.py").read_text(encoding="utf-8")
    ws = _stage(tmp_path, task, bad)
    s = sb.NoneSandbox()
    hid = acceptance.run_suite(s, ws, task["hidden_dir"], suite="hidden",
                               task_id=task["task_id"],
                               verify_root=tmp_path / "_verify")
    assert not hid["all_pass"]
    names = {c["case"] for c in acceptance.failing_cases(hid)}
    # 名字由 `export_bank.py` 從 `bank/<task>/hidden/h*.py` 的檔名投影而來
    # （`check_h01_comma_in_quotes`…）⇒ 這裡不釘死某一個名字，
    # 釘的是「引號裡的逗號那一條**有**被抓到」——那是 goal 逐字寫的客戶困擾。
    assert any("comma" in n for n in names), sorted(names)
    for c in acceptance.failing_cases(hid):
        assert c["kind"] in acceptance.CASE_KINDS
        assert c["message"], "失敗原文不准是空的——回饋要說得出哪裡錯"


def test_runner_reports_a_missing_solution_as_import_not_as_pass(tmp_path):
    """**量不到不是通過**：沒有 solution.py 必須是「全不過」不是「0/0 全過」。"""
    task = taskmod.load_task("ow_02_ratelimit")
    ws = tmp_path / "ws"
    oa.prepare_workspace(task["template_dir"], ws, git_init=False)
    s = sb.NoneSandbox()
    hid = acceptance.run_suite(s, ws, task["hidden_dir"], suite="hidden",
                               task_id=task["task_id"],
                               verify_root=tmp_path / "_verify")
    assert hid["all_pass"] is False
    kinds = {c["kind"] for c in acceptance.failing_cases(hid)}
    assert kinds == {"import"}


def test_empty_suite_is_not_a_pass(tmp_path):
    task = taskmod.load_task("ow_01_csvjson")
    ws = _stage(tmp_path, task, "def csv_to_jsonl(t): return ''\n")
    empty = tmp_path / "empty_suite"
    empty.mkdir()
    s = sb.NoneSandbox()
    res = acceptance.run_suite(s, ws, empty, suite="hidden",
                               task_id=task["task_id"],
                               verify_root=tmp_path / "_verify")
    assert res["all_pass"] is False and res["total"] == 0
    assert res["empty_reason"]


def test_hidden_suite_does_not_touch_the_workspace(tmp_path):
    """§五-3 第 1 條的可執行版本。"""
    task = taskmod.load_task("ow_01_csvjson")
    good = (task["gauge_dir"] / "good.py").read_text(encoding="utf-8")
    ws = _stage(tmp_path, task, good)
    before = wshash.tree_hash(ws)
    s = sb.NoneSandbox()
    acceptance.run_suite(s, ws, task["hidden_dir"], suite="hidden",
                         task_id=task["task_id"],
                         verify_root=tmp_path / "_verify")
    assert wshash.tree_hash(ws) == before


def test_verify_dir_is_deleted_after_the_run(tmp_path):
    """隱藏驗收跑完就該從磁碟上消失（不准留在 run 目錄裡）。"""
    task = taskmod.load_task("ow_01_csvjson")
    good = (task["gauge_dir"] / "good.py").read_text(encoding="utf-8")
    ws = _stage(tmp_path, task, good)
    vroot = tmp_path / "_verify"
    acceptance.run_suite(sb.NoneSandbox(), ws, task["hidden_dir"],
                         suite="hidden", task_id=task["task_id"],
                         verify_root=vroot)
    assert list(vroot.iterdir()) == []


def test_result_digest_ignores_timing_but_not_outcomes():
    a = {"suite": "hidden", "task_id": "t",
         "files": [{"file": "f", "wall_ms": 10,
                    "cases": [{"case": "c", "ok": True, "kind": "pass"}]}],
         "passed": 1, "total": 1}
    b = json.loads(json.dumps(a))
    b["files"][0]["wall_ms"] = 9999
    assert acceptance.result_digest(a) == acceptance.result_digest(b)
    b["files"][0]["cases"][0]["ok"] = False
    assert acceptance.result_digest(a) != acceptance.result_digest(b)


def test_render_failures_names_the_test_and_the_values(tmp_path):
    task = taskmod.load_task("ow_01_csvjson")
    bad = (task["gauge_dir"] / "bad_a.py").read_text(encoding="utf-8")
    ws = _stage(tmp_path, task, bad)
    vis = acceptance.run_suite(sb.NoneSandbox(), ws, task["visible_dir"],
                               suite="visible", task_id=task["task_id"],
                               verify_root=tmp_path / "_verify")
    block = acceptance.render_failures(vis)
    # 回饋要說得出**哪個測試**與**期望 vs 實際**——那三個欄位逐字會進
    # `A-GATE` 的回饋（§二-5），零資訊的「你的程式壞了」是 R460 §3.2
    # 已經量過的壞回饋。
    assert "test_visible.py::" in block
    assert "got=" in block and "want=" in block, block[:300]


# ── 雙向量具 ──────────────────────────────────────────────────────────────
def test_gauge_is_green_on_the_two_shipped_tasks():
    # 題庫已經是 20 題（主線 44be37f）；這一條測的是**沙箱端**的雙向量具
    # （`ops/gain/r530/gauge.py`，跑真的 acceptance runner），
    # 全 20 題會太慢。逐題的 bank 級檢查由 `gauge_r530.py --check` 負責。
    out = gauge.run_gauge("ow_01_csvjson,ow_02_ratelimit", backend="none")
    assert out["verdict"] == "OK", json.dumps(out, ensure_ascii=False)[:2000]
    assert out["coverage_n"] == out["n_tasks"]
    assert out["stubs_blocked_n"] == out["stubs_n"] >= 6
