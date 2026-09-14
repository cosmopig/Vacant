#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 `bank/` 投影成 `TASK_FORMAT.md` 規定的三個目錄。

這支在架構裡承重什麼
--------------------
題庫有兩種形狀，而且**兩種都要**：

* `ops/gain/r530/bank/<task_id>/` —— **作者的正典**。一題一個目錄，六件東西
  （`goal.md`／`contract.md`／`tests_visible/`／`hidden/`／`rubric.md`／`meta.json`）
  加上只給量具用的 `reference/`。隱藏驗收**一條一檔**，檔頭帶
  `# anchor_kind:`／`# anchor:`／`# derivation:` 三行——§五-2 的對照表因此是
  **可執行的**（`gauge_r530.py` 逐條驗 anchor 在 goal／contract 裡逐字存在）。
* `ops/gain/r530/{templates,hidden,gauge}/<task_id>/` —— **執行基建吃的形狀**，
  規格在 `ops/gain/r530/TASK_FORMAT.md`（基建代理寫的）。可見與隱藏各**一個檔案**，
  裡面是一組零引數的 `check_*()`，模組層 `import solution`。

這支把前者投影成後者。**方向是單向的**：正典是 `bank/`，投影出來的東西不要手改，
改了會在下一次 `--check` 被抓到（投影是確定性的，逐檔比對得出來）。

轉換做了什麼（只有一件事值得記）
--------------------------------
`bank/` 的一條驗收是一個檔案，裡面 `def run(solution)`；投影時把**整個檔案的原始碼
縮排四格塞進一個 `check_<檔名>()` 裡**，`run` 改名 `_bank_entry`，尾巴補一行呼叫它。
這樣做而不是把函式抄出來，是因為那些檔案裡有 `Clock`、`_width` 這種同名 helper，
抄出來會互相蓋掉；包成巢狀就各自獨立，而且**斷言的字面值一個位元組都沒有動**。

用法
----
    python3 ops/gain/r530/export_bank.py            # 投影
    python3 ops/gain/r530/export_bank.py --check    # 只檢查投影是不是最新的
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "bank")

RUN_TESTS_SH = """#!/bin/sh
# Run the checks that ship with this task against the current directory.
# Each check_* function in tests_visible/ is run; failures are printed.
exec python3 - "$@" <<'PY'
import importlib.util, os, sys, traceback
sys.path.insert(0, os.getcwd())
failed = 0
d = os.path.join(os.getcwd(), "tests_visible")
for name in sorted(os.listdir(d)):
    if not (name.startswith("test_") and name.endswith(".py")):
        continue
    path = os.path.join(d, name)
    spec = importlib.util.spec_from_file_location("vis_" + name[:-3], path)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        failed += 1
        print("%s: could not be imported" % name)
        traceback.print_exc()
        continue
    checks = [(n, v) for n, v in vars(mod).items()
              if n.startswith("check_") and callable(v)]
    if not checks:
        main = getattr(mod, "main", None)
        checks = [("main", main)] if callable(main) else []
    for cname, fn in checks:
        try:
            fn()
        except Exception as e:
            failed += 1
            print("FAIL %s::%s  %s: %s" % (name, cname, type(e).__name__, e))
        else:
            print("pass %s::%s" % (name, cname))
print("%d check(s) failed" % failed)
sys.exit(1 if failed else 0)
PY
"""

ANCHOR_KIND_RE = re.compile(r"^#\s*anchor_kind:\s*(goal|contract)\s*$", re.M)
ANCHOR_RE = re.compile(r"^#\s*anchor:\s*(.+?)\s*$", re.M)
DERIVATION_RE = re.compile(r"^#\s*derivation:\s*(.+?)\s*$", re.M)
MAIN_GUARD_RE = re.compile(r"\nif __name__ == \"__main__\":.*\Z", re.S)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def listdir_py(directory):
    if not os.path.isdir(directory):
        return []
    return sorted(f for f in os.listdir(directory) if f.endswith(".py") and not f.startswith("_"))


def wrap_as_check(source, name):
    """縮排整個檔案塞進 check_<name>()，把 run 改名 _run 並在尾巴呼叫它。"""
    source = MAIN_GUARD_RE.sub("\n", source).rstrip() + "\n"
    source = source.replace("def run(solution):", "def _bank_entry(solution):", 1)
    body = "\n".join(("    " + line) if line.strip() else "" for line in source.splitlines())
    return "def check_%s():\n%s\n    _bank_entry(solution)\n" % (name, body)


def slug_of(filename):
    return re.sub(r"\W", "_", filename[:-3])


def render_tests(task_dir, subdir, banner):
    names = listdir_py(os.path.join(task_dir, subdir))
    chunks = [banner, "import solution", "", ""]
    for filename in names:
        chunks.append(wrap_as_check(read(os.path.join(task_dir, subdir, filename)),
                                    slug_of(filename)))
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n", names


def render_anchors(task_id, task_dir, hidden_names):
    rows = []
    for filename in hidden_names:
        source = read(os.path.join(task_dir, "hidden", filename))
        kind = ANCHOR_KIND_RE.search(source)
        anchor = ANCHOR_RE.search(source)
        derivation = DERIVATION_RE.search(source)
        rows.append((("check_" + slug_of(filename)),
                     kind.group(1) if kind else "?",
                     anchor.group(1).strip() if anchor else "?",
                     derivation.group(1).strip() if derivation else "?"))

    out = []
    add = out.append
    add("# %s — 隱藏驗收 ⇄ 目標／契約 對照表" % task_id)
    add("")
    add("§五-2 的公平性複核表。**本檔由 `export_bank.py` 從 `bank/%s/hidden/*.py` 的" % task_id)
    add("檔頭自動產生，不要手改**——改了下一次投影就蓋掉。要改內容請改那些檔頭。")
    add("")
    add("`gauge_r530.py --check` 已經把**正向**那一半變成可執行的擋門：每一條的")
    add("`anchor_quote` 都逐字比對過，在 `goal.md` 或 `contract.md` 裡找得到才算過。")
    add("")
    add("⚠ **反向那一半機器做不到**（目標敘述裡每一句「客戶困擾」至少要有一條驗收對應）。")
    add("下面第二張表只能列出「有驗收指過去的目標句子」，列不出**沒有被任何驗收指到的句子**")
    add("——那正是反向擋門要找的東西。**複核者必須自己讀一次 `goal.md`**。")
    add("複核者不得是作者；目前狀態：**作者自填，未複核**。")
    add("")
    add("## 一、正向：每一條隱藏驗收指回哪一句")
    add("")
    add("| hidden_id | anchor_kind | anchor_quote（逐字） | derivation |")
    add("|---|---|---|---|")
    for hidden_id, kind, quote, derivation in rows:
        add("| `%s` | %s | %s | %s |"
            % (hidden_id, kind, quote.replace("|", "\\|"), derivation.replace("|", "\\|")))
    add("")
    add("## 二、反向：被指到的目標句子（**不完整，見上面的警告**）")
    add("")
    add("| goal 裡的句子 | 指到它的驗收 |")
    add("|---|---|")
    grouped = {}
    for hidden_id, kind, quote, _derivation in rows:
        if kind == "goal":
            grouped.setdefault(quote, []).append(hidden_id)
    for quote in sorted(grouped):
        add("| %s | %s |" % (quote.replace("|", "\\|"),
                             ", ".join("`%s`" % x for x in grouped[quote])))
    add("")
    add("`contract` 錨點 %d 條、`goal` 錨點 %d 條。"
        % (sum(1 for r in rows if r[1] == "contract"), sum(1 for r in rows if r[1] == "goal")))
    return "\n".join(out) + "\n"


def project(task_id):
    """回傳 {相對路徑: 內容}，相對於 ops/gain/r530/。"""
    task_dir = os.path.join(BANK, task_id)
    meta = json.loads(read(os.path.join(task_dir, "meta.json")))
    files = {}

    files["templates/%s/goal.md" % task_id] = read(os.path.join(task_dir, "goal.md"))
    files["templates/%s/contract.md" % task_id] = read(os.path.join(task_dir, "contract.md"))
    files["templates/%s/run_tests.sh" % task_id] = RUN_TESTS_SH

    banner = ('"""Checks that ship with this task. You can run them yourself:'
              ' `sh run_tests.sh`.\n\n'
              'Each `check_*` function is one check. A check passes when it returns\n'
              'normally. These are the same checks the client runs before accepting\n'
              'the work.\n"""')
    visible, _names = render_tests(task_dir, "tests_visible", banner)
    files["templates/%s/tests_visible/test_visible.py" % task_id] = visible

    hidden_banner = ('"""%s — hidden checks, %d. **Never enters a workspace.**\n\n'
                     'Generated from bank/%s/hidden/*.py by export_bank.py; the\n'
                     'anchor table is in ANCHORS.md beside this file.\n"""'
                     % (task_id, meta["hidden_n"], task_id))
    hidden, hidden_names = render_tests(task_dir, "hidden", hidden_banner)
    files["hidden/%s/test_hidden.py" % task_id] = hidden
    files["hidden/%s/ANCHORS.md" % task_id] = render_anchors(task_id, task_dir, hidden_names)

    files["gauge/%s/good.py" % task_id] = read(os.path.join(task_dir, "reference", "solution.py"))
    for name in sorted(os.listdir(os.path.join(task_dir, "reference"))):
        if name.startswith("bad_") and name.endswith(".py"):
            files["gauge/%s/%s" % (task_id, name)] = read(os.path.join(task_dir, "reference", name))

    files["rubrics/%s.md" % task_id] = read(os.path.join(task_dir, "rubric.md"))
    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description="project bank/ into the TASK_FORMAT layout")
    parser.add_argument("--check", action="store_true",
                        help="只比對，不寫檔；投影過期就 exit 1")
    parser.add_argument("--out", default=HERE)
    args = parser.parse_args(argv)

    tasks = sorted(d for d in os.listdir(BANK)
                   if d.startswith("ow_") and os.path.isdir(os.path.join(BANK, d)))
    wanted = {}
    for task_id in tasks:
        wanted.update(project(task_id))

    stale = []
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
            if relative.endswith("run_tests.sh"):
                os.chmod(path, 0o755)

    # 投影目錄裡多出來的東西＝上一次投影留下的垃圾，投影模式下清掉。
    orphans = []
    for top in ("templates", "hidden", "gauge", "rubrics"):
        root = os.path.join(args.out, top)
        for base, _dirs, names in os.walk(root):
            if "__pycache__" in base:
                continue
            for name in names:
                relative = os.path.relpath(os.path.join(base, name), args.out)
                if relative not in wanted:
                    orphans.append(relative)
    if orphans and not args.check:
        for relative in orphans:
            os.remove(os.path.join(args.out, relative))

    sizes = {}
    for task_id in tasks:
        root = os.path.join(args.out, "templates", task_id)
        total = 0
        for base, _dirs, names in os.walk(root):
            for name in names:
                total += os.path.getsize(os.path.join(base, name))
        sizes[task_id] = total

    print("tasks=%d  projected files=%d" % (len(tasks), len(wanted)))
    too_big = [t for t, n in sizes.items() if not (200 <= n <= 30 * 1024)]
    print("template sizes: min=%d max=%d bytes (TASK_FORMAT bound: 200 B - 30 KB) -> %s"
          % (min(sizes.values()), max(sizes.values()), "OK" if not too_big else "OUT OF BOUNDS"))
    for task_id in too_big:
        print("  OUT OF BOUNDS %s: %d bytes" % (task_id, sizes[task_id]))

    if args.check:
        if stale or orphans or too_big:
            for relative in stale:
                print("STALE   %s" % relative)
            for relative in orphans:
                print("ORPHAN  %s" % relative)
            print("RESULT: FAIL (run export_bank.py to refresh)")
            return 1
        print("RESULT: PASS (projection is up to date)")
        return 0

    print("wrote/updated %d, removed %d orphan(s)" % (len(stale), len(orphans)))
    if too_big:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
