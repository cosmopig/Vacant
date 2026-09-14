"""`ops/gain/r530/export_for_judge.py` 的紅線（題庫 → 盲評管線的接線）。

這支在架構裡承重什麼：這個投影壞掉**不會噴錯**。`judge_r530` 照樣會吐出一份
四維分數，而「評審讀的是這一題的目標」與「評審讀的是別人的目標／半張評分表」
在那份 JSON 裡長得一模一樣。所以三種靜默的壞法各要有一條跑得到的紅線：

  1. **題目正文不逐字**——`task.md` 少一段、多一段、或被重排，評審就在評
     另一個需求；
  2. **評分表在不同題目之間偷偷不一樣**——20 題的 `rubric.md` 共用段只要有一題
     漂掉，`rubric.<seed>.<dim>.<ARM>` 就不是同一把尺，而下游讀不出來；
  3. **`rubric.json`／`visible.json` 擴大了洩漏字樣的豁免面**——它們會進
     `load_bank` 的 `vocab`，而 `vocab` 的作用是**豁免**；多帶一個字進去，
     去識別化那道門就對那個字失效，而失效是安靜的。
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ops.gain.r530.export_bank import read  # noqa: E402
from ops.gain.r530.export_for_judge import (  # noqa: E402
    BANK, BankShapeError, DEFAULT_OUT, DIM_ROWS, RUBRIC_LEVELS, list_tasks,
    main, parse_rubric_table, rubric_document, shared_rubric_section,
    task_markdown,
)
from ops.gain.r530.judge_r530 import (  # noqa: E402
    DIMS, FROZEN_LEAK_TOKENS, NEVER_EXCUSABLE, _PATTERNS, _normalise_rubric,
)

OUT = pathlib.Path(DEFAULT_OUT)
TASKS = list_tasks()


def _rubric_md(task_id: str) -> str:
    return read(str(pathlib.Path(BANK) / task_id / "rubric.md"))


# ── 1. 端到端：落盤的產物與 `--check` ───────────────────────────────────
def test_check_is_green_on_the_committed_judge_bank():
    """`--check` ＝ 逐位元比對 ＋ rubric 20 題一致 ＋ judge 的 `--dry-run`。

    綠燈的意思是：落盤的 `judge_bank/` 就是現在的 `bank/` 投影得出來的東西，
    而且 `judge_r530` 真的吃得下去（20 題各產一份 prompt，沒有一格被去識別化丟掉）。
    紅燈**不要**用手改 `judge_bank/` 去弄綠——正典是 `bank/`。
    """
    assert main(["--check", "--out", str(OUT)]) == 0


# ── 2. `task.md` 逐字 ──────────────────────────────────────────────────
def test_task_md_is_goal_plus_contract_verbatim():
    """`task.md` ＝ `goal.md` ＋ 一個空行 ＋ `contract.md`，一個位元組都沒動。

    用長度相等而不只是 `in`：`in` 過得了「多塞了一段本檔自己寫的話」，
    而那一段會變成評審讀到、worker 沒讀到的需求。
    """
    assert TASKS, "題庫是空的"
    for task_id in TASKS:
        goal = read(str(pathlib.Path(BANK) / task_id / "goal.md"))
        contract = read(str(pathlib.Path(BANK) / task_id / "contract.md"))
        built = task_markdown(task_id)
        on_disk = (OUT / task_id / "task.md").read_text("utf-8")

        assert built == on_disk, f"{task_id}: 落盤的 task.md 與重算的不一樣"
        assert goal in built and contract in built, f"{task_id}: 不逐字"
        assert len(built) == len(goal) + 1 + len(contract), \
            f"{task_id}: task.md 裡有 goal＋contract 以外的字"
        assert built.startswith("# Goal\n")
        assert "\n# Contract\n" in built


# ── 3. 20 題一張表 ─────────────────────────────────────────────────────
def test_all_twenty_rubrics_parse_to_the_same_bytes():
    """20 題的共用段解析出**逐位元相同**的 JSON，而且鍵與 `judge_r530.DIMS` 一致。

    ⚠ 這一條驗的是**共用段**，不是整份 `rubric.md`——底部的 worked examples
    是逐題的，本來就不一樣，而它們不進 `rubric.json`。
    """
    docs = set()
    for task_id in TASKS:
        md = _rubric_md(task_id)
        levels = parse_rubric_table(md, task_id)
        section = shared_rubric_section(md, task_id)
        docs.add(rubric_document(
            levels, hashlib.sha256(section.encode("utf-8")).hexdigest()))
    assert len(docs) == 1, f"{len(docs)} 份不同的評分表，20 題應該共用一份"

    doc = json.loads(docs.pop())
    assert tuple(d["key"] for d in doc["dims"]) == DIMS
    assert tuple(t for t, _k in DIM_ROWS) == tuple(d["title"] for d in doc["dims"])
    for d in doc["dims"]:
        assert sorted(d["levels"]) == sorted(RUBRIC_LEVELS)
        assert all(d["levels"][lvl].strip() for lvl in RUBRIC_LEVELS)
    # 落盤的那一份要是同一份，而且 judge 的 fail-closed 正規化吃得下去。
    assert (OUT / "rubric.json").read_text("utf-8") == json.dumps(
        doc, ensure_ascii=False, indent=2) + "\n"
    norm = _normalise_rubric(doc, "test")
    assert set(norm) == set(DIMS)


# ── 4. 解析器 fail-closed ──────────────────────────────────────────────
#: `(名稱, 突變, 錯誤訊息裡要看得到的字)`。第三欄是刻意的：只斷言「有丟例外」
#: 會讓六種突變全部撞同一條路徑也算過，那樣測到的是一條紅線不是六條。
_MUTATIONS = [
    ("刪掉一整列（少一個維度）",
     lambda md: md.replace("| **Structure** |", "x| **Structure** |"),
     "要 4 列"),
    ("某一列少一欄（級距錯位）",
     lambda md: md.replace(
         " | One responsibility per unit; no duplicated logic;"
         " adding one new rule means editing one place |", " |"),
     "要 5 個"),
    ("某一格變空的",
     lambda md: md.replace(
         "| **Structure** | Everything in one function or one tangle;"
         " the pieces cannot be moved |", "| **Structure** |  |"),
     "是空的"),
    ("維度改名（對到別人的準則）",
     lambda md: md.replace("| **Error handling** |", "| **Error Handling** |"),
     "列順序也是判準"),
    ("表頭不見了",
     lambda md: md.replace("| Dim | 1 | 2 | 3 | 4 | 5 |", "| Dim |"),
     "找不到逐字表頭"),
    ("分不出共用段",
     lambda md: md.replace("## Worked examples for this task", "## Notes"),
     "拒跑"),
]


@pytest.mark.parametrize("name,mutate,expect", _MUTATIONS,
                         ids=[m[0] for m in _MUTATIONS])
def test_rubric_parser_is_fail_closed(name, mutate, expect):
    """每一種漂法都要**拒跑**，不是靜靜地用預設值補。

    靜靜補上的後果不是當機，是「評分表在不同題目之間偷偷不一樣」——
    `judge_r530._normalise_rubric` 擋的是同一件事，本檔把它往上游挪了一層。
    """
    md = _rubric_md(TASKS[0])
    mutated = mutate(md)
    assert mutated != md, f"突變 {name!r} 沒有真的改到東西（測試自己壞了）"
    with pytest.raises(BankShapeError) as excinfo:
        parse_rubric_table(mutated, "mutated")
    assert expect in str(excinfo.value), \
        f"突變 {name!r} 被擋下來了，但走的是別條路徑：{excinfo.value}"


# ── 5. vocab 不准變寬 ──────────────────────────────────────────────────
def test_rubric_and_visible_do_not_widen_the_leak_excuse_vocabulary():
    """`rubric.json`／`visible.json` 不准帶進工作區本來沒有的洩漏字樣。

    `load_bank` 把 `task.md`＋`visible.json`＋正規化後的 `rubric` 串成 `vocab`，
    而 `vocab` 命中 ⇒ **豁免**。所以：

    * **`rubric.json` 要完全乾淨**。`rubric.md` 的共用段裡其實有
      `hidden`／`rubric`／`R530` 三個字（標題與 prereg 的那條註記），只要解析器
      多抄一行進來，那三個字就對 **20 題全部**失效——而 `rubric` 與 `hidden`
      同時還是 `FORBIDDEN_PATH_PARTS`。
    * **`visible.json` 只准帶樣板本來就有的字**。它是 worker 看得到的那份可見
      測試的複本，所以它的貢獻應該是零；帶進新字＝評審那一側單方面放寬了門。
    """
    from ops.gain.r530.export_for_judge import template_files

    tokens = set(FROZEN_LEAK_TOKENS) | set(NEVER_EXCUSABLE)
    rubric_norm = _normalise_rubric(
        json.loads((OUT / "rubric.json").read_text("utf-8")), "test")
    rubric_vocab = json.dumps(rubric_norm, ensure_ascii=False)
    dirty = sorted(t for t in tokens if _PATTERNS[t].search(rubric_vocab))
    assert not dirty, f"rubric.json 進 vocab 的部分帶了洩漏字樣：{dirty}"

    for task_id in TASKS:
        visible = (OUT / task_id / "visible.json").read_text("utf-8")
        workspace = "\n".join(
            list(template_files(task_id)) + list(template_files(task_id).values()))
        widened = sorted(t for t in tokens
                         if _PATTERNS[t].search(visible)
                         and not _PATTERNS[t].search(workspace))
        assert not widened, f"{task_id}: visible.json 帶進樣板沒有的字樣：{widened}"


# ── 6. 不准把發射題庫當輸出目錄 ────────────────────────────────────────
def test_refuses_to_write_into_the_launch_bank(tmp_path):
    """`--out` 指到發射題庫要**拒跑**。這一條擋的是資料被刪掉，不是風格。

    本檔會刪掉投影不認得的檔案（孤兒＝上一次投影的垃圾）。預註冊 §一-1 的
    `ops/gain/data/openwork/<task_id>/` 底下，「投影不認得的檔案」正好是
    `hidden.json`／`meta.json`／`reference/`——隱藏驗收與參考解。
    """
    from ops.gain.r530.export_for_judge import refuse_if_launch_bank

    (tmp_path / "ow_01_csvjson").mkdir()
    (tmp_path / "ow_01_csvjson" / "hidden.json").write_text("{}", encoding="utf-8")
    with pytest.raises(BankShapeError) as excinfo:
        refuse_if_launch_bank(str(tmp_path))
    assert "hidden.json" in str(excinfo.value)
    # 走 CLI 也要拒，而且**不准動到**那個目錄。
    before = sorted(p.name for p in (tmp_path / "ow_01_csvjson").iterdir())
    assert main(["--out", str(tmp_path)]) == 1
    assert sorted(p.name for p in (tmp_path / "ow_01_csvjson").iterdir()) == before
