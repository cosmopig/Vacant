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
import re

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
            if isinstance(error, str):
                post["error"] = error
            elif output and isinstance(output, dict) and output.get("stdout"):
                post["error"] = output["stdout"]
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


# ── 5. 真實 2,111 格軌跡重播抓出的誤退回歸測試 (P1/P3 Regressions) ─────

def test_dabench_at_name_placeholder_and_scratch_files_do_not_false_positive(env):
    # 回歸測試 1：contract.md 寫 `in the form @name[value]` 時，`name` 是範例佔位詞，不能誤退
    # 回歸測試 2：明確要求寫 answer.txt 時，中間產生的 scratch 檔 (volumes.jsonl) 不能被當成交付檔誤判
    p = _proj(env, "dabench_real", {
        "contract.md": "Write the final output to `answer.txt` in the form @name[value].",
        "goal.md": "Format: @mean_fare[value] where value is a float.",
        "data.csv": "fare\n10.0\n20.0\n",
    })
    a = Agent(p)
    a.ask("Read contract.md and goal.md, analyze data.csv, and write answer.txt.")
    a.read("contract.md")
    a.read("goal.md")
    a.read("data.csv")
    a.bash("python3 -c 'print(15.0)'", stdout="15.0\n")
    # Agent 寫了一個多行 JSONL 中間暫存檔（不是單一 JSON object）
    a.write("volumes.jsonl", "{\"a\": 1}\n{\"a\": 2}\n")
    a.write("answer.txt", "@mean_fare[15.0]\n")
    ev = a.evidence("Done.")
    assert ev["findings"] == []


def test_shell_comments_and_recovered_oneliner_do_not_false_positive(env):
    # 回歸測試 3a：多行 bash 含 `# comment` 的 grep 沒匹配（exit 1）不應被當成 failed_step
    # 回歸測試 3b：探索性 python -c 讀資料檔語法錯，但隨後寫 script 跑成功，不應殘留 failed_step
    p = _proj(env, "shell_comment_real", {
        "goal.md": "Analyze data/fees.json and write answer.txt.",
        "data/fees.json": "[{\"id\": 1}]\n",
    })
    a = Agent(p)
    a.ask("Read goal.md and write answer.txt.")
    a.read("goal.md")
    a.bash("# Check if pattern exists\ngrep -i 'nonexistent' data/fees.json", stdout="", error=True)
    a.bash("python3 -c \"import json; d = json.load(open('data/fees.json')\"", stdout="SyntaxError", error=True)
    a.write("solve.py", "import json\nd = json.load(open('data/fees.json'))\nprint(len(d))\n")
    a.bash("python3 solve.py", stdout="1\n", error=False)
    a.write("answer.txt", "1\n")
    ev = a.evidence("1")
    assert [f for f in ev["findings"] if f["kind"] == "failed_step"] == []


def test_test_hint_extracted_in_test_failed_and_clean_review(env):
    p = _proj(env, "test_hint_proj", {"solution.py": "def f(): return 0\n"})
    a = Agent(p)
    a.ask("Write solution.py and run pytest.")
    a.write("solution.py", "def f(): return 1\n")
    a.bash("pytest -q", stdout="E   AssertionError: assert 1 == 0\n1 failed in 0.1s\n", error=True)
    ev = a.evidence("Done.")
    failed = [f for f in ev["findings"] if f["kind"] == "failed_step"]
    assert len(failed) == 1
    assert failed[0].get("sub") == "test_failed"
    assert "AssertionError" in failed[0].get("test_hint", "")
    _assert_clean_review(ev)


# e002 C 臂實測形態：unittest 多行 FAIL（多個測試方法）+ "FAILED (failures=N)" 總結行。
# 紅燈：hint 必須點名具體失敗的測試方法與斷言差異，而不是只有總結行——
# 否則模型拿不到可修改的線索（e002_hypothesis_arms C 臂退回題的診斷結論：
# 回饋若只到 "FAILED (failures=7)" 這層，模型沒有修的方向）。
def test_unittest_multifail_hint_names_failing_test_not_summary(env):
    p = _proj(env, "unittest_multifail",
              {"bottle_song.py": "def recite(start=10, take=None):\n    raise NotImplementedError\n"})
    a = Agent(p)
    a.ask("Write bottle_song.py and run the unittest suite.")
    a.write("bottle_song.py", "def recite(start=10, take=None):\n    return []\n")
    unittest_out = (
        "FFFFFFF\n"
        "======================================================================\n"
        "FAIL: test_first_generic_verse (bottle_song_test.BottleSongTest.test_first_generic_verse)\n"
        "----------------------------------------------------------------------\n"
        "Traceback (most recent call last):\n"
        '  File "/app/bottle_song_test.py", line 20, in test_first_generic_verse\n'
        "    self.assertEqual(recite(start=10), expected)\n"
        'AssertionError: "10 green bottles hanging on the wall,\\n1[1745 chars]all." != '
        "['Ten green bottles hanging on the wall,'[146 chars]ll.\"]\n"
        "\n"
        "======================================================================\n"
        "FAIL: test_verse_with_2_bottles (bottle_song_test.BottleSongTest.test_verse_with_2_bottles)\n"
        "----------------------------------------------------------------------\n"
        "Traceback (most recent call last):\n"
        '  File "/app/bottle_song_test.py", line 38, in test_verse_with_2_bottles\n'
        "    self.assertEqual(recite(start=2), expected)\n"
        'AssertionError: "2 green bottles hanging on the wall,\\n2 [311 chars]all." != '
        "['Two green bottles hanging on the wall,'[144 chars]ll.\"]\n"
        "----------------------------------------------------------------------\n"
        "Ran 7 tests in 0.001s\n"
        "\n"
        "FAILED (failures=7)\n"
    )
    a.bash("python -m unittest bottle_song_test.py", stdout=unittest_out, error=True)
    ev = a.evidence("Done.")
    failed = [f for f in ev["findings"] if f["kind"] == "failed_step"]
    assert len(failed) == 1
    assert failed[0].get("sub") == "test_failed"
    hint = failed[0].get("test_hint", "")
    # 紅燈 1：hint 必須點名具體失敗的測試方法（哪個 FAIL 區塊隨平台記錄路徑而異，
    # 但必須是 test_xxx 之一；直接抽取器的「最後一個區塊」行為由下方單元測試 pin）
    assert re.search(r"test_(first_generic_verse|verse_with_2_bottles)\b", hint)
    # 紅燈 2：hint 必須帶斷言差異，而不是只有總結行
    assert "AssertionError" in hint
    assert "FAILED (failures=" not in hint
    # 紅燈 3：渲染出的 review 訊息含失敗測試方法名與斷言，且過 KS-1
    txt = _assert_clean_review(ev)
    assert re.search(r"test_(first_generic_verse|verse_with_2_bottles)\b", txt)
    assert "AssertionError" in txt


def test_extract_test_hint_unittest_multiline_and_summary_only(env):
    from vacant_network.trace.evidence import _extract_test_hint
    out = (
        "======================================================================\n"
        "FAIL: test_two (suite_mod.SuiteTest.test_two)\n"
        "----------------------------------------------------------------------\n"
        "Traceback (most recent call last):\n"
        '  File "/home/user1/dev/Vacant/tests/suite_mod_test.py", line 8, in test_two\n'
        "    self.assertEqual(got, expected)\n"
        "AssertionError: 42 != 43\n"
        "----------------------------------------------------------------------\n"
        "Ran 2 tests in 0.001s\n"
        "\n"
        "FAILED (failures=1)\n"
    )
    hint = _extract_test_hint(out, err="FAILED (failures=1)")
    assert hint is not None
    assert hint.startswith("test_two")
    assert "AssertionError" in hint
    # 總結行不得成為 hint；敏感路徑不得外洩
    assert "FAILED (failures=" not in hint
    assert "/home/user1" not in hint
    # 只有總結行（無 FAIL 區塊、無斷言）→ 回 None，而不是把總結行當 hint
    assert _extract_test_hint("Ran 7 tests in 0.001s\n\nFAILED (failures=7)\n",
                              err="FAILED (failures=7)") is None


def test_sed_modify_overwritten_by_subsequent_write_exempt(env):
    p = _proj(env, "sed_exempt", {"solution.py": "def solve(): return 0\n"})
    a = Agent(p)
    a.ask("Fix solution.py so tests pass.")
    # sed 嘗試修改失敗
    a.bash("sed -i 's/0/1/g' solution.py", stdout="sed: -e expression #1: unknown option", error=True)
    # 隨後直接用 write 重寫正確內容
    a.write("solution.py", "def solve(): return 42\n")
    # 測試成功通過
    a.bash("pytest -q", stdout="1 passed in 0.05s", error=False)
    ev = a.evidence("Done.")
    assert [f for f in ev["findings"] if f["kind"] == "failed_step"] == []


def test_invalid_output_python_repr_and_empty_collection(env):
    # (a) Python repr 殘留 (<function ...> / <generator object ...>)
    p1 = _proj(env, "inv_repr")
    a1 = Agent(p1)
    a1.ask("Write the answer to answer.txt.")
    a1.write("answer.txt", "<function solve at 0x7f123456>\n")
    ev1 = a1.evidence()
    inv1 = [f for f in ev1["findings"] if f["kind"] == "invalid_output"]
    assert len(inv1) == 1 and inv1[0]["sub"] == "stub"
    _assert_clean_review(ev1)

    # (b) 問句要求 Which / List / What are 卻輸出空集合 []
    p2 = _proj(env, "inv_empty_col", {"data.csv": "id,val\n1,10\n2,20\n"})
    a2 = Agent(p2)
    a2.ask("Which transactions have value > 5? List their ids in answer.txt.")
    a2.read("data.csv")
    a2.write("answer.txt", "[]\n")
    ev2 = a2.evidence()
    inv2 = [f for f in ev2["findings"] if f["kind"] == "invalid_output"]
    assert len(inv2) == 1 and inv2[0]["sub"] == "empty"
    _assert_clean_review(ev2)


def test_answer_format_forbid_empty_collection_and_numeric_range(env):
    proj = env / "vproj_adv"
    (proj / ".vacant").mkdir(parents=True, exist_ok=True)
    raw = C.scaffold("task-v2", deliverable=["*.json", "*.txt"], destination="dir:published")
    raw["claims"] = [
        {"id": "ans_range", "verifier": "answer_format",
         "params": {"path": "answer.txt", "format": "number", "numeric_range": [0.0, 1.0]}},
        {"id": "json_no_empty", "verifier": "answer_format",
         "params": {"path": "out.json", "format": "json", "forbid_empty_collection": True}},
    ]
    cpath = proj / ".vacant" / "contract.json"
    cpath.write_text(json.dumps(raw, indent=2))
    flow.lock(cpath)
    task = flow.open_task(cpath)

    # 1) 壞交付：數值超出範圍 (1.5 > 1.0) + 空 JSON 陣列 [] -> reject
    ws_bad = env / "ws_bad_adv"
    ws_bad.mkdir()
    (ws_bad / "answer.txt").write_text("1.5\n")
    (ws_bad / "out.json").write_text("[]\n")
    r_bad = flow.submit(task, ws_bad, source="test")
    assert r_bad["outcome"] == "reject"
    by_id = {c["claim_id"]: c["status"] for c in r_bad["results"]}
    assert by_id == {"ans_range": "FAIL", "json_no_empty": "FAIL"}

    # 2) 好交付：合法數值 0.85 + 非空 JSON 陣列 [1, 2] -> accept
    ws_good = env / "ws_good_adv"
    ws_good.mkdir()
    (ws_good / "answer.txt").write_text("0.85\n")
    (ws_good / "out.json").write_text("[1, 2]\n")
    r_good = flow.submit(task, ws_good, source="test")
    assert r_good["outcome"] == "accept", r_good["reasons"]


def test_unread_doc_finding_and_clean_review(env):
    files = {
        "data/manual.md": "# Business Rules\nFees are waived for account_type=R.\n",
        "data/payments.csv": "id,account_type,fee\n1,R,0\n2,S,15\n"
    }
    p = _proj(env, "unread_doc_proj", files=files)
    a = Agent(p)
    a.ask("Before answering, reference documentation in data/ dir. What is the fee? Write answer to answer.txt.")
    a.bash("python3 -c \"import pandas as pd; df=pd.read_csv('data/payments.csv'); print(df['fee'].sum())\"", "15\n")
    a.write("answer.txt", "15\n")
    ev = a.evidence("15")
    unread_docs = [f for f in ev["findings"] if f.get("sub") == "unread_doc"]
    assert len(unread_docs) == 1
    assert unread_docs[0]["path"] == "data/manual.md"
    _assert_clean_review(ev)


def test_empty_filter_finding_and_clean_review(env):
    p = _proj(env, "empty_filter_proj")
    a = Agent(p)
    a.ask("What is the fee for account_type = 'R'? Write ONLY the final answer to answer.txt.")
    a.bash("python3 -c \"import pandas as pd; df=pd.read_csv('data.csv'); print(df[df['type']=='WRONG']['fee'].sum())\"", "0\n")
    a.write("answer.txt", "0\n")
    ev = a.evidence("0")
    inv = [f for f in ev["findings"] if f.get("sub") == "empty_filter"]
    assert len(inv) == 1
    assert inv[0]["path"] == "answer.txt"
    _assert_clean_review(ev)


# ── C37 正式批次（2026-10-02，764 pass）的 12 個最終誤報場景重構 ─────────────────
# 來源：~/dev/ops/ref/c37_final.json（1187 格，pass=764，最終誤報 12 格）。
# 這些場景的共性：交付內容正確（Harbor 評分為 pass），但 trace 層仍退回。
# 重構原則：用最小步驟重現當時的 finding payload 形狀（cmd / path / value），
# 斷言現行代碼不再誤退；另加一個反向控制，確保真失敗仍被標記。

def test_c37_failed_head_after_consumed_does_not_false_positive(env):
    """dabstep-14-s2：讀過 payments.csv 後再跑 `head -n 1 payments.csv` 失敗，
    改用別的方法算出正確答案並交付 → 不得 failed_step。"""
    p = _proj(env, "c37_fp1", {"payments.csv": "merchant,amount\nA,10\nB,20\n"})
    a = Agent(p)
    a.ask("Analyze payments.csv and write the total to answer.txt.")
    a.read("payments.csv")
    a.bash("head -n 1 payments.csv", error=True)
    a.bash("python3 -c \"print(10+20)\"", stdout="30\n")
    a.write("answer.txt", "30\n")
    ev = a.evidence("30")
    assert not [f for f in ev["findings"] if f["kind"] == "failed_step"], ev["findings"]
    _assert_clean_review(ev)


def test_c37_grep_batch_no_match_does_not_false_positive(env):
    """dabstep-20-s2：一批 `grep -c` 無匹配（exit 1）後用別的方法交付 → 不得 failed_step。"""
    p = _proj(env, "c37_fp2", {"payments.csv": "merchant\nA\nB\n"})
    a = Agent(p)
    a.ask("Check payments.csv for known merchants and write the count to answer.txt.")
    a.bash("grep -c \",Crossfit_Hanna,\" payments.csv\ngrep -c \",Eggnest,\" payments.csv",
           stdout="", error=True)
    a.bash("wc -l < payments.csv", stdout="3\n")
    a.write("answer.txt", "3\n")
    ev = a.evidence("3")
    assert not [f for f in ev["findings"] if f["kind"] == "failed_step"], ev["findings"]
    _assert_clean_review(ev)


def test_c37_heredoc_script_fail_then_other_path_does_not_false_positive(env):
    """C37R-dabstep-25-s2：heredoc 寫 analyze_outliers.py 並執行失敗（無 pandas），
    改用另一條路徑算出正確答案並交付 → 不得 failed_step。"""
    p = _proj(env, "c37_fp3", {"payments.csv": "amount\n1\n2\n"})
    a = Agent(p)
    a.ask("Count outliers in payments.csv and write the answer to answer.txt.")
    a.read("payments.csv")
    a.bash("cat << 'EOF' > analyze_outliers.py\nimport pandas as pd\nprint(pd)\nEOF\npython3 analyze_outliers.py",
           stdout="Traceback (most recent call last):\nModuleNotFoundError: No module named 'pandas'",
           error=True)
    a.write("count.py", "print(3)\n")
    a.bash("python3 count.py", stdout="3\n")
    a.write("answer.txt", "3\n")
    ev = a.evidence("3")
    assert not [f for f in ev["findings"] if f["kind"] == "failed_step"], ev["findings"]
    _assert_clean_review(ev)


def test_c37_sed_fail_then_rewrite_does_not_false_positive(env):
    """C37R-dabstep-61-s2：`sed -i` 改 analyze_fraud.py 失敗，重寫後跑通並交付 → 不得 failed_step。"""
    p = _proj(env, "c37_fp4", {"analyze_fraud.py": "print(1)\n"})
    a = Agent(p)
    a.ask("Fix analyze_fraud.py to print the top count and write it to answer.txt.")
    a.bash("sed -i 's/print(1)/print(2)/' analyze_fraud.py\npython3 analyze_fraud.py",
           stdout="sed: -e expression #1: error", error=True)
    a.write("analyze_fraud.py", "print(3)\n")
    a.bash("python3 analyze_fraud.py", stdout="3\n")
    a.write("answer.txt", "3\n")
    ev = a.evidence("3")
    assert not [f for f in ev["findings"] if f["kind"] == "failed_step"], ev["findings"]
    _assert_clean_review(ev)


def test_c37_app_prefix_answer_path_does_not_false_positive(env):
    """dabstep-62/65、C37R-dabstep-71：任務說寫 `/app/answer.txt`，
    agent 在專案根寫了 `answer.txt` → 不得 missing_output。"""
    p = _proj(env, "c37_fp5", {"payments.csv": "amount\n1\n2\n"})
    a = Agent(p)
    a.ask("Analyze payments.csv and write your final answer to /app/answer.txt.")
    a.read("payments.csv")
    a.bash("python3 -c \"print(1+2)\"", stdout="3\n")
    a.write("answer.txt", "3\n")
    ev = a.evidence("3")
    assert not [f for f in ev["findings"] if f["kind"] == "missing_output"], ev["findings"]
    _assert_clean_review(ev)


def test_c37_computed_answer_not_unsourced(env):
    """dabench-055/129：答案數字是算出來的（資料欄加總），不在逐字語料裡 → 不得 unsourced。"""
    p = _proj(env, "c37_fp6", {"data.csv": "x\n1\n2\n"})
    a = Agent(p)
    a.ask("Compute the sum of x in data.csv and write it to answer.txt.")
    a.bash("cat data.csv", stdout="x\n1\n2\n")
    a.write("answer.txt", "3\n")
    ev = a.evidence("3")
    assert not [f for f in ev["findings"] if f["kind"] == "unsourced"], ev["findings"]
    _assert_clean_review(ev)


def test_c37_failed_head_never_consumed_still_flagged(env):
    """反向控制：資料從未讀到，`head` 失敗就交付不來源答案 → failed_step 仍須標記。"""
    p = _proj(env, "c37_neg0", {"payments.csv": "merchant,amount\nA,10\n"})
    a = Agent(p)
    a.ask("Analyze payments.csv and write the total to answer.txt.")
    a.bash("head -n 1 payments.csv", error=True)
    a.write("answer.txt", "42\n")
    ev = a.evidence("42")
    assert [f for f in ev["findings"] if f["kind"] == "failed_step"], ev["findings"]


def test_c37_helper_script_fails_then_awk_recovery_does_not_false_positive(env):
    """自寫 helper（calc.py）跑失敗，agent 改用 `awk` 直接讀同一份資料算出正確值並交付
    → 失敗是放棄的嘗試，不是略過；不得 failed_step。
    （2026-10-25：此類真實樣式在舊邏輯下被誤報——豁免只認 reads_given，不認 runs_own。）"""
    p = _proj(env, "c37_fp7", {"sales.csv": "day,amount\nmon,100\ntue,20\n"})
    a = Agent(p)
    a.ask("Read sales.csv, total the amount column, and write the result to report.md.")
    a.write("calc.py", "import csv\nprint(sum(r['amount'] for r in csv.DictReader(open('sales.csv'))))\n")
    a.bash("python3 calc.py",
           stdout="Traceback (most recent call last):\nKeyError: 'amount'", error=True)
    a.bash("awk -F, 'NR>1{n+=\\$2} END{print n}' sales.csv", stdout="120\n")
    a.write("report.md", "# Total\n\n120\n")
    ev = a.evidence("Wrote report.md.")
    assert not [f for f in ev["findings"] if f["kind"] == "failed_step"], ev["findings"]
    _assert_clean_review(ev)


def test_c37_helper_fails_then_other_script_succeeds_not_false_positive(env):
    """自寫 calc.py 跑失敗、改用另一支自寫 count.py 跑通並交付 → 不得 failed_step。
    （2026-10-25：與 test_s5 的差別只在「有無後續成功替代」；反向控制見 test_s5_own_script_\
    fails_then_the_report_is_written_by_hand。）"""
    p = _proj(env, "c37_fp8", {"data.csv": "x\n1\n2\n"})
    a = Agent(p)
    a.ask("Sum the x column of data.csv and write the answer to answer.txt.")
    a.write("calc.py", "print('boom')\nraise RuntimeError('bad')\n")
    a.bash("python3 calc.py",
           stdout="Traceback (most recent call last):\nRuntimeError: bad", error=True)
    a.write("count.py", "print(1+2)\n")
    a.bash("python3 count.py", stdout="3\n")
    a.write("answer.txt", "3\n")
    ev = a.evidence("3")
    assert not [f for f in ev["findings"] if f["kind"] == "failed_step"], ev["findings"]
    _assert_clean_review(ev)


def test_c37_cd_and_grep_no_match_does_not_false_positive(env):
    """`cd . && grep -c '免運' doc.md` 無匹配（exit 1）後誠實回報「沒有」→ 不得 failed_step。
    （2026-10-25：`cd … &&` 鏈頭讓 `_no_match_only` 認不出搜尋指令而誤報；
    真正的 grep 錯誤仍須標記，見 test_a_search_that_errors_on_a_given_file_is_still_a_failed_step。）"""
    p = _proj(env, "c37_fp9", {"doc.md": "# Policy\nshipping: standard only\n"})
    a = Agent(p)
    a.ask("Check doc.md for a 免運 policy and write your answer to answer.txt.")
    a.bash("cd . && grep -c '免運' doc.md", stdout="0\n", error=True)
    a.write("answer.txt", "not found\n")
    ev = a.evidence("doc.md has no 免運 policy.")
    assert not [f for f in ev["findings"] if f["kind"] == "failed_step"], ev["findings"]
    _assert_clean_review(ev)


def test_pushable_for_caps_test_failed_to_one_round():
    from vacant_network.trace.zerostop import pushable_for
    f_test = {"kind": "failed_step", "sub": "test_failed", "cmd": "pytest"}
    f_miss = {"kind": "missing_output", "path": "answer.txt"}

    # 第 0 回合：全部可退回
    p0 = pushable_for([f_test, f_miss], used=0, error_stop=False)
    assert len(p0) == 2

    # 第 1 回合：test_failed 不再退回，但 missing_output 照常退回
    p1 = pushable_for([f_test, f_miss], used=1, error_stop=False)
    assert len(p1) == 1 and p1[0]["kind"] == "missing_output"


def test_parse_test_score_and_best_checkpoint():
    from vacant_network.trace.evidence import parse_test_score
    # unittest OK
    assert parse_test_score("Ran 24 tests in 0.05s\n\nOK") == (24, 0)
    # unittest FAILED
    assert parse_test_score("Ran 20 tests in 0.05s\n\nFAILED (failures=2, errors=1)") == (17, 3)
    # pytest passed
    assert parse_test_score("15 passed in 0.1s") == (15, 0)
    # pytest failed
    assert parse_test_score("12 passed, 3 failed in 0.2s") == (12, 3)


def test_fresh_hint_renders_clean_memory():
    from vacant_network.vrun import retry as R
    failures = "FAILED test_square: assert 9 == 10\nAssertionError: mismatch\n"
    hint = R.render_fresh_hint(failures, attempt=1, max_attempts=3)
    assert len(hint.encode("utf-8")) <= 400
    assert "AssertionError" in hint or "FAILED" in hint
    assert "clean origin" in hint


def test_checkpoint_restore_records_chain_event_and_only_restores_on_regression(env):
    """重現並釘住 e002 C 臂實跑缺陷：
    1. restore_best_checkpoint 必須寫入合法的 `checkpoint_restore` 鏈事件（通過 rec.verify()），
       並更新 state.last_index 與 Trace.latest_index()，後續步驟不產生假 unrecorded_change。
    2. zerostop 只在分數退步（best_score > cur_score）且最後一次測試後無新寫入時才回滾；
       分數平手（如 pg_bottle_song 連續 (1, 6)）或最後一次測試後有修改時不得覆寫工作區。
    3. zerostop.ended 在步驟 input_blob 被 GC 回收後不得因 FileNotFoundError 崩潰。
    """
    from vacant_network.trace.blame import Trace

    # (A) 分數退步：v1 (5 passed, 1 failed) -> v2 (2 passed, 4 failed)
    p1 = _proj(env, "ckpt_regress", {"solution.py": "v0\n"})
    a1 = Agent(p1)
    a1.ask("Implement solution.py and run solution_test.py.")
    a1.write("solution.py", "def f():\n    return 'v1_best'\n")
    a1.bash("python3 solution_test.py",
            stdout="Ran 6 tests in 0.01s\n\nFAILED (failures=1)", error=True)
    # 第一次 stop：退回 failed_step/test_failed（round 1）
    r1 = a1.stop("Tried v1.")
    assert r1.get("decision") == "block"

    # 第二回合：agent 改壞成 v2 (2 passed, 4 failed) 後再 stop（used=1，不再退回）
    a1.write("solution.py", "def f():\n    return 'v2_worse'\n")
    a1.bash("python3 solution_test.py",
            stdout="Ran 6 tests in 0.01s\n\nFAILED (failures=4)", error=True)
    r2 = a1.stop("Tried v2.")
    assert r2.get("decision") != "block"
    # 工作區必須已回滾到 v1_best，且鏈上有 checkpoint_restore 事件並通過驗鏈
    assert (p1 / "solution.py").read_text() == "def f():\n    return 'v1_best'\n"
    rec1 = Recorder(capture.workspace_for(str(p1)))
    ok, msg = rec1.verify()
    assert ok, msg
    evs1 = rec1.events()
    restores1 = [e for e in evs1 if e.get("type") == "checkpoint_restore"]
    assert len(restores1) == 1
    tr1 = Trace(rec1)
    assert tr1.latest_index() == restores1[0]["target_index"]
    assert tr1.file_text(tr1.latest_index(), "solution.py") == "def f():\n    return 'v1_best'\n"

    # (B) 分數平手（如 pg_bottle_song 連續 1 passed, 6 failed）：不得把 v2 覆寫回 v1
    p2 = _proj(env, "ckpt_tie", {"solution.py": "v0\n"})
    a2 = Agent(p2)
    a2.ask("Implement solution.py and run solution_test.py.")
    a2.write("solution.py", "def f():\n    return 'v1_tie'\n")
    a2.bash("python3 -m unittest solution_test.py",
            stdout="Ran 7 tests in 0.01s\n\nFAILED (failures=6)", error=True)
    assert a2.stop("Tried v1.").get("decision") == "block"
    a2.write("solution.py", "def f():\n    return 'v2_tie_latest'\n")
    a2.bash("python3 -m unittest solution_test.py",
            stdout="Ran 7 tests in 0.01s\n\nFAILED (failures=6)", error=True)
    assert a2.stop("Tried v2.").get("decision") != "block"
    assert (p2 / "solution.py").read_text() == "def f():\n    return 'v2_tie_latest'\n"
    rec2 = Recorder(capture.workspace_for(str(p2)))
    assert not [e for e in rec2.events() if e.get("type") == "checkpoint_restore"]

    # (C) 最後一次測試失敗後 agent 又改了交付檔（尚未重跑測試）且被強制切斷（ended），
    #     且舊步驟的 input_blob 已被 GC 刪除：不得崩潰，也不得覆寫最後一次未測修改
    p3 = _proj(env, "ckpt_post_edit", {"solution.py": "v0\n"})
    a3 = Agent(p3)
    a3.ask("Implement solution.py and run pytest.")
    a3.write("solution.py", "def f():\n    return 'v1_good'\n")
    a3.bash("pytest -q", stdout="5 passed, 1 failed in 0.02s", error=True)
    assert a3.stop("Tried v1.").get("decision") == "block"
    a3.write("solution.py", "def f():\n    return 'v2_bad'\n")
    a3.bash("pytest -q", stdout="1 passed, 5 failed in 0.02s", error=True)
    a3.write("solution.py", "def f():\n    return 'v3_untested_fix'\n")
    rec3 = Recorder(capture.workspace_for(str(p3)))
    # 模擬 GC 刪除了某個步驟的 input_blob
    for e in rec3.events():
        if e.get("type") == "step" and e.get("input_blob"):
            rec3.blobs.path(e["input_blob"]).unlink(missing_ok=True)
            break
    end_res = zerostop.ended("claude", a3.s, str(p3), mode="evidence")
    assert "ended" in end_res
    assert (p3 / "solution.py").read_text() == "def f():\n    return 'v3_untested_fix'\n"





