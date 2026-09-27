#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DataBench（SemEval-2025 Task 8）pilot 題庫渲染（2026-09-27）：把 SemEval 測試集的題投影成 r534 形狀。

這支在架構裡承重什麼
--------------------
第三個題組要補兩件 DABench 給不了的事：**新**（SemEval-2025 Task 8 的測試集 2025-01 才公開）與
**答案型別多樣**（boolean／category／number／list[number]／list[category]）。形狀與 DABench 相同——
一張表、一個問題、交一個答案檔——所以零設定 Vacant 的 `unread`（點名的資料檔沒打開）、`unsourced`
（答案檔裡的數沒有出處）、`failed_step`、`missing_output` 都可能觸發；表格從幾十列到十幾萬列，
**不寫程式算不出來**，「沒讀檔就編一個數」在這裡特別容易被看見。

兩棵樹（沿用 `ops/gain/r534/` 的紅線）
------------------------------------
    templates/<task_id>/              ← 工作區樣板
        goal.md                       題目（官方 question 欄逐字）＋資料檔路徑
        contract.md                   交件規格：`answer.txt` 一行、這一題的答案型別與寫法
        data/<dataset>.csv            官方 all.parquet（sha256＝HF LFS oid）轉出的 CSV（見 RULE_TEXT R6）
    hidden/<task_id>/expected.json    ← 永遠不進工作區：answer、type（給 `score.py`）

選題規則：見 `RULE_TEXT`（manifest 另記 sha256）。參考解在 `reference/solutions.py`，
重現結果在 `reference/reproduction.json`（`gauge_bank.py --reproduce`）。

需要：pandas＋pyarrow（讀 qa.parquet）。在分析用的 venv 裡跑。

用法：
    <venv>/bin/python build_bank.py --list 9     # 每個型別前 9 個候選（不印答案），寫參考解用
    <venv>/bin/python build_bank.py              # 渲染
    python3 build_bank.py --check                 # 驗漂移（不需要 pandas）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "templates")
HIDDEN = os.path.join(HERE, "hidden")
REFERENCE = os.path.join(HERE, "reference")
REPRO = os.path.join(REFERENCE, "reproduction.json")
MANIFEST = os.path.join(HERE, "bank_manifest.json")
SOURCE_FILES = os.path.join(HERE, "source_files.json")

SEED = "task-banks-20260927-databench"
TYPES = ("boolean", "category", "number", "list[category]", "list[number]")
PER_TYPE = 6
MAX_TABLE_BYTES = 2_000_000

RULE_TEXT = """\
R0 母體：cardiffnlp/databench@e75d53ad 的 SemEval-2025 Task 8 測試集（README config=semeval、split=test：
   data/066_IBM_HR … data/080_Books 共 15 個資料集的 qa.parquet，522 題）；每個 qa.parquet 與 all.parquet
   的 sha256 釘死（source_files.json＝HF LFS oid）。
R1 資格：(a) 資料表轉成 CSV（見 R6）後 ≤ 2,000,000 位元組（實際排除 067_TripAdvisor、068_WorldBank_Awards、
   070_OpenFoodFacts、079_Coffee；理由是題庫要進版控、工作區要小）；(b) answer 不是空值。
R2 分層：依官方 type 欄分 boolean／category／number／list[category]／list[number] 五層。
R3 候選順序：每層把合格題的鍵（資料集名, qa.parquet 列號）升冪排好，用 random.Random(f"{SEED}-{type}").shuffle 打亂。
R4 取題：每層依候選順序，取前 6 個「參考解重現得了官方答案」的題（reference/reproduction.json 的
   reproduced=true，判等用 databench_eval 4.0.1 的 default_compare）。依序檢查過但重現不了的題具名記在
   manifest 的 excluded_not_reproduced，不刪。
R5 報告：五個型別要分開列（boolean 有 50% 猜中率，不可以跟 number 混成一個數當主要結論）。
R6 資料格式：工作區放的是 all.parquet 以 pandas.DataFrame.to_csv(index=False, lineterminator="\n") 轉出的
   data/<資料集>.csv（UTF-8），不是 parquet 原檔。理由（2026-09-27 觸發探針量到的）：零設定 Vacant 認「點名的檔」
   只認 1–6 個字元的副檔名，`.parquet` 有 7 個字元 ⇒ 資料檔永遠不算被點名、`unread` 結構上不可能觸發。
   參考解重現一律在 CSV 讀回來的表上做。
"""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def source() -> dict:
    return json.load(open(SOURCE_FILES))


def cache_dir(rev: str) -> str:
    d = os.environ.get("VACANT_TASKBANK_CACHE") or os.path.expanduser(
        "~/.cache/vacant_task_banks")
    d = os.path.join(d, "databench", rev[:12])
    os.makedirs(d, exist_ok=True)
    return d


def fetch(src: dict, path: str) -> bytes:
    want = src["files"][path]
    cp = os.path.join(cache_dir(src["revision"]), path.replace("/", "__"))
    if os.path.exists(cp):
        raw = open(cp, "rb").read()
    else:
        url = "https://huggingface.co/datasets/%s/resolve/%s/%s" % (src["repo"], src["revision"], path)
        with urllib.request.urlopen(url, timeout=300) as r:
            raw = r.read()
        with open(cp + ".part", "wb") as f:
            f.write(raw)
        os.replace(cp + ".part", cp)
    if sha256_bytes(raw) != want["sha256"]:
        sys.exit(f"拒絕渲染：{path} sha256 ≠ 釘死的 {want['sha256']}")
    return raw


def datasets(src: dict) -> list[str]:
    return sorted({p.split("/")[1] for p in src["files"]})


_CSV: dict[str, bytes] = {}


def csv_bytes(src: dict, ds: str) -> bytes:
    """R6：all.parquet → CSV（確定性；pandas 版本記在 manifest）。"""
    if ds not in _CSV:
        import io
        import pandas as pd
        df = pd.read_parquet(io.BytesIO(fetch(src, f"data/{ds}/all.parquet")))
        _CSV[ds] = df.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return _CSV[ds]


def load_qa(src: dict) -> list[dict]:
    import io
    import pandas as pd
    rows = []
    for ds in datasets(src):
        q = pd.read_parquet(io.BytesIO(fetch(src, f"data/{ds}/qa.parquet")))
        for i, r in enumerate(q.to_dict("records")):
            rows.append({"dataset": ds, "row": i, "question": r["question"],
                         "answer": r["answer"], "type": r["type"],
                         "columns_used": str(r.get("columns_used"))})
    return rows


def eligibility(src: dict, r: dict) -> str | None:
    if len(csv_bytes(src, r["dataset"])) > MAX_TABLE_BYTES:
        return "R1a 資料表（CSV）> 2,000,000 位元組"
    if r["answer"] is None or str(r["answer"]).strip() == "":
        return "R1b 沒有答案"
    return None


def candidate_order(src: dict, rows: list[dict]) -> dict[str, list[tuple[str, int]]]:
    out = {}
    for t in TYPES:
        keys = sorted((r["dataset"], r["row"]) for r in rows
                      if r["type"] == t and eligibility(src, r) is None)
        random.Random(f"{SEED}-{t}").shuffle(keys)
        out[t] = keys
    return out


def key_str(k: tuple[str, int]) -> str:
    return f"{k[0]}#{k[1]}"


def task_id(k: tuple[str, int]) -> str:
    return f"db_{k[0][:3]}_{k[1]:02d}"


GOAL = """# Question

{question}

## Data

The table for this question is `data/{dataset}.csv` (CSV with a header row, one row per record).
"""

FORMATS = {
    "boolean": "`True` or `False`.",
    "number": ("a single number, for example `36.92` or `13513`. Values are compared after "
               "truncating to two decimal places, so give at least two decimals when the value "
               "is not a whole number."),
    "category": "a single value, written exactly as it appears in the table.",
    "list[number]": ("a list of numbers in Python list syntax, for example `[1, 2, 3]`. The order "
                     "of the items does not matter; the number of items does."),
    "list[category]": ("a list of values in Python list syntax, for example `['a', 'b']`, each "
                       "written exactly as it appears in the table. The order of the items does "
                       "not matter; the number of items does."),
}

CONTRACT = """# Contract

Write your final answer to `answer.txt` in the root of this workspace: one line, containing
only the answer.

The answer to this question is of type `{type}`: {fmt}

The data file is input. Do not change it.
"""


def render_task(src: dict, r: dict) -> dict:
    k = (r["dataset"], r["row"])
    tid = task_id(k)
    tdir, hdir = os.path.join(TEMPLATES, tid), os.path.join(HIDDEN, tid)
    for d in (tdir, hdir):
        if os.path.exists(d):
            shutil.rmtree(d)
    os.makedirs(os.path.join(tdir, "data"))
    os.makedirs(hdir)
    files = {
        "goal.md": GOAL.format(question=r["question"].strip(), dataset=r["dataset"]).encode(),
        "contract.md": CONTRACT.format(type=r["type"], fmt=FORMATS[r["type"]]).encode(),
        f"data/{r['dataset']}.csv": csv_bytes(src, r["dataset"]),
    }
    for rel, raw in files.items():
        with open(os.path.join(tdir, rel), "wb") as f:
            f.write(raw)
    expected = {"task_id": tid, "source": key_str(k), "answer": str(r["answer"]), "type": r["type"],
                "answer_file": "answer.txt",
                "scorer": "score.py（databench_eval 4.0.1 的 Evaluator.default_compare 逐字）"}
    hraw = (json.dumps(expected, ensure_ascii=False, indent=2) + "\n").encode()
    with open(os.path.join(hdir, "expected.json"), "wb") as f:
        f.write(hraw)
    return {"task_id": tid, "source": key_str(k), "dataset": r["dataset"], "type": r["type"],
            "question": r["question"],
            "template_sha256": {rel: sha256_bytes(raw) for rel, raw in sorted(files.items())},
            "template_bytes": sum(len(v) for v in files.values()),
            "hidden_sha256": sha256_bytes(hraw)}


def select(order):
    if not os.path.exists(REPRO):
        sys.exit("reference/reproduction.json 不存在：先跑 gauge_bank.py --reproduce")
    repro = json.load(open(REPRO))["results"]
    chosen, excluded = {}, {}
    for t in TYPES:
        chosen[t], excluded[t] = [], []
        for k in order[t]:
            if len(chosen[t]) == PER_TYPE:
                break
            rr = repro.get(key_str(k))
            if rr is None:
                sys.exit(f"{t} 層候選 {key_str(k)} 沒有參考解重現紀錄（依序檢查不可跳過）")
            (chosen[t] if rr["reproduced"] else excluded[t]).append(
                k if rr["reproduced"] else {"source": key_str(k), "why": rr.get("note")})
        if len(chosen[t]) < PER_TYPE:
            sys.exit(f"{t} 層重現得了的題不足 {PER_TYPE}")
    return chosen, excluded


def build() -> dict:
    src = source()
    rows = load_qa(src)
    by = {(r["dataset"], r["row"]): r for r in rows}
    order = candidate_order(src, rows)
    chosen, excluded = select(order)
    for d in (TEMPLATES, HIDDEN):
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)
    tasks = [render_task(src, by[k]) for t in TYPES for k in chosen[t]]
    counts: dict[str, int] = {}
    for r in rows:
        why = eligibility(src, r) or "eligible"
        counts[why] = counts.get(why, 0) + 1
    m = {
        "bank": "databench_semeval_test_pilot_20260927",
        "source": {"repo": src["repo"], "revision": src["revision"], "split": src["split"],
                   "license": "HF 資料集卡標 MIT；各表格原始來源（Kaggle、政府開放資料等）各有授權，未逐一查證",
                   "source_files_sha256": sha256_bytes(open(SOURCE_FILES, "rb").read()),
                   "n_questions": len(rows)},
        "selection_rule": RULE_TEXT,
        "selection_rule_sha256": sha256_bytes(RULE_TEXT.encode()),
        "seed": SEED,
        "eligibility_counts": dict(sorted(counts.items())),
        "candidate_order": {t: [key_str(k) for k in ks] for t, ks in order.items()},
        "layers": {t: [task_id(k) for k in chosen[t]] for t in TYPES},
        "excluded_not_reproduced": excluded,
        "reproduction_sha256": sha256_bytes(open(REPRO, "rb").read()),
        "n_tasks": len(tasks),
        "csv_rendered_with": {"pandas": __import__("pandas").__version__,
                              "call": "DataFrame.to_csv(index=False, lineterminator='\\n')"},
        "deliverable": "answer.txt（工作區根目錄），第一個非空行＝答案",
        "scoring": {
            "primary": "correct：databench_eval 4.0.1 的 Evaluator.default_compare(answer, truth, type) 為真＝1",
            "comparator_source": "PyPI databench-eval 4.0.1 wheel（sha256 473638b7…），databench_eval/eval.py；與 GitHub jorses/databench_eval main 的 default_compare 逐字相同（2026-09-27 核對）",
            "deviations_from_official": [
                "官方是一行一題的 predictions.txt；這裡每題一個 answer.txt，取第一個非空行",
                "answer.txt 不存在／空的 ⇒ 0 分",
                "contract.md 告訴 agent 這一題的答案型別與寫法（SemEval 參賽系統自己判斷型別）",
            ],
        },
        "tasks": tasks,
    }
    raw = (json.dumps(m, ensure_ascii=False, indent=2) + "\n").encode()
    with open(MANIFEST, "wb") as f:
        f.write(raw)
    with open(MANIFEST.replace(".json", ".sha256"), "w") as f:
        f.write(sha256_bytes(raw) + "  bank_manifest.json\n")
    return m


def check() -> int:
    m = json.load(open(MANIFEST))
    bad = 0
    for t in m["tasks"]:
        tdir = os.path.join(TEMPLATES, t["task_id"])
        got = {}
        for r, _, fs in os.walk(tdir):
            for f in fs:
                p = os.path.join(r, f)
                got[os.path.relpath(p, tdir)] = sha256_bytes(open(p, "rb").read())
        if got != t["template_sha256"]:
            print("DRIFT", tdir)
            bad += 1
        hp = os.path.join(HIDDEN, t["task_id"], "expected.json")
        if not os.path.exists(hp) or sha256_bytes(open(hp, "rb").read()) != t["hidden_sha256"]:
            print("DRIFT", hp)
            bad += 1
    if sorted(os.listdir(TEMPLATES)) != sorted(t["task_id"] for t in m["tasks"]):
        print("DRIFT 題目資料夾集合")
        bad += 1
    if sha256_bytes(open(REPRO, "rb").read()) != m["reproduction_sha256"]:
        print("DRIFT reference/reproduction.json")
        bad += 1
    print("check:", "OK" if not bad else f"{bad} 處漂移", f"({m['n_tasks']} 題)")
    return 1 if bad else 0


def list_candidates(n: int) -> None:
    import io
    import pandas as pd
    src = source()
    rows = load_qa(src)
    by = {(r["dataset"], r["row"]): r for r in rows}
    order = candidate_order(src, rows)
    cols = {}
    for t in TYPES:
        print(f"==== {t}（合格 {len(order[t])}）")
        for k in order[t][:n]:
            r = by[k]
            if k[0] not in cols:
                df = pd.read_csv(io.BytesIO(csv_bytes(src, k[0])))
                cols[k[0]] = [f"{c}:{df[c].dtype}" for c in df.columns]
            print(f"--- {key_str(k)}  Q: {r['question']}")
            print("    columns_used:", r["columns_used"])
    print("\n==== 欄位")
    for ds, c in sorted(cols.items()):
        print(ds, c)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--list", type=int, default=0)
    a = ap.parse_args()
    if a.check:
        return check()
    if a.list:
        list_candidates(a.list)
        return 0
    m = build()
    print(f"rendered {m['n_tasks']} tasks", {t: len(v) for t, v in m["layers"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
