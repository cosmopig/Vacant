"""`M7_name`／`M7_file` 的分工——**兩個數字合起來才說得出那句話**。

這支在架構裡承重什麼
────────────────────
R535 三個主要交付數字的第一個是「RF 臂的回饋有沒有進到模型輸入」。
預註冊草稿把 `VACANT_FEEDBACK` 列進 `M7_file` 的特徵字串，但——

**回饋檔的內容裡一個字都沒有提到自己叫什麼。** `FEEDBACK_HEADER` 是
``<!-- Written by `vacant run` … -->`` ＋ ``# Acceptance feedback (attempt …)``，
`FEEDBACK_BODY` 也沒有。三個樣板常數實測都是 `False`。

⇒ 那個 needle **只可能命中檔名**。而 NOTHINK 下 agent 一跑 `ls`，tool result 就回
``solution.py\\nTASK.md\\nVACANT_FEEDBACK.md`` ⇒ 照字面算，RF 的 `M7_file` 會是 ≈100%，
**把「看見檔名沒讀」記成「讀了」，方向正好相反**。

修法是把它拆成兩個量：

| | 量什麼 | NOTHINK 下的預期 |
|---|---|---|
| `M7_name` | **檔名**出現在 wire | ≈ 100% |
| `M7_file` | **內容**出現在 wire | 0 |

**`M7_name` 高 ＋ `M7_file` = 0 ＝「看見了檔名，沒有讀」。**
單看任何一個都說不出這件事——`M7_file = 0` 可能是「根本沒看到」，
`M7_name` 高本身也不代表沒讀。

⚠ 這不是假想：2026-09-18 的 NOTHINK 冒煙裡，RF 那格的 `ls -F` tool result 逐字是
``solution.py\\nTASK.md\\nVACANT_FEEDBACK.md``，而 RS 只有 ``TASK.md``；
RF 看見了兩個檔、兩個都沒讀，回頭讀 `TASK.md`、覆寫成同一份錯碼，
最後交付的 `solution.py` 與 RS **sha256 逐位元相同**。
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "_r535_runner", REPO / "ops" / "gain" / "r535" / "run_r535.py")
R = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(R)

FEEDBACK_TEXT = (
    "<!-- Written by `vacant run` between attempts.\n"
    "     This is machine output, not a person. It is not part of the"
    " deliverable. -->\n\n"
    "# Acceptance feedback (attempt 1 of 3)\n\n"
    "The checks that ship with this task were run against your\n"
    "working directory. They did not all pass.\n\n"
    "test_visible.py::check_add — exception: ImportError: cannot import"
    " name 'add' from 'solution'\n"
)


def test_the_feedback_content_never_names_its_own_file():
    """⚠ 這是整個分工的地基。它一旦不成立，兩個指標就會互相汙染。"""
    from vacant_network.vrun.retry import (FEEDBACK_BODY, FEEDBACK_FILENAME,
                                   FEEDBACK_HEADER, FEEDBACK_TEMPLATE)
    assert FEEDBACK_FILENAME == "VACANT_FEEDBACK.md"
    for blob in (FEEDBACK_HEADER, FEEDBACK_BODY, FEEDBACK_TEMPLATE):
        assert "VACANT_FEEDBACK" not in blob, (
            "回饋內容開始提到自己的檔名了——`M7_name` 與 `M7_file` 的分工失效，"
            "`M7_file` 會被檔名灌爆。要嘛改樣板，要嘛改 needle。")


def _mk(tmp_path: pathlib.Path, bodies: dict[int, list[str]]) -> tuple:
    """造一個最小的 run 目錄：`{attempt: [request body 文字, …]}`。"""
    arm = "RUN-ON"
    wire = tmp_path / f"wire_{arm}"
    wire.mkdir(parents=True)
    slices: dict[int, list[str]] = {}
    n = 0
    for attempt, blobs in sorted(bodies.items()):
        ids = []
        for b in blobs:
            n += 1
            cid = f"c{n:04d}"
            (wire / f"{cid}.req.bin").write_bytes(
                json.dumps({"messages": [{"role": "user", "content": b}]},
                           ensure_ascii=False).encode("utf-8"))
            ids.append(cid)
        slices[attempt] = ids
    summary = {"arm": arm, "attempts": [
        {"attempt": a, "feedback": {"text": FEEDBACK_TEXT}}
        for a in sorted(bodies)]}
    return summary, slices, {"ok": True}


LS_RESULT = "solution.py\nTASK.md\nVACANT_FEEDBACK.md\n"


def test_only_the_filename_means_saw_it_but_did_not_read_it(tmp_path):
    """**這一條就是那個 bug 的形狀。** 只有檔名 ⇒ name=True、file=False。"""
    summary, slices, meta = _mk(tmp_path, {
        1: ["Read TASK.md and do what it says."],
        2: ["Read TASK.md and do what it says.\n\ntool result: " + LS_RESULT],
    })
    name = R.measure_m7_name(tmp_path, "RF", summary, slices, meta)
    file_ = R.measure_m7_file(tmp_path, "RF", summary, slices, meta)
    assert name["m7_name"] is True, name
    assert file_["m7_file"] is False, (
        "檔名被算成「讀到了內容」——方向反了，第一個主要交付數字會被灌爆")


def test_the_header_line_means_it_really_read_it(tmp_path):
    """回饋**內容**進了 wire ⇒ file=True。"""
    summary, slices, meta = _mk(tmp_path, {
        1: ["Read TASK.md and do what it says."],
        2: ["Read TASK.md.\n\ntool result: " + LS_RESULT
            + "\n\n" + FEEDBACK_TEXT],
    })
    assert R.measure_m7_file(tmp_path, "RF", summary, slices, meta
                             )["m7_file"] is True
    assert R.measure_m7_name(tmp_path, "RF", summary, slices, meta
                             )["m7_name"] is True


def test_neither_when_the_agent_never_looked(tmp_path):
    """兩個都 False——這與「只有檔名」在收官上是兩句不同的話。"""
    summary, slices, meta = _mk(tmp_path, {
        1: ["Read TASK.md and do what it says."],
        2: ["Read TASK.md and do what it says."],
    })
    assert R.measure_m7_name(tmp_path, "RF", summary, slices, meta
                             )["m7_name"] is False
    assert R.measure_m7_file(tmp_path, "RF", summary, slices, meta
                             )["m7_file"] is False


def test_rs_is_by_policy_null_not_false(tmp_path):
    """RS 走 `resample`，那個檔從來不存在（I-8）⇒ `null` 不是 `False`。"""
    summary, slices, meta = _mk(tmp_path, {1: ["x"], 2: ["y"]})
    r = R.measure_m7_name(tmp_path, "RS", summary, slices, meta)
    assert r["m7_name"] is None
    assert r["m7_name_reason"] == "arm_has_no_feedback_by_policy"


def test_single_attempt_is_null_not_false(tmp_path):
    summary, slices, meta = _mk(tmp_path, {1: ["x"]})
    r = R.measure_m7_name(tmp_path, "RF", summary, slices, meta)
    assert r["m7_name"] is None
    assert r["m7_name_reason"] == "no_second_attempt"


def test_a_leaky_needle_is_reported_not_silently_counted(tmp_path):
    """檔名若在 attempt 1 就出現 ⇒ 它沒有鑑別力，要說出來而不是照算。

    第 1 次嘗試時回饋檔還不存在，所以正常不會命中；命中代表它從別的地方
    （argv／system prompt）漏進來了。
    """
    summary, slices, meta = _mk(tmp_path, {
        1: ["please avoid writing VACANT_FEEDBACK.md"],
        2: ["tool result: " + LS_RESULT],
    })
    r = R.measure_m7_name(tmp_path, "RF", summary, slices, meta)
    assert r["m7_name"] is None
    assert r["m7_name_leaky"] is True
    assert "not_discriminative" in (r["m7_name_reason"] or "")


@pytest.mark.parametrize("field", ["m7_name", "m7_name_reason",
                                   "m7_name_by_attempt", "m7_name_leaky"])
def test_the_new_fields_are_persisted_and_rescannable(field):
    """新欄位要進 `derived`，否則 `--rescan` 重算不到它們。"""
    src = (REPO / "ops" / "gain" / "r535" / "run_r535.py").read_text(
        encoding="utf-8")
    derived = src.split("derived = [k for k in (", 1)[1].split(")]", 1)[0]
    assert f'"{field}"' in derived, f"{field} 不在 derived 清單裡"
