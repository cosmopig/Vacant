"""twin/probe_pii_filter — 公網個資過濾器的雙向擋門（誤殺 0、漏擋 0，兩個方向都測）。

## 這支原本在做什麼、現在在做什麼

2026-09-20 端到端實跑時，一張**完全沒有個資**的卡被線上服務退回 422
（「請拿掉可識別資訊再送」）。原因是 `vacant-world-cloud/server.js` 的

```js
const PHONE_RE = /\\+?\\d(?:[\\s-]?\\d){7,}/;
```

——「8 位以上、允許空白或連字號隔開的數字串」。`2026-09-20` 攤平就是
**2,0,2,6,0,9,2,0 共 8 位數字，中間只隔連字號**，完全命中。本機 13 例
測出 6 例誤殺、0 例漏擋（此檔第一版只做到「證明有 bug」，不修）。

**這一版把 server.js 修了**（兩個方向都做，見那邊的檔頭註解）：
  (a) 电話正則對「形狀像合法日期」的片段先挖掉再判——合法是關鍵
      （年 1900–2099、月 1–12、日 1–31），且日期形狀不准是更長的
      連字號數字鏈的中間一段（不然市話「02-1987-2020」會被誤放走）。
  (b) 422 的錯誤訊息從一句通用的「請拿掉可識別資訊再送」改成指出
      **是哪一段**被判定、判定成什麼（`findPiiHits`／`piiMessage`）。

**這支檔案的角色也跟著變了**：從「只負責證明 bug 存在」變成「雙向擋門」——
既要驗證誤殺清空了，也要驗證原本擋得住的真個資一個都沒有因為 (a) 的放寬
而漏接（漏擋 1 例就算失敗，比誤殺更硬——放寬電話正則的安全代價就是可能
漏接真電話，這條線不能鬆）。

## 這支的四個區塊

1. `MUST_BLOCK` —— 真個資（各種分隔符的手機／市話／Email／身分證字號），
   一個都不准漏擋。
2. `MUST_NOT_BLOCK` —— 誤殺清單（2026-09-20 那 6 例＋日期形狀的變體），
   一個都不准再被擋。這兩塊合起來的錯誤數決定退出碼。
3. `ACCEPTED_RESIDUALS` —— **刻意沒修的兩個殘餘案例**，方向相反：一個是
   殘留的誤殺（裸 8 位數字分不出是不是市話），一個是殘留的漏擋風險
   （沒有區碼前綴、剛好長得像年份區間的裸市話號碼）。兩個都是「數字本身
   分辨不出來」的死角，修其中一個必然會讓另一個變嚴重——記在這裡讓它們
   被看見，不計入退出碼，也不准用來假裝這條線已經封死。
4. `UNCOVERED_CATEGORIES` —— 中文姓名／地址／學校名。過濾器**完全不認得
   這些**（只認數字型個資與 Email），這裡直接示範「擋不到」並解釋為什麼
   不打算用 regex 硬猜（見檔案下方說明）——不算過濾器的失敗，是範圍宣告。

## 負控制

`--no-regression-check` 之外預設一定跑：把「修之前的舊邏輯」（沒有日期形狀
遮罩）套在 `MUST_NOT_BLOCK` 語料上，確認**舊邏輯真的會在這批語料上出錯**。
這是「證明這份測試語料量得動 2026-09-20 那個 bug」的負控制——沒有這一步，
「新邏輯全綠」有可能只是因為語料本身沒有踩到那個 bug，不是因為真的修好了。

## 用法

    python3 ops/exhibit/twin/probe_pii_filter.py            # 本機確定性重現，零網路
    python3 ops/exhibit/twin/probe_pii_filter.py --live     # 加打線上服務對照
                                                              # （線上還沒部署這次的修法，
                                                              #  預期會跟本機不一致——見下方）
    python3 ops/exhibit/twin/probe_pii_filter.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request

# ---------------------------------------------------------------------------
# 逐字抄自 `vacant-world-cloud/server.js`（2026-09-20 這次改動之後的版本）。
# 抄而不是 import，是因為那是 JS；抄過來就有義務在對面改動時跟著改——
# `--live` 模式、以及下面的 --regression-check 就是用來抓「兩邊漂掉了」的。
#
# ⚠ `re.ASCII`：JS 的 `\b`／`\w` 預設不含 Unicode 字母（中文字不算 word
# character），Python 的 `\b`／`\w` 預設**含** Unicode 字母（中文字算）。
# 兩邊語意要一致，Python 這邊要顯式加 `re.ASCII` 把 `\w`／`\b` 釘回
# ASCII-only，否則「在2026-09-20之前」這種中文字緊貼數字、中間沒有空白的
# 寫法，兩邊判斷會分岔而測不出來。
# ---------------------------------------------------------------------------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.ASCII)
PHONE_RE = re.compile(r"\+?\d(?:[\s-]?\d){7,}", re.ASCII)

_YEAR = r"(?:19|20)\d{2}"
_MONTH = r"(?:0?[1-9]|1[0-2])"
_DAY = r"(?:0?[1-9]|[12]\d|3[01])"

#: 三種日期形狀，逐一對應 server.js 檔頭列的三種誤殺樣式。
#: 前後都掛 `(?<!\d-)` / `(?!-\d)`（空白版掛 `(?<!\d[\s-])` / `(?![\s-]\d)`）：
#: 日期形狀不准是更長的連字號／空白數字鏈的中間一段——這是為了不讓
#: 「02-1987-2020」這種市話（區碼-號碼，號碼恰好長得像年份區間）被誤放走。
ISO_DATE_RE = re.compile(rf"(?<!\d-)\b{_YEAR}-{_MONTH}-{_DAY}\b(?!-\d)", re.ASCII)
YEAR_RANGE_RE = re.compile(rf"(?<!\d-)\b{_YEAR}-{_YEAR}\b(?!-\d)", re.ASCII)
SPACE_DATE_RE = re.compile(
    rf"(?<!\d[\s-])\b{_YEAR}\s{_MONTH}\s{_DAY}\b(?![\s-]\d)", re.ASCII
)
DATE_SHAPE_RES = (ISO_DATE_RE, YEAR_RANGE_RE, SPACE_DATE_RE)

PII_LABELS = {"email": "像電子郵件", "phone": "像電話號碼或身分證字號"}

LIVE = "https://vacant-world.cosmopig.com"


def mask_date_shapes(text: str) -> str:
    """把「形狀像合法日期」的片段換成等長的 # 佔位符，再拿去判電話。

    換成等長字串、不是直接砍掉，是為了不讓日期前後兩段本來不相鄰的數字
    被縫成一段新的長數字串——那樣反而會生出一個原本不存在的假電話誤判。
    """
    masked = text
    for pat in DATE_SHAPE_RES:
        masked = pat.sub(lambda m: "#" * len(m.group(0)), masked)
    return masked


def find_pii_hits(text: str) -> list[dict]:
    """回傳「這段文字被判定成什麼、原文是哪一段」的清單（server.js 的鏡像）。"""
    hits: list[dict] = []
    for m in EMAIL_RE.finditer(text):
        hits.append({"type": "email", "match": m.group(0)})
    masked = mask_date_shapes(text)
    for m in PHONE_RE.finditer(masked):
        hits.append({"type": "phone", "match": text[m.start() : m.end()]})
    return hits


def blocked(text: str) -> bool:
    return bool(find_pii_hits(text))


def pii_message(hits: list[dict]) -> str:
    parts = "、".join(f"「{h['match']}」（{PII_LABELS[h['type']]}）" for h in hits)
    return f"這段被判定成可識別資訊，請拿掉或改寫再送出：{parts}"


def blocked_unfixed(text: str) -> bool:
    """2026-09-20 修之前的邏輯：沒有日期形狀遮罩，純粹兩條正則各自 test。

    只用在 `--regression-check`：證明「新邏輯的語料」套在舊邏輯上真的會出錯，
    否則「新邏輯全綠」可能只是語料太弱，不是真的修好了。
    """
    return bool(EMAIL_RE.search(text)) or bool(PHONE_RE.search(text))


# ---------------------------------------------------------------------------
# 語料
# ---------------------------------------------------------------------------

#: (卡片內容, 這是什麼) —— 一個都不准漏擋，漏擋 1 例整支腳本判失敗。
MUST_BLOCK: list[tuple[str, str]] = [
    # 2026-09-21 併分支時發現舊版有而新版沒有的唯一一例（+886 國碼形式）。
    # （2026-09-24：這一例原本被併進了型別標註裡、根本不在清單上——ruff F722 抓到——
    #   現在放回清單。）
    ("需求：打 +886912345678", "手機（國碼、無分隔、前面有字）"),
    ("需求：打給 0912345678", "手機（無分隔）"),
    ("需求：聯絡 0912-345-678", "手機（連字號 4-3-3）"),
    ("需求：LINE 不方便就打 0912 345 678", "手機（空白 4-3-3）"),
    ("需求：+886912345678 找我", "手機（國碼、無分隔）"),
    ("需求：+886-912-345-678 找我", "手機（國碼、連字號）"),
    ("需求：市話 02-23456789", "市話（區碼-號碼，2+8）"),
    ("需求：市話 02-2345-6789", "市話（區碼-號碼，2+4+4）"),
    ("需求：市話 0223456789", "市話（無分隔，10 位）"),
    ("需求：市話 049-2345678", "市話（3 碼區碼）"),
    ("需求：市話 02-1987-2020", "市話（號碼恰好長得像年份區間——邊界修正的回歸測試）"),
    ("需求：寄給我 a@b.com", "Email（簡單）"),
    ("需求：foo.bar+tag@sub.example.co.uk 收件", "Email（加號、子網域、多段 TLD）"),
    ("需求：身分證字號 A123456789", "身分證字號（男性代碼 1）"),
    ("需求：身分證是B234567890沒有空格", "身分證字號（無空白、緊貼中文）"),
]

#: (卡片內容, 這是什麼) —— 一個都不准再被誤殺；這兩塊合起來的錯誤數決定退出碼。
MUST_NOT_BLOCK: list[tuple[str, str]] = [
    ("需求：在 2026-09-20 之前整理好桌面", "ISO 日期（展場最常見、2026-09-20 事故本例）"),
    ("需求：把 2026-01-01 到 2026-03-31 的帳整理好", "日期區間（兩個 ISO 日期）"),
    ("需求：整理 2025-2026 兩年的收據", "年份區間"),
    ("需求：把 1999-2024 的照片分類", "年份區間（更長）"),
    ("需求：把 2026 09 20 那天的行程排好", "空白分隔日期"),
    ("需求：在 2026-1-5 之前交件", "ISO 日期（月/日無前導 0）"),
    ("需求：從 2020-2021 到 2023-2024 整理照片", "相鄰兩個年份區間"),
    ("需求：紀錄 2099-01-01 之後的事", "ISO 日期（年份上界）"),
    ("需求：查 1900-01-01 的資料", "ISO 日期（年份下界）"),
    ("需求：整理桌面", "乾淨短句（沒有任何數字，對照組）"),
    ("需求：整理 2026 年的收據", "只有四位數年份（對照組）"),
    ("需求：把 10/15 之前的待辦列出來", "斜線日期（本來就不在規則範圍內，對照組）"),
]

#: (卡片內容, 修完之後實際會是什麼, 為什麼不修) —— 刻意的殘餘案例，
#: **不計入**退出碼，但一定要印出來、被看見。方向相反的兩例都收在這裡：
#: 一個是殘留誤殺（該過但被擋），一個是殘留漏擋風險（該擋但被放走）。
ACCEPTED_RESIDUALS: list[tuple[str, bool, str]] = [
    (
        "需求：算一下 12345678 這串數字的位數",
        True,  # 實際仍會被擋（should_block 應該是 False，這裡刻意不修）
        "裸 8 位數字、沒有分隔符、也湊不出合法日期——跟裸市話號碼在數字層級"
        "分不開，沒有辦法只從數字本身判斷這是討論位數還是打電話。放走它＝"
        "把裸市話號碼一起放走，直接撞上『漏擋 1 例就算失敗』，所以刻意不修。"
        "(b) 的訊息會指名「12345678」，至少讓觀眾知道要改哪裡。",
    ),
    (
        "需求：市話 1987-2020 打得通",
        False,  # 實際會被放走（should_block 應該是 True，這裡是已知漏洞）
        "邊界修正只堵住『前面接著區碼、形成更長連字號鏈』的情況（如"
        "02-1987-2020）。沒有區碼前綴、單獨一段剛好長得像「19xx-20xx」"
        "年份區間的裸市話號碼，仍會被誤判成日期而放走——跟上一條是同一類"
        "『數字本身無法分辨』的死角，方向相反（這裡是漏擋不是誤殺）。"
        "台灣市話慣例上不會省略區碼單獨報號碼，機率極低，但誠實記在這裡，"
        "不假裝這條線已經封死。",
    ),
]

#: 中文姓名／地址／學校名——過濾器完全不認得這些，這裡直接示範「擋不到」。
#: 不計入退出碼（這些本來就在過濾器的設計範圍外），列出來是為了讓這件事
#: 被看見、被下一個接手的人看到，而不是要在這裡用 regex 硬猜。
#:
#: 為什麼不猜：姓名清單會漏掉不在清單裡的姓名，也會誤傷剛好同名的普通詞
#: （例如「陳」「李」也是常見姓氏但也可能出現在別的語境）；用「兩三個連續
#: 中文字」這種形狀去猜，中文裡幾乎任何名詞片語都長這樣，誤判率高到不能
#: 用在沒有解說員的展場（CLAUDE.md 展場硬約束 2、6）。這條防線目前只能靠
#: 提示詞本身（叫觀眾的 AI 不要放真名／地址／學校）加展場人工抽查，
#: 不是伺服器端可以自動擋掉的。
UNCOVERED_CATEGORIES: list[tuple[str, str]] = [
    ("需求：跟王小明約在台北市信義區松仁路 100 號見面", "中文姓名＋門牌地址"),
    ("需求：幫我查一下國立台灣大學資訊工程學系的截止日期", "學校＋科系全名"),
    ("需求：陳大文明天要交報告給指導教授李美華", "兩個中文姓名"),
]


def _run_group(rows, force_should):
    """回傳 (mismatches, printed_rows)；force_should=True/False 時每列的
    should_block 直接用這個值（給 MUST_BLOCK / MUST_NOT_BLOCK 用）。"""
    mismatches = 0
    printed = []
    for text, why in rows:
        hits = find_pii_hits(text)
        got = bool(hits)
        ok = got == force_should
        if not ok:
            mismatches += 1
        printed.append(
            {
                "text": text,
                "why": why,
                "should_block": force_should,
                "blocked": got,
                "hits": hits,
                "ok": ok,
            }
        )
    return mismatches, printed


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true",
                    help="同時打線上服務對照（會真的投卡，且有 10 秒頻率限制）")
    ap.add_argument("--no-regression-check", action="store_true",
                    help="跳過負控制（不建議；沒有負控制的綠燈不算數）")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)

    report: dict = {"groups": {}}
    total_mismatches = 0

    print("=== 一、MUST_BLOCK（真個資，一個都不准漏擋）===")
    mb_bad, mb_rows = _run_group(MUST_BLOCK, True)
    for r in mb_rows:
        tag = "OK  " if r["ok"] else "🔴漏擋"
        print(f"{tag}  {r['why']}")
        print(f"      {r['text']}")
        if r["hits"]:
            print(f"      -> {r['hits']}")
    total_mismatches += mb_bad
    report["groups"]["must_block"] = {"mismatches": mb_bad, "rows": mb_rows}
    print(f"MUST_BLOCK 漏擋數：{mb_bad}\n")

    print("=== 二、MUST_NOT_BLOCK（誤殺清單，一個都不准再被擋）===")
    mnb_bad, mnb_rows = _run_group(MUST_NOT_BLOCK, False)
    for r in mnb_rows:
        tag = "OK  " if r["ok"] else "🔴誤殺"
        print(f"{tag}  {r['why']}")
        print(f"      {r['text']}")
        if r["hits"]:
            print(f"      -> {r['hits']}")
    total_mismatches += mnb_bad
    report["groups"]["must_not_block"] = {"mismatches": mnb_bad, "rows": mnb_rows}
    print(f"MUST_NOT_BLOCK 誤殺數：{mnb_bad}\n")

    print("=== 三、ACCEPTED_RESIDUALS（刻意不修，不計入退出碼，但要看得見）===")
    residual_rows = []
    for text, expect_blocked_after_fix, reason in ACCEPTED_RESIDUALS:
        got = blocked(text)
        matches_prediction = got == expect_blocked_after_fix
        tag = "⚠已知（符合預期）" if matches_prediction else "🔴連已知的都跟預期不符了，先停下來查"
        print(f"{tag}")
        print(f"      {text}")
        print(f"      實際 blocked={got}（預期={expect_blocked_after_fix}）")
        print(f"      理由：{reason}")
        residual_rows.append({
            "text": text, "expect_blocked_after_fix": expect_blocked_after_fix,
            "actual_blocked": got, "matches_prediction": matches_prediction,
            "reason": reason,
        })
    report["groups"]["accepted_residuals"] = residual_rows
    # 已知案例如果連「跟我們的預測一致」都做不到，代表分析本身錯了或程式碼
    # 又漂走了——這個不能悄悄放過，要算進失敗。
    residual_drift = sum(1 for r in residual_rows if not r["matches_prediction"])
    total_mismatches += residual_drift
    print(f"已知殘留案例與預期不符數：{residual_drift}（非 0 會讓整支腳本判失敗）\n")

    print("=== 四、UNCOVERED_CATEGORIES（中文姓名／地址／學校——明講擋不到，不計入退出碼）===")
    uncovered_rows = []
    for text, why in UNCOVERED_CATEGORIES:
        hits = find_pii_hits(text)
        print(f"擋不到  {why}")
        print(f"      {text}")
        print(f"      -> hits={hits}（預期是空清單：這條防線本來就不在伺服器端的範圍內）")
        uncovered_rows.append({"text": text, "why": why, "hits": hits})
    report["groups"]["uncovered_categories"] = uncovered_rows
    print()

    if not a.no_regression_check:
        print("=== 五、負控制：修之前的舊邏輯，套在 MUST_NOT_BLOCK 語料上應該要出錯 ===")
        old_bad = sum(1 for text, _ in MUST_NOT_BLOCK if blocked_unfixed(text))
        print(f"舊邏輯在 {len(MUST_NOT_BLOCK)} 例誤殺語料上出錯 {old_bad} 例")
        if old_bad == 0:
            print("🔴 負控制沒有紅——語料量不到這個 bug，新邏輯全綠不能採信")
            total_mismatches += 1
        else:
            print("OK：語料證實量得到 2026-09-20 那個 bug（舊邏輯在這批語料上會出錯）")
        report["regression_check"] = {"old_logic_mismatches": old_bad}
        print()

    if a.live:
        print("=== 線上對照（每張卡之間等 11 秒避開頻率限制；線上還沒部署這次的修法）===")
        print("⚠ 這裡預期會跟本機不一致：MUST_NOT_BLOCK 那批本機不擋、線上（未修）還是會擋。")
        live_rows = []
        all_cases = (
            [(t, True) for t, _ in MUST_BLOCK]
            + [(t, False) for t, _ in MUST_NOT_BLOCK]
        )
        for text, local_should in all_cases:
            local_hits = find_pii_hits(text)
            local_blocked = bool(local_hits)
            body = json.dumps({"card_text": text}).encode("utf-8")
            req = urllib.request.Request(
                LIVE + "/api/submit", data=body, method="POST",
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    code = resp.status
            except urllib.error.HTTPError as e:
                code = e.code
            except Exception as e:  # noqa: BLE001
                # 連不上就寫 None，不准寫 0 也不准當成「沒被擋」
                code = None
                print(f"  連不上：{type(e).__name__}")
            live_blocked = (code == 422) if code is not None else None
            row = {
                "text": text, "local_should_block": local_should,
                "local_blocked": local_blocked, "live_http": code,
                "live_blocked": live_blocked,
            }
            print(f"  HTTP {str(code):5} local_blocked={str(local_blocked):5} "
                  f"live_blocked={str(live_blocked):5}  {text}")
            live_rows.append(row)
            time.sleep(11)
        report["live"] = live_rows

    report["total_mismatches"] = total_mismatches
    print(f"\n===== 總計：MUST_BLOCK 漏擋 {mb_bad}、MUST_NOT_BLOCK 誤殺 {mnb_bad}、"
          f"已知殘留案例偏離預期 {residual_drift} =====")
    print("（ACCEPTED_RESIDUALS 本身的 2 個已知案例、UNCOVERED_CATEGORIES 的 3 個"
          "示範案例，只要跟預期一致就不算進上面這個總計）")

    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"落盤：{a.json}")

    return 1 if total_mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
