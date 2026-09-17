#!/usr/bin/env python3
"""R531 公開題庫的抓取——**釘 URL、記 sha256、落盤到 `.vacant-private/`**。

這支在架構裡承重什麼（`DECISION_20260915_R531_…_PREREG.md` §三）：
Fable 2026-09-15 裁決第 3 點：「抓下來的公開資料一律放
`.vacant-private/benchmarks/<family>/`（gitignored），**不進 repo**；
repo 只放 `manifest.json`（來源 URL、版本、sha256、授權、題 id 清單）與轉換器。」

⇒ 這支是**取得**那一半，`bankspec.py`／`build_bank.py` 是**轉換**那一半。
它不做任何選擇、不做任何渲染：抓下來、算雜湊、寫一張 `sources.json`。

## 為什麼要自己寫而不是 `datasets.load_dataset`

vacant-dev **沒有 pip**（實測 `No module named pip`，連 `ensurepip` 都沒有），
所以 `datasets`／`pyarrow` 都不存在，parquet 讀不了。
可用的只有標準庫 ＋ `requests`。
⇒ 走 **HF datasets-server 的 `/rows` API**（回 JSON，免 token、免 pyarrow），
或 GitHub raw 的純檔案。兩條都實測過（2026-09-15）。

## 速率限制是這支最容易踩的坑（實測）

匿名的 datasets-server **會回 429**，而且**兩個行程同時抓一定會踩到**
（2026-09-15 在 Mac 上實測：並行兩支各自重試六次全部用盡）。
⇒ 這支**單行程、循序、每次請求之間固定間隔**，而且 429 走
指數退避（鐵律 3 的 retry×4 在這裡放寬成 6 次，因為 429 不是故障是節流）。
**不准為了快而並行**——省下來的幾分鐘會換成一次沒抓完的題庫。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import random
import time
import urllib.error
import urllib.request

UA = "vacant-r531-bank-builder"
ROWS_API = "https://datasets-server.huggingface.co/rows"

#: **釘死的來源**。改任何一行都是題庫變更，要重寫 DECISION。
SOURCES = {
    "bigcodebench": {
        "kind": "hf_rows", "dataset": "bigcode/bigcodebench",
        "config": "default", "split": "v0.1.4", "n": 1140, "page": 50,
        "out": "bigcodebench/v0.1.4.jsonl",
        "license": "Apache-2.0",
        "license_note": "HF cardData license=apache-2.0；GitHub harness repo 已於 2026-07-20 封存（read-only）",
        "homepage": "https://huggingface.co/datasets/bigcode/bigcodebench",
    },
    "bigcodebench_hard": {
        "kind": "hf_rows", "dataset": "bigcode/bigcodebench-hard",
        "config": "default", "split": "v0.1.4", "n": 148, "page": 50,
        "out": "bigcodebench_hard/v0.1.4.jsonl",
        "license": "Apache-2.0（繼承 bigcodebench；HF card 本身未標）",
        "license_note": "hard 子集的 card 沒有 license 欄位，沿用母集的 Apache-2.0，**這是推定不是宣告**",
        "homepage": "https://huggingface.co/datasets/bigcode/bigcodebench-hard",
    },
    "codecontests": {
        "kind": "hf_rows", "dataset": "deepmind/code_contests",
        "config": "default", "split": "test", "n": 165, "page": 5,
        "out": "codecontests/test.jsonl",
        "license": "Apache-2.0（程式）／CC BY-4.0（非程式資料）",
        "license_note": "HF cardData license=cc-by-4.0；DeepMind repo 的 code 是 Apache-2.0",
        "homepage": "https://huggingface.co/datasets/deepmind/code_contests",
    },
    "classeval": {
        "kind": "raw", "n": 100,
        "url": "https://raw.githubusercontent.com/FudanSELab/ClassEval/master/data/ClassEval_data.json",
        "out": "classeval/ClassEval_data.json",
        "license": "程式 MIT／**資料 CC BY-NC 4.0（非商用）**",
        "license_note": ("Fable 2026-09-15 裁決第 3 點：我們是非商業學術與展覽用途，可用，"
                         "但**授權逐字記進 manifest 與收官檔，不得再散布原始資料**"),
        "homepage": "https://github.com/FudanSELab/ClassEval",
    },
    "lcb_v3": {
        "kind": "local", "n": 189,
        "path": "ops/gain/data/lcb_bank_v3.jsonl",
        "out": None,                       # 已在 repo，不重抓
        "license": "**不明確**",
        "license_note": ("HF dataset card 的 YAML 只寫 `license: cc`，"
                         "**沒有指明 BY／SA／NC**；題目本身抓自 LeetCode／AtCoder／Codeforces。"
                         "Fable 2026-09-15 裁決第 3 點：照實記「授權不明確」。"),
        "homepage": "https://huggingface.co/datasets/livecodebench/code_generation_lite",
    },
    "lcb_v3_solutions": {
        "kind": "local", "n": 12,
        "path": "ops/gain/data/lcb_v3_probe_solutions.json",
        "out": None,
        "license": "同 lcb_v3（不明確）",
        "license_note": "只有 12 題有參考解——這是 `pba` 族題數的硬上界（§六）",
        "homepage": "",
    },
}

REPO = pathlib.Path(__file__).resolve().parents[3]
DEST = REPO / ".vacant-private" / "benchmarks"


def _get(url: str, *, tries: int = 6, timeout: int = 120) -> bytes:
    """429／5xx 指數退避。**429 不是故障是節流**，所以放寬到 6 次。"""
    last: Exception | None = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(min(2 ** k, 60) + random.random() * 2)
                continue
            raise
        except Exception as e:                      # noqa: BLE001 —— 連線層什麼都可能丟
            last = e
            time.sleep(min(2 ** k, 60) + random.random() * 2)
    raise RuntimeError(f"抓不到 {url}：{type(last).__name__} {last}")


def fetch_rows(spec: dict, *, gap_s: float) -> list[dict]:
    """HF datasets-server `/rows` 分頁。**截斷的格子直接中止**——
    `truncated_cells` 非空代表我們拿到的不是完整測資，那種資料不能當題庫。"""
    rows: list[dict] = []
    off = 0
    while off < spec["n"]:
        url = (f"{ROWS_API}?dataset={spec['dataset']}&config={spec['config']}"
               f"&split={spec['split']}&offset={off}&length={spec['page']}")
        d = json.loads(_get(url))
        for x in d["rows"]:
            if x.get("truncated_cells"):
                raise RuntimeError(
                    f"{spec['dataset']} row {x['row_idx']} 有被截斷的欄位："
                    f"{x['truncated_cells']}。停——截斷的測資不能當題庫。")
            rows.append(x["row"])
        off += spec["page"]
        print(f"  … {min(off, spec['n'])}/{spec['n']}", flush=True)
        time.sleep(gap_s)
    if len(rows) != spec["n"]:
        raise RuntimeError(f"{spec['dataset']} 拿到 {len(rows)} 列，期望 {spec['n']}。停。")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="R531 題庫來源抓取（零模型呼叫）")
    ap.add_argument("--only", default=None, help="逗號分隔的來源名；預設全部")
    ap.add_argument("--gap-s", type=float, default=2.0,
                    help="datasets-server 兩次請求之間的間隔秒數（預設 2.0；**不要調到 0**）")
    ap.add_argument("--out", default=str(DEST))
    args = ap.parse_args()

    dest = pathlib.Path(args.out)
    dest.mkdir(parents=True, exist_ok=True)
    want = set((args.only or "").split(",")) if args.only else set(SOURCES)
    report: dict = {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "sources": {}}

    for name, spec in SOURCES.items():
        if name not in want:
            continue
        print(f"[{name}] {spec.get('dataset') or spec.get('url') or spec.get('path')}", flush=True)
        if spec["kind"] == "local":
            p = REPO / spec["path"]
            if not p.is_file():
                raise SystemExit(f"{name}: 本地來源不存在 {p}。停。")
            blob = p.read_bytes()
            rel = spec["path"]
        else:
            if spec["kind"] == "hf_rows":
                rows = fetch_rows(spec, gap_s=args.gap_s)
                blob = ("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"
                                for r in rows)).encode("utf-8")
            else:
                blob = _get(spec["url"])
            op = dest / spec["out"]
            op.parent.mkdir(parents=True, exist_ok=True)
            op.write_bytes(blob)
            rel = str(op.relative_to(REPO)) if str(op).startswith(str(REPO)) else str(op)
        report["sources"][name] = {
            "kind": spec["kind"],
            "homepage": spec["homepage"],
            "dataset": spec.get("dataset"), "config": spec.get("config"),
            "split": spec.get("split"), "url": spec.get("url"),
            "path": rel,
            "n_expected": spec["n"],
            "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "license": spec["license"],
            "license_note": spec["license_note"],
        }
        print(f"  ✓ {len(blob)} B  sha256={report['sources'][name]['sha256'][:16]}…", flush=True)

    outp = dest / "sources.json"
    outp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nsources.json → {outp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
