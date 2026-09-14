#!/usr/bin/env python3
"""R530 題庫的載入與釘死——**題目是資料不是程式**（R452 的同一條紀律）。

一題 ＝ 兩個目錄：

    ops/gain/r530/templates/<task_id>/     ← 工作區樣板（worker 看得到全部）
        goal.md            目標敘述（不給步驟、不給演算法、不給資料結構）
        contract.md        介面契約（語意的釘死點）
        tests_visible/     2–3 條可見驗收（**也是出貨閘門**）
        run_tests.sh       一行：跑可見驗收（worker 可以自己跑）
    ops/gain/r530/hidden/<task_id>/        ← 隱藏驗收（**永遠不進工作區**）
        test_*.py          ≥10 條

＋ 選配的量具樁：

    ops/gain/r530/gauge/<task_id>/
        good.py            參考解（必須**全過**可見與隱藏）
        bad_*.py           已知壞樁（每一個都**必須被擋**）

格式的完整規格在 `ops/gain/r530/TASK_FORMAT.md`。這支只做三件事：
載入、算 sha256、**對不上就拒跑**。

⚠ **`bank_sha256` 是發射閘門不是裝飾**（預註冊 §五-5 E-2）：
  題庫的逐檔 sha256 要在 AMEND1 裡釘死，發射器與 analyzer 都逐檔比對，
  對不上就 `abort_bank_sha_mismatch`。本支提供 `bank_manifest()` 產生那份表，
  與 `assert_bank_matches()` 做比對。**沒有那份表的時候不假裝有**——
  `--bank-sha` 沒給就在 summary 裡記 `bank_sha_pinned: false`，
  不准讓「沒有釘」看起來像「釘了而且過了」。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))

from ops.gain.r530 import wshash  # noqa: E402

R530_DIR = pathlib.Path(__file__).resolve().parent
TEMPLATES_DIR = R530_DIR / "templates"
HIDDEN_DIR = R530_DIR / "hidden"
GAUGE_DIR = R530_DIR / "gauge"

VISIBLE_SUBDIR = "tests_visible"
GOAL_FILE = "goal.md"
CONTRACT_FILE = "contract.md"

#: 樣板大小的上下界（Fable 裁決：10–30 KB）。超出就拒收——
#: 一個 200 KB 的樣板代表題目裡塞了不該塞的東西（例如一份參考實作）。
TEMPLATE_MIN_BYTES = 200
TEMPLATE_MAX_BYTES = 30 * 1024


class TaskBankError(SystemExit):
    """題庫不合格。**fail-closed**：載不起來不是「這一題跳過」，是停。"""


def task_ids(templates_dir: pathlib.Path = TEMPLATES_DIR) -> list[str]:
    if not templates_dir.is_dir():
        return []
    return sorted(p.name for p in templates_dir.iterdir()
                  if p.is_dir() and not p.name.startswith("_"))


def load_task(task_id: str, *, templates_dir: pathlib.Path = TEMPLATES_DIR,
              hidden_dir: pathlib.Path = HIDDEN_DIR) -> dict:
    """載入一題。缺任何一件東西就 `TaskBankError`。"""
    tpl = templates_dir / task_id
    hid = hidden_dir / task_id
    if not tpl.is_dir():
        raise TaskBankError(f"題目樣板不存在：{tpl}。停。")
    if not hid.is_dir():
        raise TaskBankError(f"隱藏驗收不存在：{hid}。停。")
    goal_p, contract_p = tpl / GOAL_FILE, tpl / CONTRACT_FILE
    for p in (goal_p, contract_p):
        if not p.is_file():
            raise TaskBankError(f"題目缺 {p.name}：{p}。停。")
    vis = tpl / VISIBLE_SUBDIR
    if not vis.is_dir():
        raise TaskBankError(f"題目缺 {VISIBLE_SUBDIR}/：{vis}。停。")
    vis_files = sorted(p.name for p in vis.glob("test_*.py"))
    hid_files = sorted(p.name for p in hid.glob("test_*.py"))
    if not vis_files:
        raise TaskBankError(f"{task_id} 的 {VISIBLE_SUBDIR}/ 裡沒有 test_*.py。停。")
    if not hid_files:
        raise TaskBankError(f"{task_id} 的 hidden/ 裡沒有 test_*.py。停。")
    manifest = wshash.tree_manifest(tpl)
    if not (TEMPLATE_MIN_BYTES <= manifest["bytes_n"] <= TEMPLATE_MAX_BYTES):
        raise TaskBankError(
            f"{task_id} 的樣板是 {manifest['bytes_n']} bytes，"
            f"超出 {TEMPLATE_MIN_BYTES}–{TEMPLATE_MAX_BYTES} 的約定"
            "（Fable 2026-09-13 裁決：10–30 KB）。停。")
    # 結構性紅線：樣板裡不准有任何看起來像隱藏驗收的東西。
    for leaf in manifest["leaves"]:
        low = leaf["path"].lower()
        if "hidden" in low or "rubric" in low:
            raise TaskBankError(
                f"{task_id} 的樣板裡有 {leaf['path']}——"
                "隱藏驗收與評分表永遠不進工作區（§五-3 第 1 條）。停。")
    return {
        "task_id": task_id,
        "goal": goal_p.read_text(encoding="utf-8"),
        "contract": contract_p.read_text(encoding="utf-8"),
        "template_dir": tpl,
        "visible_dir": vis,
        "hidden_dir": hid,
        "gauge_dir": GAUGE_DIR / task_id,
        "visible_files": vis_files,
        "hidden_files": hid_files,
        "template_sha256": manifest["ws_sha256"],
        "template_bytes": manifest["bytes_n"],
        "hidden_sha256": wshash.tree_hash(hid),
    }


def resolve_task_set(spec: str, *, templates_dir: pathlib.Path = TEMPLATES_DIR
                     ) -> list[str]:
    """`all` ／ 逗號分隔的 task_id ／ `@<path>.json`（含 `tasks` 陣列）。"""
    spec = (spec or "").strip()
    if not spec:
        raise TaskBankError("--task-set 是空的。停。")
    if spec == "all":
        ids = task_ids(templates_dir)
        if not ids:
            raise TaskBankError(f"{templates_dir} 底下一題都沒有。停。")
        return ids
    if spec.startswith("@"):
        p = pathlib.Path(spec[1:])
        if not p.is_file():
            raise TaskBankError(f"題目集檔不存在：{p}。停。")
        raw = json.loads(p.read_text(encoding="utf-8"))
        ids = raw.get("tasks") if isinstance(raw, dict) else raw
        if not isinstance(ids, list) or not ids:
            raise TaskBankError(f"{p} 裡沒有非空的 tasks 陣列。停。")
        return [str(x) for x in ids]
    return [s.strip() for s in spec.split(",") if s.strip()]


def load_tasks(spec: str, *, templates_dir: pathlib.Path = TEMPLATES_DIR,
               hidden_dir: pathlib.Path = HIDDEN_DIR) -> list[dict]:
    return [load_task(t, templates_dir=templates_dir, hidden_dir=hidden_dir)
            for t in resolve_task_set(spec, templates_dir=templates_dir)]


def bank_manifest(tasks: list[dict]) -> dict:
    """逐題逐檔的 sha256——AMEND1 要釘死的那一份表。"""
    out: dict = {}
    for t in tasks:
        files: dict[str, str] = {}
        for leaf in wshash.tree_leaves(t["template_dir"]):
            files[f"templates/{t['task_id']}/{leaf['path']}"] = leaf["sha256"]
        for leaf in wshash.tree_leaves(t["hidden_dir"]):
            files[f"hidden/{t['task_id']}/{leaf['path']}"] = leaf["sha256"]
        out[t["task_id"]] = {
            "template_sha256": t["template_sha256"],
            "hidden_sha256": t["hidden_sha256"],
            "files": dict(sorted(files.items())),
        }
    out["_root_sha256"] = hashlib.sha256(
        json.dumps({k: v for k, v in sorted(out.items())},
                   sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")).hexdigest()
    return out


def assert_bank_matches(tasks: list[dict], pinned_path: str | pathlib.Path) -> dict:
    """與釘死的表逐檔比對。對不上 ⇒ `abort_bank_sha_mismatch`。"""
    p = pathlib.Path(pinned_path)
    if not p.is_file():
        raise TaskBankError(f"abort_bank_sha_mismatch：釘死的表不存在 {p}。停。")
    pinned = json.loads(p.read_text(encoding="utf-8"))
    now = bank_manifest(tasks)
    bad: list[str] = []
    for tid in sorted(t["task_id"] for t in tasks):
        want = (pinned.get(tid) or {}).get("files") or {}
        got = (now.get(tid) or {}).get("files") or {}
        for k in sorted(set(want) | set(got)):
            if want.get(k) != got.get(k):
                bad.append(f"{k}: pinned={want.get(k)} now={got.get(k)}")
    if bad:
        raise TaskBankError(
            "abort_bank_sha_mismatch：題庫與釘死的表對不上\n  "
            + "\n  ".join(bad[:40]) + "\n停。")
    return now


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="R530 題庫檢查／manifest（零模型呼叫）")
    ap.add_argument("--task-set", default="all")
    ap.add_argument("--manifest", default=None, help="把 manifest 寫成 JSON")
    args = ap.parse_args()
    tasks = load_tasks(args.task_set)
    man = bank_manifest(tasks)
    for t in tasks:
        print(f"{t['task_id']:22} template={t['template_sha256'][:12]}… "
              f"{t['template_bytes']:>6}B  visible={len(t['visible_files'])} "
              f"hidden={len(t['hidden_files'])}")
    print(f"\n_root_sha256 = {man['_root_sha256']}")
    if args.manifest:
        p = pathlib.Path(args.manifest)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
        print(f"manifest → {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
