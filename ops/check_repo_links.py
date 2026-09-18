#!/usr/bin/env python3
"""死連結／死路徑擋門：repo 裡指向不存在檔案的引用，一個都不准有。

這支在架構裡承重什麼：2026-09-18 把 227 份實驗紀錄從根目錄搬進 `decisions/`
之後，「引用還對不對」不能靠人眼。本檔把四類引用各自變成可執行的檢查：

  1. markdown 相對連結     `[文字](路徑)`、`[文字](路徑#錨點)`
  2. 程式裡的路徑字面值     `ROOT / "..."`、`REPO / "..."`
  3. 發射指令              `--decision <路徑>`
  4. GitHub 絕對網址        `https://github.com/cosmopig/Vacant/blob/<ref>/<路徑>`

誠實邊界（改碼時保留這句）：本檔擋的是**指向不存在的檔案**，不是「引用內容正確」。
連結指到存在但講錯話的檔案，這支一樣會放行——它是死連結擋門，不是事實查核。

刻意不判紅、但一定印出來的兩類（**具名、可數、有理由**，不是安靜跳過）：

  1. `_HISTORICAL`：`runs/**` 的 `*.launch.log` 等落盤紀錄。那是「當時實際下了
     什麼指令」的證據，路徑過期是**史實**不是錯誤，改掉才是說謊。
  2. `decisions/**` 裡的 `--decision <舊路徑>` 逐塊發射指令（見 `_FROZEN_RECORD_DIRS`）。
     裁決／預註冊檔是證據，2026-09-18 的搬家**只動位置不動內容**：
     · `docs/paper_2026-09-14/source_manifest.json` 對其中 13 份釘了 sha256（現況 28/29 相符），
       改內文會讓那份出處紀錄安靜失效；
     · 預註冊的重點就是「發射前凍結」，事後改寫它記載的指令 ＝ 讓紀錄描述一個
       從沒下過的指令。
     **代價寫在這裡，不要假裝沒有**：照抄那些指令會被 R440G 閘門擋下
     （`拒絕啟動：DECISION 檔不存在`）。那是 fail-closed，不是安靜跑錯——
     自己補上 `decisions/` 前綴即可。新一輪的實際發射走的是
     `ops/gain/r5xx/*_queue.sh`，那些已經指向新路徑。

用法：
  python3 ops/check_repo_links.py            # rc=0 全過；rc=1 有死連結
  python3 ops/check_repo_links.py --verbose  # 連歷史紀錄與統計一起印
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 歷史落盤紀錄：路徑過期是史實，不判紅（見模組 docstring）
_HISTORICAL = (".launch.log", ".log", ".jsonl")

# 凍結的紀錄目錄：裡面的 `--decision` 舊路徑不判紅（理由見模組 docstring 第 2 點）。
# ⚠ 只赦免 `launch` 這一類。同一份檔案裡的 markdown 死連結照樣判紅。
_FROZEN_RECORD_DIRS = ("decisions/",)

# 具名排除（不是安靜跳過）：這些目標**本來就不該存在於工作樹**。
# 每一筆都要寫得出理由，沒理由的不准進這張表。
_NAMED_EXCLUSIONS: dict[str, str] = {
    "STATE.md": "迴圈每輪產生的狀態檔，未跑過就沒有；`ops/progress.py` 自帶缺檔預設字串",
    "PROGRESS.md": "同上，迴圈產物",
    "ops/gain/_r458_pre_tmp.py": "R456 量測時寫出、量完刪掉的暫存腳本",
    "ops/gain/data/_r494_mut.json": "R494 突變檢查的輸出檔，跑完即刪",
    "ops/gain/data/_r497_mut_tmp.json": "R497 突變檢查的輸出檔，跑完即刪",
    "ops/gain/data/_r498_mut_tmp.json": "R498 突變檢查的輸出檔，跑完即刪",
    "D.md": "`tests/test_r530_scheduler.py` 合成的假 `ps` 輸出，不是真路徑",
    "DECISION_20260913_R530_….md": "`run_r530.py` docstring 的用法示例，含刪節號的佔位符",
}

# markdown 連結：排除 http(s)/mailto/純錨點
_MD_LINK = re.compile(r"\[[^\]^]*\]\(\s*(?!https?:|mailto:|data:|#)([^)\s]+?)\s*\)")
# 程式裡的路徑字面值：ROOT / "xxx"、REPO / "xxx"（只認單段字面值）。
# ⚠ 只認**指向 repo 根**的那兩個名字。`BASE` 之類是各腳本自己的子目錄錨點
# （例如 `docs/paper_2026-09-14/build_paper.py` 的 `BASE`），拿 ROOT 去解會全部假紅。
_PY_PATH = re.compile(r"\b(?:ROOT|REPO)\s*/\s*[\"']([^\"']+\.(?:md|py|json|txt|sh))[\"']")
# 發射指令
_DECISION_ARG = re.compile(r"--decision[=\s]+([^\s\"'\\`]+\.md)")
# GitHub 絕對網址（blob/tree）
_GH_URL = re.compile(
    r"https://github\.com/cosmopig/Vacant/(?:blob|tree)/[^/\s]+/"
    r"([^)\s\"'<>,、。]+)")


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"],
                         capture_output=True, text=True, check=True).stdout
    return [x for x in out.split("\n") if x]


def _exists(rel: str) -> bool:
    rel = rel.split("#", 1)[0].strip()
    if not rel:
        return True                      # 純錨點
    p = (ROOT / rel)
    return p.exists()


def scan() -> tuple[list[tuple], list[tuple]]:
    """回傳 (dead, historical)。每筆 = (kind, file, lineno, target, line)。"""
    dead: list[tuple] = []
    historical: list[tuple] = []
    for rel in tracked_files():
        p = ROOT / rel
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        is_hist = rel.endswith(_HISTORICAL)
        base = Path(rel).parent
        for i, line in enumerate(text.split("\n"), 1):
            found: list[tuple[str, str, str]] = []   # (kind, target, resolve_base)

            # `llms.txt` 是給模型讀的索引，用的也是 markdown 連結語法 ⇒ 一起掃
            if rel.endswith(".md") or rel == "llms.txt":
                for t in _MD_LINK.findall(line):
                    found.append(("md_link", t, "rel"))
            if rel.endswith((".py", ".sh")):
                for t in _PY_PATH.findall(line):
                    found.append(("py_path", t, "root"))
            for t in _DECISION_ARG.findall(line):
                found.append(("launch", t, "root"))
            for t in _GH_URL.findall(line):
                found.append(("gh_url", t.rstrip(").,、。"), "root"))

            for kind, target, mode in found:
                tgt = target.split("#", 1)[0].strip()
                if not tgt or tgt.startswith(("<", "$", "{")):
                    continue             # 樣板佔位符
                if tgt in _NAMED_EXCLUSIONS:
                    continue             # 具名排除，理由在 _NAMED_EXCLUSIONS
                if mode == "rel":
                    cand = (base / tgt).as_posix()
                    # 正規化 ../
                    try:
                        cand = str(Path(cand).resolve().relative_to(ROOT))
                    except (ValueError, OSError):
                        continue         # 指到 repo 之外，不管
                else:
                    cand = tgt
                if _exists(cand):
                    continue
                rec = (kind, rel, i, target, line.strip()[:160])
                frozen = kind == "launch" and rel.startswith(_FROZEN_RECORD_DIRS)
                (historical if (is_hist or frozen) else dead).append(rec)
    return dead, historical


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    dead, historical = scan()

    if a.verbose and historical:
        print(f"historical（歷史落盤紀錄，刻意不判紅）：{len(historical)} 筆")
        for kind, f, i, tgt, line in historical:
            print(f"  [{kind}] {f}:{i} -> {tgt}")
        print()

    if dead:
        print(f"死連結 {len(dead)} 筆：")
        for kind, f, i, tgt, line in dead:
            print(f"  [{kind}] {f}:{i} -> {tgt}")
            print(f"        {line}")
        return 1

    n_hist = (f"（另有 {len(historical)} 筆歷史／凍結紀錄，具名不判紅，"
              f"用 --verbose 看清單）") if historical else ""
    print(f"OK：沒有死連結／死路徑{n_hist}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
