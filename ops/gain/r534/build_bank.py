#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R534 題庫渲染：把選中的 20 題 LCB v2 投影成 pi agent 直接能跑的工作區形狀。

這支在架構裡承重什麼
--------------------
可究責層的三件事（可執行驗收當出貨閘門／沒過就重抽／仍沒過就拒交）要能在**外部
agent harness**（pi）上量，前提是「客戶的驗收測試」得以**檔案**的形式存在於工作區
裡——agent 看得到、跑得到、可以照著改。既有的 `gain_run.py` 是把 `visible_check`
的原始碼字串塞進沙箱執行，那個形狀餵不了一個會自己 `ls`／`cat`／跑指令的 agent。
這支就是那個轉換器，而且轉換是**確定性**的：同一份 `lcb_bank_v2.jsonl` ＋ 同一份
選題，渲染幾次都逐位元組相同，`--check` 直接驗有沒有漂。

兩棵樹，紅線就是它們的距離
--------------------------
    ops/gain/r534/templates/<task_id>/   ← 工作區樣板（複製給 pi，agent 看得到全部）
        goal.md                 LCB 題目敘述，**逐位元組等於題庫的 prompt 欄位**
        contract.md             介面釘死（檔名／函式名／位置引數／回傳／比對語義）
        tests_visible/test_visible.py   可見驗收（＝出貨閘門，agent 可自行執行）
        run_tests.sh            一行跑完可見驗收（形狀沿用 r530 的 RUN_TESTS_SH）

    ops/gain/r534/hidden/<task_id>/      ← **永遠不進工作區**，只給事後計分
        test_hidden.py          完整測資（可見 ∪ 隱藏），計分用

hidden 不是工作區的子目錄，而是**另一棵樹**：agent 的工作目錄裡結構上不存在那條
路徑，所以「不小心讀到」這件事沒有表達式。樣板裡也不出現 `hidden` 字樣的路徑
（`--check` 會掃）。

三個「照抄不動」的決定
----------------------
1. **goal.md ＝ prompt 逐字**。既有的 r460（12B）／r532（27B）送給模型的就是這個
   字串；改寫一個字，這 20 題就不再與那兩組歸檔資料比得起來（差異會混進「題目
   被重寫過」）。prompt 尾端那三行中文（頂層函式、只用標準函式庫、要 return）
   是題庫產生器加的，照樣留著。
2. **比對語義沿用 `vacant_network/codebench.py::_lcb_check_code`**：先試 `==`，bool 與數值
   不混談，數值容差 1e-6，list/tuple 逐元素遞迴。渲染出來的 `_aeq` 與那支的
   `__aeq` 是同一套判等，斷言訊息也保持 `args=… got=… want=…` 三欄位逐字
   ——H 臂的回饋就是轉發這個字串（`harness_arms.visible_report`）。
3. **hidden/test_hidden.py 是可見 ∪ 隱藏的超集**，與 `LiveCodeBenchLoader` 的
   `hidden_check`（`visible + hidden_tests`）逐字同一組 case。這樣算出來的分子
   才與 r460／r532 的 `meets_demand` 是同一把尺；換成「只有隱藏那 24 條」會是
   另一個指標，兩邊的數字不可互相引用。

誠實邊界（不要在報告裡漏掉）
----------------------------
LCB 沒有 canonical solution ⇒ **這 20 題沒有參考解正控制**。r530 的量具紀律
（參考解全過、壞樁全擋）在這裡做不到，能做的只有 `check_bank_precision.py` 的
KNOWN_BAD 篩除，以及 manifest 逐題記的 `any_arm_passed_hidden`：那一格是 false
的題（歸檔資料裡六個臂全軍覆沒），我們**沒有證據**證明一個正確解會被判過。

用法
----
    python3 ops/gain/r534/build_bank.py            # 渲染兩棵樹＋寫 bank_manifest.json
    python3 ops/gain/r534/build_bank.py --check    # 只驗：磁碟上的檔案與 manifest 對不對得上
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, REPO)

from ops.gain.r534.select_tasks import (  # noqa: E402
    BANK_PATH, BANK_SHA256, LAYER_B_SEED, RULE_TEXT, select)

TEMPLATES = os.path.join(HERE, "templates")
HIDDEN = os.path.join(HERE, "hidden")
MANIFEST = os.path.join(HERE, "bank_manifest.json")

# 樣板大小的**理智上界**（不是預註冊判準）：LCB 的題目敘述 1–2 KB、可見測資
# 少數幾條，正常落在 3–20 KB。超過 100 KB 代表某一題的可見測資字面值大得不像話，
# 那種東西塞進工作區會把 agent 的脈絡吃光——要人來看，不要默默通過。
TEMPLATE_BYTES_SANITY_MAX = 100_000

# 沿用 r530 的 run_tests.sh（`ops/gain/r530/export_bank.py::RUN_TESTS_SH`），
# 逐字相同：兩批題目的「跑一下驗收」在 agent 眼裡要是同一個動作。
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

# `_aeq` ＝ `vacant_network/codebench.py::_lcb_check_code` 裡那個 `__aeq` 的同義字，
# 一行一行對得上（先 ==、bool 不與數值混談、數值 1e-6、list/tuple 遞迴）。
AEQ_SRC = '''\
def _aeq(a, b):
    """與 vacant_network/codebench.py::_lcb_check_code 的 __aeq 同一套判等（逐行對應）。"""
    try:
        if a == b:
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= 1e-6
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_aeq(x, y) for x, y in zip(a, b))
    return a == b
'''

CONTRACT_TMPL = """\
# Contract

Write your answer in `solution.py` at the root of this workspace.

- Define a top-level function named `{entry_point}`. Not a method, not a class.
- It is called positionally: `{entry_point}(*args)`. The checks pass the arguments
  in the order the task statement gives them.
- It must **return** the answer. Printing is not returning; anything written to
  stdout is ignored.
- Standard library only. No network, no file system, no installed packages.
- A returned value counts as correct when it compares equal under this rule:
  plain `==` first; `True`/`False` never compare equal to `1`/`0`; two numbers
  are equal within 1e-6; lists and tuples are compared element by element,
  recursively, and must have the same length.

The checks that ship with this task are in `tests_visible/`. Run them with:

    sh run_tests.sh

Each failure prints `args=... got=... want=...` for the first case that failed.
"""

VISIBLE_HEADER = '''\
"""Visible checks for {task_id} -- these ship with the task and can be run.

Rendered from ops/gain/data/lcb_bank_v2.jsonl (sha256 {bank_sha_short}...) by
ops/gain/r534/build_bank.py. The literal (args, expected) pairs are the bank's
`visible_tests` field, byte for byte.
"""

import solution

'''

HIDDEN_HEADER = '''\
"""Scoring checks for {task_id} -- NOT part of any workspace.

⚠ 這個檔案是計分用的 GT。它住在 ops/gain/r534/hidden/ 這棵**另外的樹**裡，
  永遠不複製進 agent 的工作區；任何把它的內容（含失敗訊息）回饋給模型的路徑
  都是 R534 的紅線。

case 組成 ＝ 題庫的 `visible_tests` ＋ `hidden_tests`（超集），與
vacant_network/codebench.py::LiveCodeBenchLoader 的 `hidden_check` 逐字同一組，
所以算出來的分子與 runs/g_r460_harness_lcb2_*／runs/g_r532_lcb2_* 的
`meets_demand` 是同一把尺。
"""

import solution

'''


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _render_cases(entry_point: str, cases: list[dict], prefix: str) -> str:
    """一條 case 一個 `check_*()`，字面值用 `repr`（與 `_lcb_check_code` 同一種寫法）。"""
    out = []
    for i, case in enumerate(cases, 1):
        args = case["args"]
        want = case["expected"]
        out.append(
            f"def {prefix}_{i:02d}():\n"
            f"    args = {args!r}\n"
            f"    want = {want!r}\n"
            f"    got = solution.{entry_point}(*args)\n"
            f"    assert _aeq(got, want), \"args=%r got=%r want=%r\" % (args, got, want)\n"
        )
    return "\n\n".join(out) + "\n"


def render_task(rec: dict) -> dict[str, str]:
    """回 `{相對路徑: 內容}`；`templates/…` 與 `hidden/…` 兩棵樹都在裡面。"""
    tid = rec["task_id"]
    ep = rec["entry_point"]
    visible = rec["visible_tests"]
    full = visible + rec["hidden_tests"]
    vis_src = (VISIBLE_HEADER.format(task_id=tid, bank_sha_short=BANK_SHA256[:12])
               + AEQ_SRC + "\n\n" + _render_cases(ep, visible, "check_visible"))
    hid_src = (HIDDEN_HEADER.format(task_id=tid)
               + AEQ_SRC + "\n\n" + _render_cases(ep, full, "check_case"))
    return {
        f"templates/{tid}/goal.md": rec["prompt"],
        f"templates/{tid}/contract.md": CONTRACT_TMPL.format(entry_point=ep),
        f"templates/{tid}/tests_visible/test_visible.py": vis_src,
        f"templates/{tid}/run_tests.sh": RUN_TESTS_SH,
        f"hidden/{tid}/test_hidden.py": hid_src,
    }


def _bank_records() -> dict[str, dict]:
    raw = open(BANK_PATH, "rb").read()
    got = _sha256_bytes(raw)
    if got != BANK_SHA256:
        raise SystemExit(f"題庫 sha256 不符：got {got} want {BANK_SHA256}。停。")
    return {json.loads(l)["task_id"]: json.loads(l)
            for l in raw.decode("utf-8").splitlines() if l.strip()}


def build(check_only: bool = False) -> int:
    sel = select()
    recs = _bank_records()
    layers = {"A_high_divergence": sel["layer_a"], "B_random": sel["layer_b"]}

    files: dict[str, str] = {}
    tasks_meta: dict[str, dict] = {}
    for layer_name, tids in layers.items():
        for tid in tids:
            rec = recs[tid]
            rendered = render_task(rec)
            files.update(rendered)
            p = sel["per_task"][tid]
            tmpl_bytes = sum(len(v.encode("utf-8"))
                             for k, v in rendered.items() if k.startswith("templates/"))
            if tmpl_bytes > TEMPLATE_BYTES_SANITY_MAX:
                raise SystemExit(
                    f"{tid} 的樣板 {tmpl_bytes} B 超過理智上界 "
                    f"{TEMPLATE_BYTES_SANITY_MAX} B——要人來看，不默默通過。停。")
            leak = [k for k in rendered if k.startswith("templates/")
                    and "hidden" in k.lower()]
            if leak:
                raise SystemExit(f"{tid} 的樣板路徑出現 hidden 字樣：{leak}。停。")
            any_pass = any(v for stratum in p["arms"].values() for v in stratum.values())
            tasks_meta[tid] = {
                "task_id": tid,
                "layer": layer_name,
                "difficulty": rec["difficulty"],
                "platform": rec["platform"],
                "contest_date": rec["contest_date"],
                "entry_point": rec["entry_point"],
                "n_visible_cases": len(rec["visible_tests"]),
                "n_hidden_cases_full": len(rec["visible_tests"]) + len(rec["hidden_tests"]),
                "n_hidden_total_upstream": rec["n_hidden_total"],
                "prompt_sha256": _sha256_bytes(rec["prompt"].encode("utf-8")),
                "template_bytes": tmpl_bytes,
                "divergence": {"D_net": p["D_net"], "D_plus": p["D_plus"],
                               "D_minus": p["D_minus"],
                               "off_pass_count": p["off_pass_count"]},
                "archived_meets_demand": p["arms"],
                "archived_accepted": p["accepted"],
                "any_arm_passed_hidden": any_pass,
                "sha256": {k.split("/", 2)[2] if k.startswith("templates/") else k:
                           _sha256_bytes(v.encode("utf-8"))
                           for k, v in sorted(rendered.items())},
            }

    manifest = {
        "run_id": "r534",
        "generated_by": "ops/gain/r534/build_bank.py",
        "selection_rule": RULE_TEXT,
        "selection_rule_sha256": _sha256_bytes(RULE_TEXT.encode("utf-8")),
        "bank": {"path": sel["bank_path"], "sha256": BANK_SHA256, "n": sel["bank_n"],
                 "known_bad_excluded": sel["known_bad_excluded"],
                 "eligible_n": sel["eligible_n"]},
        "evidence_sources": sel["evidence_sources"],
        "strata": sel["strata"],
        "layer_b_seed": LAYER_B_SEED,
        "layers": {k: sorted(v) for k, v in layers.items()},
        "layer_order": {k: list(v) for k, v in layers.items()},
        "n_tasks": sum(len(v) for v in layers.values()),
        "trees": {
            "workspace_template": "ops/gain/r534/templates/<task_id>/",
            "scoring_only": "ops/gain/r534/hidden/<task_id>/",
            "red_line": "hidden/ 不是工作區的子目錄，永遠不複製進工作區；"
                        "任何把隱藏測資或其失敗訊息回饋給模型的路徑都作廢這一批資料。",
        },
        "comparator": "vacant_network/codebench.py::_lcb_check_code 的 __aeq（逐行同義，"
                      "渲染成每個測試檔裡的 _aeq）",
        "hidden_case_composition": "visible_tests + hidden_tests（超集），"
                                   "與 LiveCodeBenchLoader.hidden_check 同一組 ⇒ "
                                   "分子與 r460／r532 的 meets_demand 可比",
        "scoring": {
            "primary_numerator": "gain_run.meets_demand(code, "
                                 "codebench._lcb_check_code(entry_point, "
                                 "visible_tests + hidden_tests), entry_point=entry_point)",
            "why": "主指標走既有那條沙箱路徑，R534 的分子才與 r460／r532 是同一把尺。",
            "rendered_hidden_file_is": "同一組 case、同一個比對器，但**沒有沙箱的 AST "
                                       "政策**（vacant_network/checks.py 的 _FORBIDDEN_ATTRS 連 "
                                       "list.remove 都擋、_GAIN_ALLOWED_IMPORTS 擋 typing "
                                       "以外的第三方 import）⇒ 對用到那些東西的碼，"
                                       "渲染檔比既有判準**寬**。ops/gain/r534/gauge_bank.py "
                                       "的實測：政策收得下的 100 份已歸檔候選碼上兩條路徑 "
                                       "100/100 一致；另有 12 份被政策擋掉，那 12 份上兩條"
                                       "路徑本來就會不同（例：lcb_3783 的 list.remove）。",
            "rule": "兩條路徑的數字不可混報：報表要指名每個數字走的是哪一條。",
        },
        "honesty_bounds": [
            "LCB 沒有 canonical solution ⇒ 這 20 題沒有參考解正控制；"
            "r530 的雙向量具（參考解全過／壞樁全擋）在這裡做不到。",
            "any_arm_passed_hidden=false 的題，歸檔資料裡沒有任何臂通過過 ⇒ "
            "我們沒有證據證明一個正確解會被判過。",
            "A 層是條件在過去結果上挑的 ⇒ 差值上偏；B 層抽的是扣掉 A 層後的剩餘 ⇒ "
            "差值偏保守。兩層分開報，不合併。",
            "每題每臂在每個歸檔層只有一個觀測，D_net 是帶雜訊的排序鍵。",
        ],
        "tasks": tasks_meta,
    }

    if check_only:
        if not os.path.exists(MANIFEST):
            print("FAIL: bank_manifest.json 不存在", file=sys.stderr)
            return 1
        on_disk = json.load(open(MANIFEST, encoding="utf-8"))
        bad = []
        if on_disk.get("layers") != manifest["layers"]:
            bad.append("layers 與重新選題的結果不同")
        if on_disk.get("selection_rule_sha256") != manifest["selection_rule_sha256"]:
            bad.append("selection_rule 變了")
        for rel, content in sorted(files.items()):
            path = os.path.join(HERE, rel)
            if not os.path.exists(path):
                bad.append(f"缺檔 {rel}")
                continue
            got = _sha256_bytes(open(path, "rb").read())
            want = _sha256_bytes(content.encode("utf-8"))
            if got != want:
                bad.append(f"漂了 {rel}: on-disk {got[:12]} vs rendered {want[:12]}")
        for rel in sorted(files):
            tid = rel.split("/")[1]
            key = rel.split("/", 2)[2] if rel.startswith("templates/") else rel
            rec_sha = on_disk.get("tasks", {}).get(tid, {}).get("sha256", {}).get(key)
            if rec_sha != _sha256_bytes(files[rel].encode("utf-8")):
                bad.append(f"manifest 的 sha 對不上 {rel}")
        if bad:
            for b in bad:
                print("FAIL:", b, file=sys.stderr)
            return 1
        print(f"OK: {manifest['n_tasks']} 題、{len(files)} 個檔案與 manifest 一致")
        print(f"manifest sha256 = {_sha256_bytes(open(MANIFEST, 'rb').read())}")
        return 0

    for root in (TEMPLATES, HIDDEN):
        if os.path.isdir(root):
            shutil.rmtree(root)
    for rel, content in sorted(files.items()):
        path = os.path.join(HERE, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)
        if rel.endswith(".sh"):
            os.chmod(path, 0o755)
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    digest = _sha256_bytes(open(MANIFEST, "rb").read())
    with open(os.path.join(HERE, "bank_manifest.sha256"), "w", encoding="utf-8") as fh:
        fh.write(f"{digest}  bank_manifest.json\n")
    print(f"寫出 {len(files)} 個檔案（{manifest['n_tasks']} 題）")
    print(f"manifest sha256 = {digest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="R534 題庫渲染（確定性）")
    ap.add_argument("--check", action="store_true",
                    help="只驗磁碟上的檔案與 manifest 對不對得上，不寫任何東西")
    args = ap.parse_args(argv)
    return build(check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
