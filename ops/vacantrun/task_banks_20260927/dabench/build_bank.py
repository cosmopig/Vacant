#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""InfiAgent-DABench pilot 題庫渲染（2026-09-27）：把官方 closed-form validation 題投影成 r534 形狀。

這支在架構裡承重什麼
--------------------
Colab A/B（A＝只裝 pi；C＝pi＋零設定 Vacant）需要「讀資料檔→算出數值→交一個檔」的題，
因為零設定 Vacant 的五類退回裡有三類（`unread`／`unsourced`／`failed_step`）只在
**任務點名了資料檔、交付物是文件、值是 agent 自己打出來的**時候才可能觸發
（`vacant_network/trace/evidence.py` 的判準，見 README §三）。DABench 的每一題剛好是這個形狀：
一個 CSV、一個問題、一段把答案收斂成封閉形式的限制、一行 `@name[value]` 的答案格式。

兩棵樹（沿用 `ops/gain/r534/` 的紅線）
------------------------------------
    templates/<task_id>/            ← 工作區樣板（整棵複製給 agent）
        goal.md                     題目（官方 question／constraints／format 三欄逐字）＋資料檔路徑
        contract.md                 交件規格：`answer.txt`、`@name[value]`、官方判等規則
        data/<file_name>            官方 CSV，逐位元組（sha256 記在 manifest）
    hidden/<task_id>/expected.json  ← **永遠不進工作區**，只給 `score.py`

選題規則（逐字寫死在 `RULE_TEXT`，manifest 另記 sha256）
------------------------------------------------------
見 `RULE_TEXT`。重點：只收「每一個子答案都是數值」的題（`unsourced` 只比對數值與日期；
字串答案 Vacant 看不到，放進來量不到東西，而且官方判等對字串大小寫敏感、雜訊大），
依難度分層、每層用固定種子排出候選順序，**依序取參考解重現得了標準答案的前 10 題**。
參考解（`reference/<id>.py`）是我們照題目與限制獨立寫的，重現結果落在
`reference/reproduction.json`（`gauge_bank.py --reproduce` 產生）；重現不了的題具名排除、不刪紀錄。

誠實邊界
--------
1. 只收數值題 ⇒ 題庫偏向「算一個數」的題，DABench 原本 36% 的字串／分類答案不在裡面（偏誤要寫進報告）。
2. 參考解是我們寫的；「重現得了」只證明**存在一個照限制做的解**會得到標準答案，
   不證明限制沒有第二種合理解讀（見 README §五）。
3. 官方流程在計分前有一步 GPT-3.5 reformat；這裡沒有（agent 必須自己照格式寫），
   而且沒交的題記 0 分、留在分母裡（官方把沒有回應的題從分母拿掉）。

用法
----
    python3 build_bank.py --list 14          # 印每層前 14 個候選的題目（不印答案），寫參考解用
    python3 build_bank.py                    # 渲染 templates/＋hidden/＋bank_manifest.json
    python3 build_bank.py --check            # 驗磁碟與 manifest 沒漂
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "templates")
HIDDEN = os.path.join(HERE, "hidden")
REFERENCE = os.path.join(HERE, "reference")
REPRO = os.path.join(REFERENCE, "reproduction.json")
MANIFEST = os.path.join(HERE, "bank_manifest.json")

#: 上游：InfiAgent/InfiAgent（程式碼 Apache-2.0、資料 CC BY-NC 4.0），2026-09-27 的 main HEAD。
SOURCE_REPO = "InfiAgent/InfiAgent"
SOURCE_COMMIT = "3d6c4a70198e0a41fadf539f5b43c88b8c1a2d9c"
SOURCE_DIR = "examples/DA-Agent/data"
#: 釘死。讀到的檔不是這個雜湊 ⇒ 停（fail-closed，不會安靜地換一份題庫）。
QUESTIONS_SHA256 = "49ae783b20ecb60449ce1443c524e89f8ca8353a04e05e4d14a055b7a6f06126"
LABELS_SHA256 = "83b8fb8133c1794fcb6b42435e9cce124d22f68b71e2eedb37c973e40b5a18c2"
N_QUESTIONS = 257

SEED = "task-banks-20260927-dabench"
PER_LEVEL = 10
LEVELS = ("easy", "medium", "hard")
MAX_CSV_BYTES = 1_000_000

RULE_TEXT = """\
R0 母體：InfiAgent-DABench closed-form validation 集（da-dev-questions.jsonl＋da-dev-labels.jsonl，
   InfiAgent/InfiAgent@3d6c4a70，257 題），兩個檔的 sha256 釘死。
R1 資格：(a) 每一個子答案（common_answers 的每個 value）都能被 float() 解析；
   (b) 每個子答案名稱符合 \\w+、值裡沒有 '[' 或 ']'（官方正規式 @(\\w+)\\[(.*?)\\] 才抽得回來）；
   (c) 資料檔名不含空白（零設定 Vacant 的點名判準以空白切詞，檔名有空白就點名不到）；
   (d) 資料檔 ≤ 1,000,000 位元組；
   (e) 每個標準答案的項目名都出現在題目 format 欄的 @name[ 裡（否則 agent 無從知道要用哪個名字）。
   題目 format 要求、但標準答案沒有的項目（例如字串項）照樣寫進 contract，只是不計分。
R2 分層：依官方 level 欄位分 easy／medium／hard 三層。
R3 候選順序：每層把合格題 id 升冪排好，用 random.Random(f"{SEED}-{level}").shuffle 打亂，得到該層的候選順序。
R4 取題：每層依候選順序，取前 10 個「參考解重現得了標準答案」的題（reference/reproduction.json
   的 reproduced=true，判等用官方 eval_closed_form.py 的 is_equal）。依序檢查過但重現不了的題具名記在
   manifest 的 excluded_not_reproduced，不刪。
R5 報告：三層可以合併報（同一把尺、同一種題），也要分層列；這是 pilot，不做檢定。
"""


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def cache_dir() -> str:
    d = os.environ.get("VACANT_TASKBANK_CACHE") or os.path.expanduser(
        "~/.cache/vacant_task_banks")
    d = os.path.join(d, "dabench", SOURCE_COMMIT[:12])
    os.makedirs(d, exist_ok=True)
    return d


def fetch(rel: str) -> bytes:
    """上游檔（固定 commit）→ bytes；有快取就讀快取。"""
    path = os.path.join(cache_dir(), rel.replace("/", "__"))
    if os.path.exists(path):
        return open(path, "rb").read()
    url = ("https://raw.githubusercontent.com/%s/%s/%s/%s"
           % (SOURCE_REPO, SOURCE_COMMIT, SOURCE_DIR, urllib.parse.quote(rel)))
    with urllib.request.urlopen(url, timeout=120) as r:
        raw = r.read()
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(raw)
    os.replace(tmp, path)
    return raw


def load() -> tuple[list[dict], dict[int, dict]]:
    qraw, lraw = fetch("da-dev-questions.jsonl"), fetch("da-dev-labels.jsonl")
    for name, raw, want in (("questions", qraw, QUESTIONS_SHA256), ("labels", lraw, LABELS_SHA256)):
        got = sha256_bytes(raw)
        if got != want:
            sys.exit(f"拒絕渲染：{name} sha256={got} ≠ 釘死的 {want}")
    qs = [json.loads(l) for l in qraw.decode().splitlines() if l.strip()]
    ls = {}
    for l in lraw.decode().splitlines():
        if l.strip():
            o = json.loads(l)
            ls[o["id"]] = o
    if len(qs) != N_QUESTIONS or set(ls) != {q["id"] for q in qs}:
        sys.exit("拒絕渲染：題數或 id 集合與預期不符")
    return qs, ls


def format_names(q: dict) -> list[str]:
    """題目的答案格式裡要求的項目名（`@name[`），依出現順序去重。"""
    return list(dict.fromkeys(re.findall(r"@(\w+)\[", q["format"])))


def eligibility(q: dict, lab: dict) -> str | None:
    """None＝合格；否則回不合格理由（R1）。"""
    for name, val in lab["common_answers"]:
        if not re.fullmatch(r"\w+", name) or "[" in val or "]" in val:
            return "R1b 官方正規式抽不回來"
        try:
            float(val)
        except ValueError:
            return "R1a 非數值子答案"
    asked = format_names(q)
    if any(name not in asked for name, _ in lab["common_answers"]):
        return "R1e 標準答案的項目名不在題目的答案格式裡"
    if re.search(r"\s", q["file_name"]):
        return "R1c 檔名含空白"
    size = len(fetch("da-dev-tables/" + q["file_name"]))
    if size > MAX_CSV_BYTES:
        return f"R1d 資料檔 {size} 位元組 > {MAX_CSV_BYTES}"
    return None


def candidate_order(qs: list[dict], ls: dict[int, dict]) -> dict[str, list[int]]:
    out = {}
    for level in LEVELS:
        ids = sorted(q["id"] for q in qs if q["level"] == level
                     and eligibility(q, ls[q["id"]]) is None)
        random.Random(f"{SEED}-{level}").shuffle(ids)
        out[level] = ids
    return out


def task_dir(qid: int) -> str:
    return f"dab_{qid:03d}"


# ── 渲染 ────────────────────────────────────────────────────────────────

GOAL = """# Task

{question}

## Constraints

{constraints}

## Answer format

{format}

## Data

The data file for this task is `data/{file_name}`.
"""

CONTRACT = """# Contract

Write your final answer to `answer.txt` in the root of this workspace.

- Put each answer item on its own line, in the form `@name[value]`, using exactly the
  names given under "Answer format" in the task. This task expects {n_items} item(s):
  {names}.
- Only the `@name[value]` items in `answer.txt` are read. Any other text in the file is
  ignored.
- A value counts as correct when it is exactly the reference text, or when both parse as
  numbers that differ by less than 0.000001. Round as the answer format says.
- The data file is input. Do not change it.
"""


def render_task(q: dict, lab: dict) -> dict:
    tid = task_dir(q["id"])
    tdir, hdir = os.path.join(TEMPLATES, tid), os.path.join(HIDDEN, tid)
    for d in (tdir, hdir):
        if os.path.exists(d):
            shutil.rmtree(d)
    os.makedirs(os.path.join(tdir, "data"))
    os.makedirs(hdir)
    names = format_names(q)          # 題目要求的項目（可能比計分的多，例如字串項）
    scored = [n for n, _ in lab["common_answers"]]
    goal = GOAL.format(question=q["question"].strip(), constraints=q["constraints"].strip(),
                       format=q["format"].strip(), file_name=q["file_name"])
    contract = CONTRACT.format(n_items=len(names), names=", ".join(f"`@{n}[...]`" for n in names))
    files = {"goal.md": goal.encode(), "contract.md": contract.encode(),
             "data/" + q["file_name"]: fetch("da-dev-tables/" + q["file_name"])}
    for rel, raw in files.items():
        with open(os.path.join(tdir, rel), "wb") as f:
            f.write(raw)
    expected = {"task_id": tid, "source_id": q["id"], "answer_file": "answer.txt",
                "common_answers": lab["common_answers"],
                "scorer": "score.py（官方 eval_closed_form.py 的 extract_format＋is_equal 逐字）"}
    hraw = (json.dumps(expected, ensure_ascii=False, indent=2) + "\n").encode()
    with open(os.path.join(hdir, "expected.json"), "wb") as f:
        f.write(hraw)
    return {"task_id": tid, "source_id": q["id"], "level": q["level"],
            "concepts": q["concepts"], "file_name": q["file_name"],
            "n_items": len(names), "answer_names": names, "scored_names": scored,
            "template_sha256": {rel: sha256_bytes(raw) for rel, raw in sorted(files.items())},
            "template_bytes": sum(len(r) for r in files.values()),
            "hidden_sha256": sha256_bytes(hraw)}


def select(order: dict[str, list[int]]) -> tuple[dict[str, list[int]], dict[str, list[dict]]]:
    if not os.path.exists(REPRO):
        sys.exit("reference/reproduction.json 不存在：先跑 gauge_bank.py --reproduce")
    repro = json.load(open(REPRO))["results"]
    chosen, excluded = {}, {}
    for level in LEVELS:
        chosen[level], excluded[level] = [], []
        for qid in order[level]:
            if len(chosen[level]) == PER_LEVEL:
                break
            r = repro.get(str(qid))
            if r is None:
                sys.exit(f"{level} 層候選 {qid} 沒有參考解重現紀錄（依序檢查不可跳過）")
            if r["reproduced"]:
                chosen[level].append(qid)
            else:
                excluded[level].append({"source_id": qid, "why": r.get("note", "not reproduced")})
        if len(chosen[level]) < PER_LEVEL:
            sys.exit(f"{level} 層重現得了的題不足 {PER_LEVEL}")
    return chosen, excluded


def build() -> dict:
    qs, ls = load()
    byid = {q["id"]: q for q in qs}
    order = candidate_order(qs, ls)
    chosen, excluded = select(order)
    for d in (TEMPLATES, HIDDEN):
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)
    tasks = []
    for level in LEVELS:
        for qid in chosen[level]:
            tasks.append(render_task(byid[qid], ls[qid]))
    for t in tasks:  # 樣板裡不准出現 hidden／expected 字樣的路徑或檔名
        for rel in t["template_sha256"]:
            assert "hidden" not in rel and "expected" not in rel, rel
    reasons: dict[str, int] = {}
    for q in qs:
        why = eligibility(q, ls[q["id"]])
        reasons[why or "eligible"] = reasons.get(why or "eligible", 0) + 1
    repro_raw = open(REPRO, "rb").read()
    manifest = {
        "bank": "dabench_pilot_20260927",
        "source": {"repo": SOURCE_REPO, "commit": SOURCE_COMMIT, "dir": SOURCE_DIR,
                   "license": "程式碼 Apache-2.0、資料 CC BY-NC 4.0（上游 README 的兩個徽章）；CSV 由上游從 GitHub 蒐集，各檔原始授權未逐一查證。本題庫為非商業用途，轉載須附出處",
                   "questions_sha256": QUESTIONS_SHA256, "labels_sha256": LABELS_SHA256,
                   "n_questions": N_QUESTIONS},
        "selection_rule": RULE_TEXT,
        "selection_rule_sha256": sha256_bytes(RULE_TEXT.encode()),
        "seed": SEED,
        "eligibility_counts": dict(sorted(reasons.items())),
        "candidate_order": order,
        "layers": {lv: [task_dir(i) for i in chosen[lv]] for lv in LEVELS},
        "excluded_not_reproduced": excluded,
        "reproduction_sha256": sha256_bytes(repro_raw),
        "n_tasks": len(tasks),
        "deliverable": "answer.txt（工作區根目錄），每行 @name[value]",
        "scoring": {
            "primary": "ABQ：這一題每個子答案都判對＝1，否則 0（官方 Accuracy by Question）",
            "secondary": "PSAQ：判對的子答案比例（官方 Accuracy Proportional by Sub-Question）",
            "comparator": "官方 eval_closed_form.py：extract_format（@(\\w+)\\[(.*?)\\]）＋is_equal（字串相等，或兩邊 float 差 < 1e-6）",
            "deviations_from_official": [
                "沒有 GPT-3.5 reformat 步驟：agent 必須自己照格式寫",
                "answer.txt 不存在／空檔／抽不到任何項目 ⇒ 0 分且留在分母（官方把沒有回應的題拿出分母）",
                "官方 agent prompt 是 'Question: {question}\\n{constraints}'，format 只給 reformat；這裡 format 放進 goal.md",
            ],
        },
        "tasks": tasks,
    }
    raw = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode()
    with open(MANIFEST, "wb") as f:
        f.write(raw)
    with open(MANIFEST.replace(".json", ".sha256"), "w") as f:
        f.write(sha256_bytes(raw) + "  bank_manifest.json\n")
    return manifest


def check() -> int:
    m = json.load(open(MANIFEST))
    bad = 0
    for t in m["tasks"]:
        tdir = os.path.join(TEMPLATES, t["task_id"])
        on_disk = sorted(os.path.relpath(os.path.join(r, f), tdir)
                         for r, _, fs in os.walk(tdir) for f in fs)
        if on_disk != sorted(t["template_sha256"]):
            print(f"DRIFT {t['task_id']}: 檔案集合 {on_disk}")
            bad += 1
        for rel, want in t["template_sha256"].items():
            p = os.path.join(tdir, rel)
            if not os.path.exists(p) or sha256_bytes(open(p, "rb").read()) != want:
                print(f"DRIFT {t['task_id']}/{rel}")
                bad += 1
        hp = os.path.join(HIDDEN, t["task_id"], "expected.json")
        if not os.path.exists(hp) or sha256_bytes(open(hp, "rb").read()) != t["hidden_sha256"]:
            print(f"DRIFT hidden/{t['task_id']}")
            bad += 1
    extra = set(os.listdir(TEMPLATES)) ^ {t["task_id"] for t in m["tasks"]}
    if extra:
        print("DRIFT 多出／少了的題目資料夾", sorted(extra))
        bad += 1
    if sha256_bytes(open(REPRO, "rb").read()) != m["reproduction_sha256"]:
        print("DRIFT reference/reproduction.json")
        bad += 1
    print("check:", "OK" if not bad else f"{bad} 處漂移", f"({m['n_tasks']} 題)")
    return 1 if bad else 0


def list_candidates(n: int) -> None:
    qs, ls = load()
    byid = {q["id"]: q for q in qs}
    order = candidate_order(qs, ls)
    for level in LEVELS:
        print(f"==== {level}（合格 {len(order[level])}）")
        for qid in order[level][:n]:
            q = byid[qid]
            print(f"--- id={qid} file=data/{q['file_name']}")
            print("Q:", q["question"])
            print("C:", q["constraints"])
            print("F:", q["format"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--list", type=int, default=0)
    a = ap.parse_args()
    if a.list:
        list_candidates(a.list)
        return 0
    if a.check:
        return check()
    m = build()
    print(f"rendered {m['n_tasks']} tasks; layers:",
          {k: len(v) for k, v in m["layers"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
