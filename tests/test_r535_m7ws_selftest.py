"""這支在架構裡承重什麼：`run_r535.py --selftest` 的**牙齒**。

護欄表第二列把那支自檢放進了判定路徑：

    RF ≠ RS 顯著 ∧ M7_ws = 0 ⇒ 先跑 `--selftest`
      紅 ⇒ M7_ws 判 INVALID（**量具壞了**，不是 MECHANISM_BREACH）
      綠 ⇒ MECHANISM_BREACH

一個在解析器壞掉時照樣回綠的自檢，跟把它關掉在輸出上同形——而它現在決定的是
「這是機制的發現」還是「這是我們的 bug」。所以本檔把解析器**故意弄壞四種壞法**，
每一種都要讓 `--selftest` 轉紅。只證明「好的時候是綠的」不夠。

同時釘住三種 wire 在 `measure_m7_ws` 上的答案：
沒有工具呼叫 ⇒ `null`（不是 `False`）／形狀解不動 ⇒ `null` ＋
`unparsable_tool_shape`／正常 ⇒ `True` 且子指標認得 `bash cat solution.py`。
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "ops" / "gain" / "r535" / "run_r535.py"


def _load():
    spec = importlib.util.spec_from_file_location("run_r535_under_test", SRC)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def R():
    return _load()


def test_selftest_is_green_when_the_parser_works(R):
    doc = R.selftest_m7_ws(verbose=False)
    assert doc["green"] is True, doc
    assert len(doc["cases"]) == 4


def test_selftest_goes_red_when_the_parser_always_returns_empty(R):
    """壞法 A：解析器退化成永遠回空陣列 ⇒ M7_ws 會恆為 0。"""
    R._tool_calls_from_body = lambda blob: (
        [], {"tool_role_msgs": 0, "tool_use_blocks": 0, "unparsable": False})
    assert R.selftest_m7_ws(verbose=False)["green"] is False


def test_selftest_goes_red_when_unknown_shapes_are_silently_zero(R):
    """壞法 B：**舊版的行為**——不認得的工具形狀安靜當成 0 通。

    這一條是本檔存在的主因：那個 bug 不會讓任何東西壞掉，它只會把
    「量具壞了」報成「機制沒被觸發」。
    """
    orig = R._tool_calls_from_body

    def silent(blob):
        calls, ev = orig(blob)
        return calls, {**ev, "unparsable": False}

    R._tool_calls_from_body = silent
    doc = R.selftest_m7_ws(verbose=False)
    assert doc["green"] is False
    bad = [c["case"] for c in doc["cases"] if not c["ok"]]
    assert bad == ["unknown_tool_shape_must_say_unparsable"], bad


def test_selftest_goes_red_when_submetric_misses_bash_cat(R):
    """壞法 C：子指標只認 read 工具、不認 `bash cat solution.py`。

    兩條路在機制上是同一件事（讀了自己上一份錯碼），漏掉一條會讓
    `M7_ws_solution` 系統性偏低。
    """
    R.reads_own_solution = lambda name, args: (
        "solution.py" in args
        and any(v in (name or "").lower() for v in R._READ_VERBS))
    assert R.selftest_m7_ws(verbose=False)["green"] is False


def test_selftest_goes_red_when_bad_bytes_return_empty_not_none(R):
    """壞法 D：parse 不動時回空陣列而不是 None。

    那會讓「這通解不動」與「這通真的沒有工具呼叫」在輸出上同形。
    """
    orig = R._tool_calls_from_body

    def swallow(blob):
        calls, ev = orig(blob)
        return ([] if calls is None else calls), ev

    R._tool_calls_from_body = swallow
    assert R.selftest_m7_ws(verbose=False)["green"] is False


def _one_attempt_run(tmp_path: pathlib.Path, blob: bytes) -> pathlib.Path:
    run = tmp_path / "run"
    (run / "wire_RUN-ON").mkdir(parents=True)
    (run / "wire_RUN-ON" / "c1.req.bin").write_bytes(blob)
    (run / "wire_RUN-ON" / "index.jsonl").write_text(
        json.dumps({"call_id": "c1"}) + "\n", encoding="utf-8")
    return run


_SUMMARY = {"arm": "RUN-ON", "attempts": [
    {"attempt": 1, "requests_seen_cumulative": 0},
    {"attempt": 2, "requests_seen_cumulative": 1}]}
_SLICES = {1: [], 2: ["c1"]}


def test_no_tool_calls_is_null_not_false(R, tmp_path):
    """**沒有工具呼叫 ⇒ `null`**（分母是 0），不是 `False`。"""
    run = _one_attempt_run(tmp_path, R._selftest_wire_no_tools())
    res = R.measure_m7_ws(run, _SUMMARY, _SLICES, {"ok": True})
    assert res["m7_ws"] is None
    assert res["m7_ws_reason"] == "no_tool_calls_in_attempt_ge2"
    assert res["m7_ws_solution"] is None


def test_unparsable_shape_is_null_not_zero(R, tmp_path):
    """**解不動的工具形狀 ⇒ `null`**，理由講出來是「量具」不是「機制」。"""
    run = _one_attempt_run(tmp_path, R._selftest_wire_unknown_shape())
    res = R.measure_m7_ws(run, _SUMMARY, _SLICES, {"ok": True})
    assert res["m7_ws"] is None
    assert res["m7_ws_reason"] == "unparsable_tool_shape"
    assert res["m7_ws_unparsable_evidence"]


def test_tools_jsonl_lands_every_call_with_the_required_fields(R, tmp_path):
    """工具序列**一律落盤**，欄位齊全（`args_head` 截 80 字）。"""
    run = _one_attempt_run(tmp_path, R._selftest_wire_openai())
    out = tmp_path / "tools.jsonl"
    res = R.measure_m7_ws(run, _SUMMARY, _SLICES, {"ok": True},
                          tools_path=out)
    rows = [json.loads(x) for x in out.read_text().splitlines() if x.strip()]
    assert len(rows) == 5
    assert [r["seq"] for r in rows] == [1, 2, 3, 4, 5]
    for r in rows:
        assert {"attempt", "call_id", "tool", "args_head", "seq"} <= set(r)
        assert len(r["args_head"]) <= 80
    # 子指標認得兩條路：`bash cat solution.py` 與 `read solution.py`
    assert [r["reads_own_solution"] for r in rows] == [
        False, False, True, True, False]
    assert res["m7_ws"] is True and res["m7_ws_solution"] is True
    assert res["m7_ws_solution_n"] == 2


def test_submetric_null_when_there_is_no_second_attempt(R, tmp_path):
    """沒有第 2 次嘗試 ⇒ 兩個指標都 `null`，**不可以記成 false**。"""
    run = _one_attempt_run(tmp_path, R._selftest_wire_openai())
    res = R.measure_m7_ws(run, {"arm": "RUN-ON", "attempts": [
        {"attempt": 1, "requests_seen_cumulative": 1}]}, {1: ["c1"]},
        {"ok": True})
    assert res["m7_ws"] is None and res["m7_ws_solution"] is None
    assert res["m7_ws_reason"] == "no_second_attempt"
    assert res["m7_ws_solution_reason"] == "no_second_attempt"
