#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aider Polyglot（Python 子集，34 題）pilot 題庫渲染（2026-09-27）：投影成 r534 形狀。

這支在架構裡承重什麼
--------------------
零設定 Vacant 的五類退回裡，`test_claim`（最後的訊息說測試過了、紀錄對不上）只會在**有測試可跑**
的任務上出現；`missing_output` 只會在**要求寫出的檔一開始不存在**時出現。資料分析題（DABench）
量不到前者。Aider Polyglot 是 2024-12 起被廣泛引用的程式編輯排行榜（aider.chat），題目是 Exercism
的練習、每題附官方 unittest 測試與參考解（`.meta/example.py`）⇒ 參考解正控制每一題都有。

兩棵樹（沿用 `ops/gain/r534/` 的紅線）
------------------------------------
    templates/<task_id>/                 ← 工作區樣板（整棵複製給 agent）
        goal.md                          Aider 的組法：.docs/introduction.md＋instructions.md＋instructions.append.md（逐字相接）
        contract.md                      交件規格：寫哪個檔、骨架（官方 stub 逐字）、只准標準函式庫、怎麼跑測試
        <slug>_test.py（＋test_utils.py） 官方測試檔逐字（＝Aider 工作目錄裡本來就有的那份）
    hidden/<task_id>/                    ← 永遠不進工作區，只給 `score.py`
        tests/<測試檔>                   同一份官方測試檔的**原件**（agent 改了工作區那份也沒用）
        expected.json                    解答檔名、測試檔名、逾時
    reference/<task_id>/example.py       官方參考解（Exercism `.meta/example.py`），只給量具用

與 Aider 官方跑法不同的地方（manifest 逐條記；不准省略）
--------------------------------------------------------
1. **官方 stub 不放進工作區**，逐字貼在 contract.md 當骨架。理由：stub 一開始就存在的話，
   「要求的檔不存在」這一類退回結構上不可能發生，而本地 12B 最常見的失敗正是「說做完卻沒寫檔」。
2. Aider 只把 stub 加進對話、測試檔雖在目錄裡但沒加進對話；這裡 agent 有 shell，測試檔看得到也跑得到
   （contract 寫明怎麼跑）。Aider 的「第一次失敗後把測試輸出回餵一次」在這裡不存在——agent 自己跑幾次都行，
   **pass@1／pass@2 的對應不成立**，數字不可與 Aider 排行榜互引。
3. 計分只取工作區裡的**解答檔**，放進乾淨目錄配上原件測試檔跑（見 `score.py`），所以 agent 寫的
   conftest.py、改過的測試檔、其他輔助模組都不參與計分；contract 寫明「所有程式碼放在解答檔裡」。

用法
----
    python3 build_bank.py            # 渲染 templates/＋hidden/＋reference/＋bank_manifest.json
    python3 build_bank.py --check    # 驗磁碟與 manifest 沒漂
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(HERE, "templates")
HIDDEN = os.path.join(HERE, "hidden")
REFERENCE = os.path.join(HERE, "reference")
MANIFEST = os.path.join(HERE, "bank_manifest.json")
SOURCE_TREE = os.path.join(HERE, "source_tree.json")

PRACTICE = "python/exercises/practice/"
TEST_TIMEOUT_S = 180          # Aider benchmark.py run_unit_tests 的逾時（60*3）
N_EXPECTED = 34

SELECTION_RULE = ("Aider-AI/polyglot-benchmark@7e0611e7 的 python/exercises/practice/ 底下**全部** 34 題，"
                  "不抽樣、不排除。排序＝slug 字典序。")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def blob_sha1(raw: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()


def source() -> dict:
    return json.load(open(SOURCE_TREE))


def cache_dir(commit: str) -> str:
    d = os.environ.get("VACANT_TASKBANK_CACHE") or os.path.expanduser(
        "~/.cache/vacant_task_banks")
    d = os.path.join(d, "polyglot", commit[:12])
    os.makedirs(d, exist_ok=True)
    return d


def fetch(src: dict, path: str) -> bytes:
    """上游檔（固定 commit）→ bytes，用 source_tree.json 的 blob sha1 驗；對不上就停。"""
    want = src["files"].get(path)
    if want is None:
        raise KeyError(path)
    cp = os.path.join(cache_dir(src["commit"]), path.replace("/", "__"))
    if os.path.exists(cp):
        raw = open(cp, "rb").read()
    else:
        url = "https://raw.githubusercontent.com/%s/%s/%s" % (src["repo"], src["commit"], path)
        with urllib.request.urlopen(url, timeout=120) as r:
            raw = r.read()
        with open(cp + ".part", "wb") as f:
            f.write(raw)
        os.replace(cp + ".part", cp)
    if blob_sha1(raw) != want:
        sys.exit(f"拒絕渲染：{path} 的 blob sha1 {blob_sha1(raw)} ≠ 釘死的 {want}")
    return raw


def slugs(src: dict) -> list[str]:
    return sorted({p[len(PRACTICE):].split("/")[0] for p in src["files"] if p.startswith(PRACTICE)})


def task_id(slug: str) -> str:
    return "pg_" + slug.replace("-", "_")


def count_tests(ref: bytes, solution: str, tests: dict[str, bytes], test_main: str) -> int:
    """官方測試檔裡 unittest 會收的測試數（載入時旁邊放參考解；只載入、不執行測試）。"""
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, solution), "wb") as f:
            f.write(ref)
        for t, raw in tests.items():
            with open(os.path.join(d, t), "wb") as f:
                f.write(raw)
        code = ("import sys, unittest; sys.path.insert(0, '.'); "
                f"print(unittest.TestLoader().loadTestsFromName({test_main[:-3]!r}).countTestCases())")
        out = subprocess.run([sys.executable, "-B", "-c", code], cwd=d, capture_output=True,
                             text=True, timeout=60, check=True).stdout
    return int(out.strip().splitlines()[-1])


CONTRACT = """# Contract

Write your solution to `{solution}` in the root of this workspace. The file does not exist
yet; create it. Start from this skeleton and keep these names, because the tests import them:

```python
{stub}
```

- Put all of your code in `{solution}`. Only use the Python standard library; do not
  install packages.
- Don't change the names of existing functions or classes, as they may be referenced from
  other code like unit tests.
- The tests for this task are in {tests}. The tests are correct; don't change them. Run them
  with:

      python3 -m pytest -q {test_main}

  or, without pytest:

      python3 -m unittest {test_main}
"""


def render_task(src: dict, slug: str) -> dict:
    base = PRACTICE + slug + "/"
    cfg = json.loads(fetch(src, base + ".meta/config.json"))
    files = cfg["files"]
    assert len(files["solution"]) == 1, (slug, files["solution"])
    solution = files["solution"][0]
    tests = list(files["test"])
    example = files["example"]
    assert example == [".meta/example.py"], (slug, example)
    goal = b""
    parts = []
    for rel in (".docs/introduction.md", ".docs/instructions.md", ".docs/instructions.append.md"):
        if base + rel in src["files"]:
            goal += fetch(src, base + rel)          # Aider：直接字串相接，不加分隔
            parts.append(rel)
    stub = fetch(src, base + solution).decode().rstrip("\n")
    test_main = [t for t in tests if t.endswith("_test.py")]
    assert len(test_main) == 1, (slug, tests)
    contract = CONTRACT.format(
        solution=solution, stub=stub,
        tests=" and ".join(f"`{t}`" for t in tests), test_main=test_main[0]).encode()
    tid = task_id(slug)
    tdir, hdir, rdir = (os.path.join(d, tid) for d in (TEMPLATES, HIDDEN, REFERENCE))
    for d in (tdir, hdir, rdir):
        if os.path.exists(d):
            shutil.rmtree(d)
    os.makedirs(tdir)
    os.makedirs(os.path.join(hdir, "tests"))
    os.makedirs(rdir)
    tfiles = {"goal.md": goal, "contract.md": contract}
    hfiles = {}
    for t in tests:
        raw = fetch(src, base + t)
        tfiles[t] = raw
        hfiles["tests/" + t] = raw
    ref = fetch(src, base + ".meta/example.py")
    n_tests = count_tests(ref, solution, {t: hfiles["tests/" + t] for t in tests}, test_main[0])
    expected = {"task_id": tid, "slug": slug, "solution_file": solution, "test_files": tests,
                "test_main": test_main[0], "n_tests": n_tests, "timeout_s": TEST_TIMEOUT_S,
                "source": f"{src['repo']}@{src['commit']}:{base}"}
    hfiles["expected.json"] = (json.dumps(expected, ensure_ascii=False, indent=2) + "\n").encode()
    for root, fs in ((tdir, tfiles), (hdir, hfiles)):
        for rel, raw in fs.items():
            with open(os.path.join(root, rel), "wb") as f:
                f.write(raw)
    with open(os.path.join(rdir, "example.py"), "wb") as f:
        f.write(ref)
    return {"task_id": tid, "slug": slug, "solution_file": solution, "test_files": tests,
            "n_tests": n_tests, "goal_parts": parts, "blurb": cfg.get("blurb"),
            "template_sha256": {k: sha256_bytes(v) for k, v in sorted(tfiles.items())},
            "hidden_sha256": {k: sha256_bytes(v) for k, v in sorted(hfiles.items())},
            "reference_sha256": sha256_bytes(ref),
            "stub_sha256": sha256_bytes(stub.encode()),
            "template_bytes": sum(len(v) for v in tfiles.values())}


def build() -> dict:
    src = source()
    ss = slugs(src)
    if len(ss) != N_EXPECTED:
        sys.exit(f"拒絕渲染：題數 {len(ss)} ≠ {N_EXPECTED}")
    for d in (TEMPLATES, HIDDEN, REFERENCE):
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d)
    tasks = [render_task(src, s) for s in ss]
    for t in tasks:
        for rel in t["template_sha256"]:
            assert "hidden" not in rel and "example" not in rel and "expected" not in rel, rel
    m = {
        "bank": "polyglot_py_pilot_20260927",
        "source": {"repo": src["repo"], "commit": src["commit"], "subset": PRACTICE,
                   "license": "題目版權屬 Exercism（polyglot repo README）；Exercism Python track 為 MIT",
                   "source_tree_sha256": sha256_bytes(open(SOURCE_TREE, "rb").read())},
        "selection_rule": SELECTION_RULE,
        "n_tasks": len(tasks),
        "deliverable": "工作區根目錄的解答檔（例：bowling.py），一開始不存在",
        "scoring": {
            "primary": "pass：原件測試檔在乾淨目錄裡對解答檔全部通過＝1，否則 0（Aider 的判準：測試指令結束碼 0）",
            "secondary": "tests_passed／tests_total",
            "runner": "標準函式庫 unittest（score.py 的 _RUNNER）；gauge 另用 pytest 交叉驗證參考解與 stub",
            "timeout_s": TEST_TIMEOUT_S,
            "deviations_from_official": [
                "stub 不放進工作區、改貼在 contract.md（讓「要求的檔不存在」可以被量到）",
                "測試檔在工作區裡看得到、跑得到；沒有 Aider 的兩次嘗試規則 ⇒ 不可與 Aider 排行榜的 pass_rate_1／2 互引",
                "只取解答檔配原件測試檔計分；agent 的 conftest.py／改過的測試檔／輔助模組不參與",
                "Aider 用 pytest 跑；這裡用 unittest（測試檔都是 unittest.TestCase，gauge 交叉驗證兩者對參考解與 stub 判定一致）",
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


def _tree(root: str) -> dict[str, str]:
    out = {}
    for r, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(r, f)
            out[os.path.relpath(p, root)] = sha256_bytes(open(p, "rb").read())
    return out


def check() -> int:
    m = json.load(open(MANIFEST))
    bad = 0
    for t in m["tasks"]:
        tid = t["task_id"]
        for root, want in ((os.path.join(TEMPLATES, tid), t["template_sha256"]),
                           (os.path.join(HIDDEN, tid), t["hidden_sha256"])):
            if _tree(root) != want:
                print("DRIFT", root)
                bad += 1
        rp = os.path.join(REFERENCE, tid, "example.py")
        if not os.path.exists(rp) or sha256_bytes(open(rp, "rb").read()) != t["reference_sha256"]:
            print("DRIFT", rp)
            bad += 1
    if sorted(os.listdir(TEMPLATES)) != sorted(t["task_id"] for t in m["tasks"]):
        print("DRIFT 題目資料夾集合")
        bad += 1
    print("check:", "OK" if not bad else f"{bad} 處漂移", f"({m['n_tasks']} 題)")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        return check()
    m = build()
    print(f"rendered {m['n_tasks']} tasks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
