#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R530 開放目標題庫的量具（gauge）。

這支在架構裡承重什麼
--------------------
R530 預註冊（`DECISION_20260913_R530_OPEN_GOAL_WITH_WITHOUT_VACANT_PREREG.md`
§一-1、§五-1、§五-2）要求：題庫在**任何一通模型呼叫之前**就要被量過。
「量過」在本專題有既定判準，寫在 `vacant/suitegauge.py`：

  1. 參考解必須通過**全部**可見與隱藏驗收（否則驗收本身是壞的）；
  2. 每題至少兩個「已知壞解」必須被隱藏驗收擋下（否則隱藏驗收沒有鑑別力）；
  3. 至少一個已知壞解也要被**可見**驗收擋下（否則可見測資太弱，
     `A-GATE`／`A-CONF` 的出貨閘門會變成橡皮圖章）。

本檔另外承重 §五-2 擋門第 1 條的**可執行版本**：每一條隱藏驗收的檔頭
`# anchor:` 必須是 `goal.md` 或 `contract.md` 裡**逐字存在**的一句話。
指不回原文的隱藏驗收＝「藏了目標沒暗示的需求」，本量具直接判 FAIL。

誠實邊界（逐字沿用 `vacant/suitegauge.py` 的單邊保證）
------------------------------------------------------
**擋得住已知壞解 ≠ 涵蓋真需求。** 本量具給的是單邊保證：它證明
「這些已知的錯法會被擋下來」，它**不**證明「所有錯法都會被擋下來」，
更不證明隱藏驗收涵蓋了目標敘述講的全部需求。§五-2 的反向擋門
（目標敘述裡每一句客戶困擾都要有驗收對應）**必須由另一位代理人工複核**，
本量具只做得到 anchor 的存在性，做不到覆蓋的完備性。
不准把 `--check` 全綠讀成「驗收套件固定點已解」。

用法
----
    python ops/gain/r530/gauge_r530.py --check
    python ops/gain/r530/gauge_r530.py --check --task ow_01_csvjson
    python ops/gain/r530/gauge_r530.py --sha-refresh      # 重算 meta.json 的 sha256
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import traceback

BANK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bank")

REQUIRED_FILES = ("goal.md", "contract.md", "rubric.md", "meta.json")
REQUIRED_DIRS = ("tests_visible", "hidden", "reference")

# AMEND1（2026-09-14）的**具名例外**，不是把界線放寬。
# §五-2 的反向擋門在 `ow_08_logscan` 失敗一句（goal 的「from the shell without
# writing a script」零驗收），Fable 裁決補 1 條可見 ＋ 2 條隱藏 ⇒ 那一題的條數
# 超出 §一-1 的可見 2–3／`tight` 隱藏 10–15。
# **為什麼寫成具名例外而不是改界線**：改界線會讓其他 19 題一起漂，而且下一次有人
# 多寫兩條就再也擋不住。具名例外會在 diff 裡看得見，也逐字抄進 AMEND1。
COUNT_EXCEPTIONS = {
    "ow_08_logscan": {
        "visible": (2, 4),
        "hidden": (10, 16),
        "why": "AMEND1 item 1: CLI checks added so the goal's shell sentence is graded",
    },
}

ANCHOR_RE = re.compile(r"^#\s*anchor:\s*(.+?)\s*$", re.M)
ANCHOR_KIND_RE = re.compile(r"^#\s*anchor_kind:\s*(goal|contract)\s*$", re.M)
DERIVATION_RE = re.compile(r"^#\s*derivation:\s*(.+?)\s*$", re.M)


# ---------------------------------------------------------------- helpers

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_ws(s):
    """把換行與連續空白壓成單一空格——目標／契約原文在 markdown 裡會折行，
    逐字比對必須先正規化，否則折行位置會變成假 FAIL。"""
    return re.sub(r"\s+", " ", s).strip()


def load_candidate(path, tmp_root, tag):
    """把候選解複製成 `<tmp>/<tag>/solution.py` 再載入。

    複製這一步不是潔癖：契約裡有 `python -m solution FILE` 這種 CLI 條款
    （`ow_01_csvjson`），子行程必須在一個「模組就叫 solution」的目錄裡跑，
    而已知壞解的檔名是 `bad_a.py`。統一複製成 solution.py 讓兩種驗收同形。
    """
    d = os.path.join(tmp_root, tag)
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, "solution.py")
    shutil.copyfile(path, dst)
    name = "r530_sol_%s" % re.sub(r"\W", "_", tag)
    spec = importlib.util.spec_from_file_location(name, dst)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_test(path):
    name = "r530_test_" + re.sub(r"\W", "_", os.path.relpath(path, BANK_DIR))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "run"):
        raise RuntimeError("test file has no run(solution): %s" % path)
    return mod


def run_one(test_mod, solution_mod):
    """回傳 (ok, detail)。任何例外都算 fail——壞解炸掉也是被擋下來。"""
    try:
        test_mod.run(solution_mod)
        return True, ""
    except BaseException as exc:  # noqa: BLE001 - 壞解會丟任何東西
        text = str(exc).strip()
        line = text.splitlines()[0] if text else exc.__class__.__name__
        return False, "%s: %s" % (exc.__class__.__name__, line[:160])


def constants_of(path):
    """抽出一個測試檔 body 裡所有字面值，用來做可見／隱藏零重疊檢查。"""
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except SyntaxError:
        return ()
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value is not None:
            out.append(repr(node.value))
    return tuple(out)


def listdir_py(d):
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d) if f.endswith(".py") and not f.startswith("_"))


# ---------------------------------------------------------------- per task

class TaskResult(object):
    def __init__(self, task_id):
        self.task_id = task_id
        self.errors = []
        self.stratum = "?"
        self.visible_n = 0
        self.hidden_n = 0
        self.ref_visible_ok = 0
        self.ref_hidden_ok = 0
        self.bad_rows = []      # (name, n_visible_failed, n_hidden_failed)

    @property
    def ok(self):
        return not self.errors


def check_task(task_dir, tmp_root):
    task_id = os.path.basename(task_dir)
    res = TaskResult(task_id)
    err = res.errors.append

    # --- 結構 ---------------------------------------------------------
    for f in REQUIRED_FILES:
        if not os.path.isfile(os.path.join(task_dir, f)):
            err("missing file %s" % f)
    for d in REQUIRED_DIRS:
        if not os.path.isdir(os.path.join(task_dir, d)):
            err("missing dir %s/" % d)
    if res.errors:
        return res

    meta = json.load(open(os.path.join(task_dir, "meta.json"), encoding="utf-8"))
    res.stratum = meta.get("stratum", "?")
    if res.stratum not in ("tight", "loose"):
        err("stratum must be tight|loose, got %r" % res.stratum)
    if not str(meta.get("origin", "")).startswith("authored"):
        err("meta.origin must start with 'authored'")
    if not meta.get("why_not_offtheshelf"):
        err("meta.why_not_offtheshelf missing")
    if meta.get("task_id") != task_id:
        err("meta.task_id=%r != directory name" % meta.get("task_id"))

    vis_files = listdir_py(os.path.join(task_dir, "tests_visible"))
    hid_files = listdir_py(os.path.join(task_dir, "hidden"))
    res.visible_n, res.hidden_n = len(vis_files), len(hid_files)

    if meta.get("visible_n") != res.visible_n:
        err("meta.visible_n=%r but %d files in tests_visible/" % (meta.get("visible_n"), res.visible_n))
    if meta.get("hidden_n") != res.hidden_n:
        err("meta.hidden_n=%r but %d files in hidden/" % (meta.get("hidden_n"), res.hidden_n))

    waiver = COUNT_EXCEPTIONS.get(task_id, {})
    lo, hi = waiver.get("hidden") or ((5, 7) if res.stratum == "loose" else (10, 15))
    if not (lo <= res.hidden_n <= hi):
        err("hidden_n=%d outside [%d,%d] for stratum=%s" % (res.hidden_n, lo, hi, res.stratum))
    vlo, vhi = waiver.get("visible") or (2, 3)
    if not (vlo <= res.visible_n <= vhi):
        err("visible_n=%d outside [%d,%d]" % (res.visible_n, vlo, vhi))

    # --- sha256 清單 --------------------------------------------------
    listed = meta.get("sha256", {})
    on_disk = {}
    for root, _dirs, files in os.walk(task_dir):
        if "__pycache__" in root:
            continue
        for f in sorted(files):
            if f == "meta.json" or f.endswith(".pyc"):
                continue
            rel = os.path.relpath(os.path.join(root, f), task_dir)
            on_disk[rel] = sha256_file(os.path.join(root, f))
    for rel, digest in sorted(on_disk.items()):
        if rel not in listed:
            err("sha256 missing entry for %s" % rel)
        elif listed[rel] != digest:
            err("sha256 mismatch for %s" % rel)
    for rel in listed:
        if rel not in on_disk:
            err("sha256 lists vanished file %s" % rel)

    # --- anchor 擋門（§五-2 擋門 1 的可執行版本）-----------------------
    goal_txt = norm_ws(open(os.path.join(task_dir, "goal.md"), encoding="utf-8").read())
    contract_txt = norm_ws(open(os.path.join(task_dir, "contract.md"), encoding="utf-8").read())
    for f in hid_files:
        src = open(os.path.join(task_dir, "hidden", f), encoding="utf-8").read()
        m_kind = ANCHOR_KIND_RE.search(src)
        m_anchor = ANCHOR_RE.search(src)
        m_deriv = DERIVATION_RE.search(src)
        if not m_kind:
            err("%s: no '# anchor_kind: goal|contract' header" % f)
            continue
        if not m_anchor:
            err("%s: no '# anchor:' header" % f)
            continue
        if not m_deriv:
            err("%s: no '# derivation:' header" % f)
        quote = norm_ws(m_anchor.group(1).strip().strip('"'))
        hay = goal_txt if m_kind.group(1) == "goal" else contract_txt
        if quote not in hay:
            err("%s: anchor not found verbatim in %s.md: %r" % (f, m_kind.group(1), quote[:70]))

    # --- 可見／隱藏零重疊 ---------------------------------------------
    vis_consts = {}
    for f in vis_files:
        vis_consts[f] = constants_of(os.path.join(task_dir, "tests_visible", f))
    for hf in hid_files:
        hc = constants_of(os.path.join(task_dir, "hidden", hf))
        for vf, vc in vis_consts.items():
            if hc and hc == vc:
                err("hidden/%s has byte-identical literals with tests_visible/%s" % (hf, vf))

    # --- 跑參考解與已知壞解 -------------------------------------------
    ref = os.path.join(task_dir, "reference", "solution.py")
    if not os.path.isfile(ref):
        err("missing reference/solution.py")
        return res
    bads = sorted(f for f in os.listdir(os.path.join(task_dir, "reference"))
                  if f.startswith("bad_") and f.endswith(".py"))
    if len(bads) < 2:
        err("need >=2 known-bad solutions in reference/, got %d" % len(bads))

    vis_mods = [(f, load_test(os.path.join(task_dir, "tests_visible", f))) for f in vis_files]
    hid_mods = [(f, load_test(os.path.join(task_dir, "hidden", f))) for f in hid_files]

    ref_mod = load_candidate(ref, tmp_root, task_id + "__ref")
    for f, tm in vis_mods:
        ok, detail = run_one(tm, ref_mod)
        if ok:
            res.ref_visible_ok += 1
        else:
            err("reference FAILS visible %s -- %s" % (f, detail))
    for f, tm in hid_mods:
        ok, detail = run_one(tm, ref_mod)
        if ok:
            res.ref_hidden_ok += 1
        else:
            err("reference FAILS hidden %s -- %s" % (f, detail))

    any_bad_caught_by_visible = False
    for b in bads:
        bad_mod = load_candidate(os.path.join(task_dir, "reference", b), tmp_root, task_id + "__" + b[:-3])
        nv = sum(0 if run_one(tm, bad_mod)[0] else 1 for _f, tm in vis_mods)
        nh = sum(0 if run_one(tm, bad_mod)[0] else 1 for _f, tm in hid_mods)
        res.bad_rows.append((b, nv, nh))
        if nh == 0:
            err("known-bad %s is NOT blocked by any hidden check" % b)
        if nv > 0:
            any_bad_caught_by_visible = True
    if bads and not any_bad_caught_by_visible:
        err("no known-bad solution is blocked by the VISIBLE checks (visible suite too weak)")

    return res


# ---------------------------------------------------------------- sha refresh

def sha_refresh(task_dir):
    meta_path = os.path.join(task_dir, "meta.json")
    meta = json.load(open(meta_path, encoding="utf-8"))
    table = {}
    for root, _dirs, files in os.walk(task_dir):
        if "__pycache__" in root:
            continue
        for f in sorted(files):
            if f == "meta.json" or f.endswith(".pyc"):
                continue
            rel = os.path.relpath(os.path.join(root, f), task_dir)
            table[rel] = sha256_file(os.path.join(root, f))
    meta["sha256"] = dict(sorted(table.items()))
    meta["visible_n"] = len(listdir_py(os.path.join(task_dir, "tests_visible")))
    meta["hidden_n"] = len(listdir_py(os.path.join(task_dir, "hidden")))
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2, sort_keys=False)
        fh.write("\n")


# ------------------------------------------------------- difficulty gate

CORE_PREFIXES = tuple("ow_%02d" % n for n in range(1, 13))


def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def difficulty_gate(bank, tasks, verbose=True):
    """Prereg S1-3b D1/D2, fail-closed.

    D1 compares the median `ref_solution_lines` of the eight new tasks against the
    median of the frozen core twelve; more than 40% apart sends the whole batch
    back. D2 is the per-task floor on hidden checks.

    Honest boundary, carried verbatim from the prereg: line count is a coarse proxy
    for difficulty, not difficulty, and the 40% line is a choice with no external
    anchor. D1 catches a batch that is uniformly lighter than the core; it does not
    catch a per-task mismatch.
    """
    errors = []
    core, new = [], []
    for task_id in tasks:
        path = os.path.join(bank, task_id, "meta.json")
        if not os.path.isfile(path):
            continue
        meta = json.load(open(path, encoding="utf-8"))
        lines = meta.get("ref_solution_lines")
        if not isinstance(lines, int):
            errors.append("%s: meta.ref_solution_lines missing" % task_id)
            continue
        (core if task_id.startswith(CORE_PREFIXES) else new).append((task_id, meta, lines))

    for task_id, meta, _lines in new:
        floor = 5 if meta.get("stratum") == "loose" else 10
        if meta.get("hidden_n", 0) < floor:
            errors.append("D2 %s: hidden_n=%s below the floor of %d for stratum=%s"
                          % (task_id, meta.get("hidden_n"), floor, meta.get("stratum")))

    if not core or not new:
        if verbose:
            print("difficulty gate: skipped (needs both the core twelve and the new eight)")
        return errors

    m_core, m_new = median([x[2] for x in core]), median([x[2] for x in new])
    delta = abs(m_new - m_core) / m_core
    if delta > 0.40:
        errors.append("D1: median ref_solution_lines new=%.1f core=%.1f, relative diff %.3f > 0.40"
                      % (m_new, m_core, delta))
    if verbose:
        tight_new = [x[2] for x in new if x[1].get("stratum") == "tight"]
        print("difficulty gate (prereg S1-3b): core n=%d median=%.1f | new n=%d median=%.1f"
              " | relative diff=%.3f | D1=%s D2=%s"
              % (len(core), m_core, len(new), m_new, delta,
                 "GREEN" if delta <= 0.40 else "RED",
                 "GREEN" if not any(e.startswith("D2") for e in errors) else "RED"))
        if tight_new:
            tight_delta = abs(median(tight_new) - m_core) / m_core
            print("  (descriptive, not a gate: new tight-only median=%.1f, relative diff=%.3f;"
                  " the loose three are shorter by design and pull the D1 median down)"
                  % (median(tight_new), tight_delta))
        print("  line count is a coarse proxy for difficulty, and 40 per cent is a choice with"
              " no external anchor (prereg S1-3b honest boundary 1 and 2).")
    return errors


# ------------------------------------------------------- bank manifest

def bank_manifest(bank):
    """回傳 (逐行清單, 合併雜湊)。AMEND1 的 sha256 釘死表就是這一份。

    合併雜湊的定義寫死在這裡，不准事後改：把每一行 `<sha256>  <bank/ 起算的相對路徑>`
    以 `\n` 串起來（路徑以 UTF-8 位元組序排序、結尾補一個 `\n`），整串 UTF-8 取 sha256。
    `__pycache__` 與 `.pyc` 不算——它們是跑出來的，不是題庫。
    **`meta.json` 也在裡面**：`meta.sha256` 是每一題自己算自己的，算不到自己那一檔，
    所以 `meta.json` 的雜湊只能在這一層釘死。
    """
    rows = []
    for root, dirs, files in os.walk(bank):
        dirs[:] = sorted(d for d in dirs if d != "__pycache__")
        for name in sorted(files):
            if name.endswith(".pyc"):
                continue
            path = os.path.join(root, name)
            rows.append((os.path.relpath(path, bank).replace(os.sep, "/"), sha256_file(path)))
    rows.sort(key=lambda row: row[0].encode("utf-8"))
    lines = ["%s  %s" % (digest, rel) for rel, digest in rows]
    combined = hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()
    return lines, combined


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="R530 open-goal task bank gauge")
    ap.add_argument("--check", action="store_true", help="跑全部判準，任何一條不過就 exit 1")
    ap.add_argument("--sha-refresh", action="store_true", help="重算 meta.json 的 sha256 清單")
    ap.add_argument("--bank-sha", action="store_true",
                    help="印出 bank/ 的逐檔 sha256 清單與合併雜湊（AMEND1 的釘死表）")
    ap.add_argument("--task", default=None, help="只跑這一題")
    ap.add_argument("--bank", default=BANK_DIR)
    args = ap.parse_args(argv)

    tasks = sorted(d for d in os.listdir(args.bank)
                   if os.path.isdir(os.path.join(args.bank, d)) and d.startswith("ow_"))
    if args.task:
        tasks = [t for t in tasks if t == args.task]
        if not tasks:
            print("no such task", file=sys.stderr)
            return 2

    if args.bank_sha:
        lines, combined = bank_manifest(args.bank)
        for line in lines:
            print(line)
        print()
        print("bank_sha256  %s  (%d files)" % (combined, len(lines)))
        return 0

    if args.sha_refresh:
        for t in tasks:
            sha_refresh(os.path.join(args.bank, t))
        print("sha256 refreshed for %d task(s)" % len(tasks))
        return 0

    if not args.check:
        ap.print_help()
        return 2

    results = []
    with tempfile.TemporaryDirectory(prefix="r530gauge_") as tmp_root:
        for t in tasks:
            try:
                results.append(check_task(os.path.join(args.bank, t), tmp_root))
            except Exception:
                r = TaskResult(t)
                r.errors.append("gauge crashed: " + traceback.format_exc(limit=3).replace("\n", " | "))
                results.append(r)

    print("R530 task-bank gauge  (suitegauge 判準：參考解全過 / >=2 壞解被隱藏擋下 / >=1 壞解也被可見擋下)")
    print("=" * 104)
    hdr = "%-20s %-6s %4s %4s  %-11s  %-30s %s"
    print(hdr % ("task_id", "strat", "vis", "hid", "ref pass", "known-bad blocked vis/hid", "verdict"))
    print("-" * 104)
    n_bad = 0
    for r in results:
        badtxt = " ".join("%s=%d/%d" % (b.replace("bad_", "").replace(".py", ""), nv, nh)
                          for b, nv, nh in r.bad_rows)
        verdict = "OK" if r.ok else "FAIL(%d)" % len(r.errors)
        if not r.ok:
            n_bad += 1
        print(hdr % (r.task_id, r.stratum, r.visible_n, r.hidden_n,
                     "%d/%d %d/%d" % (r.ref_visible_ok, r.visible_n, r.ref_hidden_ok, r.hidden_n),
                     badtxt, verdict))
    print("-" * 104)
    tot_v = sum(r.visible_n for r in results)
    tot_h = sum(r.hidden_n for r in results)
    n_tight = sum(1 for r in results if r.stratum == "tight")
    n_loose = sum(1 for r in results if r.stratum == "loose")
    print("tasks=%d (tight=%d loose=%d)  visible=%d  hidden=%d" % (len(results), n_tight, n_loose, tot_v, tot_h))

    gate_errors = difficulty_gate(args.bank, tasks, verbose=not args.task)
    if gate_errors:
        n_bad += 1
    if n_bad:
        print()
        for r in results:
            for e in r.errors:
                print("FAIL %s :: %s" % (r.task_id, e))
        for e in gate_errors:
            print("FAIL difficulty-gate :: %s" % e)
        print()
        print("RESULT: FAIL")
        return 1
    print()
    print("RESULT: PASS (%d/%d tasks)" % (len(results), len(results)))
    print("單邊保證：擋得住已知壞解 != 涵蓋真需求。§五-2 的反向擋門（目標裡每句困擾都要有驗收）")
    print("由另一位代理人工複核，本量具只驗 anchor 逐字指得回 goal.md / contract.md。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
