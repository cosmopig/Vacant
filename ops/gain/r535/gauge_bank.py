#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R535 題庫量具：**零模型呼叫，發射前必須全綠**（Fable 2026-09-19 裁決 R535）。

這支在架構裡承重什麼
--------------------
題庫是自造的，所以「它真的能量到東西」這件事沒有外部背書，只能自己證。
這支就是那個證明，五項逐項實跑，一項不過就不准發射。

    1. 參考解**過**可見 ＋ **過**隱藏。
    2. 三個壞樁（`bad_a`／`bad_b`／`bad_c`）**都被可見擋**。
    3. 回饋**充分決定修法**——這一條是 S1 正控制性質的關鍵：
       · 「名字錯」樁（`bad_c`）的 `render_failures` 輸出必須**含被要求的名字**；
       · 「名字對、行為錯」樁（`bad_a`）的輸出必須含 `args=` 與 `want=`。
       裁決只要求 S1 驗前者、S2 驗後者；這裡**兩層都驗兩條**（超集），
       因為「哪一條才是這一層的代表失敗模式」是判斷，而判斷不該藏在量具裡。
    4. `grep -ril hidden <workspace 樣板>` **零命中**（兩份樣板都驗：一般臂的
       `TASK.md`，以及 PC 臂的 `TASK_explicit.md`）。
    5. `TASK.md` 內 grep **不到**套件 import 的名字（S1）／被 withhold 的字面值（S2）。
    6. `TASK_explicit.md` 與 `TASK.md` 的 diff **只准是介面／細節那幾行**，
       其餘逐位元相同——而且必須是**純插入**（`difflib` 的 opcode 只有
       `equal` 與**一段** `insert`，一個 `delete`／`replace` 都不准有）。

第 6 項是擋門不是形式：PC 臂（正控制，每題只跑 1 次、不重試）是 RP 臂的
**天花板**，兩份 TASK 若在別的地方也不一樣（多一句提示、少一個例子、換個語氣），
PC 就不再是同一題的天花板，整個 `CEILING_TOO_LOW` 判準失效。
`--diff` 會把每一題實際插入的行印出來。

⚠ **單邊保證（`vacant/suitegauge.py` 逐字）**：擋得住已知壞解 **≠** 涵蓋真需求。
第 1、2 項全綠只說明「參考解過得了我們自己寫的那幾條，而我們自己想到的三種錯
被擋下來了」，**不准讀成「驗收套件固定點已解」**。同一句話也寫在
`bank_manifest.json` 的 `honesty_bounds`。

⚠ 第 3 項驗的是**回饋裡有那個名字／有 args= 與 want=**，
**不驗 agent 會不會照做**。看得到 ≠ 照做（`docs/VACANT_RUN.md` 誠實邊界 10）。

判準用的是**既有的那把尺**：`vacant/vrun/acceptance.py::run_suite` 與
`render_failures`，和 `vacant run` 真跑時跑的是同一支，不准另寫第二把。

用法
----
    python3 ops/gain/r535/gauge_bank.py
    python3 ops/gain/r535/gauge_bank.py --task s1_01_addmul
    python3 ops/gain/r535/gauge_bank.py --stratum S1 --json /tmp/g.json
    python3 ops/gain/r535/gauge_bank.py --show s1_01_addmul   # 印第 3 項的回饋原文
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from vacant.vrun import acceptance  # noqa: E402
from vacant.vrun.sandbox import make_sandbox  # noqa: E402

BANK_DIR = os.path.join(HERE, "bank")
STAKES = ("bad_a", "bad_b", "bad_c")

#: 第 4 項的關鍵字。工作區樣板裡出現這個字就是漏了隱藏驗收的存在。
FORBIDDEN_IN_WORKSPACE = "hidden"


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _tasks(stratum: str | None, only: str | None) -> list[str]:
    out = []
    for tid in sorted(os.listdir(BANK_DIR)):
        d = os.path.join(BANK_DIR, tid)
        if not os.path.isdir(d):
            continue
        if only and tid != only:
            continue
        meta = json.loads(_read(os.path.join(d, "meta.json")))
        if stratum and meta["stratum"] != stratum:
            continue
        out.append(tid)
    return out


def _run(sb, ws: str, suite_dir: str, *, suite: str, tid: str,
         verify_root: str) -> dict:
    return acceptance.run_suite(sb, ws, suite_dir, suite=suite, task_id=tid,
                                verify_root=verify_root, timeout_s=10.0)


def _materialise(dst: str, src_dir: str, files: list[str],
                 solution_src: str | None = None) -> None:
    os.makedirs(dst, exist_ok=True)
    for rel in files:
        shutil.copy2(os.path.join(src_dir, rel), os.path.join(dst, rel))
    if solution_src is not None:
        shutil.copy2(solution_src, os.path.join(dst, "solution.py"))


def _name_variants(name: str) -> list[str]:
    """一個函式名在散文裡可能長成的樣子：`to_c` / `to c` / `toc`。"""
    return sorted({name, name.replace("_", " "), name.replace("_", ""),
                   name.replace("_", "-")})


def _word_hit(text: str, needle: str) -> bool:
    pat = r"(?<![A-Za-z0-9_])" + re.escape(needle) + r"(?![A-Za-z0-9_])"
    return re.search(pat, text, re.I) is not None


def gauge_task(sb, tid: str, tmp_root: str, *, keep: bool = False) -> dict:
    d = os.path.join(BANK_DIR, tid)
    meta = json.loads(_read(os.path.join(d, "meta.json")))
    visible_dir = os.path.join(d, "tests_visible")
    hidden_dir = os.path.join(d, "hidden")
    root = os.path.join(tmp_root, tid)
    verify_root = os.path.join(root, "_verify")
    os.makedirs(verify_root, exist_ok=True)
    rec: dict = {"task_id": tid, "stratum": meta["stratum"], "items": {},
                 "detail": {}}

    # ── 1. 參考解過可見 ＋ 過隱藏 ────────────────────────────────────────
    ws_ref = os.path.join(root, "ref")
    _materialise(ws_ref, d, [], os.path.join(d, "reference", "solution.py"))
    vis_ref = _run(sb, ws_ref, visible_dir, suite="visible", tid=tid,
                   verify_root=verify_root)
    hid_ref = _run(sb, ws_ref, hidden_dir, suite="hidden", tid=tid,
                   verify_root=verify_root)
    rec["items"]["1_reference_passes"] = bool(vis_ref["all_pass"]
                                              and hid_ref["all_pass"])
    rec["detail"]["reference"] = {
        "visible": "%d/%d" % (vis_ref["passed"], vis_ref["total"]),
        "hidden": "%d/%d" % (hid_ref["passed"], hid_ref["total"]),
        "visible_failures": (acceptance.render_failures(vis_ref)
                             if not vis_ref["all_pass"] else ""),
        "hidden_failures": (acceptance.render_failures(hid_ref)
                            if not hid_ref["all_pass"] else ""),
    }

    # ── 2. 三個壞樁都被可見擋 ／ 3. 回饋充分決定修法 ───────────────────
    blocked = {}
    feedback = {}
    for stake in STAKES:
        ws = os.path.join(root, stake)
        _materialise(ws, d, [], os.path.join(d, "reference", stake + ".py"))
        res = _run(sb, ws, visible_dir, suite="visible", tid=tid,
                   verify_root=verify_root)
        blocked[stake] = not res["all_pass"]
        feedback[stake] = acceptance.render_failures(res)
    rec["items"]["2_stakes_blocked"] = all(blocked.values())
    rec["detail"]["stakes_blocked"] = blocked

    missing = meta["wrong_name_stake_missing_names"]
    fb_c = feedback["bad_c"]
    names_in_feedback = {n: (n in fb_c) for n in missing}
    fb_a = feedback["bad_a"]
    rec["items"]["3a_wrong_name_feedback_names_it"] = (
        bool(missing) and all(names_in_feedback.values()))
    rec["items"]["3b_wrong_behaviour_feedback_has_args_want"] = (
        "args=" in fb_a and "want=" in fb_a)
    rec["detail"]["feedback"] = {
        "bad_c_missing_names": missing,
        "bad_c_names_present_in_feedback": names_in_feedback,
        "bad_c_render_failures": fb_c,
        "bad_a_render_failures": fb_a,
    }

    # ── 4. 工作區樣板裡 grep 不到 "hidden"（一般臂 ＋ PC 臂各一份）─────
    tpl_files = list(meta["workspace_template"]) + list(
        meta["workspace_template_pc"])
    ws_tpl = os.path.join(root, "ws_template")
    _materialise(ws_tpl, d, tpl_files)
    g = subprocess.run(["grep", "-ril", FORBIDDEN_IN_WORKSPACE, ws_tpl],
                       capture_output=True, text=True)
    hits = [ln for ln in g.stdout.splitlines() if ln.strip()]
    rec["items"]["4_no_hidden_in_workspace"] = (not hits)
    rec["detail"]["grep_hidden"] = {"rc": g.returncode, "hits": hits,
                                    "template_files": tpl_files}

    # ── 5. TASK.md 不洩漏被 withhold 的東西 ────────────────────────────
    task_md = _read(os.path.join(d, "TASK.md"))
    leaks: list[str] = []
    if meta["stratum"] == "S1":
        for name in meta["required_names"]:
            for v in _name_variants(name):
                if _word_hit(task_md, v):
                    leaks.append("name %r (as %r)" % (name, v))
    else:
        for lit in meta["withheld"]:
            if lit.lower() in task_md.lower():
                leaks.append("withheld literal %r" % lit)
    rec["items"]["5_task_md_withholds"] = (not leaks)
    rec["detail"]["task_md_leaks"] = leaks

    # ── 6. TASK_explicit.md 與 TASK.md 的 diff 只准是插入的那一塊 ──────
    plain = task_md.splitlines()
    expl = _read(os.path.join(d, "TASK_explicit.md")).splitlines()
    ops = difflib.SequenceMatcher(None, plain, expl, autojunk=False)\
        .get_opcodes()
    inserts = [o for o in ops if o[0] == "insert"]
    other = [o for o in ops if o[0] not in ("equal", "insert")]
    inserted_lines: list[str] = []
    for _, _, _, j1, j2 in inserts:
        inserted_lines += expl[j1:j2]
    expected = meta["explicit_block_lines"]
    rec["items"]["6_explicit_diff_is_the_block_only"] = (
        not other and len(inserts) == 1
        and len(inserted_lines) == expected
        and inserted_lines[0] in ("## Interface", "## Details"))
    rec["detail"]["explicit_diff"] = {
        "inserted_line_count": len(inserted_lines),
        "expected_line_count": expected,
        "insert_blocks": len(inserts),
        "non_insert_opcodes": [o[0] for o in other],
        "inserted": inserted_lines,
        "unified": list(difflib.unified_diff(
            plain, expl, fromfile="TASK.md", tofile="TASK_explicit.md",
            lineterm="", n=1)),
    }

    rec["ok"] = all(rec["items"].values())
    if not keep:
        shutil.rmtree(root, ignore_errors=True)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser(
        description="R535 題庫量具（零模型呼叫；五項逐項實跑）")
    ap.add_argument("--task", default=None, help="只量一題")
    ap.add_argument("--stratum", default=None, choices=["S1", "S2"])
    ap.add_argument("--backend", default="none",
                    help="沙箱後端（本機稽核用 none；vacant-dev 上用 auto）")
    ap.add_argument("--json", default=None, help="把完整結果寫成 JSON")
    ap.add_argument("--show", default=None,
                    help="印這一題第 3 項的回饋原文（看回饋長什麼樣）")
    ap.add_argument("--diff", action="store_true",
                    help="逐題印第 6 項的實際 diff 行數與內容")
    args = ap.parse_args()

    tids = _tasks(args.stratum, args.task or args.show)
    if not tids:
        raise SystemExit("沒有符合的題目。")

    tmp_root = tempfile.mkdtemp(prefix="r535_gauge_")
    sb, backend_meta = make_sandbox(args.backend, workdir=tmp_root)
    rows = []
    try:
        for tid in tids:
            rows.append(gauge_task(sb, tid, tmp_root))
    finally:
        if not args.show:
            shutil.rmtree(tmp_root, ignore_errors=True)

    if args.show:
        r = rows[0]
        print("=== %s (%s) ===" % (r["task_id"], r["stratum"]))
        print("--- 3a 「名字錯」樁 bad_c 的 render_failures ---")
        print(r["detail"]["feedback"]["bad_c_render_failures"])
        print("--- 3b 「名字對、行為錯」樁 bad_a 的 render_failures ---")
        print(r["detail"]["feedback"]["bad_a_render_failures"])
        shutil.rmtree(tmp_root, ignore_errors=True)
        return 0 if r["ok"] else 1

    if args.diff:
        print("第 6 項：TASK_explicit.md 相對 TASK.md 的實際 diff（純插入）")
        for r in rows:
            dd = r["detail"]["explicit_diff"]
            print("\n%s (%s): +%d 行, insert blocks=%d, 非插入 opcode=%s"
                  % (r["task_id"], r["stratum"], dd["inserted_line_count"],
                     dd["insert_blocks"], dd["non_insert_opcodes"] or "none"))
            for line in dd["inserted"]:
                print("    + %s" % line)
        counts: dict[int, int] = {}
        for r in rows:
            n = r["detail"]["explicit_diff"]["inserted_line_count"]
            counts[n] = counts.get(n, 0) + 1
        print("\n插入行數分布：%s"
              % ", ".join("%d 行 × %d 題" % (k, v) for k, v in sorted(counts.items())))
        clean = sum(1 for r in rows
                    if r["items"]["6_explicit_diff_is_the_block_only"])
        print("純插入且只有那一塊：%d/%d" % (clean, len(rows)))
        print()

    items = ["1_reference_passes", "2_stakes_blocked",
             "3a_wrong_name_feedback_names_it",
             "3b_wrong_behaviour_feedback_has_args_want",
             "4_no_hidden_in_workspace", "5_task_md_withholds",
             "6_explicit_diff_is_the_block_only"]
    print("backend = %s" % backend_meta.get("backend", args.backend))
    print("tasks   = %d" % len(rows))
    for it in items:
        good = sum(1 for r in rows if r["items"][it])
        flag = "OK " if good == len(rows) else "FAIL"
        print("  [%s] %-42s %d/%d" % (flag, it, good, len(rows)))
    bad = [r for r in rows if not r["ok"]]
    if bad:
        print("\n不合格的題目（%d）：" % len(bad))
        for r in bad:
            failed = [k for k, v in r["items"].items() if not v]
            print("  %s (%s): %s" % (r["task_id"], r["stratum"], ", ".join(failed)))
            if r["detail"]["task_md_leaks"]:
                print("      leaks: %s" % r["detail"]["task_md_leaks"])
            if not r["items"]["1_reference_passes"]:
                print("      ref visible=%s hidden=%s"
                      % (r["detail"]["reference"]["visible"],
                         r["detail"]["reference"]["hidden"]))
                for line in (r["detail"]["reference"]["visible_failures"]
                             or r["detail"]["reference"]["hidden_failures"]
                             ).splitlines()[:4]:
                    print("      " + line)
            if not r["items"]["2_stakes_blocked"]:
                print("      blocked=%s" % r["detail"]["stakes_blocked"])
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump({"backend": backend_meta, "rows": rows}, fh,
                      ensure_ascii=False, indent=2)
        print("\nJSON → %s" % args.json)
    print("\n單邊保證：擋得住已知壞解 ≠ 涵蓋真需求（vacant/suitegauge.py）。")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
