"""LiveCodeBench → G 實驗 bank 轉換器（人類指令 2026-09-01：題目可能太簡單）。

輸入：HF `livecodebench/code_generation_lite` 的原始 test*.jsonl（不進 repo，
太大）。輸出：釘死的 bank JSONL（`ops/gain/data/lcb_bank_v1.jsonl`）＋
供 LiveCodeBenchLoader 用的 sha256／題數釘值（印在 stdout，貼進 codebench.py）。

只收 functional（LeetCode、有 starter_code）題：stdin 型要改 worker prompt
慣例與沙箱執行模型，v1 不做（誠實範圍聲明，見 DECISION_20260901_R440）。
難度只收 medium＋hard——easy 就是「太簡單」假說要排除的東西。

轉換內容（每題）：
  - class Solution 方法 → 頂層函式簽名（拆 self；worker 見到的是普通函式契約）
  - public_test_cases → visible tests；private（b64+zlib+pickle）→ hidden tests
  - 每題 hidden 上限 24 筆（沙箱時限 8s 的預算；超過取決定性前綴）
  - 記 provenance：question_id、platform、difficulty、contest_date、來源檔

用法：
    python3 ops/gain/build_lcb_bank.py raw/test5.jsonl raw/test6.jsonl \
        --out ops/gain/data/lcb_bank_v1.jsonl
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import pickle
import re
import zlib

MAX_HIDDEN = 24
MAX_ARG_CHARS = 20000   # 單筆測資 repr 超過這個就丟（巨無霸輸入撐爆 prompt/沙箱）


def _parse_meta(rec: dict) -> dict:
    md = rec.get("metadata") or {}
    if isinstance(md, str):
        try:
            md = json.loads(md)
        except ValueError:
            md = {}
    return md


def _decode_private(raw: str) -> list[dict]:
    try:
        return json.loads(raw)
    except ValueError:
        dec = pickle.loads(zlib.decompress(base64.b64decode(raw)))
        return json.loads(dec) if isinstance(dec, str) else dec


def _parse_args_line(inp: str) -> list:
    """functional input＝每行一個 JSON 值＝一個 positional argument。"""
    return [json.loads(line) for line in inp.strip().split("\n")]


def _parse_expected(out: str):
    try:
        return json.loads(out)
    except ValueError:
        return out.strip()


_SIG_RE = re.compile(r"def\s+(\w+)\s*\(\s*self\s*,?\s*([^)]*)\)")


def _unwrap_signature(starter: str) -> tuple[str, str] | None:
    """class Solution 方法 → (函式名, 參數字串（含型別註記、去 self）)。"""
    m = _SIG_RE.search(starter)
    if not m:
        return None
    return m.group(1), m.group(2).strip()


def _convert(rec: dict, src: str) -> dict | None:
    starter = rec.get("starter_code") or ""
    if not starter.strip():
        return None                       # stdin 型，v1 不收
    if rec.get("difficulty") not in ("medium", "hard"):
        return None
    sig = _unwrap_signature(starter)
    if not sig:
        return None
    fn, params = sig
    meta_fn = _parse_meta(rec).get("func_name")
    if meta_fn and meta_fn != fn:
        return None                       # 名字對不上，寧可丟（fail-closed）

    def load_tests(raw) -> list[dict] | None:
        if isinstance(raw, str):
            try:
                cases = json.loads(raw)
            except ValueError:
                cases = _decode_private(raw)
        else:
            cases = raw
        out = []
        for c in cases:
            if c.get("testtype") != "functional":
                return None               # 混型題整題丟
            try:
                args = _parse_args_line(c["input"])
                exp = _parse_expected(c["output"])
            except (ValueError, KeyError):
                return None               # 測資解析不了＝整題丟（不產半殘題）
            if len(repr(args)) + len(repr(exp)) > MAX_ARG_CHARS:
                continue
            out.append({"args": args, "expected": exp})
        return out

    visible = load_tests(rec["public_test_cases"])
    hidden_all = load_tests(rec["private_test_cases"])
    if not visible or not hidden_all:
        return None
    hidden = hidden_all[:MAX_HIDDEN]

    prompt = (
        f"{rec['question_content'].strip()}\n\n"
        f"請寫一個頂層 Python 函式（不要用 class）：\n"
        f"def {fn}({params}):\n"
        f"只能用標準函式庫。函式必須回傳答案，不要印出。"
    )
    return {
        "task_id": f"lcb_{rec['question_id']}",
        "entry_point": fn,
        "difficulty": rec["difficulty"],
        "platform": rec["platform"],
        "contest_date": rec.get("contest_date", ""),
        "source_file": src,
        "prompt": prompt,
        "visible_tests": visible,
        "hidden_tests": hidden,
        "n_hidden_total": len(hidden_all),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("raw", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    tasks: dict[str, dict] = {}
    stats = {"in": 0, "kept": 0, "stdin": 0, "easy": 0, "dropped": 0}
    for path in a.raw:
        src = pathlib.Path(path).name
        with open(path, encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                stats["in"] += 1
                if not (rec.get("starter_code") or "").strip():
                    stats["stdin"] += 1
                    continue
                if rec.get("difficulty") == "easy":
                    stats["easy"] += 1
                    continue
                t = _convert(rec, src)
                if t is None:
                    stats["dropped"] += 1
                    continue
                tasks[t["task_id"]] = t     # 跨檔重複題以後見者為準（LCB 無重複 id）
                stats["kept"] += 1
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(tasks.values(), key=lambda t: t["task_id"])
    with open(out, "w", encoding="utf-8") as f:
        for t in ordered:
            f.write(json.dumps(t, ensure_ascii=False, sort_keys=True) + "\n")
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    by_diff: dict[str, int] = {}
    for t in ordered:
        by_diff[t["difficulty"]] = by_diff.get(t["difficulty"], 0) + 1
    print(json.dumps({
        "bank": str(out), "sha256": digest, "count": len(ordered),
        "by_difficulty": by_diff, "stats": stats,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
