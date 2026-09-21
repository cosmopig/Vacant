#!/usr/bin/env python3
"""三句假話 ＋「信任」掃**整個展件頁**，而且分得出註解與螢幕字串。

## 為什麼要這一支

三句話今天是假的或越級，任何**螢幕上的文案**都不准出現（人類 2026-09-21）：

  1 「你可以隨時要求我們刪除」 —— 文案要對得上實際行為。
  2 「每一通模型呼叫都經過 Vacant」 —— 那是 **A 級**的句子；展場這批是 **C 級**。
  3 「抬頭看螢幕」 —— 手機喊這句的時候，台上那一隻**已經演完、記號正在退場**
      （讀碼查證過的時序）。

再加 CLAUDE.md 口徑 5：不要用「**信任**」，用「可究責／讓依賴有根據」。

## 為什麼不能只 `grep -c`

這四個詞在 repo 裡**大量**出現在註解與規格宣告裡——而且**應該**出現：
`seam_ending.js` 開頭那一段誠實邊界就逐條寫著「不寫 X」。一支只會數命中的
掃描器會把「我們寫下了這條禁令」算成「我們違反了這條禁令」，
然後所有人開始忽略它。⇒ 必須**分類**：註解／規格宣告 vs 真的會畫到螢幕上的字串。

## 🔴 分類器自己的負控制

一把分不出來的尺回報「零違規」跟一把分得出來的尺回報「零違規」**印出來一模一樣**。
所以開跑之前先餵六條手搓的假行，六條都判對才往下跑（`--selftest` 單獨看）：
四條該判註解、一條該判螢幕字串、一條該完全不命中。
有一條判錯就直接 exit 2，**不掃、也不回報綠燈**。

## 退出碼

    0  螢幕字串零違規
    1  有螢幕字串違規（或分不出來的命中——fail-closed）
    2  分類器自己的負控制沒過 / 檔案讀不到

用法：
    python3 forbidden_scan.py                 # 掃預設那一組展件檔
    python3 forbidden_scan.py --verbose       # 連註解命中一起列（數得出來）
    python3 forbidden_scan.py --selftest      # 只跑分類器的負控制
    python3 forbidden_scan.py --root <展件根>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_ROOT = Path("/Users/cosmopig/Documents/GitHub/vacant_hm")

TARGETS = [
    "world3/index.html",
    "world3/bridge.js",
    "world3/twinseam.js",
    "world3/scenes/seam_ending.js",
    "world3/twinseam.html",
    "world3/scenes/narrative_order.json",
    "world3/scenes/index.json",
]

BANNED = {
    "你可以隨時要求我們刪除": "撤回入口的實際行為對不上這句話。",
    "每一通模型呼叫都經過 Vacant": "A 級的句子；展場這批是 C 級。",
    "抬頭看螢幕": "手機喊這句時台上那一隻已經演完、記號正在退場。",
    "信任": "CLAUDE.md 口徑 5：用「可究責／讓依賴有根據」。",
}

# 具名排除：**數得出來、不是安靜跳過**。
# narrative_order.json 的 `forbidden_lines` 區塊就是拿來寫下這些禁語的，
# 那裡出現＝規格宣告，不是文案。
NAMED_EXEMPT_KEYS = ("forbidden_lines", "禁語", "banned")

QUOTES = ("\"", "'", "`")


def classify(line: str, phrase: str, in_block: bool, is_html: bool) -> str:
    """這一行的這一個命中，是註解還是螢幕字串。

    回傳："註解" ／ "螢幕字串" ／ "分不出來"（fail-closed 當違規算）。
    """
    if in_block:
        return "註解"
    pos = line.find(phrase)
    if pos < 0:
        return "分不出來"
    head = line[:pos]
    # 行內 // 註解（`//` 之前沒有引號開著才算，免得把字串裡的 http:// 誤判）
    slash = head.find("//")
    if slash >= 0 and head[:slash].count('"') % 2 == 0 and head[:slash].count("'") % 2 == 0:
        return "註解"
    if head.lstrip().startswith("*"):          # 區塊註解的續行
        return "註解"
    if head.lstrip().startswith("#"):          # python/sh
        return "註解"
    if "<!--" in head and "-->" not in head:   # HTML 註解
        return "註解"
    if is_html and "<!--" in head:
        return "註解"
    # 引號裡面 ⇒ 會被畫出來的字串
    for q in QUOTES:
        if head.count(q) % 2 == 1:
            return "螢幕字串"
    # 引號成對但片語自己被引號夾住（例：`head: "…信任…"` 已由上面抓到；
    # 這裡處理 `「信任」` 這種中文引號包在一般文字裡的情形）
    return "分不出來"


def scan_text(text: str, is_html: bool, is_json: bool):
    """回傳 [(行號, 片語, 分類, 行內容)]。"""
    hits = []
    in_block = False
    json_exempt_depth = None
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw
        if is_json:
            # JSON 沒有註解。具名排除：`forbidden_lines` 那個物件之內算規格宣告。
            if any(f'"{k}"' in line for k in NAMED_EXEMPT_KEYS):
                json_exempt_depth = line.count(" ") - len(line.lstrip())
            elif json_exempt_depth is not None:
                indent = len(line) - len(line.lstrip())
                if line.strip() and indent <= json_exempt_depth:
                    json_exempt_depth = None
        before_block = in_block
        if not is_json:
            # 粗略追蹤 /* … */。夠用：這幾個檔沒有字串裡放 /* 的寫法。
            if not in_block and "/*" in line and "*/" not in line.split("/*", 1)[1]:
                in_block = True
                before_block = False if line.index("/*") > 0 else True
            elif in_block and "*/" in line:
                in_block = False
                before_block = True
        for phrase in BANNED:
            if phrase in line:
                if is_json:
                    kind = "規格宣告" if json_exempt_depth is not None else "螢幕字串"
                    # JSON 裡的說明欄位（`_`／`why`／`honest`…）也是規格文字，
                    # 但它們**不會被畫到螢幕上**。只有 `head`／`sub` 會。
                    key = line.strip().split('"')[1] if line.strip().startswith('"') else ""
                    if kind == "螢幕字串" and key not in ("head", "sub", "sub_many"):
                        kind = "規格宣告"
                else:
                    kind = classify(line, phrase, before_block or in_block, is_html)
                hits.append((i, phrase, kind, line.strip()[:140]))
    return hits


SELFTEST = [
    ('  this.titleOv = { head: "他還在", sub: "你可以隨時要求我們刪除" };',
     "你可以隨時要求我們刪除", False, False, "螢幕字串"),
    ('  // ❌ 不寫「你可以隨時要求我們刪除」——撤回入口還沒做好。',
     "你可以隨時要求我們刪除", False, False, "註解"),
    ('   *  ❌ 不用「信任」（CLAUDE.md 口徑 5）。',
     "信任", False, False, "註解"),
    ('  <!-- 每一通模型呼叫都經過 Vacant 這句不准印 -->',
     "每一通模型呼叫都經過 Vacant", False, True, "註解"),
    ('    const t = { head: "現在，抬頭看螢幕" };',
     "抬頭看螢幕", False, False, "螢幕字串"),
    ('    const t = { head: "他上場了 · 去看他的卡" };',
     None, False, False, None),
]


def selftest(verbose: bool) -> bool:
    ok = True
    for line, phrase, in_block, is_html, want in SELFTEST:
        if phrase is None:
            got = "（無命中）" if not any(p in line for p in BANNED) else "命中了"
            good = got == "（無命中）"
        else:
            got = classify(line, phrase, in_block, is_html)
            good = got == want
        ok = ok and good
        if verbose or not good:
            print(f"  [{'OK    ' if good else 'BROKEN'}] 想要={want} 得到={got}  {line.strip()[:70]}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    print("== 分類器自己的負控制（六條手搓假行）==")
    if not selftest(True):
        print("🔴 分類器判錯 ⇒ 這一次**不掃**，也不回報綠燈。")
        return 2
    print("  六條都判對。")
    if a.selftest:
        return 0

    print("\n== 掃描 ==")
    violations = []
    counts = {"螢幕字串": 0, "註解": 0, "規格宣告": 0, "分不出來": 0}
    missing = []
    for rel in TARGETS:
        p = a.root / rel
        if not p.is_file():
            missing.append(rel)
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        hits = scan_text(text, rel.endswith(".html"), rel.endswith(".json"))
        for n, phrase, kind, line in hits:
            counts[kind] = counts.get(kind, 0) + 1
            if kind in ("螢幕字串", "分不出來"):
                violations.append((rel, n, phrase, kind, line))
            elif a.verbose:
                print(f"  [{kind}] {rel}:{n}  「{phrase}」  {line}")
        print(f"  {rel}: 命中 {len(hits)} 條"
              + (f"（違規 {sum(1 for h in hits if h[2] in ('螢幕字串','分不出來'))}）"
                 if hits else ""))

    if missing:
        # 掃不到的檔**要說出來**：一支掃不到目標的尺不該回報通過。
        print(f"\n🔴 這幾個目標不存在，這一次沒掃到：{'／'.join(missing)}")
        return 2

    print(f"\n分類統計：{json.dumps(counts, ensure_ascii=False)}")
    if violations:
        print("\n🔴 螢幕字串違規：")
        for rel, n, phrase, kind, line in violations:
            print(f"  {rel}:{n}  [{kind}]  「{phrase}」  {line}")
            print(f"       理由：{BANNED[phrase]}")
        return 1
    print("✅ 螢幕字串零違規（註解／規格宣告的命中數列在上面，不是零、也不該是零）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
