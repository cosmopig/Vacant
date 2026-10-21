"""通用任務強化（資料分析/文件/單一答案）與程式任務強化測試。

涵蓋：
1. 長副檔名（`.parquet` / `.feather` / `.duckdb`）與指令檔（`goal.md` / `contract.md`）輸入材料自動傳遞。
2. 未加引號的目錄提示（`in the data directory`）與 Python `-m unittest <stem>` 觀察判定。
3. 先寫入交付檔、後執行測試/腳本失敗卻未重跑通過的 `failed_step` 攔截。
4. `invalid_output` 四種子類（`empty`, `syntax`, `stub`, `contract_shape`）攔截與真實正確交付不誤判。
5. `review.render()` 與 `zerostop` 的 KS-1 零術語合規性檢查。
6. 收件口（`intake/verifiers.py`）新增的 `syntax_valid` 與 `answer_format` 決定性驗證器。
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib

import pytest

from vacant_network.adapters import hook, install as INS
from vacant_network.intake import contract as C, flow
from vacant_network.memory import assert_ks1_clean
from vacant_network.trace import capture, review, zerostop
from vacant_network.trace.evidence import evidence_for
from vacant_network.trace.feedback import feedback_ks1_clean
from vacant_network.trace.recorder import Recorder


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VACANT_HOME", str(tmp_path / "vh"))
    for k in ("VACANT_TRACE", "VACANT_MODE"):
        monkeypatch.delenv(k, raising=False)
    p = INS.state_root() / "install.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": {}, "mode": "evidence"}))
    return tmp_path


class Agent:
    def __init__(self, proj: pathlib.Path, session: str = "S"):
        self.p, self.s, self.n = proj, session, 0

    def ask(self, text: str) -> None:
        hook.handle("claude", "UserPromptSubmit", {"session_id": self.s, "cwd": str(self.p),
                                                   "prompt": text})

    def step(self, tool: str, inp: dict, output=None, *, write: dict | None = None,
             error: bool = False) -> None:
        self.n += 1
        pre = {"session_id": self.s, "cwd": str(self.p), "tool_name": tool,
               "tool_use_id": f"t{self.n}", "tool_input": inp}
        hook.handle("claude", "PreToolUse", pre)
        for rel, content in (write or {}).items():
            f = self.p / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content)
        post = {**pre, "tool_response": output if output is not None else {}}
        if error:
            post["is_error"] = True
        hook.handle("claude", "PostToolUseFailure" if error else "PostToolUse", post)

    def read(self, rel: str) -> None:
        self.step("Read", {"file_path": str(self.p / rel)},
                  {"file": {"content": (self.p / rel).read_text()}})

    def bash(self, cmd: str, stdout: str = "", *, write: dict | None = None,
             error: bool = False) -> None:
        self.step("Bash", {"command": cmd}, {"stdout": stdout, "stderr": ""}, write=write,
                  error=error)

    def write(self, rel: str, content: str) -> None:
        self.step("Write", {"file_path": str(self.p / rel), "content": content}, {},
                  write={rel: content})

    def stop(self, last_msg: str = "Done.") -> dict:
        out, err, code = hook.handle("claude", "Stop", {
            "session_id": self.s, "cwd": str(self.p), "hook_event_name": "Stop",
            "stop_hook_active": False, "last_assistant_message": last_msg})
        assert code == 0 and err == ""
        return json.loads(out) if out else {}

    def evidence(self, final_text: str = "", today=dt.date(2026, 9, 25)) -> dict:
        ws = capture.workspace_for(str(self.p))
        return evidence_for(Recorder(ws), platform="claude", session=self.s,
                            final_text=final_text, today=today)


def _proj(env, name="proj", files=None):
    p = env / "work" / name
    p.mkdir(parents=True, exist_ok=True)
    for rel, c in (files or {}).items():
        f = p / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(c)
    return p


def _assert_clean_review(ev: dict) -> str:
    txt, withheld = review.render(ev["findings"])
    assert withheld == 0
    assert_ks1_clean(txt)
    feedback_ks1_clean(txt, set())
    return txt


# ── 1. .parquet 與指令檔（goal.md）材料傳遞 ──────────────────────────────

def test_parquet_and_goal_md_propagates_materials_and_catches_unread(env):
    p = _proj(env, "parquet_proj", {
        "goal.md": (
            "# Task\n"
            "Analyze the dataset `065_RFM.parquet` and write ONLY the final answer to `answer.txt`.\n"
        ),
        "065_RFM.parquet": "PAR1_FAKE_PARQUET_CONTENT",
    })
    a = Agent(p)
    a.ask("Read goal.md and complete the task. Write your final answer to answer.txt.")
    a.read("goal.md")
    # 偷懶沒讀 065_RFM.parquet 就直接寫答案
    a.write("answer.txt", "42\n")
    ev = a.evidence()
    kinds = [f["kind"] for f in ev["findings"]]
    assert "unread" in kinds
    assert any(f.get("path") == "065_RFM.parquet" for f in ev["findings"] if f["kind"] == "unread")
    _assert_clean_review(ev)


def test_unquoted_directory_cue_and_python_module_stem_observed(env):
    p = _proj(env, "dir_cue", {
        "data/metrics.csv": "k,v\na,125\n",
        "foo_test.py": "import unittest\n",
    })
    a = Agent(p)
    a.ask("Inspect the files in the data directory and run foo_test.py, then write out.txt.")
    # 用 python3 -m unittest foo_test 執行 foo_test.py，但沒讀 data/metrics.csv
    a.bash("python3 -m unittest foo_test", stdout="OK")
    a.write("out.txt", "125\n")
    ev = a.evidence()
    assert "foo_test.py" in ev["observed"]
    assert ev["materials_in_dirs"] == ["data/metrics.csv"]
    assert ev["unread_dir"] == ["data/metrics.csv"]
    _assert_clean_review(ev)


# ── 2. 先寫入程式碼、後執行測試失敗卻直接交卷 ──────────────────────────

def test_deliverable_written_before_failing_test_is_flagged(env):
    p = _proj(env, "code_fail", {
        "solution.py": "def solve(x):\n    return 0\n",
        "run_tests.sh": "#!/bin/sh\npytest -q\n",
    })
    a = Agent(p)
    a.ask("Fix solution.py and verify with run_tests.sh.")
    a.read("solution.py")
    a.write("solution.py", "def solve(x):\n    return x + 1\n")
    # 寫完 solution.py 後跑測試失敗，卻沒有再修改或重跑通過就停下
    a.bash("sh run_tests.sh", stdout="1 failed in 0.12s", error=True)
    ev = a.evidence("Fixed solution.py.")
    failed = [f for f in ev["findings"] if f["kind"] == "failed_step"]
    assert len(failed) == 1
    assert "run_tests.sh" in failed[0]["cmd"]
    _assert_clean_review(ev)


# ── 3. invalid_output 四種子類檢查 ─────────────────────────────────────

def test_invalid_output_empty_deliverable(env):
    p = _proj(env, "empty_out", {"input.txt": "hello\n"})
    a = Agent(p)
    a.ask("Read input.txt and write the result to answer.txt.")
    a.read("input.txt")
    a.write("answer.txt", "   \n")
    ev = a.evidence()
    inv = [f for f in ev["findings"] if f["kind"] == "invalid_output"]
    assert len(inv) == 1
    assert inv[0]["sub"] == "empty"
    assert inv[0]["path"] == "answer.txt"
    _assert_clean_review(ev)


def test_invalid_output_syntax_errors_python_json_and_fence(env):
    # (a) Python SyntaxError
    p1 = _proj(env, "syn_py", {"solution.py": "def f(x):\n    return x\n"})
    a1 = Agent(p1)
    a1.ask("Update solution.py.")
    a1.read("solution.py")
    a1.write("solution.py", "def f(x):\n    return (\n")
    ev1 = a1.evidence()
    inv1 = [f for f in ev1["findings"] if f["kind"] == "invalid_output"]
    assert len(inv1) == 1 and inv1[0]["sub"] == "syntax"
    _assert_clean_review(ev1)

    # (b) JSON syntax error + Markdown fence
    p2 = _proj(env, "syn_json")
    a2 = Agent(p2)
    a2.ask("Write the config to config.json.")
    a2.write("config.json", "```json\n{\"a\": 1}\n```\n")
    ev2 = a2.evidence()
    inv2 = [f for f in ev2["findings"] if f["kind"] == "invalid_output"]
    assert len(inv2) == 1 and inv2[0]["sub"] == "syntax"
    _assert_clean_review(ev2)


def test_invalid_output_stub_not_implemented_and_nan_and_traceback(env):
    # (a) Python NotImplementedError left in requested output
    p1 = _proj(env, "stub_py", {"solution.py": "def compute(x):\n    raise NotImplementedError\n"})
    a1 = Agent(p1)
    a1.ask("Implement compute(x) in solution.py.")
    a1.read("solution.py")
    a1.write("solution.py", "def compute(x):\n    # TODO\n    raise NotImplementedError('later')\n")
    ev1 = a1.evidence()
    inv1 = [f for f in ev1["findings"] if f["kind"] == "invalid_output"]
    assert len(inv1) == 1 and inv1[0]["sub"] == "stub"
    _assert_clean_review(ev1)

    # (b) Answer file containing nan
    p2 = _proj(env, "stub_ans", {"data.csv": "a,b\n1,2\n"})
    a2 = Agent(p2)
    a2.ask("Read data.csv and write the mean to answer.txt.")
    a2.read("data.csv")
    a2.write("answer.txt", "nan\n")
    ev2 = a2.evidence()
    inv2 = [f for f in ev2["findings"] if f["kind"] == "invalid_output"]
    assert len(inv2) == 1 and inv2[0]["sub"] == "stub"
    _assert_clean_review(ev2)


def test_invalid_output_contract_shape_dabench_and_only_answer_and_func(env):
    # (a) DABench @key[value] format requested in goal.md, but agent writes plain prose
    p1 = _proj(env, "shape_dabench", {
        "goal.md": "Format your answer as @mean_fare[value] where value is rounded to 2 decimals. Write to answer.txt.",
        "train.csv": "fare\n10.5\n20.5\n",
    })
    a1 = Agent(p1)
    a1.ask("Follow goal.md and write answer.txt.")
    a1.read("goal.md")
    a1.read("train.csv")
    a1.write("answer.txt", "15.50\n")
    ev1 = a1.evidence()
    inv1 = [f for f in ev1["findings"] if f["kind"] == "invalid_output"]
    assert len(inv1) == 1 and inv1[0]["sub"] == "contract_shape"
    _assert_clean_review(ev1)

    # 修成正確的 @mean_fare[15.50] 後即通過
    a1.write("answer.txt", "@mean_fare[15.50]\n")
    ev1_ok = a1.evidence()
    assert [f for f in ev1_ok["findings"] if f["kind"] == "invalid_output"] == []

    # (b) ONLY_ANSWER 卻寫了整段解釋句子與 Markdown 標題
    p2 = _proj(env, "shape_only", {"data.csv": "x\n42\n"})
    a2 = Agent(p2)
    a2.ask("Read data.csv and write ONLY the final answer to answer.txt (a single number).")
    a2.read("data.csv")
    a2.write("answer.txt", "# Final Answer\nBased on the analysis, the answer is 42.\n")
    ev2 = a2.evidence()
    inv2 = [f for f in ev2["findings"] if f["kind"] == "invalid_output"]
    assert len(inv2) == 1 and inv2[0]["sub"] == "contract_shape"
    _assert_clean_review(ev2)

    # (c) 要求實作函式 `def solve_puzzle(` 卻漏掉該函式名稱
    p3 = _proj(env, "shape_func")
    a3 = Agent(p3)
    a3.ask("Write a function `def solve_puzzle(grid)` in solution.py.")
    a3.write("solution.py", "def helper(grid):\n    return len(grid)\n")
    ev3 = a3.evidence()
    inv3 = [f for f in ev3["findings"] if f["kind"] == "invalid_output"]
    assert len(inv3) == 1 and inv3[0]["sub"] == "contract_shape"
    assert "solve_puzzle" in inv3[0]["detail"]
    _assert_clean_review(ev3)


def test_zerostop_blocks_invalid_output_with_ks1_clean_message(env, monkeypatch):
    monkeypatch.setattr(zerostop, "_run_child", zerostop.check)
    p = _proj(env, "zs_inv", {"data.csv": "x\n10\n"})
    a = Agent(p)
    a.ask("Read data.csv and write ONLY the final answer to answer.txt.")
    a.read("data.csv")
    a.write("answer.txt", "nan\n")
    payload = a.stop("Done.")
    assert payload.get("decision") == "block"
    feedback_ks1_clean(payload["reason"], set())


# ── 4. Intake Verifiers: syntax_valid & answer_format ──────────────────

def test_intake_verifiers_syntax_valid_and_answer_format(env):
    proj = env / "vproj"
    (proj / ".vacant").mkdir(parents=True, exist_ok=True)
    raw = C.scaffold("task-v1", deliverable=["*.py", "*.json", "*.txt"], destination="dir:published")
    raw["claims"] = [
        {"id": "py_ok", "verifier": "syntax_valid",
         "params": {"paths": ["solution.py"], "forbid_stubs": True, "required_symbols": ["add"]}},
        {"id": "json_ok", "verifier": "syntax_valid", "params": {"paths": ["out.json"]}},
        {"id": "ans_ok", "verifier": "answer_format",
         "params": {"path": "answer.txt", "format": "at_tags", "required_keys": ["corr"]}},
    ]
    cpath = proj / ".vacant" / "contract.json"
    cpath.write_text(json.dumps(raw, indent=2))
    flow.lock(cpath)
    task = flow.open_task(cpath)

    # 1) 壞交付：NotImplementedError stub + 壞 JSON + nan answer -> reject
    ws_bad = env / "ws_bad"
    ws_bad.mkdir()
    (ws_bad / "solution.py").write_text("def add(a, b):\n    raise NotImplementedError\n")
    (ws_bad / "out.json").write_text("{bad json")
    (ws_bad / "answer.txt").write_text("nan\n")
    r_bad = flow.submit(task, ws_bad, source="test")
    assert r_bad["outcome"] == "reject"
    by_id = {c["claim_id"]: c["status"] for c in r_bad["results"]}
    assert by_id == {"py_ok": "FAIL", "json_ok": "FAIL", "ans_ok": "FAIL"}

    # 2) 好交付：合法 Python + 合法 JSON + 正確 @corr[0.82] -> accept
    ws_good = env / "ws_good"
    ws_good.mkdir()
    (ws_good / "solution.py").write_text("def add(a, b):\n    return a + b\n")
    (ws_good / "out.json").write_text("{\"ok\": true}\n")
    (ws_good / "answer.txt").write_text("@corr[0.82]\n")
    r_good = flow.submit(task, ws_good, source="test")
    assert r_good["outcome"] == "accept", r_good["reasons"]
