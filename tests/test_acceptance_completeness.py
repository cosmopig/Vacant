"""驗收彙總的完整性——外部質疑報告（2026-09-24）§03 P0 ＋附錄 B（T1）搬進 repo。

報告的最小重現只照節錄邏輯跑；這裡走**真的** `acceptance.run_suite`
（`NoneSandbox`，同一支 driver、同一個對帳），把那張表的每一列變成一個斷言：

    | 情況                          | 宣告 | 回報 | rc | 舊判定   | 應判定 |
    | 兩項都成功                     | 2    | 2    | 0  | 全過     | 全過   |
    | 第二項 assertion 失敗          | 2    | 2    | 0  | 不過     | 不過   |
    | 第一項成功後 os._exit(7)       | 2    | 1    | 7  | 全過 ✗   | 不過   |
    | 第一項成功後 os._exit(0)       | 2    | 1    | 0  | 全過 ✗   | 不過   |
    | 單項 return False              | 1    | 1    | 0  | 全過 ✗   | 不過   |

另外補報告 §16 要求「先證明它會對壞狀況拒絕」的幾種：重複 id、清單外 id、
async check、動態產生的 check、偽造一行 PASS 後真的結果又來。
"""
from __future__ import annotations

import pathlib

import pytest

from vacant_network.vrun import acceptance, sandbox as sb


def _run(tmp_path: pathlib.Path, test_src: str, solution: str = "") -> dict:
    ws = tmp_path / "ws"
    suite = tmp_path / "suite"
    ws.mkdir()
    suite.mkdir()
    if solution:
        (ws / "solution.py").write_text(solution, encoding="utf-8")
    (suite / "test_visible.py").write_text(test_src, encoding="utf-8")
    return acceptance.run_suite(sb.NoneSandbox(), ws, suite, suite="visible",
                                task_id="t", verify_root=tmp_path / "_v",
                                timeout_s=20)


def _kinds(res: dict) -> list[str]:
    return [c["kind"] for f in res["files"] for c in f["cases"]]


def test_positive_control_two_passes(tmp_path):
    res = _run(tmp_path, "def check_a():\n    pass\n\ndef check_b():\n    assert 1 + 1 == 2\n")
    assert res["all_pass"] is True
    assert res["complete"] is True
    assert (res["passed"], res["total"]) == (2, 2)
    assert res["files"][0]["declared"] == ["check_a", "check_b"]


def test_negative_control_assert_keeps_original_reason(tmp_path):
    res = _run(tmp_path, "def check_a():\n    pass\n\ndef check_b():\n    assert 1 == 2, 'nope'\n")
    assert res["all_pass"] is False
    bad = acceptance.failing_cases(res)
    assert [(c["case"], c["kind"], c["message"]) for c in bad] == [("check_b", "assert", "nope")]


@pytest.mark.parametrize("code", [7, 0])
def test_early_exit_after_first_pass_is_not_all_pass(tmp_path, code):
    """報告附錄 B 第三、四列：舊版在這兩格都判 all_pass=True。"""
    res = _run(tmp_path,
               "import os\n\ndef check_a():\n    pass\n\n"
               f"def check_b():\n    os._exit({code})\n")
    assert res["all_pass"] is False
    assert res["complete"] is False
    f = res["files"][0]
    assert f["end_marker"] is False
    by_case = {c["case"]: c for c in f["cases"]}
    assert by_case["check_a"]["ok"] is True
    assert by_case["check_b"]["kind"] == "incomplete"
    assert by_case["<file>"]["kind"] == "incomplete"
    assert res["passed"] < res["total"]


def test_return_false_is_a_failure(tmp_path):
    """附錄 B 第五列：舊版契約把 `return False` 記成 pass。"""
    res = _run(tmp_path, "def check_a():\n    return False\n")
    assert res["all_pass"] is False
    assert _kinds(res) == ["assert"]


def test_return_true_and_none_still_pass(tmp_path):
    res = _run(tmp_path, "def check_a():\n    return True\n\ndef check_b():\n    return None\n")
    assert res["all_pass"] is True


def test_other_return_value_is_protocol_failure(tmp_path):
    res = _run(tmp_path, "def check_a():\n    return 0\n")
    assert res["all_pass"] is False
    assert _kinds(res) == ["protocol"]


def test_async_check_is_not_silently_passed(tmp_path):
    res = _run(tmp_path, "async def check_a():\n    assert False\n")
    assert res["all_pass"] is False
    assert _kinds(res) == ["protocol"]


def test_dynamic_check_is_reported_not_skipped(tmp_path):
    res = _run(tmp_path,
               "def check_a():\n    pass\n\n"
               "globals()['check_generated'] = lambda: None\n")
    assert res["all_pass"] is False
    cases = {c["case"]: c for c in res["files"][0]["cases"]}
    assert cases["check_generated"]["kind"] == "protocol"


def test_forged_pass_line_then_real_result_is_duplicate(tmp_path):
    """候選碼讀得到 nonce（同一個直譯器）⇒ 能偽造一行。對帳至少抓得到「重複」。"""
    res = _run(tmp_path,
               "import sys, json\n\n"
               "def check_a():\n"
               "    sys.__stdout__.write(sys.argv[3] + json.dumps({'case': 'check_a', 'ok': True,"
               " 'kind': 'pass', 'message': '', 'where': None, 'output': ''}) + '\\n')\n"
               "    sys.__stdout__.flush()\n"
               "    assert False, 'real failure'\n")
    assert res["all_pass"] is False
    kinds = sorted(_kinds(res))
    assert "protocol" in kinds


def test_import_error_marks_every_declared_case(tmp_path):
    res = _run(tmp_path,
               "from solution import add\n\n"
               "def check_a():\n    assert add(1, 2) == 3\n\n"
               "def check_b():\n    assert add(2, 2) == 4\n")
    assert res["all_pass"] is False
    cases = {c["case"]: c["kind"] for c in res["files"][0]["cases"]}
    assert cases["<module>"] == "import"
    assert cases["check_a"] == cases["check_b"] == "import"
    # 分母是宣告清單（2 條＋檔案層級 1 筆），回饋文字仍只貼那一行 import 錯誤
    assert res["total"] == 3 and res["passed"] == 0
    assert acceptance.render_failures(res).count("::") == 1


def test_main_mode_still_works(tmp_path):
    res = _run(tmp_path, "def main():\n    assert True\n")
    assert res["all_pass"] is True
    assert res["files"][0]["declared"] == ["main"]


def test_hand_built_record_without_complete_is_not_all_pass():
    """舊呼叫端手造的檔案紀錄沒有 `complete` 欄位 ⇒ fail-closed。"""
    res = acceptance._finish("visible", "t", [
        {"file": "test_x.py", "cases": [{"case": "check_a", "ok": True, "kind": "pass"}],
         "passed": 1, "total": 1}])
    assert res["all_pass"] is False


def test_declared_cases_reads_syntax_only(tmp_path):
    p = tmp_path / "test_x.py"
    p.write_text("raise SystemExit('never executed')\n\n"
                 "def check_b():\n    pass\n\ndef helper():\n    pass\n\n"
                 "async def check_c():\n    pass\n\ndef main():\n    pass\n",
                 encoding="utf-8")
    assert acceptance.declared_cases(p) == ["check_b", "check_c"]
    p.write_text("def (:\n", encoding="utf-8")
    assert acceptance.declared_cases(p) == []


def test_earlier_file_cannot_rewrite_a_later_test_file(tmp_path):
    """`none` 後端沒有唯讀掛載：舊版裡 test_a 引入的候選碼能改寫 test_b（實測）。
    現在每個測試檔各拿一份從記憶體重寫的新目錄 ⇒ 改了也不影響下一個檔案。"""
    ws = tmp_path / "ws"
    suite = tmp_path / "suite"
    ws.mkdir()
    suite.mkdir()
    (ws / "solution.py").write_text(
        "import os, sys\n"
        "d = os.path.dirname(os.path.abspath(sys.argv[2]))\n"
        "p = os.path.join(d, 'test_b.py')\n"
        "if os.path.exists(p):\n"
        "    open(p, 'w').write('def check_b():\\n    pass\\n')\n",
        encoding="utf-8")
    (suite / "test_a.py").write_text("import solution\n\ndef check_a():\n    pass\n",
                                     encoding="utf-8")
    (suite / "test_b.py").write_text("def check_b():\n    assert False, 'real b'\n",
                                     encoding="utf-8")
    res = acceptance.run_suite(sb.NoneSandbox(), ws, suite, suite="visible",
                               task_id="t", verify_root=tmp_path / "_v", timeout_s=20)
    assert res["all_pass"] is False
    assert any(c["message"] == "real b" for c in acceptance.failing_cases(res))
    assert res["suite_sha256"] and len(res["suite_sha256"]) == 64


def test_launcher_child_sees_pwd_equal_to_workspace(tmp_path, monkeypatch):
    """agentlane 36609614 的洞：直接 exec 的子行程繼承了啟動目錄的 PWD。"""
    import json
    import sys

    from vacant_network.vrun import launcher

    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.setenv("PWD", str(tmp_path))  # 啟動目錄 ≠ 工作區
    probe = ("import os, json; open('pwd.json','w').write(json.dumps("
             "{'PWD': os.environ.get('PWD'), 'cwd': os.getcwd()}))")
    launcher.run([sys.executable, "-c", probe], workspace=ws, run_dir=tmp_path / "rd",
                 suite_dir=None, allow_no_suite=True, sandbox_name="none",
                 vacant_on=True, task_id="pwd_probe")
    seen = json.loads((ws / "pwd.json").read_text())
    assert seen["PWD"] == str(ws.resolve()) == seen["cwd"]
