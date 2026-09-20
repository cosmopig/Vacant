"""twin/probe_pii_filter — 證明公網那一頁的個資過濾器會誤殺日期。

## 為什麼這支存在

2026-09-20 端到端實跑時，一張**完全沒有個資**的卡被線上服務退回 422
（「請拿掉可識別資訊再送」）。原因是 `vacant-world-cloud/server.js` 的

```js
const PHONE_RE = /\\+?\\d(?:[\\s-]?\\d){7,}/;
```

——「8 位以上、允許空白或連字號隔開的數字串」。`2026-09-20` 攤平就是
**2,0,2,6,0,9,2,0 共 8 位數字，中間只隔連字號**，完全命中。

那個 repo 的註解自己寫了「寬到會誤殺長流水號，但這頁的正當內容不該出現那種東西，
寧可誤殺」。**日期不是長流水號**，而且觀眾寫「我想在 10/15 之前做完」「2026 年底前」
這種話是這張卡最自然的內容之一（第一欄就叫「需求：我最近想完成的一件具體的小事」）。

## 這在展場會怎麼出事

觀眾站在機器前面，用自己的 AI 生了一張卡、複製、貼上、送出，畫面回他
**「請拿掉可識別資訊再送」**。他的卡上沒有任何可識別資訊。他不知道要拿掉什麼，
而旁邊沒有解說員（CLAUDE.md 展場硬約束 2）。最可能的結果是**他放棄走人**——
而且我們的 log 只會看到一個 422，看不到「這個人本來要參加」。

⚠ **這支只負責證明，不負責修。** 要怎麼收（放寬 regex？只擋真的像電話的？
還是把訊息從「請拿掉可識別資訊」改成指出**是哪一段**被判定？）牽涉到
「寧可誤殺」這個既有取捨，那是人類的決定。

用法：
    python3 ops/exhibit/twin/probe_pii_filter.py            # 本機確定性重現
    python3 ops/exhibit/twin/probe_pii_filter.py --live     # 加打線上服務對照
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request

#: 逐字抄自 `vacant-world-cloud/server.js`（2026-09-20 當下的線上版本）。
#: 抄而不是 import，是因為那是 JS；抄過來就有義務在對面改動時跟著改——
#: `--live` 模式就是用來抓「兩邊漂掉了」的。
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d(?:[\s-]?\d){7,}")

LIVE = "https://vacant-world.cosmopig.com"


def blocked(text: str) -> bool:
    return bool(EMAIL_RE.search(text)) or bool(PHONE_RE.search(text))


#: （卡的內容, 應該被擋嗎, 這是什麼）
CASES: list[tuple[str, bool, str]] = [
    # --- 正控制：真的該擋的 ---
    ("需求：寄給我 a@b.com", True, "真的 email"),
    ("需求：打給 0912345678", True, "真的手機號碼"),
    ("需求：聯絡 0912-345-678", True, "有連字號的手機號碼"),
    ("需求：打 +886912345678", True, "國碼手機"),

    # --- 🔴 誤殺：完全沒有個資，卻被擋 ---
    ("需求：在 2026-09-20 之前整理好桌面", False, "ISO 日期（展場最常見）"),
    ("需求：把 2026-01-01 到 2026-03-31 的帳整理好", False, "日期區間"),
    ("需求：整理 2025-2026 兩年的收據", False, "年份區間"),
    ("需求：把 1999-2024 的照片分類", False, "年份區間（更長）"),
    ("需求：算一下 12345678 這串數字的位數", False, "八位數字（真的只是數字）"),
    ("需求：把 2026 09 20 那天的行程排好", False, "空白分隔的日期"),

    # --- 對照：沒被擋的（證明過濾器不是全部都擋）---
    ("需求：整理桌面", False, "乾淨短句"),
    ("需求：整理 2026 年的收據", False, "只有四位數年份"),
    ("需求：把 10/15 之前的待辦列出來", False, "斜線日期（斜線不在 regex 裡）"),
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="同時打線上服務對照（會真的投卡，且有 10 秒頻率限制）")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)

    rows = []
    mismatches = 0
    print(f"{'應該擋':6} {'實際擋':6} {'判定':6}  說明 / 內容")
    print("-" * 78)
    for text, should, why in CASES:
        got = blocked(text)
        verdict = "OK" if got == should else ("🔴誤殺" if got else "🔴漏擋")
        if got != should:
            mismatches += 1
        print(f"{str(should):6} {str(got):6} {verdict:6}  {why}")
        print(f"{'':20}  {text}")
        rows.append({"text": text, "should_block": should,
                     "local_blocked": got, "why": why,
                     "mismatch": got != should})

    if a.live:
        print("\n=== 線上對照（每張卡之間等 11 秒避開頻率限制）===")
        for r in rows:
            body = json.dumps({"card_text": r["text"]}).encode("utf-8")
            req = urllib.request.Request(
                LIVE + "/api/submit", data=body, method="POST",
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    code = resp.status
            except urllib.error.HTTPError as e:
                code = e.code
            except Exception as e:  # noqa: BLE001
                # 連不上就寫 None，**不准寫 0 也不准當成「沒被擋」**
                code = None
                print(f"  連不上：{type(e).__name__}")
            r["live_http"] = code
            r["live_blocked"] = (code == 422) if code is not None else None
            agree = (r["live_blocked"] == r["local_blocked"]
                     if code is not None else None)
            r["local_matches_live"] = agree
            print(f"  HTTP {str(code):5} live_blocked={str(r['live_blocked']):5} "
                  f"與本機一致={agree}  {r['why']}")
            time.sleep(11)

    print()
    print(f"誤殺／漏擋共 {mismatches} 例（本機重現，零網路）")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump({"cases": rows, "mismatches": mismatches},
                      f, ensure_ascii=False, indent=2)
        print(f"落盤：{a.json}")

    # 🔴 退出碼刻意是「有誤殺就 1」：這支是**擋門**，不是報告產生器。
    #    修好了它會自己變綠；沒修的時候 CI 會一直紅，那正是我們要的。
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
