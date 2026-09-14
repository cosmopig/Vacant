#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `bank/` 投影成**盲評管線吃的形狀**（`judge_r530.py --bank <outdir>`）。

這支在架構裡承重什麼
--------------------
R530 的題庫有一個正典（`ops/gain/r530/bank/<task_id>/`）與兩個下游：

* `export_bank.py` 投影出**執行基建**吃的三個目錄
  （`templates/`／`hidden/`／`gauge/`，規格在 `TASK_FORMAT.md`）；
* **這一支**投影出**質化盲評**吃的第四個形狀
  （`<outdir>/<task_id>/{task.md,visible.json,template/}` ＋ `<outdir>/rubric.json`，
  規格在 `judge_r530.load_bank` 的 docstring）。

方向一樣是單向的：**正典是 `bank/`**，投影出來的東西不要手改，改了 `--check`
會抓到。兩個投影**共用同一個 `export_bank.project()`**——`template/` 不是去讀
`templates/` 那個已經落盤的目錄，而是當場從 `bank/` 重算，所以「評審看到的樣板」
與「worker 拿到的樣板」逐位元相同這件事不依賴投影有沒有先跑過。

四個產物各自的判準
------------------
* **`task.md`** ＝ `goal.md` ＋ `contract.md` **逐字串接**，中間空一行。兩份檔案
  各自已經帶 `# Goal`／`# Contract` 標題，所以串接就是標題分隔；本檔對這兩件事
  是 fail-closed 的（標題不對／結尾不是剛好一個換行就拒跑），這樣「逐字」才驗得起來
  ——`--check` 會斷言 `goal in task_md and contract in task_md`。
* **`rubric.json`** ＝ 從 `rubric.md` 的**共用表**解析。20 題的 `rubric.md`
  各自不同（底部的 worked examples 是逐題的），但表格那一段
  （prereg S1-4 所謂「the scale below is shared by every R530 task」）
  20 題逐位元相同；本檔逐題解析、逐位元比對，**任何一題解出不一樣的 JSON 就拒跑**。
  因為它確實只有一份，所以**只寫一份**在 `<outdir>/rubric.json`（`load_bank`
  支援的 shared 路徑），不寫 20 份複本——「只有一個檔案」比「20 份複本相等」強。
* **`visible.json`** ＝ **worker 看得到的那份可見測試**（`template/tests_visible/*`）
  的檔名與原始碼，純資料、不帶任何本檔自己的散文。理由是它會進
  `load_bank` 的 `vocab`，而 `vocab` 的作用是**豁免洩漏字樣**；只放工作區本來就
  有的字，vocab 才不會擴出新的豁免面（`ow_02`／`ow_07` 的 `retry`／`attempt`
  就是靠這條路被豁免的，而那兩個字本來就寫在它們自己的 `goal.md`／`contract.md` 裡）。
  ⚠ `judge_r530` **不執行**它，也**不把它放進 prompt**——目前只讀來當 vocab。
* **`template/`** ＝ 樣板工作區複本（`export_bank.project()` 的 `templates/<id>/`
  那一段）。`judge_r530.deidentify` 只拿它做 `DROP_IF_UNCHANGED` 的比對。

與預註冊 `ops/gain/data/openwork/` 的關係（**兩個目錄，不要搞混**）
---------------------------------------------------------------
預註冊 §一-1 釘的落盤形狀是 `ops/gain/data/openwork/<task_id>/`，裡面除了盲評讀的
四樣，還有 `hidden.json`／`meta.json`／`reference/`——那是**發射基建**的題庫，
由基建代理建（`review/README.md` 同一句）。`judge_r530.py` 的 `--bank` 預設值
正好指著它，因為 `load_bank` 只挑自己要的四樣讀，多出來的東西它不看。

本檔**不寫那個目錄**，寫 `ops/gain/r530/judge_bank/`，而且**拒絕**被 `--out`
指到看起來像發射題庫的目錄。理由不是潔癖：本檔會**刪掉投影不認得的檔案**
（孤兒＝上一次投影的垃圾），指到 `openwork/` 就會把 `hidden.json`、`meta.json`、
`reference/` 當成孤兒刪掉。所以跑盲評要自己帶
`--bank ops/gain/r530/judge_bank`，不能吃預設值。

⚠ 另一處同名不同物：預註冊 §一-1 的 `visible.json` schema 是
`{kind: "call"|"cli", …}` 的字面值清單；本檔寫的是 `[{path, source}]`
（可見驗收在題庫裡是**測試檔**不是字面值，見 `meta.json` 的 `visible_note`）。
`load_bank` 兩種都不解析——它只 `read_text` 當 vocab——所以**兩種都不會噴錯**。
指錯題庫的後果是 vocab 悄悄換一份，不是當機。

用法
----
    python3 ops/gain/r530/export_for_judge.py           # 投影到 judge_bank/
    python3 ops/gain/r530/export_for_judge.py --check   # 只檢查，過期就 exit 1
    python3 ops/gain/r530/judge_r530.py --bank ops/gain/r530/judge_bank \
        --run-dir runs/<name> --dry-run --stub-graders --out-dir /tmp/x

`--check` 做三件事：**(1)** 重產後與既有輸出逐位元相同（含孤兒檔）；
**(2)** 20 題的 `rubric.md` 解析出逐位元相同的 JSON，而且四個維度鍵與
`judge_r530.DIMS` 一致；**(3)** 真的把產物餵給 `judge_r530.run_judging(dry_run=True)`
——樣板＋參考解組一個假工作區，20 題每題要產出一份 prompt，而且 prompt 裡要逐字
找得到 `goal.md`、`contract.md` 與四個維度的 1／3／5 級距文字。
(3) 不打任何後端（`dry_run` 在寫完 prompt 之後就 `continue`）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ops.gain.r530.export_bank import BANK, project, read  # noqa: E402

#: 預設輸出。跑 `judge_r530.py` 要自己 `--bank` 指這裡（它的預設值是別的目錄）。
DEFAULT_OUT = os.path.join(HERE, "judge_bank")

#: 出現這些名字 ⇒ `--out` 指到的是**發射題庫**不是盲評題庫，拒寫也拒檢查。
#: 本檔會刪孤兒，而在 `ops/gain/data/openwork/` 底下「孤兒」會是 `hidden.json`。
LAUNCH_BANK_MARKERS = ("hidden.json", "meta.json", "hidden", "reference")

GOAL_HEADING = "# Goal"
CONTRACT_HEADING = "# Contract"

#: `rubric.md` 共用表的表頭，**逐字**。表頭長得不一樣就拒跑——解析器對不上欄位
#: 卻硬吞下去，結果會是「評分表在不同題目之間偷偷不一樣」，那正是
#: `judge_r530._normalise_rubric` 要擋的東西。
RUBRIC_TABLE_HEADER = "| Dim | 1 | 2 | 3 | 4 | 5 |"
RUBRIC_LEVELS = ("1", "2", "3", "4", "5")

#: 表格第一欄的標題 → `judge_r530.DIMS` 的鍵。**順序也是判準**：表格的列順序
#: 要與這裡一致，對不上拒跑。
DIM_ROWS = (
    ("Readability", "readability"),
    ("Structure", "structure"),
    ("Error handling", "error_handling"),
    ("Fit to goal", "goal_fit"),
)

#: 共用段 ＝ `rubric.md` 從檔頭到 worked examples 之前。逐題的內容從這裡開始。
WORKED_EXAMPLES_HEADING = "## Worked examples for this task"

_ROW_TITLE_RE = re.compile(r"^\*\*(.+?)\*\*$")


class BankShapeError(RuntimeError):
    """題庫形狀不符合本檔的 fail-closed 前提。**不要降級成警告。**"""


# ── rubric.md → rubric.json ────────────────────────────────────────────
def shared_rubric_section(rubric_md: str, where: str) -> str:
    """`rubric.md` → 共用段（worked examples 之前的那一段）。"""
    cut = rubric_md.find(WORKED_EXAMPLES_HEADING)
    if cut < 0:
        raise BankShapeError(
            f"{where}: 找不到 {WORKED_EXAMPLES_HEADING!r}——"
            "分不出哪一段是 20 題共用的，拒跑")
    return rubric_md[:cut]


def _split_row(line: str) -> list[str]:
    """markdown 表格列 → 儲存格。`\\|` 是逐字的直槓，不是欄位分隔。"""
    parts = re.split(r"(?<!\\)\|", line)
    if len(parts) < 3 or parts[0].strip() or parts[-1].strip():
        raise BankShapeError(f"表格列的頭尾不是 `|`：{line[:60]!r}")
    return [p.strip().replace("\\|", "|") for p in parts[1:-1]]


def parse_rubric_table(rubric_md: str, where: str) -> dict:
    """共用段 → `{dim_key: {"1".."5": 準則}}`。**fail-closed**。

    擋下來的每一種形狀，靜靜吞掉都會讓評分表變成另一張表：欄位數不對（級距錯位）、
    列標題不對或順序不對（維度對到別人的準則）、儲存格空白（`_normalise_rubric`
    會在下游才炸，但那時候已經分不清是誰改的）。
    """
    section = shared_rubric_section(rubric_md, where)
    lines = section.splitlines()
    try:
        head_at = lines.index(RUBRIC_TABLE_HEADER)
    except ValueError:
        raise BankShapeError(
            f"{where}: 找不到逐字表頭 {RUBRIC_TABLE_HEADER!r}——拒跑") from None
    if head_at + 1 >= len(lines) or not re.fullmatch(r"\|(?:\s*-{3,}\s*\|){6}",
                                                     lines[head_at + 1]):
        raise BankShapeError(f"{where}: 表頭下一行不是六欄的分隔列——拒跑")

    rows = []
    for line in lines[head_at + 2:]:
        if not line.startswith("|"):
            break
        rows.append(_split_row(line))
    if len(rows) != len(DIM_ROWS):
        raise BankShapeError(
            f"{where}: 表格有 {len(rows)} 列，要 {len(DIM_ROWS)} 列——拒跑")

    out: dict[str, dict[str, str]] = {}
    for row, (title, key) in zip(rows, DIM_ROWS):
        m = _ROW_TITLE_RE.match(row[0])
        if not m or m.group(1) != title:
            raise BankShapeError(
                f"{where}: 第 {len(out) + 1} 列的標題是 {row[0]!r}，"
                f"要 **{title}**（列順序也是判準）——拒跑")
        cells = row[1:]
        if len(cells) != len(RUBRIC_LEVELS):
            raise BankShapeError(
                f"{where}: {title} 有 {len(cells)} 個級距，要 5 個——拒跑")
        blank = [lvl for lvl, c in zip(RUBRIC_LEVELS, cells) if not c]
        if blank:
            raise BankShapeError(f"{where}: {title} 的級距 {blank} 是空的——拒跑")
        out[key] = dict(zip(RUBRIC_LEVELS, cells))
    return out


def rubric_document(levels: dict[str, dict[str, str]], source_sha256: str) -> str:
    """`{dim: levels}` → 要落盤的 `rubric.json` 原文（尾端一個換行）。

    形狀走 `_normalise_rubric` 吃的 `{"dims": [...]}` 那一支，因為只有這一支
    放得下 `title`／`weight`。⚠ `judge_r530` **只讀 `key` 與 `levels` 的 1／3／5**：
    `weight` 與級距 2／4 是紀錄，不是行為——盲評本來就不把四維合成一個總分
    （`aggregate` 逐維分開報），所以「等權」在這裡的意思是
    **沒有任何一維被加權**，不是「有人拿 0.25 去乘」。
    """
    doc = {
        "schema": "r530.rubric.v1",
        "source": "ops/gain/r530/bank/<task_id>/rubric.md 的共用段"
                  "（20 題逐位元相同；逐題的 worked examples 不在內）",
        "source_sha256": source_sha256,
        "scale": [int(x) for x in RUBRIC_LEVELS],
        "weighting": "equal",
        "levels_shown_to_the_grader": ["1", "3", "5"],
        "dims": [
            {
                "key": key,
                "title": title,
                "weight": 0.25,
                "levels": levels[key],
            }
            for title, key in DIM_ROWS
        ],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"


# ── 一題 → 三個檔案 ────────────────────────────────────────────────────
def _check_part(text: str, heading: str, where: str) -> None:
    if not text.startswith(heading + "\n"):
        raise BankShapeError(f"{where}: 第一行不是 {heading!r}——拒跑")
    if not text.endswith("\n") or text.endswith("\n\n"):
        raise BankShapeError(f"{where}: 結尾不是剛好一個換行——串接會不逐字，拒跑")


def task_markdown(task_id: str) -> str:
    """`goal.md` ＋ `contract.md` 逐字串接（中間空一行）。"""
    task_dir = os.path.join(BANK, task_id)
    goal = read(os.path.join(task_dir, "goal.md"))
    contract = read(os.path.join(task_dir, "contract.md"))
    _check_part(goal, GOAL_HEADING, f"{task_id}/goal.md")
    _check_part(contract, CONTRACT_HEADING, f"{task_id}/contract.md")
    return goal + "\n" + contract


def template_files(task_id: str) -> dict[str, str]:
    """樣板工作區 → `{相對路徑: 內容}`。與 worker 拿到的那一份同源。"""
    prefix = "templates/%s/" % task_id
    out = {k[len(prefix):]: v for k, v in project(task_id).items()
           if k.startswith(prefix)}
    if not out:
        raise BankShapeError(f"{task_id}: 投影不出樣板工作區——拒跑")
    return out


def visible_document(template: dict[str, str], task_id: str) -> str:
    """可見測試 → `visible.json` 原文。**純資料**，不加本檔自己的字。"""
    rows = [{"path": rel, "source": template[rel]}
            for rel in sorted(template) if rel.startswith("tests_visible/")]
    if not rows:
        raise BankShapeError(f"{task_id}: 樣板裡沒有 tests_visible/——拒跑")
    return json.dumps(rows, ensure_ascii=False, indent=2) + "\n"


def project_for_judge(tasks: list[str] | None = None) -> dict[str, str]:
    """回傳 `{相對路徑: 內容}`，相對於 `--out`。"""
    tasks = tasks if tasks is not None else list_tasks()
    if not tasks:
        raise BankShapeError(f"{BANK} 裡沒有 ow_* 題目——空的投影會是一個空的"
                             "題庫，而空題庫在 judge 那邊才炸，拒跑")
    files: dict[str, str] = {}
    rubrics: dict[str, str] = {}
    for task_id in tasks:
        files["%s/task.md" % task_id] = task_markdown(task_id)
        template = template_files(task_id)
        for rel, content in template.items():
            files["%s/template/%s" % (task_id, rel)] = content
        files["%s/visible.json" % task_id] = visible_document(template, task_id)

        md = read(os.path.join(BANK, task_id, "rubric.md"))
        section = shared_rubric_section(md, f"{task_id}/rubric.md")
        levels = parse_rubric_table(md, f"{task_id}/rubric.md")
        sha = hashlib.sha256(section.encode("utf-8")).hexdigest()
        rubrics[task_id] = rubric_document(levels, sha)

    disagreeing = sorted(t for t in rubrics if rubrics[t] != rubrics[tasks[0]])
    if disagreeing:
        raise BankShapeError(
            "rubric.md 的共用段在這些題目解析出不一樣的 JSON："
            + ", ".join(disagreeing)
            + f"（基準＝{tasks[0]}）——共用表不共用了，拒跑")
    files["rubric.json"] = rubrics[tasks[0]]
    return files


def list_tasks() -> list[str]:
    return sorted(d for d in os.listdir(BANK)
                  if d.startswith("ow_") and os.path.isdir(os.path.join(BANK, d)))


# ── judge 的 --dry-run 探針 ────────────────────────────────────────────
def judge_dry_run_probe(out_dir: str, work_root: str) -> dict:
    """把產物真的餵給 `judge_r530`，回 `{prompts, dropped, bank_n}`。

    工作區 ＝ 樣板 ＋ `reference/solution.py`，也就是一格**跑完之後**該有的形狀。
    用參考解不是因為它有代表性（真 worker 寫什麼不知道），是因為它是手上唯一
    保證通得過可見驗收的東西；重點在**管線吃不吃得下**，不在分數。
    """
    from ops.gain.r530 import judge_r530 as judge

    bank = judge.load_bank(pathlib.Path(out_dir))

    work = pathlib.Path(work_root)
    ws_root = work / "ws"
    cells = []
    for task_id in sorted(bank):
        ws = ws_root / task_id
        for rel, content in template_files(task_id).items():
            p = ws / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        (ws / "solution.py").write_text(
            read(os.path.join(BANK, task_id, "reference", "solution.py")),
            encoding="utf-8")
        cells.append(judge.Cell(cell_id=f"probe|{task_id}", task_id=task_id,
                                arm="PROBE", seed="probe", ws_path=ws))

    grader = judge.Grader(gid="probe", api="", model="probe", seed="probe",
                          kind="stub")
    out = work / "judge_out"
    judge.run_judging(cells, bank, [grader], run_id="export_for_judge_check",
                      salt="export_for_judge_check", out_dir=out, dry_run=True)

    prompts = [json.loads(line) for line
               in (out / "judge_prompts.jsonl").read_text("utf-8").splitlines()
               if line.strip()]
    dropped = [json.loads(line) for line
               in (out / "deident.jsonl").read_text("utf-8").splitlines()
               if line.strip() and not json.loads(line)["ok"]]
    return {"prompts": prompts, "dropped": dropped, "bank_n": len(bank),
            "dims": list(judge.DIMS)}


def _probe_failures(probe: dict, tasks: list[str], rubric_json: str) -> list[str]:
    """探針結果 → 失敗原因清單（空的＝過）。"""
    bad = []
    if probe["bank_n"] != len(tasks):
        bad.append(f"load_bank 只認出 {probe['bank_n']} 題，題庫有 {len(tasks)} 題")
    for d in probe["dropped"]:
        bad.append(f"去識別化丟掉 {d['cell']['task_id']}：{d['reason']}")
    if len(probe["prompts"]) != len(tasks):
        bad.append(f"產出 {len(probe['prompts'])} 份 prompt，要 {len(tasks)} 份")

    emitted_dims = [d["key"] for d in json.loads(rubric_json)["dims"]]
    if tuple(emitted_dims) != tuple(probe["dims"]):
        bad.append(f"rubric.json 的維度鍵 {emitted_dims} 與 "
                   f"judge_r530.DIMS {probe['dims']} 不一致")

    levels = {d["key"]: d["levels"] for d in json.loads(rubric_json)["dims"]}
    by_sample = {p["sample_id"]: p["prompt"] for p in probe["prompts"]}
    for p in probe["prompts"]:
        task_id = p["cell"]["task_id"]
        prompt = by_sample[p["sample_id"]]
        # ⚠ 這一條**不是**盲評的擋門（那一條在 `tests/test_r530_judge.py` 的
        # `test_no_emitted_prompt_contains_any_identifying_string`，用的是假題庫）。
        # 這裡只驗「本檔產的形狀沒有把格的身分帶進 prompt」。探針的工作區用的是
        # `reference/solution.py`，它的 docstring 裡就寫著 task_id——那是探針的
        # 假工作區自己的字，不是本檔的產物，所以 task_id 不在這條清單裡。
        for ident in (p["cell"]["cell_id"], p["cell"]["arm"], p["cell"]["seed"]):
            if ident and ident in prompt:
                bad.append(f"{task_id}: prompt 裡出現格的身分 {ident!r}")
        goal = read(os.path.join(BANK, task_id, "goal.md")).strip()
        contract = read(os.path.join(BANK, task_id, "contract.md")).strip()
        if goal not in prompt:
            bad.append(f"{task_id}: prompt 裡找不到逐字的 goal.md")
        if contract not in prompt:
            bad.append(f"{task_id}: prompt 裡找不到逐字的 contract.md")
        for dim, lv in levels.items():
            for want in ("1", "3", "5"):
                if lv[want] not in prompt:
                    bad.append(f"{task_id}: prompt 裡找不到 {dim} 的第 {want} 級文字")
    return bad


# ── CLI ────────────────────────────────────────────────────────────────
def refuse_if_launch_bank(out_dir: str) -> None:
    """`--out` 指到發射題庫 ⇒ 拒跑。**這是資料保護，不是風格。**"""
    if not os.path.isdir(out_dir):
        return
    for task_id in os.listdir(out_dir):
        task_dir = os.path.join(out_dir, task_id)
        if not os.path.isdir(task_dir):
            continue
        found = sorted(m for m in LAUNCH_BANK_MARKERS
                       if os.path.exists(os.path.join(task_dir, m)))
        if found:
            raise BankShapeError(
                f"{out_dir} 看起來是**發射題庫**（{task_id}/ 裡有 {found}），"
                "不是盲評題庫。本檔會刪掉投影不認得的檔案，指到這裡會把它們刪掉——拒跑")


def _existing(out_dir: str) -> set[str]:
    found = set()
    for base, _dirs, names in os.walk(out_dir):
        if "__pycache__" in base:
            continue
        for name in names:
            found.add(os.path.relpath(os.path.join(base, name), out_dir))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="project bank/ into the judge_r530 --bank layout")
    parser.add_argument("--check", action="store_true",
                        help="只檢查：逐位元比對＋rubric 20 題一致＋judge --dry-run")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--no-probe", action="store_true",
                        help="--check 時跳過 judge 的 dry-run 探針（除錯用）")
    args = parser.parse_args(argv)

    tasks = list_tasks()
    try:
        refuse_if_launch_bank(args.out)
        wanted = project_for_judge(tasks)
    except BankShapeError as e:
        print("BANK SHAPE %s" % e)
        print("RESULT: FAIL")
        return 1

    stale, orphans = [], []
    for relative, content in sorted(wanted.items()):
        path = os.path.join(args.out, relative)
        current = read(path) if os.path.isfile(path) else None
        if current == content:
            continue
        stale.append(relative)
        if not args.check:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
            if relative.endswith(".sh"):
                os.chmod(path, 0o755)
    if os.path.isdir(args.out):
        orphans = sorted(p for p in _existing(args.out) if p not in wanted)
    if orphans and not args.check:
        for relative in orphans:
            os.remove(os.path.join(args.out, relative))

    print("tasks=%d  projected files=%d  (rubric.json 共用一份，不寫 %d 份複本)"
          % (len(tasks), len(wanted), len(tasks)))
    print("rubric: 20/%d 題的共用段解析出逐位元相同的 JSON  sha256(source)=%s"
          % (len(tasks), json.loads(wanted["rubric.json"])["source_sha256"][:16]))

    probe_bad: list[str] = []
    if args.check and not args.no_probe:
        if stale or orphans:
            print("probe: SKIP（產物先過期了，比對過不了就沒有東西好餵）")
        else:
            with tempfile.TemporaryDirectory(prefix="r530_judge_probe_") as tmp:
                probe = judge_dry_run_probe(args.out, tmp)
            probe_bad = _probe_failures(probe, tasks, wanted["rubric.json"])
            print("probe: judge_r530 --dry-run  載入 %d 題／產出 %d 份 prompt"
                  "／去識別化丟掉 %d 格 -> %s"
                  % (probe["bank_n"], len(probe["prompts"]), len(probe["dropped"]),
                     "OK" if not probe_bad else "FAIL"))

    if args.check:
        for relative in stale:
            print("STALE   %s" % relative)
        for relative in orphans:
            print("ORPHAN  %s" % relative)
        for why in probe_bad:
            print("PROBE   %s" % why)
        if stale or orphans or probe_bad:
            print("RESULT: FAIL (run export_for_judge.py to refresh)")
            return 1
        print("RESULT: PASS (judge bank is up to date)")
        return 0

    print("wrote/updated %d, removed %d orphan(s)" % (len(stale), len(orphans)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
