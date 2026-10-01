#!/usr/bin/env python3
"""build_manifest — 寫／驗 MANIFEST_REUSED.json：這個資料夾裡「從別處原樣複製過來」的每個檔案的 sha256。

為什麼要有這份：i1001 的規格說「重用第一批（colab_campaign_20260927）的工具、不要重寫；複製、不要 symlink、
把 sha256 記下來」。重用的檔案一旦被悄悄改過，這一批的結果就不能再說「用的是同一個沙箱／同一個打包程式」。
所以：
- `build_manifest.py`            寫出 MANIFEST_REUSED.json（複本的 sha256；若給 --source-root／--pr82-root，也量來源的 sha256 並比對）；
- `build_manifest.py --check`    只驗複本的 sha256 與 MANIFEST_REUSED.json 一致（測試與發射前都跑）。

來源：
- 第一批工具：分支 `origin/feat/colab-campaign-20260927` @ b19395a5 的 `ops/colab_campaign_20260927/`；
- 原生驗收橋 `native_acceptance_bridge.py`：PR #82（HEAD 23293c81）的 `ops/eval/native_acceptance_bridge.py`——
  本分支的 HEAD 還沒有這支（PR #82 還沒合進來），所以這裡是**複本**，等合進來之後改成指向 `ops/eval/` 的那一份。
`replaced`：第一批裡「沒有重用、改寫成別的」的檔案與原因（互動式要的是不同的東西，不是偷懶）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
CAMPAIGN = "ops/colab_campaign_20260927"
CAMPAIGN_REF = "origin/feat/colab-campaign-20260927@b19395a54b2e1ba01c1ff0a68d636a6a0096ec72"
PR82_REF = "PR #82 worktree HEAD 23293c81b49a92dbd0040ffcc014a75478614496 (ops/eval/native_acceptance_bridge.py)"

# (複本相對於 HERE, 來源相對於來源根, 來源說明)
REUSED: list[tuple[str, str, str]] = [
    ("vm/sandbox.sh", f"{CAMPAIGN}/sandbox.sh", CAMPAIGN_REF),
    ("vm/orproxy.py", f"{CAMPAIGN}/orproxy.py", CAMPAIGN_REF),
    ("vm/packer.py", f"{CAMPAIGN}/packer.py", CAMPAIGN_REF),
    ("vm/cu_guard.sh", f"{CAMPAIGN}/cu_guard.sh", CAMPAIGN_REF),
    ("vm/vacant_check.py", f"{CAMPAIGN}/vacant_check.py", CAMPAIGN_REF),
    ("vm/vm_setup.sh", f"{CAMPAIGN}/vm_setup.sh", CAMPAIGN_REF),
    ("scorers/code_checks.py", f"{CAMPAIGN}/scorers/code_checks.py", CAMPAIGN_REF),
    ("scorers/code_suite.py", f"{CAMPAIGN}/scorers/code_suite.py", CAMPAIGN_REF),
    ("scorers/dabench.py", f"{CAMPAIGN}/scorers/dabench.py", CAMPAIGN_REF),
    ("scorers/databench.py", f"{CAMPAIGN}/scorers/databench.py", CAMPAIGN_REF),
    ("scorers/polyglot_py.py", f"{CAMPAIGN}/scorers/polyglot_py.py", CAMPAIGN_REF),
    ("stage_code_bank.py", f"{CAMPAIGN}/stage_code_bank.py", CAMPAIGN_REF),
    ("stage_task_bank.py", f"{CAMPAIGN}/stage_task_bank.py", CAMPAIGN_REF),
    ("gauge_task3.py", f"{CAMPAIGN}/gauge_task3.py", CAMPAIGN_REF),
    ("bridge/native_acceptance_bridge.py", "ops/eval/native_acceptance_bridge.py", PR82_REF),
]

REPLACED: list[dict[str, str]] = [
    {"campaign_file": "cell.sh", "replaced_by": "vm/tui_cell.py",
     "why": "互動式 TUI（tmux）而非 `pi --print`；同樣的隔離（新使用者＋bwrap）、同樣的紀錄欄位，另加完成偵測／pane 紀錄／sessions"},
    {"campaign_file": "driver.py", "replaced_by": "vm/driver_i1001.py",
     "why": "一個單位是 A／C 兩條線＋接在 A 之後的 R／K 兩條巢狀分支；位置數以「同時在跑的 pi 對話」計；void 重跑一次"},
    {"campaign_file": "feasibility.py", "replaced_by": "vm/feasibility_i1001.py",
     "why": "原規則「逾時率 ≥30% 就停」不能用：這批的題池是 C5 的 A 失敗題，近六成本來就會撞 1800 秒；"
            "改看 void 率／非 200 率／C 安裝失敗，逾時只記錄"},
    {"campaign_file": "analyze.py", "replaced_by": "analyze_i1001.py",
     "why": "預註冊的檢定換成 K 對 R、C 對 A 兩個主要檢定＋Holm"},
    {"campaign_file": "launch_batch.sh", "replaced_by": "launch_i1001.sh",
     "why": "起的是 packer＋feasibility_i1001＋driver_i1001（auto：篩選→天花板規則→主跑）；發射紀錄多釘 tmux／bridge／plan"},
    {"campaign_file": "deploy_vm.sh", "replaced_by": "deploy_i1001.sh",
     "why": "wheel 由本機從 HEAD 建好直接給（不在 VM 上重建）；多裝 tmux／bridge venv／receivers 目錄"},
    {"campaign_file": "sync_from_colab.sh", "replaced_by": "sync_i1001.sh",
     "why": "同樣照 MANIFEST.tsv 用 `colab download` 拉＋驗 sha256；Drive 鏡像作第二份；VERIFIED.tsv 給 autostop 讀"},
]


def sha256(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build(source_root: pathlib.Path | None, pr82_root: pathlib.Path | None) -> dict:
    rows = []
    for copy, src, ref in REUSED:
        row = {"copy": copy, "copy_sha256": sha256(HERE / copy), "source": src, "source_ref": ref,
               "verbatim": True, "source_sha256": None, "source_checked": False}
        root = pr82_root if src.startswith("ops/eval/") else source_root
        if root is not None and (root / src).is_file():
            row["source_sha256"] = sha256(root / src)
            row["source_checked"] = True
            row["verbatim"] = row["source_sha256"] == row["copy_sha256"]
        rows.append(row)
    return {"schema": "i1001.manifest_reused/1", "rows": rows, "replaced_not_reused": REPLACED}


def check(manifest: dict) -> list[str]:
    bad = []
    recorded = {r["copy"]: r["copy_sha256"] for r in manifest["rows"]}
    for copy, _src, _ref in REUSED:
        p = HERE / copy
        if not p.is_file():
            bad.append(f"{copy}: missing")
        elif copy not in recorded:
            bad.append(f"{copy}: not in MANIFEST_REUSED.json")
        elif sha256(p) != recorded[copy]:
            bad.append(f"{copy}: sha256 differs from MANIFEST_REUSED.json (a reused file was edited)")
    for r in manifest["rows"]:
        if r.get("source_checked") and not r.get("verbatim"):
            bad.append(f"{r['copy']}: copy differs from its source at copy time")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--source-root", type=pathlib.Path, help="checkout of origin/feat/colab-campaign-20260927")
    ap.add_argument("--pr82-root", type=pathlib.Path, help="checkout of PR #82 (for native_acceptance_bridge.py)")
    a = ap.parse_args()
    mp = HERE / "MANIFEST_REUSED.json"
    if a.check:
        bad = check(json.loads(mp.read_text()))
        for b in bad:
            print("MANIFEST_REUSED:", b)
        print("OK" if not bad else f"{len(bad)} problem(s)")
        return 1 if bad else 0
    m = build(a.source_root, a.pr82_root)
    bad = check(m)
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote {mp} ({len(m['rows'])} reused files)")
    for b in bad:
        print("WARNING:", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
