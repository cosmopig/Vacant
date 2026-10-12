#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""五組既有題庫 → agent 工作區任務（Colab 上 pi agent A/B 用）。零模型呼叫。

這支在架構裡承重什麼
--------------------
A 臂（只有 pi）與 C 臂（pi＋`vacant install`）要在**同一組題目**上比，題目的形狀
必須是「一個工作區」：agent 看得到題目、介面契約、可見驗收，而且自己跑得動可見驗收；
計分用的隱藏驗收住在**另一棵樹**，工作區裡結構上沒有那條路徑。R534
（`ops/gain/r534/BANK_README.md`）已經把 LCB v2 的 20 題做成這個形狀；這支把**五組
全部**（LCB v1／v2／v3、MBPP+、HumanEval+）用同一個形狀渲染出來。

    <tree>/templates/<dir>/                 <tree>/hidden/<dir>/
        goal.md          題目原文                test_hidden.py   可見 ∪ 隱藏（計分用）
        contract.md      solution.py／函式名／呼叫方式／判等規則／怎麼跑可見檢查
        tests_visible/test_visible.py   check_*()（可見驗收＝出貨閘門）
        run_tests.sh     R534 的 RUN_TESTS_SH 逐字（＝r530 的 export_bank.py）

可見／隱藏怎麼切：**一律沿用 repo 既有的 V/GT 定義，這支沒有發明任何新切法**
----------------------------------------------------------------------------
- LCB：題庫檔的 `visible_tests`／`visible_tests + hidden_tests`
  （`vacant_network/codebench.py` 第 1136–1145 行 `LiveCodeBenchLoader.iter_tasks` 的
  `visible_check`／`hidden_check`）。
- MBPP+：`base_input`／`base_input + plus_input`
  （`codebench.py` 第 650–651 行正規化、第 686–695 行 `EvalPlusMBPPLoader` 的兩個 check）。
- HumanEval+：同上的 base／base＋plus
  （`codebench.py` 第 881–882 行、第 908–918 行 `EvalPlusHumanEvalLoader`）。
G 實驗（`ops/gain/gain_run.py::load_tasks` 第 144–182 行）與 R529／R532／R534 走的都是這三顆
loader，所以這裡的可見檔＝它們的 `visible_check` 那組輸入、隱藏檔＝`hidden_check` 那組輸入。

三個「照抄不動」的決定（與 R534 同一套理由）
------------------------------------------
1. **goal.md ＝ loader 吐給 G 實驗的 `prompt` 逐位元組**。LCB＝題庫 `prompt` 欄；
   MBPP+＝官方 prompt ＋ G 實驗用的 `expose_contract=True` 那段「Formal input contract」
   （`gain_run.py` 第 145 行；只有輸入前提、沒有期望輸出）；HumanEval+＝官方 prompt
   （`expose_contract=False`，`gain_run.py` 第 148–153 行）。
2. **判等規則逐行沿用既有判準**：LCB 用 `_lcb_check_code` 的 `__aeq`（R534 的 `AEQ_SRC`，
   這裡直接 import，不重寫）；MBPP+／HumanEval+ 用 `_check_code` 的 `__aeq`
   （`codebench.py` 第 477–524 行：set 等價名單、regex 真值、`atol`、list/tuple 遞迴）。
3. **隱藏檔＝可見 ∪ 隱藏**（超集），與 loader 的 `hidden_check` 同一組輸入。

MBPP+／HumanEval+ 跟既有判準**唯一**的形狀差異（量具要證明它不改變判決）
-----------------------------------------------------------------------
既有的 `_check_code` 把 canonical 解**內嵌**進檢查碼、在檢查當下算期望值。那個形狀不能
原樣放進工作區——可見檔裡內嵌 canonical 等於把參考解交給 agent。所以這裡在**建庫時**
跑 canonical、把期望值寫成字面值（R534 的 LCB 題本來就是字面值）。為了讓「預先算好」
跟「當場算」是同一個數：

- 輸入先轉成字面值再 `eval` 回來餵 canonical（＝`_check_code` 的 `__canon(*<字面值>)`）；
- 期望值轉成字面值後 `eval` 回來，逐型別、逐元素比對要**完全相同**（nan、-0.0、
  tuple/list 都分得出來），做不到就具名排除（`expected_not_literal`），不猜；
- canonical 在兩個不同的 `PYTHONHASHSEED` 底下各算一次，兩次在該題自己的判等規則下
  不相等 ⇒ 具名排除（`canonical_nondeterministic`）；
- canonical 回 `re.Match`（只在 regex 題）⇒ 寫成 `_MatchStandIn()`：真值為真、`==` 只認自己，
  與 `re.Match` 在 `__aeq` 裡的行為逐條相同（`re.Match.__eq__` 就是比身分）；
- 超過 4000 位的整數寫成十六進位字面值（Python 3.11+ 編譯十進位大整數字面值有 4300 位上限）。

私有資料紀律（不可省）
----------------------
MBPP+／HumanEval+ 的官方包在本 repo 是**私有、不轉散布、不進版控**（`.gitignore` 的
`.vacant-private/`、`.github/workflows/ci.yml` 的守門、`runs/INDEX.md` §七），而 GitHub
上這個 repo 是公開的。所以這兩組的 `templates/`／`hidden/` 只渲染到
`<private_root>/colab_banks_20260927/<bank>/`（預設 `<repo>/.vacant-private/`，已被 gitignore）；
repo 裡只放 `bank_manifest.json`（題號、條數、sha256、量具結果——**題目與測資一個位元組
都沒有**）。LCB 三組照 R534 的前例整棵進版控（題庫檔本身已在 `ops/gain/data/`）。

用法
----
    .venv/bin/python ops/vacantrun/colab_banks_20260927/build_banks.py render --bank all
    .venv/bin/python ops/vacantrun/colab_banks_20260927/build_banks.py check  --bank all
    # 私有包不在 <repo>/.vacant-private 時：--private-root /path/to/.vacant-private
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import pathlib
import re
import secrets
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))

from ops.gain.r534.build_bank import (  # noqa: E402
    AEQ_SRC as LCB_AEQ_SRC, CONTRACT_TMPL as LCB_CONTRACT_TMPL, RUN_TESTS_SH,
    _render_cases as _lcb_render_cases)

GENERATOR = "ops/vacantrun/colab_banks_20260927/build_banks.py"
RUN_ID = "colab_banks_20260927"

#: 五組題庫。`gain_bank` 是 `gain_run.py --bank` 的名字（出處對照用）。
BANKS: dict[str, dict] = {
    "lcb_v1": {"kind": "lcb", "version": "v1", "gain_bank": "lcb", "private": False},
    "lcb_v2": {"kind": "lcb", "version": "v2", "gain_bank": "lcb2", "private": False},
    "lcb_v3": {"kind": "lcb", "version": "v3", "gain_bank": "lcb3", "private": False},
    "mbppplus": {"kind": "mbpp", "gain_bank": "evalplus", "private": True},
    "humanevalplus": {"kind": "he", "gain_bank": "humanevalplus", "private": True},
}

#: V/GT 切法的出處（逐字寫進 manifest）。行號以本 commit 的 codebench.py／gain_run.py 為準。
SPLIT_SOURCE = {
    "lcb": ("visible＝題庫 `visible_tests`；隱藏檔＝`visible_tests + hidden_tests`。"
            "出處 vacant_network/codebench.py:1125-1145（LiveCodeBenchLoader.iter_tasks 的 "
            "visible_check／hidden_check）；R534 同一條（ops/gain/r534/build_bank.py::render_task）。"),
    "mbpp": ("visible＝`base_input`；隱藏檔＝`base_input + plus_input`（EvalPlus 官方 base／plus）。"
             "出處 vacant_network/codebench.py:650-651（_norm_inputs 型別還原）＋686-695"
             "（EvalPlusMBPPLoader 的 visible_check／hidden_check）；G 實驗 ops/gain/gain_run.py:145。"),
    "he": ("visible＝`base_input`；隱藏檔＝`base_input + plus_input`（EvalPlus 官方 base／plus）。"
           "出處 vacant_network/codebench.py:881-882（_he_norm_inputs）＋908-918"
           "（EvalPlusHumanEvalLoader 的 visible_check／hidden_check）；G 實驗 ops/gain/gain_run.py:148-153。"),
}

#: LCB 已知壞題的理由（名單本身的單一真相來源是 check_bank_precision.KNOWN_BAD，
#: 這裡只補理由；兩邊對不上就停，不准各說各話）。
LCB_KNOWN_BAD_REASON = {
    "lcb_3613": ("known_bad: dataset 的 expected 只存到 5 位小數（11/7 存成 1.57143，誤差 1.429e-06），"
                 "判準容差 1e-6 ⇒ 精確解也必敗。出處 decisions/DECISION_20260903_R440T_LCB_UNPASSABLE_TASKS.md"
                 "、ops/gain/check_bank_precision.py:93-94 KNOWN_BAD"),
    "lcb_3763": ("known_bad: separateSquares 的 expected 只存到 5 位小數，與容差 1e-6 矛盾 ⇒ 精確解也會被判錯。"
                 "出處 decisions/DECISION_20260903_R440T_LCB_UNPASSABLE_TASKS.md、DECISION_20260901_R441、"
                 "ops/gain/check_bank_precision.py:93-94 KNOWN_BAD"),
}

#: 樣板大小的理智上界（沿用 R534 的 TEMPLATE_BYTES_SANITY_MAX）。超過代表可見字面值大得
#: 不像話，塞進工作區會吃掉 agent 的脈絡——要人來看，不默默通過。
TEMPLATE_BYTES_SANITY_MAX = 100_000

#: 期望值字面值：超過這個位數的整數改寫成十六進位（見模組 docstring）。
BIG_INT_DIGITS = 4000

#: canonical 求期望值的子行程逾時（建庫時；與閘門的逾時無關）。
CANON_TIMEOUT_S = 180
HASH_SEEDS = ("0", "20260927")


# ─────────────────────────────────────────────────────────────────────────────
# 共用
# ─────────────────────────────────────────────────────────────────────────────

def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def default_private_root() -> pathlib.Path:
    return pathlib.Path(os.environ.get("VACANT_PRIVATE_ROOT") or (REPO / ".vacant-private"))


def tree_root(bank: str, private_root: pathlib.Path) -> pathlib.Path:
    """templates/hidden 兩棵樹住哪裡：LCB 在 repo 裡，EvalPlus 兩組在私有目錄。"""
    if BANKS[bank]["private"]:
        return private_root / RUN_ID / bank
    return HERE / bank


def dir_name(task_id: str) -> str:
    """目錄名：task_id 的 `/` 換成 `_`（`mbppplus_Mbpp/2` → `mbppplus_Mbpp_2`）。"""
    return task_id.replace("/", "_")


# ─────────────────────────────────────────────────────────────────────────────
# 字面值（父子行程共用同一份原始碼：LIT_SRC 在兩邊都是 exec 進來的）
# ─────────────────────────────────────────────────────────────────────────────

LIT_SRC = r'''
import collections as _collections, math as _m, re as _re

class _MatchStandIn:
    """代表參考解回傳的一個 re.Match：真值為真，`==` 只認自己（同 re.Match）。"""
    def __bool__(self):
        return True
    def __eq__(self, other):
        return self is other
    def __ne__(self, other):
        return self is not other
    __hash__ = object.__hash__
    def __repr__(self):
        return "<re.Match object>"

def lit(v, regex=False, big=BIG_INT_DIGITS):
    t = type(v)
    if v is None or t is bool:
        return repr(v)
    if t is int:
        if v.bit_length() > big * 3:
            return ("-" if v < 0 else "") + hex(abs(v))
        return repr(v)
    if t is float:
        if _m.isnan(v):
            return "float('nan')"
        if _m.isinf(v):
            return "float('-inf')" if v < 0 else "float('inf')"
        return repr(v)
    if t is complex:
        return "complex(%s, %s)" % (lit(v.real), lit(v.imag))
    if t is str or t is bytes:
        return repr(v)
    if t is list:
        return "[" + ", ".join(lit(x, regex, big) for x in v) + "]"
    if t is tuple:
        body = ", ".join(lit(x, regex, big) for x in v)
        return "(" + body + ("," if len(v) == 1 else "") + ")"
    if t is dict:
        return "{" + ", ".join("%s: %s" % (lit(k, regex, big), lit(x, regex, big))
                               for k, x in v.items()) + "}"
    if t is _collections.Counter:
        # Counter 的 == 語意與 dict 不同（3.10+ 視缺項為 0），所以照原型別寫回去，不降成 dict。
        return "collections.Counter({" + ", ".join(
            "%s: %s" % (lit(k, regex, big), lit(x, regex, big)) for k, x in v.items()) + "})"
    if t is set:
        return "set()" if not v else "{" + ", ".join(lit(x, regex, big) for x in v) + "}"
    if t is frozenset:
        return "frozenset()" if not v else "frozenset({" + ", ".join(lit(x, regex, big) for x in v) + "})"
    if regex and isinstance(v, _re.Match):
        return "_MatchStandIn()"
    raise TypeError("unliteralizable %s.%s" % (t.__module__, t.__qualname__))

def same(a, b):
    """逐型別、逐元素完全相同（nan 等於 nan、-0.0 不等於 0.0、list 不等於 tuple）。"""
    if isinstance(b, _re.Match) and type(a) is _MatchStandIn:
        return True
    if type(a) is not type(b):
        return False
    if type(a) is float:
        if _m.isnan(a) or _m.isnan(b):
            return _m.isnan(a) and _m.isnan(b)
        return a == b and _m.copysign(1.0, a) == _m.copysign(1.0, b)
    if type(a) is complex:
        return same(a.real, b.real) and same(a.imag, b.imag)
    if type(a) in (list, tuple):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if type(a) in (dict, _collections.Counter):
        if len(a) != len(b):
            return False
        for k in a:
            if k not in b or not same(a[k], b[k]):
                return False
        return True
    return a == b
'''.replace("BIG_INT_DIGITS", str(BIG_INT_DIGITS))

_LIT_NS: dict = {}
exec(LIT_SRC, _LIT_NS)  # noqa: S102 - 自己的原始碼，父子兩邊同一份
lit = _LIT_NS["lit"]
same = _LIT_NS["same"]

#: 子行程：exec canonical、對每個輸入字面值求期望值、轉字面值、驗來回。stdin 收一個 JSON job。
CHILD_SRC = r'''
import collections, contextlib, io, json, sys, time
sys.set_int_max_str_digits(0)
job = json.loads(sys.stdin.read())
REAL = sys.stdout
NS = {}
exec(job["lit_src"], NS)
lit, same, Stand = NS["lit"], NS["same"], NS["_MatchStandIn"]
out = {"wants": [], "error": None, "secs": None}
t0 = time.perf_counter()
try:
    cns = {}
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        exec(compile(job["canonical"], "<canonical>", "exec"), cns)
    canon = cns[job["entry_point"]]
    for i, a in enumerate(job["inputs"]):
        args = eval(a, {"__builtins__": __builtins__})
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                v = canon(*args)
        except BaseException as e:
            out["error"] = "canonical_raises: case %d %s: %s" % (i, type(e).__name__, str(e)[:200])
            break
        try:
            s = lit(v, job["regex"])
        except (TypeError, ValueError) as e:
            out["error"] = "expected_not_literal: case %d %s" % (i, e)
            break
        back = eval(s, {"__builtins__": __builtins__, "_MatchStandIn": Stand,
                        "collections": collections})
        if not same(back, v):
            out["error"] = "expected_not_literal: case %d round-trip mismatch (%s)" % (i, type(v).__name__)
            break
        out["wants"].append(s)
except BaseException as e:
    out["error"] = "canonical_load: %s: %s" % (type(e).__name__, str(e)[:200])
out["secs"] = round(time.perf_counter() - t0, 3)
REAL.write(job["nonce"] + json.dumps(out) + "\n")
REAL.flush()
'''


def _canon_expected(canonical: str, entry_point: str, inputs: list[str], regex: bool,
                    hash_seed: str) -> dict:
    """在子行程裡跑 canonical 求期望值字面值（逾時＝錯誤，照實記）。"""
    nonce = "COLABBANK:" + secrets.token_hex(8) + ":"
    job = {"canonical": canonical, "entry_point": entry_point, "inputs": inputs,
           "regex": regex, "lit_src": LIT_SRC, "nonce": nonce}
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONHASHSEED": hash_seed,
           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
    try:
        proc = subprocess.run([sys.executable, "-c", CHILD_SRC], input=json.dumps(job),
                              capture_output=True, text=True, timeout=CANON_TIMEOUT_S, env=env)
    except subprocess.TimeoutExpired:
        return {"wants": [], "error": f"canonical_timeout: > {CANON_TIMEOUT_S}s（建庫子行程）", "secs": None}
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(nonce):
            return json.loads(line[len(nonce):])
    return {"wants": [], "error": f"canonical_child_crashed rc={proc.returncode}: "
                                  f"{(proc.stderr or '')[-300:]}", "secs": None}


# ─────────────────────────────────────────────────────────────────────────────
# 載入五組來源（全部走 codebench 的 fail-closed loader：sha256／題數／schema）
# ─────────────────────────────────────────────────────────────────────────────

def _set_private_env(private_root: pathlib.Path) -> None:
    """loader 只吃環境變數換**位置**、釘值不變（codebench 的 fail-closed 紀律）。"""
    os.environ["VACANT_EVALPLUS_PATH"] = str(private_root / "evalplus" / "MbppPlus-v0.2.0.jsonl.gz")
    os.environ["VACANT_HUMANEVALPLUS_PATH"] = str(
        private_root / "evalplus" / "HumanEvalPlus-v0.1.10.jsonl.gz")


def load_source(bank: str, private_root: pathlib.Path) -> dict:
    """回 `{"source": {...}, "records": [...], "tasks": {task_id: 投影}, "excluded": {...}}`。"""
    from vacant_network import codebench as cb
    spec = BANKS[bank]
    if spec["kind"] == "lcb":
        from ops.gain.check_bank_precision import KNOWN_BAD
        ld = cb.LiveCodeBenchLoader(version=spec["version"])
        bank_spec = cb.LCB_BANKS[spec["version"]]
        known_bad = set(KNOWN_BAD.get(spec["gain_bank"], set()))
        missing = known_bad - set(LCB_KNOWN_BAD_REASON)
        if missing:
            raise SystemExit(f"KNOWN_BAD 有 {sorted(missing)} 但這支沒有對應理由——停，先補理由。")
        excluded = {t: LCB_KNOWN_BAD_REASON[t] for t in sorted(known_bad)}
        source = {"path": bank_spec["path"], "sha256": ld.expected_sha256,
                  "n_upstream": len(ld._records), "pinned_in": "vacant_network/codebench.py LCB_BANKS"}
        tasks = {t["task_id"]: t for t in ld.iter_tasks("colab-banks")}
        recs = {r["task_id"]: r for r in ld._records}
    elif spec["kind"] == "mbpp":
        _set_private_env(private_root)
        from ops.gain.gain_run import GAIN_EVALPLUS_RESOURCE_EXCLUSIONS as EXC
        ld = cb.EvalPlusMBPPLoader(expose_contract=True)
        excluded = {t: ("gain_run_resource_exclusion: " + why + "（沿用 ops/gain/gain_run.py:54-62 "
                        "GAIN_EVALPLUS_RESOURCE_EXCLUSIONS，G 實驗分母 371）")
                    for t, why in sorted(EXC.items())}
        source = {"path": ".vacant-private/evalplus/MbppPlus-v0.2.0.jsonl.gz", "sha256": ld.expected_sha256,
                  "n_upstream": len(ld._records), "pinned_in": "vacant_network/codebench.py EVALPLUS_MBPP_PLUS_SHA256",
                  "private": True}
        tasks = {t["task_id"]: t for t in ld.iter_tasks("colab-banks")}
        recs = {"mbppplus_" + r["task_id"]: r for r in ld._records}
    else:
        _set_private_env(private_root)
        from ops.gain.gain_run import GAIN_HUMANEVAL_EXCLUSIONS as EXC
        ld = cb.EvalPlusHumanEvalLoader()
        excluded = {t: ("gain_run_humaneval_exclusion: " + why + "（沿用 ops/gain/gain_run.py:82-91 "
                        "GAIN_HUMANEVAL_EXCLUSIONS，分母 156 不是 164）")
                    for t, why in sorted(EXC.items())}
        source = {"path": ".vacant-private/evalplus/HumanEvalPlus-v0.1.10.jsonl.gz",
                  "sha256": ld.expected_sha256, "n_upstream": len(ld._records),
                  "pinned_in": "vacant_network/codebench.py EVALPLUS_HUMANEVAL_PLUS_SHA256", "private": True}
        tasks = {t["task_id"]: t for t in ld.iter_tasks("colab-banks")}
        recs = {"humanevalplus_" + r["task_id"]: r for r in ld._records}
    unknown = set(excluded) - set(tasks)
    if unknown:
        raise SystemExit(f"{bank}：排除名單裡有題庫沒有的 task_id {sorted(unknown)}。停。")
    return {"source": source, "tasks": tasks, "records": recs, "excluded": excluded, "loader": ld}


def _task_order(bank: str, tids) -> list[str]:
    """確定性順序：題號數字遞增（`HumanEval/2` 排在 `/10` 前面）。"""
    def key(t: str):
        m = re.search(r"(\d+)$", t)
        return (int(m.group(1)) if m else 10**9, t)
    return sorted(tids, key=key)


# ─────────────────────────────────────────────────────────────────────────────
# LCB 渲染（R534 的形狀；判等與 case 寫法直接 import R534 那一份）
# ─────────────────────────────────────────────────────────────────────────────

LCB_VISIBLE_HEADER = '''\
"""Visible checks for {task_id} -- these ship with the task and can be run.

Rendered from {bank_path} (sha256 {bank_sha_short}...) by
{generator}. The literal (args, expected) pairs are the bank's
`visible_tests` field, byte for byte.
"""

import solution

'''

LCB_HIDDEN_HEADER = '''\
"""Scoring checks for {task_id} -- NOT part of any workspace.

⚠ 計分用的 GT。住在 hidden/ 這棵**另外的樹**，永遠不複製進 agent 的工作區；
  任何把它的內容（含失敗訊息）回饋給模型的路徑都作廢那一批資料。

case 組成 ＝ 題庫的 `visible_tests` ＋ `hidden_tests`（超集），與
vacant_network/codebench.py::LiveCodeBenchLoader 的 `hidden_check` 同一組（{bank_path}）。
"""

import solution

'''


def render_lcb(bank: str, src: dict) -> tuple[dict[str, str], dict]:
    recs = src["records"]
    files: dict[str, str] = {}
    meta: dict[str, dict] = {}
    bank_path, bank_sha = src["source"]["path"], src["source"]["sha256"]
    for tid in _task_order(bank, recs):
        if tid in src["excluded"]:
            continue
        rec = recs[tid]
        ep = rec["entry_point"]
        visible, full = rec["visible_tests"], rec["visible_tests"] + rec["hidden_tests"]
        vis = (LCB_VISIBLE_HEADER.format(task_id=tid, bank_path=bank_path, bank_sha_short=bank_sha[:12],
                                         generator=GENERATOR)
               + LCB_AEQ_SRC + "\n\n" + _lcb_render_cases(ep, visible, "check_visible"))
        hid = (LCB_HIDDEN_HEADER.format(task_id=tid, bank_path=bank_path)
               + LCB_AEQ_SRC + "\n\n" + _lcb_render_cases(ep, full, "check_case"))
        d = dir_name(tid)
        tf = {
            f"templates/{d}/goal.md": rec["prompt"],
            f"templates/{d}/contract.md": LCB_CONTRACT_TMPL.format(entry_point=ep),
            f"templates/{d}/tests_visible/test_visible.py": vis,
            f"templates/{d}/run_tests.sh": RUN_TESTS_SH,
            f"hidden/{d}/test_hidden.py": hid,
        }
        files.update(tf)
        meta[tid] = {
            "task_id": tid, "dir": d, "entry_point": ep,
            "difficulty": rec["difficulty"], "platform": rec["platform"],
            "contest_date": rec["contest_date"], "source_file": rec.get("source_file"),
            "n_visible": len(visible), "n_hidden_file": len(full),
            "n_hidden_only": len(rec["hidden_tests"]),
            "n_hidden_total_upstream": rec.get("n_hidden_total"),
            "prompt_sha256": sha256_text(rec["prompt"]),
            "comparator": {"kind": "lcb_aeq", "tol": 1e-6},
        }
    return files, meta


# ─────────────────────────────────────────────────────────────────────────────
# MBPP+／HumanEval+ 渲染
# ─────────────────────────────────────────────────────────────────────────────

#: `_check_code` 的兩個名單／判別式，逐字取自 codebench.py 第 482–486 行。
SET_EQUIVALENT = frozenset({
    "similar_elements", "find_char_long", "common_in_nested_lists",
    "extract_singly", "larg_nnum", "intersection_array", "find_dissimilar", "Diff",
})


def _flags(canonical: str, entry_point: str) -> dict:
    return {"regex_predicate": ("re.search(" in canonical or "re.match(" in canonical),
            "set_equivalent": entry_point in SET_EQUIVALENT}


EP_AEQ_TMPL = '''\
import collections
import re as _re

_REGEX_PREDICATE = {regex!r}
_SET_EQUIVALENT = {seteq!r}
_ATOL = {atol!r}
{standin}

def _aeq(a, b, atol=_ATOL):
    """與 vacant_network/codebench.py::_check_code 的 __aeq 同一套判等（逐行對應）。"""
    if _SET_EQUIVALENT:
        try:
            return set(a) == set(b)
        except TypeError:
            return False
    if _REGEX_PREDICATE:
        allowed = (bool, type(None), _re.Match{standin_type})
        if isinstance(a, allowed) and isinstance(b, allowed):
            return bool(a) == bool(b)
    try:
        if a == b:
            return True
    except (TypeError, ValueError):
        pass
    if atol and (isinstance(a, float) or isinstance(b, float)):
        try:
            return abs(a - b) <= atol
        except TypeError:
            return False
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_aeq(x, y, atol) for x, y in zip(a, b))
    return a == b
'''

STANDIN_SRC = '''
class _MatchStandIn:
    """Stands for a re.Match returned by the reference solution: truthy, equal only to itself."""
    def __bool__(self):
        return True
    def __eq__(self, other):
        return self is other
    def __ne__(self, other):
        return self is not other
    __hash__ = object.__hash__
    def __repr__(self):
        return "<re.Match object>"
'''

EP_VISIBLE_HEADER = '''\
"""Visible checks for {dir} -- these ship with the task and can be run.

Rendered by {generator} from the {bank_label} package
(sha256 {sha_short}...). Each case is one of the task's base inputs; `want` is
the reference output for that input, written out as a literal.
"""

import solution

'''

EP_HIDDEN_HEADER = '''\
"""Scoring checks for {dir} -- NOT part of any workspace.

⚠ 計分用的 GT。住在 hidden/ 這棵**另外的樹**，永遠不複製進 agent 的工作區；
  任何把它的內容（含失敗訊息）回饋給模型的路徑都作廢那一批資料。
⚠ 來自私有、不轉散布的 {bank_label} 官方包：不進版控。

case 組成 ＝ base_input ＋ plus_input（超集），與 {loader} 的 `hidden_check`
同一組輸入；期望值＝canonical 在建庫時算出的字面值（逐型別來回驗過）。
"""

import solution

'''

EP_CONTRACT_TMPL = """\
# Contract

Write your answer in `solution.py` at the root of this workspace.

- Define a top-level function named `{entry_point}`. Not a method, not a class.{he_line}
- It is called positionally: `{entry_point}(*args)`, with the arguments in the
  order of its parameters.
- It must **return** the answer. Printing is not returning; anything written to
  stdout is ignored.
- Standard library only. No network, no file system, no installed packages.
- A returned value counts as correct when it compares equal to the expected value
  under this rule:
{rule}

The checks that ship with this task are in `tests_visible/`. Run them with:

    sh run_tests.sh

Each failing check prints `args=... got=... want=...`.
"""

HE_LINE = ("\n  `goal.md` gives its signature and docstring. `solution.py` must contain the\n"
           "  whole function, plus any imports and helper functions from `goal.md` that it uses.")


def _rule_text(flags: dict, atol) -> str:
    if flags["set_equivalent"]:
        return ("  the result is compared as a set: `set(result) == set(expected)`, so order\n"
                "  and repeated elements do not matter. A result that cannot be turned into a\n"
                "  set is wrong.")
    out = []
    if flags["regex_predicate"]:
        out.append("  if both the result and the expected value are `True`, `False`, `None` or a\n"
                   "  `re.Match` object, only their truth values are compared;")
    out.append("  otherwise plain `==` first;" if flags["regex_predicate"] else "  plain `==` first;")
    if atol:
        out.append(f"  if either value is a float, they are equal when they differ by at most {atol!r};")
    out.append("  lists and tuples are compared element by element, recursively, and must have\n"
               "  the same length (a list can equal a tuple).")
    return "\n".join(out)


def _ep_render_cases(entry_point: str, cases: list[tuple[str, str]], prefix: str) -> str:
    """一條 case 一個 `check_*()`；args／want 都是字面值（每次呼叫都重新建出物件）。"""
    width = max(2, len(str(len(cases))))
    out = []
    for i, (a, w) in enumerate(cases, 1):
        out.append(
            f"def {prefix}_{i:0{width}d}():\n"
            f"    args = {a}\n"
            f"    want = {w}\n"
            f"    got = solution.{entry_point}(*args)\n"
            f"    assert _aeq(got, want), \"args=%r got=%r want=%r\" % (args, got, want)\n"
        )
    return "\n\n".join(out) + "\n"


def _ep_one(bank: str, tid: str, task: dict, rec: dict, kind: str) -> dict:
    """單題：求期望值（兩個 hash seed）＋渲染。回 {"files", "meta"} 或 {"excluded": 理由}。"""
    from vacant_network import codebench as cb
    ep = rec["entry_point"]
    if kind == "mbpp":
        canonical = rec["canonical_solution"]
        base = cb._norm_inputs(rec["base_input"], rec["task_id"])
        plus = cb._norm_inputs(rec["plus_input"], rec["task_id"])
    else:
        canonical = cb.EvalPlusHumanEvalLoader.canonical_source(rec)
        base = cb._he_norm_inputs(rec["base_input"])
        plus = cb._he_norm_inputs(rec["plus_input"])
    atol = rec.get("atol")
    atol = float(atol) if isinstance(atol, (int, float)) else None
    flags = _flags(canonical, ep)
    sys.set_int_max_str_digits(0)
    # 輸入的「值」＝既有判準實際餵進去的那個值：`_check_code` 把 `_python_expr(inp)` 寫進碼裡
    # 再執行，所以候選與 canonical 拿到的是 `eval(_python_expr(inp))`，不是官方原始值。
    # 兩者在 complex 的 -0.0 上會不同（Mbpp/124、/252：repr 的 `(-0-1j)` eval 回來虛部符號還在、
    # 實部的 -0 變成 +0）。這裡**跟既有判準走**，差幾條照實記在 meta。
    inputs: list[str] = []
    n_gain_literal_differs = 0
    for raw in base + plus:
        try:
            val = eval(cb._python_expr(raw))  # noqa: S307 - codebench 自己產生的字面值
        except Exception as e:  # noqa: BLE001
            return {"excluded": f"gain_input_literal_unevaluable: _python_expr 的輸入字面值 eval 失敗"
                                f"（{type(e).__name__}）⇒ 既有判準在這題本來就跑不起來"}
        s = lit(val)
        if not same(eval(s, {"collections": __import__("collections")}), val):  # noqa: S307
            return {"excluded": "input_not_literal: 輸入值寫不回等值的字面值"}
        if not same(val, raw):
            n_gain_literal_differs += 1
        inputs.append(s)
    runs =[_canon_expected(canonical, ep, inputs, flags["regex_predicate"], hs) for hs in HASH_SEEDS]
    for r in runs:
        if r["error"]:
            return {"excluded": r["error"], "canon_secs": r["secs"]}
    w0, w1 = runs[0]["wants"], runs[1]["wants"]
    if w0 != w1:
        ns: dict = {}
        exec(EP_AEQ_TMPL.format(regex=flags["regex_predicate"], seteq=flags["set_equivalent"],
                                atol=atol, standin=STANDIN_SRC, standin_type=", _MatchStandIn"), ns)
        env = {"_MatchStandIn": ns["_MatchStandIn"], "collections": __import__("collections")}
        for i, (a, b) in enumerate(zip(w0, w1)):
            if a != b:
                va, vb = eval(a, dict(env)), eval(b, dict(env))  # noqa: S307
                if not (ns["_aeq"](va, vb) and ns["_aeq"](vb, va)):
                    return {"excluded": f"canonical_nondeterministic: case {i} 在兩個 PYTHONHASHSEED 下"
                                        "結果不同，且該題判等規則下不相等"}
    needs_standin = any("_MatchStandIn()" in w for w in w0)
    aeq = EP_AEQ_TMPL.format(regex=flags["regex_predicate"], seteq=flags["set_equivalent"], atol=atol,
                             standin=STANDIN_SRC if needs_standin else "",
                             standin_type=", _MatchStandIn" if needs_standin else "")
    nb = len(base)
    label = "EvalPlus MBPP+ v0.2.0" if kind == "mbpp" else "EvalPlus HumanEval+ v0.1.10"
    loader = ("vacant_network/codebench.py::EvalPlusMBPPLoader" if kind == "mbpp"
              else "vacant_network/codebench.py::EvalPlusHumanEvalLoader")
    d = dir_name(tid)
    src_sha = BANK_SHA[bank]
    vis = (EP_VISIBLE_HEADER.format(dir=d, generator=GENERATOR, bank_label=label, sha_short=src_sha[:12])
           + aeq + "\n\n" + _ep_render_cases(ep, list(zip(inputs[:nb], w0[:nb])), "check_visible"))
    hid = (EP_HIDDEN_HEADER.format(dir=d, bank_label=label, loader=loader)
           + aeq + "\n\n" + _ep_render_cases(ep, list(zip(inputs, w0)), "check_case"))
    contract = EP_CONTRACT_TMPL.format(entry_point=ep, he_line=HE_LINE if kind == "he" else "",
                                       rule=_rule_text(flags, atol))
    files = {
        f"templates/{d}/goal.md": task["prompt"],
        f"templates/{d}/contract.md": contract,
        f"templates/{d}/tests_visible/test_visible.py": vis,
        f"templates/{d}/run_tests.sh": RUN_TESTS_SH,
        f"hidden/{d}/test_hidden.py": hid,
    }
    meta = {
        "task_id": tid, "dir": d,
        "n_visible": nb, "n_hidden_file": len(inputs), "n_hidden_only": len(plus),
        "prompt_sha256": sha256_text(task["prompt"]),
        "comparator": {"kind": "evalplus_check_code_aeq", **flags, "atol": atol,
                       "match_standin": needs_standin},
        "canon_secs": [r["secs"] for r in runs],
        "hashseed_literal_diff": w0 != w1,
        "n_inputs_gain_literal_differs_from_official": n_gain_literal_differs,
    }
    return {"files": files, "meta": meta}


BANK_SHA: dict[str, str] = {}


def render_evalplus(bank: str, src: dict, workers: int) -> tuple[dict[str, str], dict, dict]:
    kind = BANKS[bank]["kind"]
    BANK_SHA[bank] = src["source"]["sha256"]
    files: dict[str, str] = {}
    meta: dict[str, dict] = {}
    build_excluded: dict[str, str] = {}
    todo = [t for t in _task_order(bank, src["tasks"]) if t not in src["excluded"]]
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_ep_one, bank, t, src["tasks"][t], src["records"][t], kind): t for t in todo}
        for fu in cf.as_completed(futs):
            t = futs[fu]
            r = fu.result()
            if "excluded" in r:
                build_excluded[t] = r["excluded"]
            else:
                files.update(r["files"])
                meta[t] = r["meta"]
    return files, {t: meta[t] for t in _task_order(bank, meta)}, build_excluded


# ─────────────────────────────────────────────────────────────────────────────
# 寫出／檢查
# ─────────────────────────────────────────────────────────────────────────────

def _scan_templates(files: dict[str, str]) -> list[str]:
    """樣板裡不准出現 hidden 字樣的**路徑**（R534 的同一條）。內容裡的字樣另外計數回報。"""
    return [k for k in files if k.startswith("templates/") and "hidden" in k.lower()]


def render(bank: str, private_root: pathlib.Path, workers: int) -> int:
    src = load_source(bank, private_root)
    if BANKS[bank]["kind"] == "lcb":
        files, meta = render_lcb(bank, src)
        build_excluded: dict[str, str] = {}
    else:
        files, meta, build_excluded = render_evalplus(bank, src, workers)
    bad_paths = _scan_templates(files)
    if bad_paths:
        raise SystemExit(f"{bank}：樣板路徑出現 hidden 字樣 {bad_paths[:5]}。停。")
    per_task_files: dict[str, dict[str, str]] = {}
    for rel, content in files.items():
        tree, d, rest = rel.split("/", 2)
        per_task_files.setdefault(d, {})[f"{tree}/{rest}"] = sha256_text(content)
    for tid, m in meta.items():
        d = m["dir"]
        tbytes = sum(len(v.encode("utf-8")) for k, v in files.items() if k.startswith(f"templates/{d}/"))
        hbytes = sum(len(v.encode("utf-8")) for k, v in files.items() if k.startswith(f"hidden/{d}/"))
        m["template_bytes"], m["hidden_bytes"] = tbytes, hbytes
        if tbytes > TEMPLATE_BYTES_SANITY_MAX:
            m["template_oversize"] = True
        m["files_sha256"] = dict(sorted(per_task_files[d].items()))
        goal = files[f"templates/{d}/goal.md"]
        m["goal_mentions_hidden_word"] = bool(re.search(r"hidden", goal, re.I))
    root = tree_root(bank, private_root)
    for sub in ("templates", "hidden"):
        if (root / sub).is_dir():
            shutil.rmtree(root / sub)
    for rel, content in sorted(files.items()):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        if rel.endswith(".sh"):
            os.chmod(p, 0o755)
    rm = {
        "bank": bank, "run_id": RUN_ID, "generated_by": GENERATOR,
        "source": src["source"],
        "split_rule": SPLIT_SOURCE[BANKS[bank]["kind"]],
        "policy_excluded": src["excluded"],
        "build_excluded": dict(sorted(build_excluded.items())),
        "n_upstream": src["source"]["n_upstream"],
        "n_rendered": len(meta),
        "tasks": meta,
    }
    (root / "render_manifest.json").write_text(
        json.dumps(rm, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{bank}: 上游 {rm['n_upstream']} 題 → 政策排除 {len(src['excluded'])} → "
          f"建庫排除 {len(build_excluded)} → 渲染 {len(meta)} 題（{len(files)} 個檔）→ {root}")
    for t, why in sorted(build_excluded.items()):
        print(f"   建庫排除 {t}: {why}")
    return 0


def check(bank: str, private_root: pathlib.Path) -> int:
    """磁碟上的兩棵樹與 bank_manifest.json（沒有就退回 render_manifest.json）逐檔 sha256 對得上。"""
    root = tree_root(bank, private_root)
    man_path = root / "bank_manifest.json"
    if not man_path.exists():
        man_path = root / "render_manifest.json"
    if not man_path.exists():
        print(f"FAIL {bank}: 找不到 manifest（{root}）", file=sys.stderr)
        return 1
    man = json.loads(man_path.read_text(encoding="utf-8"))
    bad: list[str] = []
    expect: set[str] = set()
    for tid, m in man["tasks"].items():
        if m.get("usable") is False:
            continue
        for rel, want in m["files_sha256"].items():
            tree, rest = rel.split("/", 1)
            p = root / tree / m["dir"] / rest
            expect.add(str(p))
            if not p.exists():
                bad.append(f"缺檔 {p}")
            elif sha256_bytes(p.read_bytes()) != want:
                bad.append(f"漂了 {p}")
    extra = [str(p) for sub in ("templates", "hidden") if (root / sub).is_dir()
             for p in (root / sub).rglob("*") if p.is_file() and str(p) not in expect
             and "__pycache__" not in p.parts]
    bad += [f"多出來的檔 {p}" for p in extra]
    if bad:
        for b in bad[:30]:
            print("FAIL", bank, b, file=sys.stderr)
        print(f"FAIL {bank}: {len(bad)} 處不符", file=sys.stderr)
        return 1
    n = sum(1 for m in man["tasks"].values() if m.get("usable") is not False)
    print(f"OK {bank}: {n} 題、{len(expect)} 個檔與 {man_path.name} 一致")
    return 0


def write_refs(bank: str, private_root: pathlib.Path) -> int:
    """EvalPlus 兩組：把參考解與退化樁寫到私有樹的 `reference/<dir>/`（給 Colab 上的
    `gauge_banks.py --selfcheck` 用：換了機器、換了 Python，先用已知答案再試一次尺）。

    ⚠ `reference/` 是 GT 等級的東西（完整參考解），跟 `hidden/` 一樣**不准進任何工作區**，
      而且另外打包（見 `pack`），selfcheck 跑完就該刪。LCB 三組沒有這棵樹：
      它們的參考解就是 repo 裡的 `ops/gain/data/lcb*_probe_solutions.json`。
    """
    if not BANKS[bank]["private"]:
        return 0
    from vacant_network import codebench as cb
    src = load_source(bank, private_root)
    root = tree_root(bank, private_root)
    rm = json.loads((root / "render_manifest.json").read_text(encoding="utf-8"))
    if (root / "reference").is_dir():
        shutil.rmtree(root / "reference")
    for tid, m in rm["tasks"].items():
        rec = src["records"][tid]
        code = (rec["canonical_solution"] if BANKS[bank]["kind"] == "mbpp"
                else cb.EvalPlusHumanEvalLoader.canonical_source(rec))
        d = root / "reference" / m["dir"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "solution.py").write_text(code, encoding="utf-8")
        (d / "stub.py").write_text(f"def {rec['entry_point']}(*a, **k):\n    return None\n", encoding="utf-8")
    print(f"{bank}: reference/ 寫出 {len(rm['tasks'])} 題 → {root / 'reference'}")
    return 0


#: 兩個 tar：主包（Colab 跑實驗要的）與參考解包（只給 selfcheck，跑完就刪）。
#: gauge_detail.json（含失敗訊息）兩個都不進。
PACK_NAME = "colab_banks_private_20260927.tar.gz"
PACK_KEEP = ("templates/", "hidden/", "bank_manifest.json", "bank_manifest.sha256", "render_manifest.json")
PACK_REF_NAME = "colab_banks_private_reference_20260927.tar.gz"
PACK_REF_KEEP = ("reference/",)


def _pack_one(base: pathlib.Path, name: str, keep: tuple[str, ...]) -> tuple[str, int, int]:
    import gzip
    import io
    import tarfile
    members: list[tuple[str, pathlib.Path]] = []
    for bank in ("humanevalplus", "mbppplus"):
        root = base / bank
        if not (root / "bank_manifest.json").exists():
            raise SystemExit(f"{bank} 還沒有 bank_manifest.json（先跑量具）。停。")
        for p in sorted(root.rglob("*")):
            rel = p.relative_to(root).as_posix()
            if p.is_file() and "__pycache__" not in p.parts and any(
                    rel == k or rel.startswith(k) for k in keep):
                members.append((f"{RUN_ID}/{bank}/{rel}", p))
    if not members:
        raise SystemExit(f"{name}：沒有任何檔可以打包。停。")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.PAX_FORMAT) as tf:
        for arc, p in members:
            data = p.read_bytes()
            ti = tarfile.TarInfo(arc)
            ti.size, ti.mtime, ti.uid, ti.gid, ti.uname, ti.gname = len(data), 0, 0, 0, "", ""
            ti.mode = 0o755 if arc.endswith(".sh") else 0o644
            tf.addfile(ti, io.BytesIO(data))
    out = base / name
    with open(out, "wb") as fh, gzip.GzipFile(filename="", mode="wb", fileobj=fh, mtime=0,
                                              compresslevel=9) as gz:
        gz.write(buf.getvalue())
    digest = sha256_bytes(out.read_bytes())
    (base / (name + ".sha256")).write_text(f"{digest}  {name}\n", encoding="utf-8")
    return digest, len(members), out.stat().st_size


def pack(private_root: pathlib.Path) -> int:
    """把兩組私有題庫打成**可重現**的 tar.gz（排序、固定 mtime/uid/gid、gzip mtime=0）。

    解開後的路徑是 `colab_banks_20260927/<bank>/…`，所以在 Colab 上解到某個目錄 X，
    `build_banks.py check --bank mbppplus --private-root X` 就能逐檔驗 sha256。
    ⚠ 這兩個檔是私有官方包的衍生物：只放在 `.vacant-private/`（gitignore），不進版控。
    """
    base = private_root / RUN_ID
    for name, keep in ((PACK_NAME, PACK_KEEP), (PACK_REF_NAME, PACK_REF_KEEP)):
        digest, n, size = _pack_one(base, name, keep)
        print(f"{base / name}  {n} 個檔  {size} B  sha256 {digest}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="五組題庫 → agent 工作區任務（確定性、零模型呼叫）")
    ap.add_argument("cmd", choices=("render", "check", "refs", "pack"))
    ap.add_argument("--bank", default="all", help="lcb_v1／lcb_v2／lcb_v3／mbppplus／humanevalplus／all")
    ap.add_argument("--private-root", default=None,
                    help="私有包根目錄（含 evalplus/）；預設 $VACANT_PRIVATE_ROOT 或 <repo>/.vacant-private")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args(argv)
    private_root = pathlib.Path(a.private_root) if a.private_root else default_private_root()
    if a.cmd == "pack":
        return pack(private_root)
    banks = list(BANKS) if a.bank == "all" else [a.bank]
    rc = 0
    for b in banks:
        if b not in BANKS:
            raise SystemExit(f"未知的 bank {b!r}")
        if a.cmd == "render":
            rc |= render(b, private_root, a.workers)
        elif a.cmd == "refs":
            rc |= write_refs(b, private_root)
        else:
            rc |= check(b, private_root)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
