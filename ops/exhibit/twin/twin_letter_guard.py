#!/usr/bin/env python3
"""twin/twin_letter_guard — 段 1 與段 2 之間的確定性關卡（只用標準函式庫）。

這支在架構裡承重什麼：W3b 的「先寫信、再進世界」。分身第一個回合讀 TRAITS.md、寫 信.md；
**這支在 pi 結束之後、第二個回合之前**做四件事（順序不能換，TRAITS 的移走在最前面、
任何失敗都照做）：

1. 把 TRAITS.md 從工作區移走（刪掉）。第二回合的房間裡沒有它。
2. 工作區頂層除了 信.md 以外的檔全部刪掉（第一回合若把特質抄去別的檔，一起清）。
3. 信.md 防呆：與 TRAITS 連續 ≥ `LEAK_WINDOW`（8）字相同的句子刪掉、含時段詞（`TIME_WORDS`）的句子刪掉；總長上限 `MAX_LETTER`（300）字。
4. 把 `<run_dir>/stage2_in/` 裡預先備好的 WORLD.md 與 地上/ 搬進工作區（唯讀）。
   段 1 的分身看不到它們。

信.md 空了／不存在 ⇒ 結束碼 4（第二回合不起）。`<run_dir>/letter_guard.json` 只記計數，不記內容。
⚠ 信是觀眾資料（由特質寫出來的）：撤回時由 `twinagent.erase_run_artifacts` 一起刪、列進抹除清單。
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import shutil
import sys

LEAK_WINDOW = 8
MAX_LETTER = 300
#: 時段詞：信裡出現就整句刪（「時間點」是現實具體事物；世界裡沒有時段）。這是窄名單，不是完備的現實偵測。
TIME_WORDS = ("清晨", "凌晨", "深夜", "半夜", "夜裡", "夜晚", "夜間", "早晨", "早上", "傍晚", "黃昏",
              "中午", "午後", "晚上", "週末", "假日", "星期", "每天", "每週", "每個月", "每年", "年底", "春天",
              "夏天", "秋天", "冬天")
LETTER = "信.md"
_SPLIT = re.compile(r"(?<=[。！？!?；;\n])")


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s)


def shares_window(sentence: str, source: str, window: int = LEAK_WINDOW) -> bool:
    a, b = _norm(sentence), _norm(source)
    if len(a) < window:
        return False
    return any(a[i:i + window] in b for i in range(len(a) - window + 1))


def clean_letter(letter: str, traits: str) -> tuple[str, dict]:
    """刪掉與 traits 連續 ≥8 字相同的句子，再截到 300 字。回（乾淨的信, 計數）。"""
    parts = [p for p in _SPLIT.split(letter) if p.strip()]
    kept, dropped, dropped_time = [], 0, 0
    for p in parts:
        if shares_window(p, traits):
            dropped += 1
        elif any(w in p for w in TIME_WORDS):
            dropped_time += 1
        else:
            kept.append(p)
    out, n = [], 0
    for p in kept:
        if n + len(p) > MAX_LETTER:
            if not out:
                out.append(p[:MAX_LETTER])
            break
        out.append(p)
        n += len(p)
    text = "".join(out).strip()
    return text, {"sentences": len(parts), "dropped_leak": dropped, "dropped_time": dropped_time,
                  "chars_before": len(letter), "chars_after": len(text),
                  "truncated": sum(len(p) for p in kept) > len(text)}


def run(ws: pathlib.Path, rd: pathlib.Path) -> int:
    ws, rd = pathlib.Path(ws), pathlib.Path(rd)
    traits_p, letter_p = ws / "TRAITS.md", ws / LETTER
    try:
        traits = traits_p.read_text(encoding="utf-8", errors="replace") if traits_p.is_file() else ""
    except OSError:
        traits = ""
    info: dict = {"traits_removed": False, "letter_present": letter_p.is_file()}
    try:
        # 1. 先移走 TRAITS（之後任何一步出錯，房間裡都已經沒有它）
        try:
            traits_p.unlink()
        except FileNotFoundError:
            pass
        info["traits_removed"] = not traits_p.exists()
        # 2. 頂層其他檔（含第一回合寫去別處的）全清，只留信
        for p in sorted(ws.iterdir()):
            if p.name == LETTER:
                continue
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p)
            else:
                p.unlink()
        # 3. 信
        if not letter_p.is_file() or letter_p.is_symlink():
            info["ok"] = False
            return 4
        raw = letter_p.read_text(encoding="utf-8", errors="replace")
        text, cnt = clean_letter(raw, traits)
        info.update(cnt)
        if not text:
            letter_p.unlink()
            info["ok"] = False
            return 4
        letter_p.write_text(text + "\n", encoding="utf-8")
        # 4. 世界與地上進房間（唯讀）
        src = rd / "stage2_in"
        if (src / "WORLD.md").is_file():
            shutil.copyfile(src / "WORLD.md", ws / "WORLD.md")
            (ws / "WORLD.md").chmod(0o444)
        if (src / "地上").is_dir():
            shutil.copytree(src / "地上", ws / "地上")
        info["ok"] = True
        return 0
    finally:
        try:
            (rd / "letter_guard.json").write_text(
                json.dumps(info, ensure_ascii=False) + "\n", encoding="utf-8")
        except OSError:
            pass


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("用法：twin_letter_guard.py <工作區> <run_dir>", file=sys.stderr)
        sys.exit(2)
    sys.exit(run(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])))
